from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_postgres_ledger import (
    DuplicateBurnClaim,
    DuplicateExternalDeposit,
    DuplicateIssuanceClaim,
    EpochBudgetExceeded,
    PostgresLedger,
)
from sdu_burn_authorization import BurnAuthorizationService, BurnClaim
from sdu_external_deposits import ExternalDepositClaim, ExternalDepositVerifier
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
               sdu_checkpoints, sdu_external_deposit_claims, sdu_burn_claims,
               sdu_issuance_claims, sdu_idempotency,
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
                conn.execute(
                    "UPDATE sdu_balances SET balance=999 WHERE account_id='alice' AND asset_symbol='SDU'"
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


def test_postgres_holder_burn_reduces_supply_and_is_auditable():
    ledger = make_ledger()
    keys, issuance_authorizer = make_authorizer()
    mint = make_claim("claim-holder-burn", 100)
    ledger.issue(mint, approvals(mint, keys, issuance_authorizer),
                 authorizer=issuance_authorizer, idempotency_key="mint-holder-burn",
                 actor_id="issuance-service")

    holder_key = b"alice-holder-secret-material-32-bytes"
    burn_authorizer = BurnAuthorizationService(
        {"alice": holder_key},
        {"validator-a": b"a" * 32, "validator-b": b"b" * 32},
        protocol_threshold=2,
        max_burn_amount=1000,
    )
    burn_claim = BurnClaim(
        burn_id="burn-holder-001",
        source_account="alice",
        amount=30,
        burn_scope="holder",
        actor_id="alice",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        purpose="holder voluntary burn",
    )
    signature = burn_authorizer.sign_holder_for_testing(burn_claim, holder_key)
    event = ledger.burn(
        burn_claim, authorizer=burn_authorizer, idempotency_key="burn-holder-001",
        holder_signature=signature,
    )
    assert event.event_type == "SDU_BURN"
    assert ledger.balance("alice") == 70
    assert ledger.total_supply() == 70
    assert ledger.verify_integrity()["events"] == 2


def test_protocol_reserve_burn_requires_explicitly_burnable_reserve_and_threshold():
    ledger = make_ledger()
    keys, issuance_authorizer = make_authorizer()
    ledger.create_account("amm:reserve:burnable", "SDU",
                          kind="amm_reserve", burnable=True)
    mint = make_claim("claim-reserve-burn", 80, destination="amm:reserve:burnable")
    ledger.issue(mint, approvals(mint, keys, issuance_authorizer),
                 authorizer=issuance_authorizer, idempotency_key="mint-reserve-burn",
                 actor_id="issuance-service")

    validator_keys = {"validator-a": b"a" * 32, "validator-b": b"b" * 32}
    burn_authorizer = BurnAuthorizationService(
        {}, validator_keys, protocol_threshold=2, max_burn_amount=1000
    )
    burn_claim = BurnClaim(
        burn_id="burn-reserve-001",
        source_account="amm:reserve:burnable",
        amount=25,
        burn_scope="protocol_reserve",
        actor_id="dao-executor",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        purpose="explicitly approved protocol reserve burn",
    )
    approvals_for_burn = [
        burn_authorizer.sign_protocol_for_testing(
            burn_claim, validator_id, validator_keys[validator_id]
        )
        for validator_id in ("validator-a", "validator-b")
    ]
    ledger.burn(
        burn_claim, authorizer=burn_authorizer,
        idempotency_key="burn-reserve-001",
        validator_approvals=approvals_for_burn,
    )
    assert ledger.balance("amm:reserve:burnable") == 55
    assert ledger.total_supply() == 55
    assert ledger.verify_integrity()["events"] == 2


def test_burn_claim_cannot_be_replayed_with_a_new_idempotency_key():
    ledger = make_ledger()
    keys, issuance_authorizer = make_authorizer()
    mint = make_claim("claim-burn-replay", 100)
    ledger.issue(mint, approvals(mint, keys, issuance_authorizer),
                 authorizer=issuance_authorizer, idempotency_key="mint-burn-replay",
                 actor_id="issuance-service")
    holder_key = b"alice-holder-secret-material-32-bytes"
    burn_authorizer = BurnAuthorizationService(
        {"alice": holder_key}, {"validator-a": b"a" * 32},
        protocol_threshold=1, max_burn_amount=1000
    )
    claim = BurnClaim(
        burn_id="burn-replay",
        source_account="alice",
        amount=10,
        burn_scope="holder",
        actor_id="alice",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        purpose="holder voluntary burn",
    )
    signature = burn_authorizer.sign_holder_for_testing(claim, holder_key)
    ledger.burn(claim, authorizer=burn_authorizer, idempotency_key="burn-replay-1",
                holder_signature=signature)
    with pytest.raises(DuplicateBurnClaim):
        ledger.burn(claim, authorizer=burn_authorizer, idempotency_key="burn-replay-2",
                    holder_signature=signature)
    assert ledger.balance("alice") == 90
    assert ledger.total_supply() == 90


def test_verified_external_deposit_credits_only_attested_usdc_and_is_auditable():
    ledger = make_ledger()
    keys = {"verifier-a": b"a" * 32, "verifier-b": b"b" * 32}
    verifier = ExternalDepositVerifier(
        keys,
        threshold=2,
        supported_chains={"eth-mainnet"},
        supported_assets={"USDC"},
        asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40},
        minimum_confirmations={"eth-mainnet": 12},
        maximum_amounts={"USDC": 1_000_000},
    )
    claim = ExternalDepositClaim(
        deposit_id="deposit-001",
        chain_id="eth-mainnet",
        transaction_hash="c" * 64,
        asset="USDC",
        asset_reference="0x" + "1" * 40,
        amount=250,
        destination_account="alice_usdc",
        block_number=21_000_000,
        confirmations=20,
        proof_digest="d" * 64,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    attestations = [
        verifier.sign_for_testing(claim, validator, keys[validator])
        for validator in ("verifier-a", "verifier-b")
    ]
    event = ledger.credit_external_deposit(
        claim, attestations, verifier=verifier,
        idempotency_key="deposit-001", actor_id="deposit-service",
    )
    assert event.event_type == "EXTERNAL_DEPOSIT"
    assert ledger.balance("alice_usdc", "USDC") == 250
    assert ledger.total_supply("USDC") == 250
    assert ledger.verify_integrity()["events"] == 1


def test_external_transaction_cannot_be_credited_twice_with_new_claim():
    ledger = make_ledger()
    keys = {"verifier-a": b"a" * 32, "verifier-b": b"b" * 32}
    verifier = ExternalDepositVerifier(
        keys, threshold=2, supported_chains={"eth-mainnet"},
        supported_assets={"USDC"}, asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40}, minimum_confirmations={"eth-mainnet": 12},
        maximum_amounts={"USDC": 1_000_000},
    )
    claim = ExternalDepositClaim(
        deposit_id="deposit-replay-1", chain_id="eth-mainnet",
        transaction_hash="e" * 64, asset="USDC",
        asset_reference="0x" + "1" * 40, amount=100,
        destination_account="alice_usdc", block_number=21_000_001,
        confirmations=18, proof_digest="f" * 64,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    attestations = [
        verifier.sign_for_testing(claim, validator, keys[validator])
        for validator in ("verifier-a", "verifier-b")
    ]
    ledger.credit_external_deposit(
        claim, attestations, verifier=verifier,
        idempotency_key="deposit-replay-1", actor_id="deposit-service",
    )
    repeated = ExternalDepositClaim(
        deposit_id="deposit-replay-2", chain_id=claim.chain_id,
        transaction_hash=claim.transaction_hash, asset=claim.asset,
        asset_reference=claim.asset_reference,
        amount=claim.amount, destination_account=claim.destination_account,
        block_number=claim.block_number, confirmations=claim.confirmations,
        proof_digest=claim.proof_digest, expires_at=claim.expires_at,
    )
    repeated_attestations = [
        verifier.sign_for_testing(repeated, validator, keys[validator])
        for validator in ("verifier-a", "verifier-b")
    ]
    with pytest.raises(DuplicateExternalDeposit):
        ledger.credit_external_deposit(
            repeated, repeated_attestations, verifier=verifier,
            idempotency_key="deposit-replay-2", actor_id="deposit-service",
        )
    assert ledger.total_supply("USDC") == 100


def test_multiple_token_transfers_in_one_chain_transaction_are_distinct_deposits():
    ledger = make_ledger()
    verifier_keys = {"verifier-a": b"a" * 32, "verifier-b": b"b" * 32}
    verifier = ExternalDepositVerifier(
        verifier_keys, threshold=2, supported_chains={"eth-mainnet"},
        supported_assets={"USDC"}, minimum_confirmations={"eth-mainnet": 12},
        asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40},
        maximum_amounts={"USDC": 1_000_000},
    )
    common = dict(
        chain_id="eth-mainnet",
        transaction_hash="9" * 64,
        asset="USDC",
        asset_reference="0x" + "1" * 40,
        destination_account="alice_usdc",
        block_number=21_000_002,
        confirmations=24,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    for index, amount in ((0, 100), (1, 250)):
        claim = ExternalDepositClaim(
            deposit_id=f"deposit-multi-{index}",
            amount=amount,
            proof_digest=str(index + 1) * 64,
            transfer_index=index,
            **common,
        )
        attestations = [
            verifier.sign_for_testing(claim, name, verifier_keys[name])
            for name in ("verifier-a", "verifier-b")
        ]
        ledger.credit_external_deposit(
            claim, attestations, verifier=verifier,
            idempotency_key=f"deposit-multi-{index}", actor_id="deposit-service",
        )
    assert ledger.balance("alice_usdc", "USDC") == 350
    assert ledger.total_supply("USDC") == 350
    assert ledger.verify_integrity()["events"] == 2
