from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_postgres_ledger import (
    DuplicateIssuanceClaim,
    EpochBudgetExceeded,
    PostgresLedger,
)
from sdu_issuance_authorization import (
    IssuanceAuthorizationService,
    IssuanceClaim,
    ValidatorApproval,
)
from sdu_accounting_core import InsufficientFunds


DATABASE_URL = os.getenv("SDU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("SDU_TEST_DATABASE_URL is not configured", allow_module_level=True)

psycopg = pytest.importorskip("psycopg")


@pytest.fixture(scope="session", autouse=True)
def install_schema():
    migration = (ROOT / "migrations" / "001_sdu_ledger.sql").read_text()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(migration)
    yield


@pytest.fixture(autouse=True)
def clean_database(install_schema):
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """TRUNCATE TABLE
               sdu_checkpoints, sdu_issuance_claims, sdu_idempotency,
               sdu_postings, sdu_events, sdu_balances, sdu_accounts,
               sdu_assets, sdu_epoch_issuance
               RESTART IDENTITY CASCADE"""
        )
        conn.execute(
            "UPDATE sdu_ledger_state SET next_sequence=1,last_event_hash=%s WHERE singleton=TRUE",
            ("0" * 64,),
        )


def make_ledger():
    ledger = PostgresLedger(lambda: psycopg.connect(DATABASE_URL))
    ledger.register_asset("SDU", 6)
    ledger.register_asset("USDC", 6)
    ledger.create_account("alice", "SDU")
    ledger.create_account("bob", "SDU")
    ledger.create_account("amm_sdu", "SDU", kind="amm_reserve", burnable=False)
    ledger.create_account("alice_usdc", "USDC")
    ledger.set_epoch_budget("epoch-1", 2_000)
    return ledger


def make_authorizer():
    keys = {"validator-a": b"a" * 32, "validator-b": b"b" * 32, "validator-c": b"c" * 32}
    authorizer = IssuanceAuthorizationService(
        keys, threshold=2, policy_version="integration-v1", max_claim_amount=10_000
    )
    return keys, authorizer


def make_claim(claim_id, amount, destination="alice"):
    return IssuanceClaim(
        claim_id=claim_id,
        epoch_id="epoch-1",
        destination_account=destination,
        amount=amount,
        evidence_digest="d" * 64,
        purpose="integration-test contribution",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )


def approvals(claim, keys, authorizer):
    return [
        authorizer.sign_for_testing(claim, "validator-a", keys["validator-a"]),
        authorizer.sign_for_testing(claim, "validator-b", keys["validator-b"]),
    ]


def test_postgres_issue_transfer_supply_and_idempotency():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-001", 1000)
    event = ledger.issue(
        claim, approvals(claim, keys, authorizer), authorizer=authorizer,
        idempotency_key="mint-001", actor_id="issuance-service",
    )
    assert event.event_type == "SDU_MINT"
    assert ledger.total_supply() == 1000
    repeated = ledger.issue(
        claim, approvals(claim, keys, authorizer), authorizer=authorizer,
        idempotency_key="mint-001", actor_id="issuance-service",
    )
    assert repeated.event_id == event.event_id
    transfer = ledger.transfer(
        "alice", "bob", 400, asset="SDU",
        idempotency_key="transfer-001", actor_id="alice",
    )
    assert transfer.event_type == "TRANSFER"
    assert ledger.balance("alice") == 600
    assert ledger.balance("bob") == 400
    assert ledger.total_supply() == 1000


def test_epoch_budget_is_enforced_transactionally():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    first = make_claim("claim-600", 600)
    ledger.issue(first, approvals(first, keys, authorizer), authorizer=authorizer,
                 idempotency_key="mint-600", actor_id="issuance-service")
    second = make_claim("claim-1500", 1500)
    with pytest.raises(EpochBudgetExceeded):
        ledger.issue(second, approvals(second, keys, authorizer), authorizer=authorizer,
                     idempotency_key="mint-1500", actor_id="issuance-service")
    assert ledger.total_supply() == 600


def test_claim_cannot_be_consumed_twice_with_new_idempotency_key():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-once", 100)
    signed = approvals(claim, keys, authorizer)
    ledger.issue(claim, signed, authorizer=authorizer,
                 idempotency_key="mint-once", actor_id="issuance-service")
    with pytest.raises(DuplicateIssuanceClaim):
        ledger.issue(claim, signed, authorizer=authorizer,
                     idempotency_key="mint-once-again", actor_id="issuance-service")
    assert ledger.total_supply() == 100


