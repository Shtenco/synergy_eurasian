from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_issuance_authorization import (
    AuthorizationError,
    IssuanceAuthorizationService,
    IssuanceClaim,
)


def make_claim(**overrides):
    values = {
        "claim_id": "claim-001",
        "epoch_id": "epoch-2026-11",
        "destination_account": "alice",
        "amount": 500,
        "evidence_digest": "a" * 64,
        "purpose": "verified productive contribution",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }
    values.update(overrides)
    return IssuanceClaim(**values)


def make_service():
    keys = {"validator-a": b"a" * 32, "validator-b": b"b" * 32, "validator-c": b"c" * 32}
    return keys, IssuanceAuthorizationService(
        keys, threshold=2, policy_version="research-v1", max_claim_amount=10_000
    )


def test_threshold_approvals_produce_verified_issuance():
    keys, service = make_service()
    claim = make_claim()
    approvals = [
        service.sign_for_testing(claim, "validator-a", keys["validator-a"]),
        service.sign_for_testing(claim, "validator-b", keys["validator-b"]),
    ]
    verified = service.verify(claim, approvals)
    assert verified.claim == claim
    assert verified.approved_validator_ids == ("validator-a", "validator-b")
    assert verified.request_digest == claim.request_digest


def test_insufficient_validator_threshold_rejected():
    keys, service = make_service()
    claim = make_claim()
    approval = service.sign_for_testing(claim, "validator-a", keys["validator-a"])
    with pytest.raises(AuthorizationError, match="threshold"):
        service.verify(claim, [approval])


def test_duplicate_validator_cannot_count_twice():
    keys, service = make_service()
    claim = make_claim()
    approval = service.sign_for_testing(claim, "validator-a", keys["validator-a"])
    with pytest.raises(AuthorizationError, match="duplicate"):
        service.verify(claim, [approval, approval])


def test_tampered_claim_invalidates_signatures():
    keys, service = make_service()
    original = make_claim()
    approval = service.sign_for_testing(original, "validator-a", keys["validator-a"])
    changed = make_claim(amount=501)
    with pytest.raises(AuthorizationError, match="signature"):
        service.verify(changed, [approval])


def test_expired_claim_rejected():
    keys, service = make_service()
    claim = make_claim(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    approvals = [
        service.sign_for_testing(claim, "validator-a", keys["validator-a"]),
        service.sign_for_testing(claim, "validator-b", keys["validator-b"]),
    ]
    with pytest.raises(AuthorizationError, match="expired"):
        service.verify(claim, approvals)


def test_claim_limit_and_invalid_evidence_digest_rejected():
    keys, service = make_service()
    with pytest.raises(AuthorizationError, match="maximum"):
        service.verify(make_claim(amount=10_001), [])
    with pytest.raises(AuthorizationError, match="evidence_digest"):
        make_claim(evidence_digest="not-a-hash").canonical_payload()


def test_unknown_validator_and_bad_key_rejected():
    _, service = make_service()
    claim = make_claim()
    from sdu_issuance_authorization import ValidatorApproval
    with pytest.raises(AuthorizationError, match="unknown"):
        service.verify(claim, [ValidatorApproval("intruder", "0" * 64)])
    with pytest.raises(AuthorizationError, match="32 bytes"):
        IssuanceAuthorizationService({"weak": b"short"}, threshold=1,
                                     policy_version="v1", max_claim_amount=10)
