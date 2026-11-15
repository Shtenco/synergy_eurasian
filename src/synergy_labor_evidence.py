"""Ed25519 verification for content-addressed SLE evidence envelopes.

Public keys are supplied by an external governed registry. This module never
stores private keys, fetches evidence, or authorizes accounting/payment actions.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "sle.evidence/v1"
VERIFICATION_POLICY_VERSION = "SLE-ED25519-1.0"
DOMAIN = b"SYNERGY_SLE_EVIDENCE_V1\x00"
HEX = frozenset("0123456789abcdef")


class EvidenceVerificationError(ValueError):
    """Evidence envelope, content, key or signature failed verification."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceVerificationError(f"{field} is required")
    return value.strip()


def _hex64(value: Any, field: str) -> str:
    result = _text(value, field).lower()
    if len(result) != 64 or any(char not in HEX for char in result):
        raise EvidenceVerificationError(f"{field} must be a 64-character SHA-256 digest")
    return result


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceVerificationError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceVerificationError(f"{field} must be ISO-8601 date-time") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceVerificationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceVerificationError("now must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def canonical_evidence_payload(envelope: Mapping[str, Any]) -> bytes:
    """Return the exact domain-separated bytes an evidence signer must sign."""
    if not isinstance(envelope, Mapping):
        raise EvidenceVerificationError("envelope must be an object")
    body = dict(envelope)
    body.pop("signature", None)
    try:
        encoded = json.dumps(
            body, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise EvidenceVerificationError("envelope is not canonical-JSON compatible") from None
    return DOMAIN + encoded


def verify_evidence_envelope(
    envelope: Mapping[str, Any],
    evidence_bytes: bytes,
    key_registry: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
    required_role: str = "INDEPENDENT_VERIFIER",
) -> dict[str, Any]:
    """Verify content hash, key validity, signer role and Ed25519 signature."""
    if not isinstance(envelope, Mapping):
        raise EvidenceVerificationError("envelope must be an object")
    if not isinstance(evidence_bytes, bytes):
        raise EvidenceVerificationError("evidence_bytes must be bytes")
    if not isinstance(key_registry, Mapping):
        raise EvidenceVerificationError("key_registry must be an object")

    required_fields = {
        "schema", "evidence_id", "subject_id", "signer_id", "signer_role",
        "content_sha256", "issued_at", "expires_at", "key_id", "signature",
    }
    if set(envelope) != required_fields:
        missing = sorted(required_fields - set(envelope))
        extra = sorted(set(envelope) - required_fields)
        raise EvidenceVerificationError(f"envelope fields mismatch; missing={missing}, extra={extra}")
    if envelope.get("schema") != SCHEMA:
        raise EvidenceVerificationError("unsupported evidence envelope schema")

    evidence_id = _text(envelope.get("evidence_id"), "evidence_id")
    subject_id = _text(envelope.get("subject_id"), "subject_id")
    signer_id = _text(envelope.get("signer_id"), "signer_id")
    signer_role = _text(envelope.get("signer_role"), "signer_role").upper()
    role = _text(required_role, "required_role").upper()
    if signer_role != role:
        raise EvidenceVerificationError("signer role does not satisfy required role")

    supplied_digest = _hex64(envelope.get("content_sha256"), "content_sha256")
    actual_digest = hashlib.sha256(evidence_bytes).hexdigest()
    if supplied_digest != actual_digest:
        raise EvidenceVerificationError("evidence content SHA-256 mismatch")

    issued_at = _utc(envelope.get("issued_at"), "issued_at")
    expires_at = _utc(envelope.get("expires_at"), "expires_at")
    instant = _now(now)
    if expires_at <= issued_at:
        raise EvidenceVerificationError("expires_at must be after issued_at")
    if issued_at > instant:
        raise EvidenceVerificationError("evidence envelope is not yet valid")
    if instant >= expires_at:
        raise EvidenceVerificationError("evidence envelope has expired")

    key_id = _text(envelope.get("key_id"), "key_id")
    key_record = key_registry.get(key_id)
    if not isinstance(key_record, Mapping):
        raise EvidenceVerificationError("signing key is not present in trusted registry")
    if _text(key_record.get("principal_id"), "key_registry.principal_id") != signer_id:
        raise EvidenceVerificationError("signer_id does not match registered key principal")
    roles = key_record.get("roles")
    if not isinstance(roles, (list, tuple, set, frozenset)) or role not in {str(x).upper() for x in roles}:
        raise EvidenceVerificationError("registered key is not authorized for required signer role")

    key_valid_from = _utc(key_record.get("valid_from"), "key_registry.valid_from")
    key_valid_until = _utc(key_record.get("valid_until"), "key_registry.valid_until")
    if key_valid_until <= key_valid_from or instant < key_valid_from or instant >= key_valid_until:
        raise EvidenceVerificationError("signing key is outside its validity interval")
    if issued_at < key_valid_from or issued_at >= key_valid_until or expires_at > key_valid_until:
        raise EvidenceVerificationError("evidence validity interval exceeds signing key validity")
    revoked_at = key_record.get("revoked_at")
    if revoked_at is not None:
        revoked_time = _utc(revoked_at, "key_registry.revoked_at")
        if instant >= revoked_time or issued_at >= revoked_time:
            raise EvidenceVerificationError("signing key is revoked")

    public_key_b64 = _text(key_record.get("public_key_b64"), "key_registry.public_key_b64")
    signature_b64 = _text(envelope.get("signature"), "signature")
    try:
        public_key_raw = base64.b64decode(public_key_b64, validate=True)
        signature = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError):
        raise EvidenceVerificationError("public key or signature is not valid base64") from None
    if len(public_key_raw) != 32:
        raise EvidenceVerificationError("Ed25519 public key must be exactly 32 bytes")
    if len(signature) != 64:
        raise EvidenceVerificationError("Ed25519 signature must be exactly 64 bytes")

    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
            signature, canonical_evidence_payload(envelope)
        )
    except (InvalidSignature, ValueError):
        raise EvidenceVerificationError("Ed25519 signature verification failed") from None

    return {
        "verified": True,
        "schema": SCHEMA,
        "evidence_id": evidence_id,
        "subject_id": subject_id,
        "signer_id": signer_id,
        "signer_role": signer_role,
        "key_id": key_id,
        "content_sha256": actual_digest,
        "signature_sha256": hashlib.sha256(signature).hexdigest(),
        "verified_at": instant.isoformat(),
        "verification_method": "ED25519_CONTENT_HASH_AND_KEY_REGISTRY",
        "verification_policy_version": VERIFICATION_POLICY_VERSION,
    }