def test_independent_connections_cannot_double_spend():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-spend", 100)
    ledger.issue(claim, approvals(claim, keys, authorizer), authorizer=authorizer,
                 idempotency_key="mint-spend", actor_id="issuance-service")

    def spend(args):
        destination, key = args
        try:
            ledger.transfer("alice", destination, 80, asset="SDU",
                            idempotency_key=key, actor_id="alice")
            return "ok"
        except InsufficientFunds:
            return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(spend, [("bob", "spend-a"), ("amm_sdu", "spend-b")]))
    assert sorted(results) == ["insufficient", "ok"]
    assert ledger.balance("alice") == 20
    assert ledger.total_supply() == 100


def test_database_rejects_direct_negative_balance_and_journal_mutation():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-db-guards", 100)
    event = ledger.issue(claim, approvals(claim, keys, authorizer), authorizer=authorizer,
                         idempotency_key="mint-db-guards", actor_id="issuance-service")
    with psycopg.connect(DATABASE_URL) as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute(
                    "UPDATE sdu_balances SET balance=-1 WHERE account_id='alice' AND asset_symbol='SDU'"
                )
    with psycopg.connect(DATABASE_URL) as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("UPDATE sdu_events SET actor_id='tampered' WHERE event_id=%s", (event.event_id,))
    assert ledger.balance("alice") == 100


def test_database_rejects_ordinary_external_counter_account_posting():
    ledger = make_ledger()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """INSERT INTO sdu_accounts
               (account_id,asset_symbol,account_kind,allow_negative,counts_toward_supply,burnable)
               VALUES ('external:counter','SDU','external_counter',TRUE,FALSE,FALSE)"""
        )
        conn.execute(
            "INSERT INTO sdu_balances(account_id,asset_symbol,balance) VALUES ('external:counter','SDU',0)"
        )
    from sdu_accounting_core import Posting, ValidationError
    with pytest.raises(ValidationError, match="privileged counter"):
        ledger.post(
            "FAKE_MINT",
            (Posting("external:counter", "SDU", -10), Posting("alice", "SDU", 10)),
            idempotency_key="fake-mint", actor_id="attacker",
        )


def test_database_replay_audit_and_checkpoint_are_idempotent():
    from sdu_ledger_checkpoints import verify_checkpoint

    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-audit", 250)
    ledger.issue(claim, approvals(claim, keys, authorizer), authorizer=authorizer,
                 idempotency_key="mint-audit", actor_id="issuance-service")
    ledger.transfer("alice", "bob", 50, asset="SDU",
                    idempotency_key="transfer-audit", actor_id="alice")
    audit = ledger.verify_integrity()
    assert audit["events"] == 2
    assert audit["last_sequence"] == 2
    assert audit["postings"] == 4

    signing_key = b"database-checkpoint-key-material-32bytes"
    first = ledger.create_and_store_checkpoint(signing_key)
    second = ledger.create_and_store_checkpoint(signing_key)
    assert first == second
    assert first.sequence == 2
    assert verify_checkpoint(first, signing_key)


def test_system_accounts_cannot_be_created_through_public_account_api():
    ledger = make_ledger()
    from sdu_accounting_core import ValidationError
    with pytest.raises(ValidationError, match="system accounts"):
        ledger.create_account("system:issuance:SDU", "SDU", kind="system_issuance",
                              allow_negative=True, counts_toward_supply=False,
                              burnable=False)


def test_integrity_audit_detects_tampered_ledger_head():
    ledger = make_ledger()
    keys, authorizer = make_authorizer()
    claim = make_claim("claim-head-tamper", 100)
    ledger.issue(claim, approvals(claim, keys, authorizer), authorizer=authorizer,
                 idempotency_key="mint-head-tamper", actor_id="issuance-service")
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            "UPDATE sdu_ledger_state SET last_event_hash=%s WHERE singleton=TRUE",
            ("f" * 64,),
        )
    from sdu_postgres_ledger import PostgresLedgerError
    with pytest.raises(PostgresLedgerError, match="ledger state head"):
        ledger.verify_integrity()
