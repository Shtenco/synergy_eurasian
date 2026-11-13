from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_award_authorization import canonical_award_authorization_payload
from synergy_labor_award_registry import (
    AwardRegistryError,
    SLEAwardRegistry,
    issue_authorized_credit,
)
from synergy_labor_credit_ledger import LaborCreditLedger


NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def setup(database=":memory:"):
    ledger = LaborCreditLedger()
    ledger.register_issuer("issuer-a", "field-service", "service-hour", "100", "issuer-policy")
    ledger.add_capacity("issuer-a", "field-service", "service-hour", "capacity-a",
                        "50", "a" * 64, "independent-verifier", "capacity-a")
    registry = SLEAwardRegistry(database)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys = {
        "reward-key-1": {
            "principal_id": "reward-authorizer-1",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
    }
    return ledger, registry, private, keys


def signed_award(private, *, award_id="award-global-1",
                 contribution_id="contribution-global-1",
                 result_digest=None, expires_at="2026-12-01T00:00:00Z",
                 beneficiary_id="worker-b"):
    envelope = {
        "schema": "sle.award-authorization/v1",
        "award_id": award_id,
        "source_contribution_id": contribution_id,
        "result_digest": result_digest or hashlib.sha256(b"verified labor result").hexdigest(),
        "beneficiary_id": beneficiary_id,
        "issuer_id": "issuer-a",
        "service_code": "field-service",
        "unit": "service-hour",
        "quantity": "5",
        "capacity_id": "capacity-a",
        "policy_version": "SLE-AWARD-AUTH-ED25519-1.0",
        "budget_ref": "budget-cycle-2026",
        "issued_at": "2026-11-13T18:00:00Z",
        "expires_at": expires_at,
        "signer_id": "reward-authorizer-1",
        "signer_role": "REWARD_AUTHORIZER",
        "key_id": "reward-key-1",
    }
    envelope["signature"] = base64.b64encode(
        private.sign(canonical_award_authorization_payload(envelope))
    ).decode("ascii")
    return envelope


def close_all(ledger, registry):
    ledger.close()
    registry.close()


def test_global_reservation_is_idempotent_and_blocks_same_contribution_under_new_award_id():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    first = registry.reserve(envelope, keys, now=NOW)
    replay = registry.reserve(envelope, keys, now=NOW)
    assert first["status"] == "RESERVED"
    assert replay["idempotent_replay"] is True
    competing = signed_award(
        private, award_id="award-global-2",
        contribution_id="contribution-global-1",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(competing, keys, now=NOW)
    same_result = signed_award(
        private, award_id="award-global-3",
        contribution_id="contribution-global-3",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(same_result, keys, now=NOW)
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_shared_database_enforces_uniqueness_across_registry_instances(tmp_path):
    path = tmp_path / "shared-awards.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    first = signed_award(private)
    second = signed_award(
        private, award_id="award-other",
        contribution_id="contribution-global-1",
    )
    registry_a.reserve(first, keys, now=NOW)
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry_b.reserve(second, keys, now=NOW)
    assert registry_a.verify_event_chain()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_authorized_credit_issue_reserves_then_consumes_global_award():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    result = issue_authorized_credit(
        ledger, registry, envelope, keys, now=NOW,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    assert result["status"] == "ACTIVE"
    assert result["registry_status"] == "CONSUMED"
    award = registry.get_award("award-global-1")
    assert award["credit_id"] == "credit-global-1"
    assert award["ledger_event_id"]
    assert award["ledger_event_hash"]
    assert registry.verify_event_chain()["valid"] is True
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["valid"] is True
    close_all(ledger, registry)


def test_issue_retry_is_idempotent_and_does_not_consume_award_twice():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    args = dict(now=NOW, due_at="2030-01-01T00:00:00Z",
                credit_id="credit-global-1", idempotency_key="issue-global-1")
    first = issue_authorized_credit(ledger, registry, envelope, keys, **args)
    second = issue_authorized_credit(ledger, registry, envelope, keys, **args)
    assert first["credit_id"] == second["credit_id"]
    assert second["registry_status"] == "CONSUMED"
    assert ledger.verify_event_chain()["events_checked"] == 3
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_crash_after_local_issue_is_reconciled_without_requiring_unexpired_authorization():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-before-crash",
    )
    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    recovered = issue_authorized_credit(
        ledger, registry, envelope, keys, now=after_expiry,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-before-crash",
    )
    assert recovered["reconciled_after_local_issue"] is True
    assert recovered["registry_status"] == "CONSUMED"
    assert ledger.verify_projection_consistency()["valid"] is True
    close_all(ledger, registry)


def test_reservation_is_not_released_or_reused_when_local_issue_never_happens():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    competing = signed_award(
        private, award_id="award-global-2",
        contribution_id="contribution-global-1",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(competing, keys, now=NOW)
    with pytest.raises(AwardRegistryError, match="outside its validity interval"):
        registry.reserve(envelope, keys, now=datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert registry.get_award("award-global-1")["status"] == "RESERVED"
    close_all(ledger, registry)


def test_registry_refuses_local_credit_with_mismatched_economic_terms():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "4", "2030-01-01T00:00:00Z", "credit-global-1", "wrong-units",
    )
    with pytest.raises(AwardRegistryError, match="issued_units"):
        registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    assert registry.get_award("award-global-1")["status"] == "RESERVED"
    close_all(ledger, registry)


def test_registry_projection_replay_detects_direct_record_tampering():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    registry._db.execute(
        "UPDATE awards SET status='CONSUMED' WHERE award_id='award-global-1'"
    )
    audit = registry.verify_projection_consistency()
    assert audit["valid"] is False
    assert "projection differs" in audit["issues"][0]
    with pytest.raises(AwardRegistryError, match="projection is inconsistent"):
        registry.reserve(signed_award(private), keys, now=NOW)
    close_all(ledger, registry)


def test_award_registry_record_matches_strict_schema():
    import jsonschema
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    record = registry.get_award("award-global-1")
    schema = json.loads(
        (ROOT / "interfaces" / "sle_award_registry_record.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(record, schema)
    close_all(ledger, registry)

def test_award_authorization_history_survives_later_key_revocation():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    keys["reward-key-1"]["revoked_at"] = "2026-11-15T00:00:00Z"
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is True
    assert audit["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_award_authorization_history_detects_trusted_key_mismatch():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    replacement = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys["reward-key-1"]["public_key_b64"] = base64.b64encode(replacement).decode("ascii")
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is False
    assert "Ed25519 award authorization signature verification failed" in audit["issues"][0]
    close_all(ledger, registry)


def test_consumption_fails_closed_if_registry_projection_was_tampered():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-global-1",
    )
    registry._db.execute(
        "UPDATE awards SET status='CONSUMED' WHERE award_id='award-global-1'"
    )
    with pytest.raises(AwardRegistryError, match="projection is inconsistent"):
        registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    close_all(ledger, registry)


def test_registry_reconciles_original_issue_after_credit_is_transferred():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-before-transfer",
    )
    ledger.transfer("credit-global-1", "worker-b", "worker-c", 0, "transfer-before-reconcile")
    consumed = registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    assert consumed["status"] == "CONSUMED"
    assert ledger.get_credit("credit-global-1")["holder_id"] == "worker-c"
    assert registry.verify_projection_consistency()["valid"] is True
    close_all(ledger, registry)


def test_completed_issue_retry_after_authorization_expiry_is_idempotent():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    args = dict(
        due_at="2030-01-01T00:00:00Z",
        credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    first = issue_authorized_credit(
        ledger, registry, envelope, keys, now=NOW, **args
    )
    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    replay = issue_authorized_credit(
        ledger, registry, envelope, keys, now=after_expiry, **args
    )
    assert first["registry_status"] == "CONSUMED"
    assert replay["registry_status"] == "CONSUMED"
    assert replay["idempotent_replay"] is True
    assert replay["reconciled_after_local_issue"] is False
    assert ledger.verify_event_chain()["events_checked"] == 3
    close_all(ledger, registry)


def test_recovery_rejects_different_signed_envelope_for_existing_award_id():
    ledger, registry, private, keys = setup()
    original = signed_award(private)
    issue_authorized_credit(
        ledger, registry, original, keys, now=NOW,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    substituted = signed_award(private, beneficiary_id="attacker")
    with pytest.raises(AwardRegistryError, match="does not match"):
        issue_authorized_credit(
            ledger, registry, substituted, keys, now=NOW,
            due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
            idempotency_key="issue-global-1",
        )
    assert registry.get_award("award-global-1")["status"] == "CONSUMED"
    close_all(ledger, registry)


def test_award_authorization_history_detects_revocation_before_reservation_time():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    keys["reward-key-1"]["revoked_at"] = "2026-11-14T11:00:00Z"
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is False
    assert "revoked" in audit["issues"][0]
    close_all(ledger, registry)

