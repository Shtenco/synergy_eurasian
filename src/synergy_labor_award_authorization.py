"""Signed, non-monetary SLE award authorization envelopes.

This verifies an issuer-side authorization; it does not reserve a global award ID,
issue service credits, mint currency, or authorize Financial OS accounting/payment.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "sle.award-authorization/v1"
POLICY_VERSION = "SLE-AWARD-AUTH-ED25519-1.0"
DOMAIN = b"SYNERGY_SLE_AWARD_AUTHORIZATION_V1\x00"
FIELDS = frozenset({
    "schema", "award_id", "source_contribution_id", "result_digest",
    "beneficiary_id", "issuer_id", "service_code", "unit", "quantity",
    "capacity_id", "policy_version", "budget_ref", "issued_at", "expires_at",
    "signer_id", "signer_role", "key_id", "signature",
})


class AwardAuthorizationError(ValueError):
    """Award authorization envelope, registry, or signature is invalid."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AwardAuthorizationError(f"{field} is required")
    result = value.strip()
    if len(result) > 256:
        raise AwardAuthorizationError(f"{field} exceeds 256 characters")
    return result


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AwardAuthorizationError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AwardAuthorizationError(f"{field} must be ISO-8601 date-time") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AwardAuthorizationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def canonical_award_authorization_payload(envelope: Mapping[str, Any]) -> bytes:
    if not isinstance(envelope, Mapping):
        raise AwardAuthorizationError("envelope must be an object")
    body = dict(envelope)
    body.pop("signature", None)
    try:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise AwardAuthorizationError("envelope is not canonical-JSON compatible") from None
    return DOMAIN + encoded


def verify_award_authorization(
    envelope: Mapping[str, Any],
    key_registry: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Verify exact award terms and a currently authorized Ed25519 signer."""
    if not isinstance(envelope, Mapping) or set(envelope) != FIELDS:
        missing = sorted(FIELDS - set(envelope)) if isinstance(envelope, Mapping) else sorted(FIELDS)
        extra = sorted(set(envelope) - FIELDS) if isinstance(envelope, Mapping) else []
        raise AwardAuthorizationError(f"envelope fields mismatch; missing={missing}, extra={extra}")
    if envelope["schema"] != SCHEMA:
        raise AwardAuthorizationError("unsupported award authorization schema")
    if not isinstance(key_registry, Mapping):
        raise AwardAuthorizationError("key_registry must be an object")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise AwardAuthorizationError("now must be a timezone-aware datetime")
    instant = now.astimezone(timezone.utc)

    values = {field: _text(envelope[field], field) for field in (
        "award_id", "source_contribution_id", "beneficiary_id", "issuer_id",
        "service_code", "unit", "capacity_id", "policy_version", "budget_ref",
        "signer_id", "signer_role", "key_id", "signature",
    )}
    digest = values["result_digest"] if "result_digest" in values else _text(envelope["result_digest"], "result_digest")
    if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise AwardAuthorizationError("result_digest must be a SHA-256 hex digest")
    role = values["signer_role"].upper()
    if role != "REWARD_AUTHORIZER":
        raise AwardAuthorizationError("signer_role must be REWARD_AUTHORIZER")
    if values["policy_version"] == "":
        raise AwardAuthorizationError("policy_version is required")

    try:
        quantity = Decimal(_text(envelope["quantity"], "quantity"))
    except (InvalidOperation, ValueError):
        raise AwardAuthorizationError("quantity must be a finite positive decimal string") from None
    if not quantity.is_finite() or quantity <= 0:
        raise AwardAuthorizationError("quantity must be a finite positive decimal string")
    if not isinstance(envelope["quantity"], str):
        raise AwardAuthorizationError("quantity must be encoded as a decimal string")

    issued = _timestamp(envelope["issued_at"], "issued_at")
    expires = _timestamp(envelope["expires_at"], "expires_at")
    if expires <= issued or issued > instant or instant >= expires:
        raise AwardAuthorizationError("award authorization is outside its validity interval")

    record = key_registry.get(values["key_id"])
    if not isinstance(record, Mapping):
        raise AwardAuthorizationError("authorization key is not in trusted registry")
    if _text(record.get("principal_id"), "key_registry.principal_id") != values["signer_id"]:
        raise AwardAuthorizationError("signer_id does not match registered key principal")
    roles = record.get("roles")
    if not isinstance(roles, (list, tuple, set, frozenset)) or role not in {str(x).upper() for x in roles}:
        raise AwardAuthorizationError("registered key lacks REWARD_AUTHORIZER role")
    valid_from = _timestamp(record.get("valid_from"), "key_registry.valid_from")
    valid_until = _timestamp(record.get("valid_until"), "key_registry.valid_until")
    if valid_until <= valid_from or not (valid_from <= instant < valid_until):
        raise AwardAuthorizationError("authorization key is outside its validity interval")
    if issued < valid_from or expires > valid_until:
        raise AwardAuthorizationError("award validity exceeds authorization key validity")
    revoked_at = record.get("revoked_at")
    if revoked_at is not None and instant >= _timestamp(revoked_at, "key_registry.revoked_at"):
        raise AwardAuthorizationError("authorization key is revoked")

    try:
        public_raw = base64.b64decode(_text(record.get("public_key_b64"), "public_key_b64"), validate=True)
        signature = base64.b64decode(values["signature"], validate=True)
    except (binascii.Error, ValueError):
        raise AwardAuthorizationError("public key or signature is invalid base64") from None
    if len(public_raw) != 32 or len(signature) != 64:
        raise AwardAuthorizationError("invalid Ed25519 public key or signature length")
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(
            signature, canonical_award_authorization_payload(envelope)
        )
    except (InvalidSignature, ValueError):
        raise AwardAuthorizationError("Ed25519 award authorization signature verification failed") from None

    return {
        "verified": True,
        "schema": SCHEMA,
        "award_id": values["award_id"],
        "source_contribution_id": values["source_contribution_id"],
        "result_digest": digest.lower(),
        "beneficiary_id": values["beneficiary_id"],
        "issuer_id": values["issuer_id"],
        "service_code": values["service_code"],
        "unit": values["unit"],
        "quantity": format(quantity.normalize(), "f"),
        "capacity_id": values["capacity_id"],
        "policy_version": values["policy_version"],
        "budget_ref": values["budget_ref"],
        "signer_id": values["signer_id"],
        "signer_role": role,
        "key_id": values["key_id"],
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "authorization_digest": hashlib.sha256(canonical_award_authorization_payload(envelope)).hexdigest(),
        "verification_policy_version": POLICY_VERSION,
        "global_uniqueness_enforced": False,
        "credit_issued": False,
        "money_issued": False,
    }
