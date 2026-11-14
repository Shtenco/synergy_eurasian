from datetime import datetime, timezone
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_award_authorization import (
    AwardAuthorizationError,
    canonical_award_authorization_payload,
    verify_award_authorization,
)

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def fixture(*, revoked_at=None, expires_at="2027-01-01T00:00:00Z"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    envelope = {
        "schema": "sle.award-authorization/v1",
        "award_id": "award-001",
        "source_contribution_id": "contribution-001",
        "result_digest": hashlib.sha256(b"accepted result").hexdigest(),
        "beneficiary_id": "beneficiary-001",
        "issuer_id": "issuer-001",
        "service_code": "COMPUTE_SUPPORT",
        "unit": "verified_hour",
        "quantity": "12.500",
        "capacity_id": "capacity-001",
        "policy_version": "SLE-REWARD-POLICY-1",
        "budget_ref": "budget-approval-001",
        "issued_at": "2026-11-13T00:00:00Z",
        "expires_at": expires_at,
        "signer_id": "reward-officer-001",
        "signer_role": "REWARD_AUTHORIZER",
        "key_id": "reward-key-001",
    }
    envelope["signature"] = base64.b64encode(
        private.sign(canonical_award_authorization_payload(envelope))
    ).decode("ascii")
    registry = {
        "reward-key-001": {
            "principal_id": "reward-officer-001",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": revoked_at,
        }
    }
    return envelope, registry


def test_valid_authorization_verifies_all_terms_without_issuing_credit_or_money():
    envelope, registry = fixture()
    result = verify_award_authorization(envelope, registry, now=NOW)
    assert result["verified"] is True
    assert result["award_id"] == "award-001"
    assert result["quantity"] == "12.5"
    assert result["signer_role"] == "REWARD_AUTHORIZER"
    assert result["global_uniqueness_enforced"] is False
    assert result["credit_issued"] is False
    assert result["money_issued"] is False


@pytest.mark.parametrize("field,value", [
    ("beneficiary_id", "attacker"),
    ("quantity", "999"),
    ("capacity_id", "other-capacity"),
    ("budget_ref", "other-budget"),
    ("result_digest", "0" * 64),
])
def test_any_changed_economic_term_invalidates_signature(field, value):
    envelope, registry = fixture()
    envelope[field] = value
    with pytest.raises(AwardAuthorizationError, match="signature verification failed"):
        verify_award_authorization(envelope, registry, now=NOW)


def test_wrong_signer_role_is_rejected_even_if_envelope_is_resigned():
    envelope, registry = fixture()
    envelope["signer_role"] = "INDEPENDENT_VERIFIER"
    with pytest.raises(AwardAuthorizationError, match="signer_role"):
        verify_award_authorization(envelope, registry, now=NOW)


def test_registry_must_bind_signer_identity_and_role():
    envelope, registry = fixture()
    registry["reward-key-001"]["principal_id"] = "different-principal"
    with pytest.raises(AwardAuthorizationError, match="principal"):
        verify_award_authorization(envelope, registry, now=NOW)


def test_revoked_key_is_rejected():
    envelope, registry = fixture(revoked_at="2026-11-10T00:00:00Z")
    with pytest.raises(AwardAuthorizationError, match="revoked"):
        verify_award_authorization(envelope, registry, now=NOW)


def test_expired_envelope_is_rejected():
    envelope, registry = fixture(expires_at="2026-11-14T11:59:59Z")
    with pytest.raises(AwardAuthorizationError, match="validity interval"):
        verify_award_authorization(envelope, registry, now=NOW)


@pytest.mark.parametrize("quantity", ["0", "-1", "NaN", "Infinity", "1e9", 5])
def test_quantity_must_be_positive_finite_decimal_string(quantity):
    envelope, registry = fixture()
    envelope["quantity"] = quantity
    with pytest.raises(AwardAuthorizationError):
        verify_award_authorization(envelope, registry, now=NOW)


def test_unknown_or_missing_fields_are_rejected():
    envelope, registry = fixture()
    envelope["untrusted_override"] = True
    with pytest.raises(AwardAuthorizationError, match="fields mismatch"):
        verify_award_authorization(envelope, registry, now=NOW)


def test_award_schema_is_strict_and_matches_signed_envelope():
    import jsonschema

    envelope, _ = fixture()
    schema = json.loads(
        (ROOT / "interfaces" / "sle_award_authorization.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=envelope, schema=schema)


@pytest.mark.parametrize("quantity", [".5", "01", "1e2", " 2 ", "+2", "2."])
def test_quantity_syntax_matches_json_schema_exactly(quantity):
    envelope, registry = fixture()
    envelope["quantity"] = quantity
    with pytest.raises(AwardAuthorizationError, match="schema"):
        verify_award_authorization(envelope, registry, now=NOW)
