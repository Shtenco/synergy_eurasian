from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_issuance_authorization import ValidatorApproval
from sdu_external_deposits import (
    ExternalDepositClaim,
    ExternalDepositError,
    ExternalDepositVerifier,
)


def make_claim(**overrides):
    values = {
        "deposit_id": "deposit-001",
        "chain_id": "eth-mainnet",
        "transaction_hash": "a" * 64,
        "asset": "USDC",
        "asset_reference": "0x" + "1" * 40,
        "amount": 250_000,
        "destination_account": "alice-usdc",
        "block_number": 21_000_000,
        "confirmations": 24,
        "proof_digest": "b" * 64,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }
    values.update(overrides)
    return ExternalDepositClaim(**values)


def make_verifier():
    keys = {"verifier-a": b"a" * 32, "verifier-b": b"b" * 32, "verifier-c": b"c" * 32}
    verifier = ExternalDepositVerifier(
        keys,
        threshold=2,
        supported_chains={"eth-mainnet"},
        supported_assets={"USDC"},
        asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40},
        minimum_confirmations={"eth-mainnet": 12},
        maximum_amounts={"USDC": 5_000_000},
    )
    return keys, verifier


def sign(claim, keys, verifier):
    return [
        verifier.sign_for_testing(claim, "verifier-a", keys["verifier-a"]),
        verifier.sign_for_testing(claim, "verifier-b", keys["verifier-b"]),
    ]


def test_external_deposit_requires_threshold_attestations():
    keys, verifier = make_verifier()
    claim = make_claim()
    verified = verifier.verify(claim, sign(claim, keys, verifier))
    assert verified.claim == claim
    assert verified.approved_verifier_ids == ("verifier-a", "verifier-b")


def test_external_deposit_rejects_insufficient_verifier_threshold():
    keys, verifier = make_verifier()
    claim = make_claim()
    one = verifier.sign_for_testing(claim, "verifier-a", keys["verifier-a"])
    with pytest.raises(ExternalDepositError, match="threshold"):
        verifier.verify(claim, [one])


def test_external_deposit_binds_tx_hash_amount_asset_and_destination():
    keys, verifier = make_verifier()
    claim = make_claim()
    attestations = sign(claim, keys, verifier)
    altered = make_claim(amount=claim.amount + 1)
    with pytest.raises(ExternalDepositError, match="attestation"):
        verifier.verify(altered, attestations)


def test_external_deposit_checks_chain_asset_confirmations_and_limit():
    keys, verifier = make_verifier()
    attestations = sign(make_claim(), keys, verifier)
    with pytest.raises(ExternalDepositError, match="unsupported external chain"):
        verifier.verify(make_claim(chain_id="unknown-chain"), attestations)
    with pytest.raises(ExternalDepositError, match="unsupported external asset"):
        verifier.verify(make_claim(asset="BTC"), attestations)
    with pytest.raises(ExternalDepositError, match="insufficient confirmations"):
        verifier.verify(make_claim(confirmations=2), attestations)
    with pytest.raises(ExternalDepositError, match="asset limit"):
        verifier.verify(make_claim(amount=5_000_001), attestations)


def test_external_deposit_expiry_and_duplicate_verifier_rejected():
    keys, verifier = make_verifier()
    expired = make_claim(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    with pytest.raises(ExternalDepositError, match="expired"):
        verifier.verify(expired, sign(expired, keys, verifier))
    claim = make_claim()
    one = verifier.sign_for_testing(claim, "verifier-a", keys["verifier-a"])
    with pytest.raises(ExternalDepositError, match="duplicate"):
        verifier.verify(claim, [one, one])


def test_external_deposit_hash_fields_must_be_canonical():
    with pytest.raises(ExternalDepositError, match="transaction_hash"):
        make_claim(transaction_hash="0x123").canonical_payload()
    with pytest.raises(ExternalDepositError, match="proof_digest"):
        make_claim(proof_digest="bad").canonical_payload()


def test_external_verifier_requires_complete_chain_and_asset_policy():
    keys = {"verifier-a": b"a" * 32}
    with pytest.raises(ExternalDepositError, match="minimum confirmations"):
        ExternalDepositVerifier(
            keys, threshold=1, supported_chains={"eth-mainnet"},
            supported_assets={"USDC"}, asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40}, minimum_confirmations={},
            maximum_amounts={"USDC": 1000},
        )
    with pytest.raises(ExternalDepositError, match="maximum deposit"):
        ExternalDepositVerifier(
            keys, threshold=1, supported_chains={"eth-mainnet"},
            supported_assets={"USDC"}, minimum_confirmations={"eth-mainnet": 12},
            asset_references={("eth-mainnet", "USDC"): "0x" + "1" * 40},
            maximum_amounts={},
        )


def test_transfer_index_is_signed_and_must_be_non_negative_integer():
    keys, verifier = make_verifier()
    original = make_claim(transfer_index=0)
    signatures = sign(original, keys, verifier)
    altered = make_claim(transfer_index=1)
    with pytest.raises(ExternalDepositError, match="attestation"):
        verifier.verify(altered, signatures)
    with pytest.raises(ExternalDepositError, match="transfer_index"):
        make_claim(transfer_index=-1).canonical_payload()
    with pytest.raises(ExternalDepositError, match="transfer_index"):
        make_claim(transfer_index=True).canonical_payload()


def test_external_deposit_rejects_unapproved_token_contract_for_allowed_symbol():
    keys, verifier = make_verifier()
    claim = make_claim()
    signatures = sign(claim, keys, verifier)
    forged_contract = make_claim(asset_reference="0x" + "2" * 40)
    with pytest.raises(ExternalDepositError, match="contract/denom"):
        verifier.verify(forged_contract, signatures)


def test_external_verifier_rejects_noncanonical_allowlist_identifiers():
    keys = {"verifier-a": b"a" * 32}
    with pytest.raises(ExternalDepositError, match="trimmed"):
        ExternalDepositVerifier(
            keys, threshold=1, supported_chains={" eth-mainnet "},
            supported_assets={"USDC"},
            asset_references={(" eth-mainnet ", "USDC"): "0x" + "1" * 40},
            minimum_confirmations={" eth-mainnet ": 12},
            maximum_amounts={"USDC": 1000},
        )


def test_external_deposit_rejects_non_string_fields_and_malformed_attestations():
    for field in ("deposit_id", "chain_id", "destination_account", "asset", "asset_reference", "expires_at"):
        with pytest.raises(ExternalDepositError, match=field):
            make_claim(**{field: None}).canonical_payload()
    with pytest.raises(ExternalDepositError, match="transaction_hash"):
        make_claim(transaction_hash=123).canonical_payload()
    with pytest.raises(ExternalDepositError, match="proof_digest"):
        make_claim(proof_digest=123).canonical_payload()

    keys, verifier = make_verifier()
    claim = make_claim()
    with pytest.raises(ExternalDepositError, match="attestation record"):
        verifier.verify(claim, [object()])
    with pytest.raises(ExternalDepositError, match="canonical"):
        verifier.verify(claim, [ValidatorApproval("verifier-a", "not-a-signature")])
    with pytest.raises(ExternalDepositError, match="list or tuple"):
        verifier.verify(claim, iter(sign(claim, keys, verifier)))
