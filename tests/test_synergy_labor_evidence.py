from datetime import datetime, timezone
import base64
import hashlib
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_evidence import (
    EvidenceVerificationError,
    canonical_evidence_payload,
    score_verified_contributions,
    verify_evidence_envelope,
)


NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
BLOB = b"independently verified production evidence"


def signed_fixture(*, role="INDEPENDENT_VERIFIER", revoked_at=None, expires_at="2027-01-01T00:00:00Z"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    blob = BLOB
    envelope = {
        "schema": "sle.evidence/v1",
        "evidence_id": "evidence-001",
        "subject_id": "person-pseudo-001",
        "signer_id": "verifier-001",
        "signer_role": role,
        "content_sha256": hashlib.sha256(blob).hexdigest(),
        "issued_at": "2026-11-13T00:00:00Z",
        "expires_at": expires_at,
        "key_id": "key-001",
    }
    envelope["signature"] = base64.b64encode(
        private.sign(canonical_evidence_payload(envelope))
    ).decode("ascii")
    registry = {
        "key-001": {
            "principal_id": "verifier-001",
            "roles": ["INDEPENDENT_VERIFIER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": revoked_at,
        }
    }
    return envelope, blob, registry


def test_valid_ed25519_evidence_envelope_verifies_content_and_signer():
    envelope, blob, registry = signed_fixture()
    result = verify_evidence_envelope(envelope, blob, registry, now=NOW)
    assert result["verified"] is True
    assert result["signer_id"] == "verifier-001"
    assert result["verification_method"] == "ED25519_CONTENT_HASH_AND_KEY_REGISTRY"


def test_modified_envelope_fails_signature_verification():
    envelope, blob, registry = signed_fixture()
    envelope["subject_id"] = "attacker"
    with pytest.raises(EvidenceVerificationError, match="signature verification failed"):
        verify_evidence_envelope(envelope, blob, registry, now=NOW)


def test_modified_evidence_bytes_fail_content_hash_check():
    envelope, blob, registry = signed_fixture()
    with pytest.raises(EvidenceVerificationError, match="content SHA-256 mismatch"):
        verify_evidence_envelope(envelope, blob + b"tampered", registry, now=NOW)


def test_revoked_key_is_rejected():
    envelope, blob, registry = signed_fixture(revoked_at="2026-11-10T00:00:00Z")
    with pytest.raises(EvidenceVerificationError, match="revoked"):
        verify_evidence_envelope(envelope, blob, registry, now=NOW)


def test_expired_evidence_envelope_is_rejected():
    envelope, blob, registry = signed_fixture(expires_at="2026-11-14T11:59:59Z")
    with pytest.raises(EvidenceVerificationError, match="expired"):
        verify_evidence_envelope(envelope, blob, registry, now=NOW)


def test_wrong_signer_role_is_rejected():
    envelope, blob, registry = signed_fixture(role="CONTRIBUTOR")
    with pytest.raises(EvidenceVerificationError, match="role"):
        verify_evidence_envelope(envelope, blob, registry, now=NOW)


def test_key_principal_must_match_envelope_signer():
    envelope, blob, registry = signed_fixture()
    registry["key-001"]["principal_id"] = "someone-else"
    with pytest.raises(EvidenceVerificationError, match="does not match"):
        verify_evidence_envelope(envelope, blob, registry, now=NOW)


def contribution_record(digest):
    return {
        "schema_version": "1.0",
        "contribution_id": "contrib-001",
        "contributor_id": "person-pseudo-001",
        "contributor_kind": "HUMAN",
        "project_id": "project-001",
        "benefit_stream_id": "benefit-001",
        "result_digest": "d" * 64,
        "category": "TECHNICAL",
        "status": "ACCEPTED",
        "effort_units": 10,
        "effort_unit": "verified_work_package_unit",
        "complexity_factor": 1,
        "quality_factor": 1,
        "outcome_factor": 1,
        "reliability_factor": 1,
        "attribution_share": 1,
        "evidence": [{
            "evidence_id": "evidence-001",
            "sha256": digest,
            "source": "independent-review",
            "independent": True,
        }],
        "verification": {
            "verifier_id": "verifier-001",
            "independent_from_contributor": True,
            "conflict_disclosed": True,
            "signature_reference": "sig-ref-001",
        },
    }


def test_verified_scoring_requires_and_records_cryptographic_proof():
    envelope, blob, registry = signed_fixture()
    record = contribution_record(hashlib.sha256(blob).hexdigest())
    result = score_verified_contributions(
        [record], {"evidence-001": envelope}, {"evidence-001": blob}, registry, now=NOW
    )
    assert result["verification_scope"] == "CRYPTOGRAPHICALLY_VERIFIED_ED25519"
    assert result["total_labor_score"] == "10"
    assert len(result["verified_evidence"]) == 1


def test_verified_scoring_rejects_missing_evidence_material():
    envelope, blob, registry = signed_fixture()
    record = contribution_record(hashlib.sha256(blob).hexdigest())
    with pytest.raises(EvidenceVerificationError, match="missing"):
        score_verified_contributions([record], {}, {}, registry, now=NOW)


def test_shared_evidence_can_support_joint_contributions_in_same_benefit_stream():
    envelope, blob, registry = signed_fixture()
    digest = hashlib.sha256(blob).hexdigest()
    first = contribution_record(digest)
    second = contribution_record(digest)
    second["contribution_id"] = "contrib-002"
    second["contributor_id"] = "person-pseudo-002"
    second["attribution_share"] = 0
    result = score_verified_contributions(
        [first, second], {"evidence-001": envelope}, {"evidence-001": blob}, registry, now=NOW
    )
    assert len(result["verified_evidence"]) == 1


def test_evidence_reuse_across_different_benefit_streams_is_rejected():
    envelope, blob, registry = signed_fixture()
    digest = hashlib.sha256(blob).hexdigest()
    first = contribution_record(digest)
    second = contribution_record(digest)
    second["contribution_id"] = "contrib-002"
    second["benefit_stream_id"] = "benefit-002"
    second["attribution_share"] = 0
    with pytest.raises(EvidenceVerificationError, match="different benefit streams"):
        score_verified_contributions(
            [first, second], {"evidence-001": envelope}, {"evidence-001": blob}, registry, now=NOW
        )


def test_signed_evidence_envelope_matches_strict_json_schema():
    import json
    import jsonschema

    envelope, blob, registry = signed_fixture()
    schema = json.loads((ROOT / "interfaces" / "sle_evidence_envelope.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=envelope, schema=schema)


def test_verified_scoring_binds_evidence_subject_to_contributor():
    envelope, blob, registry = signed_fixture()
    envelope["subject_id"] = "different-person"
    envelope["signature"] = base64.b64encode(
        Ed25519PrivateKey.generate().sign(canonical_evidence_payload(envelope))
    ).decode("ascii")
    record = contribution_record(hashlib.sha256(blob).hexdigest())
    with pytest.raises(EvidenceVerificationError, match="subject_id"):
        score_verified_contributions(
            [record], {"evidence-001": envelope}, {"evidence-001": blob}, registry, now=NOW
        )
