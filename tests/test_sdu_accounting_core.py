from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from concurrent.futures import ThreadPoolExecutor

import pytest

from sdu_accounting_core import (
    Account,
    AssetSpec,
    IdempotencyConflict,
    InsufficientFunds,
    Ledger,
    Posting,
    ValidationError,
)


def make_ledger():
    ledger = Ledger()
    ledger.register_asset(AssetSpec("SDU", 6))
    ledger.register_asset(AssetSpec("USDC", 6))
    ledger.create_account(Account("alice", "SDU"))
    ledger.create_account(Account("bob", "SDU"))
    ledger.create_account(Account("amm_sdu", "SDU", kind="amm_reserve", burnable=False))
    ledger.create_account(Account("amm_usdc", "USDC", kind="amm_reserve", burnable=False))
    ledger.create_account(Account("alice_usdc", "USDC"))
    ledger.create_account(Account("protocol_usdc", "USDC", kind="fee"))
    return ledger


def test_mint_transfer_burn_supply_conservation():
    ledger = make_ledger()
    ledger.issue("alice", 1_000_000, approval_ref="approval-1", idempotency_key="mint-1")
    assert ledger.total_supply("SDU") == 1_000_000
    ledger.transfer(
        "alice", "bob", 250_000, asset="SDU",
        idempotency_key="transfer-1", actor_id="alice",
    )
    assert ledger.balance("alice") == 750_000
    assert ledger.balance("bob") == 250_000
    ledger.burn("bob", 50_000, idempotency_key="burn-1", actor_id="bob")
    assert ledger.total_supply("SDU") == 950_000
    ledger.verify_integrity()


def test_issuance_requires_approval_reference():
    ledger = make_ledger()
    with pytest.raises(ValidationError):
        ledger.issue("alice", 100, approval_ref="", idempotency_key="mint-x")


def test_approval_reference_is_recorded_not_cryptographically_verified():
    ledger = make_ledger()
    event = ledger.issue(
        "alice", 100, approval_ref="external-ref", idempotency_key="mint-1"
    )
    assert event.metadata["approval_ref"] == "external-ref"
    # Authorization and epoch-budget enforcement belong to a separate service.


def test_transfer_cannot_overdraw():
    ledger = make_ledger()
    with pytest.raises(InsufficientFunds):
        ledger.transfer(
            "alice", "bob", 1, asset="SDU",
            idempotency_key="x", actor_id="alice",
        )
    assert ledger.balance("alice") == 0
    assert len(ledger.events) == 0


