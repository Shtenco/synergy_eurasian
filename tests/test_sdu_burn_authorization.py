from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_burn_authorization import (
    BurnAuthorizationError,
    BurnAuthorizationService,
    BurnClaim,
)


def claim(scope="holder", source="alice", amount=10):
    return BurnClaim(
        burn_id="burn-001",
        source_account=source,
        amount=amount,
        burn_scope=scope,
        actor_id="alice" if scope == "holder" else "dao-executor",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        purpose="voluntary burn" if scope == "holder" else "approved reserve adjustment",
    )


def service():
    holder_keys = {"alice": b"holder-key-material-32-bytes-long!!"}
    validator_keys = {
        "validator-a": b"validator-a-key-material-32-bytes!!",
        "validator-b": b"validator-b-key-material-32-bytes!!",
        "validator-c": b"validator-c-key-material-32-bytes!!",
    }
    return holder_keys, validator_keys, BurnAuthorizationService(
        holder_keys, validator_keys, protocol_threshold=2, max_burn_amount=1000
    )


def test_holder_burn_requires_source_account_signature():
    holders, _, verifier = service()
    burn = claim()
    signature = verifier.sign_holder_for_testing(burn, holders["alice"])
    verified = verifier.verify(burn, holder_signature=signature)
    assert verified.claim == burn
    assert verified.approved_validator_ids == ()


def test_holder_burn_rejects_missing_or_invalid_signature():
    _, _, verifier = service()
    with pytest.raises(BurnAuthorizationError, match="required"):
        verifier.verify(claim())
    with pytest.raises(BurnAuthorizationError, match="invalid"):
        verifier.verify(claim(), holder_signature="0" * 64)


def test_protocol_reserve_burn_requires_validator_threshold():
    _, validators, verifier = service()
    burn = claim("protocol_reserve", "amm:reserve")
    approvals = [
        verifier.sign_protocol_for_testing(burn, "validator-a", validators["validator-a"]),
        verifier.sign_protocol_for_testing(burn, "validator-b", validators["validator-b"]),
    ]
    verified = verifier.verify(burn, validator_approvals=approvals)
    assert verified.approved_validator_ids == ("validator-a", "validator-b")


def test_protocol_reserve_burn_rejects_insufficient_or_duplicate_approvals():
    _, validators, verifier = service()
    burn = claim("protocol_reserve", "amm:reserve")
    approval = verifier.sign_protocol_for_testing(burn, "validator-a", validators["validator-a"])
    with pytest.raises(BurnAuthorizationError, match="threshold"):
        verifier.verify(burn, validator_approvals=[approval])
    with pytest.raises(BurnAuthorizationError, match="duplicate"):
        verifier.verify(burn, validator_approvals=[approval, approval])


def test_burn_scope_and_expiry_are_bound_to_signature():
    holders, _, verifier = service()
    original = claim()
    signature = verifier.sign_holder_for_testing(original, holders["alice"])
    changed = claim("protocol_reserve", "alice")
    with pytest.raises(BurnAuthorizationError, match="protocol reserve"):
        verifier.verify(changed, holder_signature=signature)
    expired = claim(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    with pytest.raises(BurnAuthorizationError, match="expired"):
        verifier.verify(expired, holder_signature=verifier.sign_holder_for_testing(expired, holders["alice"]))


def test_burn_amount_limit_and_protocol_scope_account_are_enforced():
    _, _, verifier = service()
    with pytest.raises(BurnAuthorizationError, match="maximum"):
        verifier.verify(claim(amount=1001), holder_signature="x")