def score_verified_contributions(
    records: list[dict[str, Any]],
    evidence_envelopes: Mapping[str, Mapping[str, Any]],
    evidence_blobs: Mapping[str, bytes],
    key_registry: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Verify every referenced evidence item before invoking the SLE scorer."""
    from synergy_labor_economy import score_contributions

    if not isinstance(records, list) or not records:
        raise EvidenceVerificationError("records must be a non-empty list")
    verified: dict[str, dict[str, Any]] = {}
    verified_streams: dict[str, tuple[str, str]] = {}

    for record in records:
        if not isinstance(record, dict):
            raise EvidenceVerificationError("each contribution must be an object")
        verification = record.get("verification")
        if not isinstance(verification, dict):
            raise EvidenceVerificationError("contribution verification metadata is required")
        declared_verifier = _text(verification.get("verifier_id"), "verification.verifier_id")
        evidence_items = record.get("evidence")
        if not isinstance(evidence_items, list) or not evidence_items:
            raise EvidenceVerificationError("contribution must reference evidence")
        independent_signer_found = False
        record_evidence_ids: set[str] = set()
        for item in evidence_items:
            if not isinstance(item, dict):
                raise EvidenceVerificationError("evidence item must be an object")
            evidence_id = _text(item.get("evidence_id"), "evidence.evidence_id")
            if evidence_id in record_evidence_ids:
                raise EvidenceVerificationError("duplicate evidence_id within one contribution")
            record_evidence_ids.add(evidence_id)
            envelope = evidence_envelopes.get(evidence_id)
            blob = evidence_blobs.get(evidence_id)
            if envelope is None or blob is None:
                raise EvidenceVerificationError(f"evidence material is missing for {evidence_id}")
            result = verify_evidence_envelope(envelope, blob, key_registry, now=now)
            if result["evidence_id"] != evidence_id:
                raise EvidenceVerificationError("envelope evidence_id does not match contribution reference")
            if result["subject_id"] != _text(record.get("benefit_stream_id"), "benefit_stream_id"):
                raise EvidenceVerificationError("evidence subject_id does not match contribution benefit_stream_id")
            if result["content_sha256"] != _hex64(item.get("sha256"), "evidence.sha256"):
                raise EvidenceVerificationError("envelope digest does not match contribution evidence digest")
            benefit_stream_id = _text(record.get("benefit_stream_id"), "benefit_stream_id")
            identity = (result["content_sha256"], benefit_stream_id)
            previous_identity = verified_streams.setdefault(evidence_id, identity)
            if previous_identity != identity:
                raise EvidenceVerificationError("one evidence_id cannot support different benefit streams")
            if item.get("independent") is True and result["signer_id"] == declared_verifier:
                independent_signer_found = True
            verified[evidence_id] = result

        if not independent_signer_found:
            raise EvidenceVerificationError(
                "each accepted contribution needs evidence signed by its declared independent verifier"
            )

    result = score_contributions(records)
    result["verification_scope"] = "CRYPTOGRAPHICALLY_VERIFIED_ED25519"
    result["verified_evidence"] = [verified[key] for key in sorted(verified)]
    return result
