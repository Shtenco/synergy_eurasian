"""Minimal, dependency-free SDU event ledger.

Research prototype only. This module is not a deployed token contract,
production payment processor, or authorization service.
Amounts are integer atomic units; each transaction must balance per asset.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Iterable, Mapping


class LedgerError(Exception):
    """Base exception for rejected ledger commands."""


class ValidationError(LedgerError):
    pass


class InsufficientFunds(LedgerError):
    pass


class IdempotencyConflict(LedgerError):
    pass


class AccountNotFound(LedgerError):
    pass


class DuplicateAccount(LedgerError):
    pass


@dataclass(frozen=True, slots=True)
class AssetSpec:
    symbol: str
    decimals: int

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol.strip() != self.symbol:
            raise ValidationError("asset symbol must be non-empty and trimmed")
        if isinstance(self.decimals, bool) or not isinstance(self.decimals, int):
            raise ValidationError("asset decimals must be an integer")
        if not 0 <= self.decimals <= 18:
            raise ValidationError("asset decimals must be between 0 and 18")


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    asset: str
    allow_negative: bool = False
    counts_toward_supply: bool = True
    kind: str = "wallet"
    burnable: bool = True


@dataclass(frozen=True, slots=True)
class Posting:
    account_id: str
    asset: str
    amount: int  # signed atomic units; positive = credit, negative = debit


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    event_id: str
    sequence: int
    event_type: str
    idempotency_key: str
    actor_id: str
    timestamp: str
    postings: tuple[Posting, ...]
    metadata_json: str
    previous_hash: str
    event_hash: str

    @property
    def metadata(self) -> dict[str, object]:
        return json.loads(self.metadata_json)


class Ledger:
    """Thread-safe in-memory event ledger with a rebuildable balance projection.

    The RLock makes commands atomic only within this Python process. A persistent
    implementation still needs database transactions, unique constraints and
    concurrency control at the storage layer.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._assets: dict[str, AssetSpec] = {}
        self._accounts: dict[str, Account] = {}
        self._balances: dict[tuple[str, str], int] = {}
        self._events: list[LedgerEvent] = []
        self._idempotency: dict[str, tuple[str, LedgerEvent]] = {}
        self._reversed: set[str] = set()
        self._lock = threading.RLock()

    @property
    def events(self) -> tuple[LedgerEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def register_asset(self, spec: AssetSpec) -> None:
        with self._lock:
            existing = self._assets.get(spec.symbol)
            if existing is not None and existing != spec:
                raise ValidationError(f"asset {spec.symbol} already has a different specification")
            self._assets[spec.symbol] = spec

    def create_account(self, account: Account) -> None:
        with self._lock:
            if account.account_id in self._accounts:
                raise DuplicateAccount(account.account_id)
            if account.asset not in self._assets:
                raise ValidationError(f"unknown asset: {account.asset}")
            if not account.account_id or account.account_id.strip() != account.account_id:
                raise ValidationError("account_id must be non-empty and trimmed")
            if not isinstance(account.allow_negative, bool) or not isinstance(account.counts_toward_supply, bool) or not isinstance(account.burnable, bool):
                raise ValidationError("account policy flags must be booleans")
            if account.counts_toward_supply and account.allow_negative:
                raise ValidationError("supply-counted accounts cannot allow negative balances")
            if not account.kind or account.kind.strip() != account.kind:
                raise ValidationError("account kind must be non-empty and trimmed")
            self._accounts[account.account_id] = account
            self._balances[(account.account_id, account.asset)] = 0

    def balance(self, account_id: str) -> int:
        with self._lock:
            account = self._accounts.get(account_id)
            if account is None:
                raise AccountNotFound(account_id)
            return self._balances[(account_id, account.asset)]

    def balance_of(self, account_id: str, asset: str) -> int:
        with self._lock:
            self._require_account_asset(account_id, asset)
            return self._balances[(account_id, asset)]

    def total_supply(self, asset: str) -> int:
        with self._lock:
            if asset not in self._assets:
                raise ValidationError(f"unknown asset: {asset}")
            return sum(
                self._balances[(a.account_id, asset)]
                for a in self._accounts.values()
                if a.asset == asset and a.counts_toward_supply
            )

    def issue(
        self, destination: str, amount: int, *, approval_ref: str,
        idempotency_key: str, actor_id: str = "issuance-engine",
        metadata: Mapping[str, object] | None = None,
    ) -> LedgerEvent:
        """Record a mint command.

        This method only requires a non-empty approval reference; it does NOT
        cryptographically validate an approval or enforce an epoch budget.
        Those controls must be implemented by the issuance command service.
        """
        with self._lock:
            if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                raise ValidationError("mint amount must be a positive integer")
            if not approval_ref or not approval_ref.strip():
                raise ValidationError("approval_ref is required")
            account = self._accounts.get(destination)
            if account is None:
                raise AccountNotFound(destination)
            if account.asset != "SDU":
                raise ValidationError("the SDU issuance engine cannot mint external assets")
            if account.kind.startswith("system_"):
                raise ValidationError("issuance destination cannot be a system account")
            if not account.counts_toward_supply:
                raise ValidationError("mint destination must count toward token supply")
            system_id = f"system:issuance:{account.asset}"
            self._ensure_system_account(system_id, account.asset, "issuance")
            data = dict(metadata or {})
            data["approval_ref"] = approval_ref
            return self._post(
                "SDU_MINT",
                (Posting(system_id, account.asset, -amount), Posting(destination, account.asset, amount)),
                idempotency_key=idempotency_key, actor_id=actor_id, metadata=data,
            )

    def burn(
        self, source: str, amount: int, *, idempotency_key: str,
        actor_id: str, metadata: Mapping[str, object] | None = None,
    ) -> LedgerEvent:
        with self._lock:
            if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                raise ValidationError("burn amount must be a positive integer")
            account = self._accounts.get(source)
            if account is None:
                raise AccountNotFound(source)
            if account.asset != "SDU":
                raise ValidationError("the SDU burn engine cannot burn external assets")
            if not account.burnable:
                raise ValidationError(f"burn is not permitted from account {source}")
            if not account.counts_toward_supply:
                raise ValidationError("burn source must count toward token supply")
            system_id = f"system:burn:{account.asset}"
            self._ensure_system_account(system_id, account.asset, "burn")
            return self._post(
                "SDU_BURN",
                (Posting(source, account.asset, -amount), Posting(system_id, account.asset, amount)),
                idempotency_key=idempotency_key, actor_id=actor_id, metadata=metadata,
            )

    def transfer(
        self, source: str, destination: str, amount: int, *, asset: str,
        idempotency_key: str, actor_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> LedgerEvent:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValidationError("transfer amount must be a positive integer")
        return self.post(
            "TRANSFER",
            (Posting(source, asset, -amount), Posting(destination, asset, amount)),
            idempotency_key=idempotency_key, actor_id=actor_id, metadata=metadata,
        )

    def post(
        self, event_type: str, postings: Iterable[Posting], *,
        idempotency_key: str, actor_id: str,
        metadata: Mapping[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> LedgerEvent:
        """Post an ordinary transaction; system accounts are command-gated."""
        legs = tuple(postings)
        with self._lock:
            if event_type in {"SDU_MINT", "SDU_BURN", "REVERSAL"}:
                raise ValidationError("reserved event type requires a privileged command")
            for leg in legs:
                account = self._accounts.get(leg.account_id)
                if account is not None and (
                    account.kind.startswith("system_")
                    or account.allow_negative
                    or not account.counts_toward_supply
                ):
                    raise ValidationError("privileged counter accounts may only be used by dedicated commands")
            return self._post(
                event_type, legs, idempotency_key=idempotency_key,
                actor_id=actor_id, metadata=metadata, timestamp=timestamp,
            )

    def _post(
        self, event_type: str, postings: Iterable[Posting], *,
        idempotency_key: str, actor_id: str,
        metadata: Mapping[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> LedgerEvent:
        with self._lock:
            if not event_type or not event_type.strip():
                raise ValidationError("event_type is required")
            if not idempotency_key or not idempotency_key.strip():
                raise ValidationError("idempotency_key is required")
            if not actor_id or not actor_id.strip():
                raise ValidationError("actor_id is required")

            legs = tuple(postings)
            if len(legs) < 2:
                raise ValidationError("a ledger event needs at least two postings")
            per_asset: dict[str, int] = {}
            per_account: dict[tuple[str, str], int] = {}
            for leg in legs:
                if isinstance(leg.amount, bool) or not isinstance(leg.amount, int):
                    raise ValidationError("posting amount must be integer atomic units")
                if leg.amount == 0:
                    raise ValidationError("zero-value postings are not allowed")
                self._require_account_asset(leg.account_id, leg.asset)
                per_asset[leg.asset] = per_asset.get(leg.asset, 0) + leg.amount
                key = (leg.account_id, leg.asset)
                per_account[key] = per_account.get(key, 0) + leg.amount
            unbalanced = {asset: total for asset, total in per_asset.items() if total != 0}
            if unbalanced:
                raise ValidationError(f"transaction is not balanced per asset: {unbalanced}")

            metadata_json = json.dumps(dict(metadata or {}), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            fingerprint = self._fingerprint(event_type, actor_id, legs, metadata_json)
            prior = self._idempotency.get(idempotency_key)
            if prior is not None:
                prior_fingerprint, prior_event = prior
                if prior_fingerprint != fingerprint:
                    raise IdempotencyConflict("idempotency key was already used for a different command")
                return prior_event

            for (account_id, asset), delta in per_account.items():
                account = self._accounts[account_id]
                resulting = self._balances[(account_id, asset)] + delta
                if resulting < 0 and not account.allow_negative:
                    raise InsufficientFunds(f"insufficient funds in {account_id}")

            event_time = timestamp or datetime.now(timezone.utc)
            if event_time.tzinfo is None:
                raise ValidationError("timestamp must be timezone-aware")
            timestamp_text = event_time.astimezone(timezone.utc).isoformat()
            sequence = len(self._events) + 1
            event_id = f"sdu-event-{sequence:012d}"
            previous_hash = self._events[-1].event_hash if self._events else self.GENESIS_HASH
            event_hash = self._hash_event(
                event_id, sequence, event_type, idempotency_key, actor_id,
                timestamp_text, legs, metadata_json, previous_hash,
            )
            event = LedgerEvent(
                event_id, sequence, event_type, idempotency_key, actor_id,
                timestamp_text, legs, metadata_json, previous_hash, event_hash,
            )

            # Commit point: no state is changed until every validation has passed.
            for (account_id, asset), delta in per_account.items():
                self._balances[(account_id, asset)] += delta
            self._events.append(event)
            self._idempotency[idempotency_key] = (fingerprint, event)
            if event_type == "REVERSAL":
                original_id = str(json.loads(metadata_json).get("original_event_id", ""))
                self._reversed.add(original_id)
            return event

    def reverse(self, event_id: str, *, idempotency_key: str, actor_id: str) -> LedgerEvent:
        with self._lock:
            original = next((e for e in self._events if e.event_id == event_id), None)
            if original is None:
                raise ValidationError(f"unknown event: {event_id}")
            if event_id in self._reversed:
                existing = next((e for e in self._events
                                 if e.event_type == "REVERSAL"
                                 and e.metadata.get("original_event_id") == event_id), None)
                if existing is not None and existing.idempotency_key == idempotency_key and existing.actor_id == actor_id:
                    return existing
                raise ValidationError("event has already been reversed")
            if original.event_type == "REVERSAL":
                raise ValidationError("reversal events cannot be reversed in this prototype")
            inverse = tuple(Posting(p.account_id, p.asset, -p.amount) for p in original.postings)
            return self._post(
                "REVERSAL", inverse, idempotency_key=idempotency_key,
                actor_id=actor_id, metadata={"original_event_id": event_id},
            )

    def verify_integrity(self) -> None:
        with self._lock:
            replay: dict[tuple[str, str], int] = {
                (a.account_id, a.asset): 0 for a in self._accounts.values()
            }
            previous_hash = self.GENESIS_HASH
            seen_keys: set[str] = set()
            seen_event_ids: set[str] = set()
            seen_events_by_id: dict[str, LedgerEvent] = {}
            replayed_reversals: set[str] = set()
            for expected_sequence, event in enumerate(self._events, start=1):
                if event.sequence != expected_sequence:
                    raise ValidationError("event sequence gap or reorder detected")
                if event.previous_hash != previous_hash:
                    raise ValidationError("event hash chain predecessor mismatch")
                expected_hash = self._hash_event(
                    event.event_id, event.sequence, event.event_type,
                    event.idempotency_key, event.actor_id, event.timestamp,
                    event.postings, event.metadata_json, event.previous_hash,
                )
                if event.event_hash != expected_hash:
                    raise ValidationError("event hash mismatch")
                if event.idempotency_key in seen_keys:
                    raise ValidationError("duplicate idempotency key in event log")
                seen_keys.add(event.idempotency_key)
                if event.event_id in seen_event_ids:
                    raise ValidationError("duplicate event id in event log")
                if event.event_type == "REVERSAL":
                    original_id = str(event.metadata.get("original_event_id", ""))
                    original_event = seen_events_by_id.get(original_id)
                    if original_event is None or original_id in replayed_reversals:
                        raise ValidationError("invalid or duplicate reversal reference")
                    if original_event.event_type == "REVERSAL":
                        raise ValidationError("reversal events cannot reverse other reversals")
                    expected_inverse = sorted(
                        (p.account_id, p.asset, -p.amount) for p in original_event.postings
                    )
                    actual_inverse = sorted(
                        (p.account_id, p.asset, p.amount) for p in event.postings
                    )
                    if actual_inverse != expected_inverse:
                        raise ValidationError("reversal postings do not exactly reverse original event")
                    replayed_reversals.add(original_id)
                seen_event_ids.add(event.event_id)
                seen_events_by_id[event.event_id] = event
                totals: dict[str, int] = {}
                for leg in event.postings:
                    self._require_account_asset(leg.account_id, leg.asset)
                    totals[leg.asset] = totals.get(leg.asset, 0) + leg.amount
                    replay[(leg.account_id, leg.asset)] += leg.amount
                if any(total != 0 for total in totals.values()):
                    raise ValidationError("unbalanced event found during replay")
                previous_hash = event.event_hash
            if replay != self._balances:
                raise ValidationError("balance projection differs from event replay")
            if replayed_reversals != self._reversed:
                raise ValidationError("reversal index differs from event replay")
            for (account_id, _asset), amount in replay.items():
                if amount < 0 and not self._accounts[account_id].allow_negative:
                    raise ValidationError(f"negative balance in non-overdraft account: {account_id}")

    def rebuild_balances(self) -> dict[tuple[str, str], int]:
        """Rebuild a fresh balance projection from the immutable event sequence."""
        with self._lock:
            rebuilt = {(a.account_id, a.asset): 0 for a in self._accounts.values()}
            for event in self._events:
                for posting in event.postings:
                    key = (posting.account_id, posting.asset)
                    rebuilt[key] = rebuilt.get(key, 0) + posting.amount
            return rebuilt

    def _ensure_system_account(self, account_id: str, asset: str, kind: str) -> None:
        expected = Account(
            account_id, asset, allow_negative=True, counts_toward_supply=False,
            kind=f"system_{kind}", burnable=False,
        )
        existing = self._accounts.get(account_id)
        if existing is None:
            self.create_account(expected)
        elif existing != expected:
            raise ValidationError(f"system account configuration mismatch: {account_id}")

    def _require_account_asset(self, account_id: str, asset: str) -> None:
        if asset not in self._assets:
            raise ValidationError(f"unknown asset: {asset}")
        account = self._accounts.get(account_id)
        if account is None:
            raise AccountNotFound(account_id)
        if account.asset != asset:
            raise ValidationError(f"account {account_id} is not denominated in {asset}")

    @staticmethod
    def _fingerprint(event_type: str, actor_id: str, legs: tuple[Posting, ...], metadata_json: str) -> str:
        normalized = sorted((p.account_id, p.asset, p.amount) for p in legs)
        payload = json.dumps([event_type, actor_id, normalized, metadata_json], separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_event(
        event_id: str, sequence: int, event_type: str, idempotency_key: str,
        actor_id: str, timestamp: str, legs: tuple[Posting, ...],
        metadata_json: str, previous_hash: str,
    ) -> str:
        payload = {
            "event_id": event_id,
            "sequence": sequence,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "actor_id": actor_id,
            "timestamp": timestamp,
            "postings": [(p.account_id, p.asset, p.amount) for p in legs],
            "metadata_json": metadata_json,
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
