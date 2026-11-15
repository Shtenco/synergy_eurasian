"""PostgreSQL-backed SDU ledger adapter.

Requires psycopg 3 at runtime. Importing this module does not require psycopg;
pass a connection_factory (usually psycopg.connect) to PostgresLedger.

All writes are serialized through sdu_ledger_state FOR UPDATE. This is
deliberately conservative: it guarantees a single global event/hash order and
prevents double-spends across processes, at the cost of write throughput.
Partitioned sequencing can be considered only after correctness benchmarks.

The runtime database role must not own the tables or have permission to disable
triggers / alter schema. Apply migrations with a separate deployment role.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Callable, Iterable, Mapping
from uuid import uuid4

from sdu_accounting_core import (
    AccountNotFound,
    IdempotencyConflict,
    InsufficientFunds,
    LedgerEvent,
    Posting,
    ValidationError,
)
from sdu_issuance_authorization import (
    IssuanceAuthorizationService,
    IssuanceClaim,
    ValidatorApproval,
)
from sdu_ledger_checkpoints import (
    LedgerCheckpoint,
    create_checkpoint as build_checkpoint,
    verify_checkpoint,
)


class PostgresLedgerError(Exception):
    pass


class EpochBudgetExceeded(PostgresLedgerError):
    pass


class DuplicateIssuanceClaim(PostgresLedgerError):
    pass


class PostgresLedger:
    GENESIS_HASH = "0" * 64

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        if not callable(connection_factory):
            raise TypeError("connection_factory must be callable")
        self._connect = connection_factory

    def register_asset(self, symbol: str, decimals: int) -> None:
        if not symbol or symbol.strip() != symbol:
            raise ValidationError("asset symbol must be non-empty and trimmed")
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 18:
            raise ValidationError("asset decimals must be an integer between 0 and 18")
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sdu_assets(symbol, decimals) VALUES (%s, %s) "
                        "ON CONFLICT (symbol) DO NOTHING",
                        (symbol, decimals),
                    )
                    cur.execute("SELECT decimals FROM sdu_assets WHERE symbol=%s", (symbol,))
                    row = cur.fetchone()
                    if row is None or row[0] != decimals:
                        raise ValidationError("asset already registered with different decimals")

    def create_account(
        self,
        account_id: str,
        asset: str,
        *,
        kind: str = "wallet",
        allow_negative: bool = False,
        counts_toward_supply: bool = True,
        burnable: bool = True,
    ) -> None:
        if not account_id or account_id.strip() != account_id:
            raise ValidationError("account_id must be non-empty and trimmed")
        if not kind or kind.strip() != kind:
            raise ValidationError("account kind must be non-empty and trimmed")
        if account_id.startswith("system:") or kind.startswith("system_"):
            raise ValidationError("system accounts are provisioned only by dedicated ledger commands")
        if any(not isinstance(v, bool) for v in (allow_negative, counts_toward_supply, burnable)):
            raise ValidationError("account policy flags must be booleans")
        if allow_negative and counts_toward_supply:
            raise ValidationError("supply-counted accounts cannot allow negative balances")
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO sdu_accounts
                           (account_id, asset_symbol, account_kind, allow_negative,
                            counts_toward_supply, burnable)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (account_id, asset, kind, allow_negative, counts_toward_supply, burnable),
                    )
                    cur.execute(
                        "INSERT INTO sdu_balances(account_id, asset_symbol, balance) VALUES (%s,%s,0)",
                        (account_id, asset),
                    )

    def set_epoch_budget(self, epoch_id: str, budget: int) -> None:
        if not epoch_id or epoch_id.strip() != epoch_id:
            raise ValidationError("epoch_id is required")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise ValidationError("epoch budget must be a non-negative integer")
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO sdu_epoch_issuance(epoch_id,budget,spent)
                           VALUES (%s,%s,0) ON CONFLICT (epoch_id) DO NOTHING""",
                        (epoch_id, budget),
                    )
                    cur.execute(
                        "SELECT spent FROM sdu_epoch_issuance WHERE epoch_id=%s FOR UPDATE",
                        (epoch_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise PostgresLedgerError("epoch budget row disappeared during configuration")
                    if int(row[0]) > budget:
                        raise ValidationError("new epoch budget cannot be below already spent amount")
                    cur.execute(
                        "UPDATE sdu_epoch_issuance SET budget=%s, updated_at=now() WHERE epoch_id=%s",
                        (budget, epoch_id),
                    )

    def transfer(
        self,
        source: str,
        destination: str,
        amount: int,
        *,
        asset: str,
        idempotency_key: str,
        actor_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> LedgerEvent:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValidationError("transfer amount must be a positive integer")
        return self.post(
            "TRANSFER",
            (Posting(source, asset, -amount), Posting(destination, asset, amount)),
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            metadata=metadata,
        )

    def post(
        self,
        event_type: str,
        postings: Iterable[Posting],
        *,
        idempotency_key: str,
        actor_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> LedgerEvent:
        if event_type in {"SDU_MINT", "SDU_BURN", "REVERSAL"}:
            raise ValidationError("reserved event type requires a dedicated authorized command")
        legs = tuple(postings)
        return self._post_transaction(
            event_type, legs, idempotency_key=idempotency_key,
            actor_id=actor_id, metadata=metadata or {}, privileged=False,
        )

    def issue(
        self,
        claim: IssuanceClaim,
        approvals: tuple[ValidatorApproval, ...] | list[ValidatorApproval],
        *,
        authorizer: IssuanceAuthorizationService,
        idempotency_key: str,
        actor_id: str,
    ) -> LedgerEvent:
        verified = authorizer.verify(claim, approvals)
        system_account = "system:issuance:SDU"
        legs = (
            Posting(system_account, "SDU", -claim.amount),
            Posting(claim.destination_account, "SDU", claim.amount),
        )
        metadata = {
            "approval_policy_version": verified.policy_version,
            "approved_validator_ids": list(verified.approved_validator_ids),
            "claim_id": claim.claim_id,
            "claim_digest": verified.request_digest,
            "epoch_id": claim.epoch_id,
            "evidence_digest": claim.evidence_digest,
            "purpose": claim.purpose,
        }
        return self._post_transaction(
            "SDU_MINT", legs, idempotency_key=idempotency_key,
            actor_id=actor_id, metadata=metadata, privileged=True,
            issuance_claim=claim,
        )

    def total_supply(self, asset: str = "SDU") -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(SUM(b.balance), 0)
                       FROM sdu_balances b
                       JOIN sdu_accounts a USING (account_id, asset_symbol)
                       WHERE b.asset_symbol=%s AND a.counts_toward_supply=TRUE""",
                    (asset,),
                )
                return int(cur.fetchone()[0])

    def balance(self, account_id: str, asset: str = "SDU") -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT balance FROM sdu_balances WHERE account_id=%s AND asset_symbol=%s",
                    (account_id, asset),
                )
                row = cur.fetchone()
                if row is None:
                    raise AccountNotFound(account_id)
                return int(row[0])

    def verify_integrity(self) -> dict[str, int | str]:
        """Audit event sequence, hash chain, postings, idempotency and balances."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT event_id,sequence,event_type,idempotency_key,actor_id,
                              event_timestamp,metadata,previous_hash,event_hash
                       FROM sdu_events ORDER BY sequence"""
                )
                events = cur.fetchall()
                expected_sequence = 1
                previous_hash = self.GENESIS_HASH
                projection: dict[tuple[str, str], int] = {}
                for row in events:
                    event_id = str(row[0])
                    sequence = int(row[1])
                    if sequence != expected_sequence:
                        raise PostgresLedgerError("event sequence gap or reorder detected")
                    if str(row[7]).strip() != previous_hash:
                        raise PostgresLedgerError("event hash-chain predecessor mismatch")
                    cur.execute(
                        """SELECT account_id,asset_symbol,amount FROM sdu_postings
                           WHERE event_id=%s ORDER BY line_number""",
                        (row[0],),
                    )
                    postings = tuple(Posting(a, asset, int(amount)) for a, asset, amount in cur.fetchall())
                    if len(postings) < 2:
                        raise PostgresLedgerError("event has fewer than two postings")
                    totals: dict[str, int] = {}
                    for posting in postings:
                        totals[posting.asset] = totals.get(posting.asset, 0) + posting.amount
                        key = (posting.account_id, posting.asset)
                        projection[key] = projection.get(key, 0) + posting.amount
                    if any(total != 0 for total in totals.values()):
                        raise PostgresLedgerError(f"event {event_id} is unbalanced")
                    metadata_json = json.dumps(
                        row[6], sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    )
                    timestamp_text = row[5].astimezone(timezone.utc).isoformat()
                    expected_hash = self._event_hash(
                        event_id, sequence, str(row[2]), str(row[3]), str(row[4]),
                        timestamp_text, postings, metadata_json, previous_hash,
                    )
                    if not hmac.compare_digest(expected_hash, str(row[8]).strip()):
                        raise PostgresLedgerError(f"event hash mismatch at sequence {sequence}")
                    cur.execute(
                        "SELECT request_hash FROM sdu_idempotency WHERE idempotency_key=%s",
                        (row[3],),
                    )
                    idem = cur.fetchone()
                    if idem is None:
                        raise PostgresLedgerError(f"missing idempotency record for event {event_id}")
                    expected_request_hash = self._request_hash(
                        str(row[2]), str(row[4]), postings, metadata_json
                    )
                    if not hmac.compare_digest(expected_request_hash, str(idem[0]).strip()):
                        raise PostgresLedgerError(f"idempotency fingerprint mismatch for event {event_id}")
                    previous_hash = expected_hash
                    expected_sequence += 1

                cur.execute("SELECT account_id,asset_symbol,balance FROM sdu_balances")
                stored_balances = {
                    (account_id, asset): int(balance)
                    for account_id, asset, balance in cur.fetchall()
                }
                cur.execute(
                    "SELECT account_id,asset_symbol,allow_negative FROM sdu_accounts"
                )
                account_policies = {
                    (account_id, asset): bool(allow_negative)
                    for account_id, asset, allow_negative in cur.fetchall()
                }
                for key in account_policies:
                    projection.setdefault(key, 0)
                if projection != stored_balances:
                    raise PostgresLedgerError("balance projection differs from event replay")
                for key, balance in projection.items():
                    if balance < 0 and not account_policies.get(key, False):
                        raise PostgresLedgerError(f"negative balance in spendable account {key[0]}")

                cur.execute(
                    """SELECT c.claim_id,c.epoch_id,c.amount,c.evidence_digest,
                              e.event_type,e.metadata,e.event_id
                       FROM sdu_issuance_claims c
                       JOIN sdu_events e ON e.event_id=c.event_id"""
                )
                claims = cur.fetchall()
                epoch_claim_totals: dict[str, int] = {}
                for claim_id, epoch_id, amount, evidence_digest, event_type, metadata, event_id in claims:
                    if event_type != "SDU_MINT":
                        raise PostgresLedgerError("issuance claim points to a non-mint event")
                    if not isinstance(metadata, dict):
                        metadata = json.loads(metadata)
                    if (
                        metadata.get("claim_id") != claim_id
                        or metadata.get("epoch_id") != epoch_id
                        or metadata.get("evidence_digest") != str(evidence_digest).strip()
                    ):
                        raise PostgresLedgerError("issuance claim metadata mismatch")
                    cur.execute(
                        """SELECT account_id,asset_symbol,amount FROM sdu_postings
                           WHERE event_id=%s ORDER BY line_number""",
                        (event_id,),
                    )
                    mint_postings = cur.fetchall()
                    mint_totals: dict[tuple[str, str], int] = {}
                    for account_id, asset, value in mint_postings:
                        key = (account_id, asset)
                        mint_totals[key] = mint_totals.get(key, 0) + int(value)
                    if (
                        len(mint_totals) != 2
                        or mint_totals.get(("system:issuance:SDU", "SDU")) != -int(amount)
                        or sum(mint_totals.values()) != 0
                        or any(asset != "SDU" for _account, asset in mint_totals)
                    ):
                        raise PostgresLedgerError("issuance postings do not exactly match claim amount")
                    epoch_claim_totals[epoch_id] = epoch_claim_totals.get(epoch_id, 0) + int(amount)
                cur.execute("SELECT COUNT(*) FROM sdu_events WHERE event_type='SDU_MINT'")
                mint_event_count = int(cur.fetchone()[0])
                if mint_event_count != len(claims):
                    raise PostgresLedgerError("SDU mint events and verified issuance claims are not one-to-one")
                cur.execute("SELECT epoch_id,budget,spent FROM sdu_epoch_issuance")
                for epoch_id, budget, spent in cur.fetchall():
                    if int(spent) != epoch_claim_totals.get(epoch_id, 0):
                        raise PostgresLedgerError(f"epoch {epoch_id} spent total differs from issued claims")
                    if int(spent) > int(budget):
                        raise PostgresLedgerError(f"epoch {epoch_id} exceeds its issuance budget")

                cur.execute(
                    "SELECT next_sequence,last_event_hash FROM sdu_ledger_state WHERE singleton=TRUE"
                )
                state = cur.fetchone()
                if state is None:
                    raise PostgresLedgerError("ledger state singleton row is missing")
                if int(state[0]) != expected_sequence or str(state[1]).strip() != previous_hash:
                    raise PostgresLedgerError("ledger state head differs from event journal")
                return {
                    "events": len(events),
                    "accounts": len(account_policies),
                    "postings": sum(1 for _ in projection) if not events else self._count_postings(cur),
                    "last_sequence": expected_sequence - 1,
                    "last_hash": previous_hash,
                }

    @staticmethod
    def _count_postings(cur: object) -> int:
        cur.execute("SELECT COUNT(*) FROM sdu_postings")
        return int(cur.fetchone()[0])

    def create_and_store_checkpoint(self, signing_key: bytes) -> LedgerCheckpoint:
        """Create a checkpoint under the ledger-head lock and store its local copy.

        The returned signed checkpoint must also be published to an independent
        anchor (separate account/provider or public append-only log). Storing it
        only in this database does not protect against a database superuser.
        """
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT next_sequence,last_event_hash FROM sdu_ledger_state "
                        "WHERE singleton=TRUE FOR UPDATE"
                    )
                    state = cur.fetchone()
                    if state is None:
                        raise PostgresLedgerError("ledger state singleton row is missing")
                    checkpoint = build_checkpoint(
                        int(state[0]) - 1, str(state[1]).strip(), signing_key
                    )
                    cur.execute(
                        """SELECT event_hash,checkpoint_digest,signature,signature_algorithm,created_at
                           FROM sdu_checkpoints WHERE sequence=%s""",
                        (checkpoint.sequence,),
                    )
                    existing = cur.fetchone()
                    if existing is not None:
                        stored = LedgerCheckpoint(
                            sequence=checkpoint.sequence,
                            event_hash=str(existing[0]).strip(),
                            digest=str(existing[1]).strip(),
                            signature=str(existing[2]),
                            algorithm=str(existing[3]),
                            created_at=existing[4].astimezone(timezone.utc).isoformat(),
                        )
                        if stored.event_hash != checkpoint.event_hash:
                            raise PostgresLedgerError("stored checkpoint event hash differs from ledger head")
                        if not verify_checkpoint(stored, signing_key):
                            raise PostgresLedgerError("stored checkpoint signature does not match supplied key")
                        return stored
                    cur.execute(
                        """INSERT INTO sdu_checkpoints
                           (sequence,event_hash,checkpoint_digest,signature,signature_algorithm,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (checkpoint.sequence, checkpoint.event_hash, checkpoint.digest,
                         checkpoint.signature, checkpoint.algorithm,
                         datetime.fromisoformat(checkpoint.created_at)),
                    )
                    return checkpoint

    def _post_transaction(
        self,
        event_type: str,
        postings: tuple[Posting, ...],
        *,
        idempotency_key: str,
        actor_id: str,
        metadata: Mapping[str, object],
        privileged: bool,
        issuance_claim: IssuanceClaim | None = None,
    ) -> LedgerEvent:
        if not event_type or not event_type.strip():
            raise ValidationError("event_type is required")
        if not idempotency_key or not idempotency_key.strip():
            raise ValidationError("idempotency_key is required")
        if not actor_id or not actor_id.strip():
            raise ValidationError("actor_id is required")
        if len(postings) < 2:
            raise ValidationError("a ledger event needs at least two postings")
        per_asset: dict[str, int] = {}
        per_account: dict[tuple[str, str], int] = {}
        for posting in postings:
            if isinstance(posting.amount, bool) or not isinstance(posting.amount, int) or posting.amount == 0:
                raise ValidationError("posting amounts must be non-zero integer atomic units")
            per_asset[posting.asset] = per_asset.get(posting.asset, 0) + posting.amount
            key = (posting.account_id, posting.asset)
            per_account[key] = per_account.get(key, 0) + posting.amount
        if any(total != 0 for total in per_asset.values()):
            raise ValidationError("transaction is not balanced per asset")

        metadata_json = json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        request_hash = self._request_hash(event_type, actor_id, postings, metadata_json)
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # One global lock makes sequence allocation, hash chaining and
                    # idempotency checks linearizable across independent processes.
                    cur.execute(
                        "SELECT next_sequence,last_event_hash FROM sdu_ledger_state "
                        "WHERE singleton=TRUE FOR UPDATE"
                    )
                    state = cur.fetchone()
                    if state is None:
                        raise PostgresLedgerError("sdu_ledger_state singleton row is missing")
                    cur.execute(
                        "SELECT request_hash,event_id FROM sdu_idempotency WHERE idempotency_key=%s",
                        (idempotency_key,),
                    )
                    prior = cur.fetchone()
                    if prior is not None:
                        if prior[0].strip() != request_hash:
                            raise IdempotencyConflict("idempotency key reused for a different command")
                        return self._load_event(cur, prior[1])

                    if issuance_claim is not None:
                        self._lock_and_consume_epoch_budget(cur, issuance_claim)

                    if event_type == "SDU_MINT":
                        expected_counter = ("SDU", "system_issuance", True, False, False)
                        cur.execute(
                            """INSERT INTO sdu_accounts
                               (account_id,asset_symbol,account_kind,allow_negative,
                                counts_toward_supply,burnable)
                               VALUES ('system:issuance:SDU','SDU','system_issuance',TRUE,FALSE,FALSE)
                               ON CONFLICT (account_id,asset_symbol) DO NOTHING"""
                        )
                        cur.execute(
                            """SELECT account_kind,allow_negative,counts_toward_supply,burnable
                               FROM sdu_accounts
                               WHERE account_id='system:issuance:SDU' AND asset_symbol='SDU'
                               FOR UPDATE"""
                        )
                        counter_policy = cur.fetchone()
                        if counter_policy is None or (
                            str(counter_policy[0]), bool(counter_policy[1]),
                            bool(counter_policy[2]), bool(counter_policy[3])
                        ) != expected_counter[1:]:
                            raise ValidationError("system issuance account configuration mismatch")
                        cur.execute(
                            """INSERT INTO sdu_balances(account_id,asset_symbol,balance)
                               VALUES ('system:issuance:SDU','SDU',0)
                               ON CONFLICT (account_id,asset_symbol) DO NOTHING"""
                        )

                    account_policies: dict[tuple[str, str], tuple[bool, bool, bool, str]] = {}
                    for account_id, asset in sorted(per_account):
                        cur.execute(
                            """SELECT allow_negative, counts_toward_supply, burnable, account_kind
                               FROM sdu_accounts
                               WHERE account_id=%s AND asset_symbol=%s FOR UPDATE""",
                            (account_id, asset),
                        )
                        policy = cur.fetchone()
                        if policy is None:
                            raise AccountNotFound(account_id)
                        account_policies[(account_id, asset)] = (
                            bool(policy[0]), bool(policy[1]), bool(policy[2]), str(policy[3])
                        )
                        if not privileged and (policy[0] or not policy[1] or str(policy[3]).startswith("system_")):
                            raise ValidationError("ordinary postings cannot use privileged counter accounts")
                        cur.execute(
                            "SELECT balance FROM sdu_balances WHERE account_id=%s AND asset_symbol=%s FOR UPDATE",
                            (account_id, asset),
                        )
                        balance_row = cur.fetchone()
                        if balance_row is None:
                            raise PostgresLedgerError(f"balance projection missing for {account_id}")
                        resulting = int(balance_row[0]) + per_account[(account_id, asset)]
                        if resulting < 0 and not policy[0]:
                            raise InsufficientFunds(f"insufficient funds in {account_id}")

                    if event_type == "SDU_MINT":
                        if not privileged or issuance_claim is None:
                            raise ValidationError("SDU_MINT requires verified issuance authorization")
                        if any(asset != "SDU" for asset in per_asset):
                            raise ValidationError("SDU issuance cannot create external assets")
                        destination = issuance_claim.destination_account
                        dest_policy = account_policies.get((destination, "SDU"))
                        if dest_policy is None or not dest_policy[1] or dest_policy[3].startswith("system_"):
                            raise ValidationError("issuance destination must be a supply-counted SDU account")
                    elif privileged:
                        raise ValidationError("unsupported privileged operation")

                    event_id = uuid4()
                    sequence = int(state[0])
                    previous_hash = str(state[1]).strip()
                    event_time = datetime.now(timezone.utc)
                    timestamp_text = event_time.isoformat()
                    event_hash = self._event_hash(
                        str(event_id), sequence, event_type, idempotency_key,
                        actor_id, timestamp_text, postings, metadata_json, previous_hash,
                    )
                    cur.execute(
                        """INSERT INTO sdu_events
                           (event_id,sequence,event_type,idempotency_key,actor_id,
                            event_timestamp,metadata,previous_hash,event_hash)
                           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                        (event_id, sequence, event_type, idempotency_key, actor_id,
                         event_time, metadata_json, previous_hash, event_hash),
                    )
                    for line_number, posting in enumerate(postings, start=1):
                        cur.execute(
                            """INSERT INTO sdu_postings
                               (event_id,line_number,account_id,asset_symbol,amount)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (event_id, line_number, posting.account_id, posting.asset, posting.amount),
                        )
                    for (account_id, asset), delta in per_account.items():
                        cur.execute(
                            """UPDATE sdu_balances SET balance=balance+%s, updated_at=now()
                               WHERE account_id=%s AND asset_symbol=%s""",
                            (delta, account_id, asset),
                        )
                    cur.execute(
                        "INSERT INTO sdu_idempotency(idempotency_key,request_hash,event_id) VALUES (%s,%s,%s)",
                        (idempotency_key, request_hash, event_id),
                    )
                    if issuance_claim is not None:
                        cur.execute(
                            """INSERT INTO sdu_issuance_claims
                               (claim_id,epoch_id,event_id,amount,evidence_digest)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (issuance_claim.claim_id, issuance_claim.epoch_id, event_id,
                             issuance_claim.amount, issuance_claim.evidence_digest),
                        )
                    cur.execute(
                        """UPDATE sdu_ledger_state
                           SET next_sequence=%s,last_event_hash=%s WHERE singleton=TRUE""",
                        (sequence + 1, event_hash),
                    )
                    return LedgerEvent(
                        str(event_id), sequence, event_type, idempotency_key,
                        actor_id, timestamp_text, postings, metadata_json,
                        previous_hash, event_hash,
                    )

    def _lock_and_consume_epoch_budget(self, cur: object, claim: IssuanceClaim) -> None:
        cur.execute(
            "SELECT budget,spent FROM sdu_epoch_issuance WHERE epoch_id=%s FOR UPDATE",
            (claim.epoch_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValidationError("issuance epoch budget is not configured")
        if int(row[1]) + claim.amount > int(row[0]):
            raise EpochBudgetExceeded("issuance exceeds remaining epoch budget")
        cur.execute(
            "SELECT 1 FROM sdu_issuance_claims WHERE claim_id=%s",
            (claim.claim_id,),
        )
        if cur.fetchone() is not None:
            raise DuplicateIssuanceClaim("issuance claim has already been consumed")
        cur.execute(
            "UPDATE sdu_epoch_issuance SET spent=spent+%s,updated_at=now() WHERE epoch_id=%s",
            (claim.amount, claim.epoch_id),
        )

    @staticmethod
    def _request_hash(
        event_type: str, actor_id: str, postings: tuple[Posting, ...], metadata_json: str
    ) -> str:
        payload = {
            "actor_id": actor_id,
            "event_type": event_type,
            "metadata": json.loads(metadata_json),
            "postings": [(p.account_id, p.asset, p.amount) for p in postings],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_hash(
        event_id: str, sequence: int, event_type: str, idempotency_key: str,
        actor_id: str, timestamp: str, postings: tuple[Posting, ...],
        metadata_json: str, previous_hash: str,
    ) -> str:
        payload = {
            "event_id": event_id,
            "sequence": sequence,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "actor_id": actor_id,
            "timestamp": timestamp,
            "postings": [(p.account_id, p.asset, p.amount) for p in postings],
            "metadata_json": metadata_json,
            "previous_hash": previous_hash,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_event(cur: object, event_id: object) -> LedgerEvent:
        cur.execute(
            """SELECT event_id,sequence,event_type,idempotency_key,actor_id,
                      event_timestamp,metadata,previous_hash,event_hash
               FROM sdu_events WHERE event_id=%s""",
            (event_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise PostgresLedgerError("idempotency record references missing event")
        cur.execute(
            """SELECT account_id,asset_symbol,amount FROM sdu_postings
               WHERE event_id=%s ORDER BY line_number""",
            (event_id,),
        )
        postings = tuple(Posting(a, asset, int(amount)) for a, asset, amount in cur.fetchall())
        metadata = row[7]
        if not isinstance(metadata, str):
            metadata = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return LedgerEvent(
            str(row[0]), int(row[1]), str(row[2]), str(row[3]), str(row[4]),
            row[5].astimezone(timezone.utc).isoformat(), postings, metadata,
            str(row[8]).strip(), str(row[9]).strip(),
        )