def test_idempotent_retry_returns_same_event():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    first = ledger.transfer(
        "alice", "bob", 40, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    second = ledger.transfer(
        "alice", "bob", 40, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    assert first == second
    assert len(ledger.events) == 2
    assert ledger.balance("alice") == 60


def test_idempotency_key_cannot_be_reused_for_different_command():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    ledger.transfer(
        "alice", "bob", 40, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    with pytest.raises(IdempotencyConflict):
        ledger.transfer(
            "alice", "bob", 30, asset="SDU",
            idempotency_key="t-1", actor_id="alice",
        )


def test_each_asset_must_balance_independently():
    ledger = make_ledger()
    with pytest.raises(ValidationError):
        ledger.post(
            "BAD_SWAP",
            (
                Posting("alice", "SDU", -10),
                Posting("bob", "SDU", 10),
                Posting("alice_usdc", "USDC", -5),
            ),
            idempotency_key="bad-swap",
            actor_id="tester",
        )


def test_atomic_multicurrency_settlement_balances_both_assets():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-sdu")
    ledger.create_account(
        Account(
            "external:usdc_genesis",
            "USDC",
            allow_negative=True,
            counts_toward_supply=False,
            kind="external_genesis",
            burnable=False,
        )
    )
    ledger.post(
        "GENESIS_USDC",
        (
            Posting("external:usdc_genesis", "USDC", -7),
            Posting("alice_usdc", "USDC", 7),
        ),
        idempotency_key="genesis-usdc",
        actor_id="test-fixture",
    )
    ledger.post(
        "SWAP_SETTLEMENT",
        (
            Posting("alice", "SDU", -20),
            Posting("amm_sdu", "SDU", 20),
            Posting("alice_usdc", "USDC", -7),
            Posting("amm_usdc", "USDC", 7),
        ),
        idempotency_key="swap-1",
        actor_id="amm",
    )
    assert ledger.balance_of("alice", "SDU") == 80
    assert ledger.balance_of("amm_sdu", "SDU") == 20
    assert ledger.balance_of("amm_usdc", "USDC") == 7
    ledger.verify_integrity()


def test_account_asset_mismatch_rejected():
    ledger = make_ledger()
    with pytest.raises(ValidationError):
        ledger.post(
            "BAD",
            (
                Posting("alice", "USDC", -1),
                Posting("protocol_usdc", "USDC", 1),
            ),
            idempotency_key="bad",
            actor_id="tester",
        )


def test_reversal_is_a_new_event_and_cannot_be_applied_twice():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    transfer = ledger.transfer(
        "alice", "bob", 40, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    reversal = ledger.reverse(
        transfer.event_id, idempotency_key="reverse-1", actor_id="admin"
    )
    assert reversal.event_type == "REVERSAL"
    assert ledger.balance("alice") == 100
    assert ledger.balance("bob") == 0
    assert ledger.reverse(
        transfer.event_id, idempotency_key="reverse-1", actor_id="admin"
    ) == reversal
    with pytest.raises(ValidationError):
        ledger.reverse(
            transfer.event_id, idempotency_key="reverse-2", actor_id="admin"
        )
    ledger.verify_integrity()


def test_concurrent_double_spend_only_one_transfer_succeeds():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")

    def spend(key, destination):
        try:
            ledger.transfer(
                "alice", destination, 80, asset="SDU",
                idempotency_key=key, actor_id="alice",
            )
            return "ok"
        except InsufficientFunds:
            return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: spend(*args),
                [("spend-1", "bob"), ("spend-2", "amm_sdu")],
            )
        )
    assert sorted(results) == ["insufficient", "ok"]
    assert ledger.balance("alice") == 20
    ledger.verify_integrity()


def test_hash_chain_and_projection_replay():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    ledger.transfer(
        "alice", "bob", 10, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    ledger.verify_integrity()
    assert ledger.events[1].previous_hash == ledger.events[0].event_hash


def test_protocol_reserve_burn_requires_explicit_permission():
    ledger = make_ledger()
    ledger.issue("amm_sdu", 100, approval_ref="a1", idempotency_key="mint-reserve")
    with pytest.raises(ValidationError):
        ledger.burn(
            "amm_sdu", 10, idempotency_key="burn-reserve", actor_id="protocol"
        )


def test_negative_or_zero_commands_rejected():
    ledger = make_ledger()
    with pytest.raises(ValidationError):
        ledger.issue("alice", 0, approval_ref="a1", idempotency_key="zero-mint")
    with pytest.raises(ValidationError):
        ledger.transfer(
            "alice", "bob", -1, asset="SDU",
            idempotency_key="negative", actor_id="alice",
        )


def test_rebuild_balances_matches_live_projection():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    ledger.transfer(
        "alice", "bob", 25, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    rebuilt = ledger.rebuild_balances()
    assert rebuilt[("alice", "SDU")] == ledger.balance("alice") == 75
    assert rebuilt[("bob", "SDU")] == ledger.balance("bob") == 25


def test_public_post_cannot_bypass_issuance_gate():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    with pytest.raises(ValidationError):
        ledger.post(
            "FORGED_MINT",
            (
                Posting("system:issuance:SDU", "SDU", -50),
                Posting("bob", "SDU", 50),
            ),
            idempotency_key="forged",
            actor_id="attacker",
        )
    assert ledger.total_supply("SDU") == 100
    assert ledger.balance("bob") == 0


def test_public_post_cannot_forge_reversal_metadata():
    ledger = make_ledger()
    ledger.issue("alice", 100, approval_ref="a1", idempotency_key="mint-1")
    transfer = ledger.transfer(
        "alice", "bob", 10, asset="SDU",
        idempotency_key="t-1", actor_id="alice",
    )
    with pytest.raises(ValidationError):
        ledger.post(
            "REVERSAL",
            (Posting("alice", "SDU", 1), Posting("bob", "SDU", -1)),
            idempotency_key="fake-reversal",
            actor_id="attacker",
            metadata={"original_event_id": transfer.event_id},
        )
    ledger.verify_integrity()


def test_supply_counted_account_cannot_be_configured_with_overdraft():
    ledger = Ledger()
    ledger.register_asset(AssetSpec("SDU", 6))
    with pytest.raises(ValidationError):
        ledger.create_account(
            Account("unsafe", "SDU", allow_negative=True, counts_toward_supply=True)
        )


def test_system_account_configuration_cannot_be_preseeded_incorrectly():
    ledger = make_ledger()
    ledger.create_account(Account("system:issuance:SDU", "SDU", kind="wallet"))
    with pytest.raises(ValidationError, match="system account configuration mismatch"):
        ledger.issue("alice", 10, approval_ref="a1", idempotency_key="mint-1")


def test_sdu_issuance_cannot_mint_external_usdc():
    ledger = make_ledger()
    with pytest.raises(ValidationError, match="cannot mint external assets"):
        ledger.issue(
            "alice_usdc", 10, approval_ref="fake-usdc", idempotency_key="mint-usdc"
        )
    assert ledger.balance_of("alice_usdc", "USDC") == 0


def test_sdu_burn_engine_cannot_burn_external_usdc():
    ledger = make_ledger()
    with pytest.raises(ValidationError, match="cannot burn external assets"):
        ledger.burn(
            "alice_usdc", 10, idempotency_key="burn-usdc", actor_id="protocol"
        )
    assert ledger.balance_of("alice_usdc", "USDC") == 0
