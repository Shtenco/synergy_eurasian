"""Threshold authorization for SDU issuance claims.

The implementation uses HMAC-SHA256 as a dependency-free research mechanism.
HMAC is symmetric: validator secrets must never be exposed to the API or DAO.
For production, replace this verifier with asymmetric signatures (for example
Ed25519), hardware-backed key custody, validator revocation and audited key
rotation. A valid authorization proves approval under this configured policy;
it does not prove the economic truth of the attached evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Mapping


class AuthorizationError(Exception):
    """An issuance claim or its validator approvals are invalid."""


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IssuanceClaim:
    claim_id: str
    epoch_id: str
    destination_account: str
    amount: int
    evidence_digest: str
    purpose: str
    expires_at: str

    def canonical_payload(self) -> bytes:
        if not self.claim_id or not self.claim_id.strip():
            raise AuthorizationError("claim_id is required")
        if not self.epoch_id or not self.epoch_id.strip():
            raise AuthorizationError("epoch_id is required")
        if not self.destination_account or not self.destination_account.strip():
            raise AuthorizationError("destination_account is required")
        if isinstance(self.amount, bool) or not isinstance(self.amount, int) or self.amount <= 0:
            raise AuthorizationError("issuance amount must be a positive integer")
        if not _HEX_64.fullmatch(self.evidence_digest):
            raise AuthorizationError("evidence_digest must be a lowercase SHA-256 hex digest")
        if not self.purpose or not self.purpose.strip():
            raise AuthorizationError("issuance purpose is required")
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise AuthorizationError("expires_at must be an ISO-8601 timestamp") from exc
        if expiry.tzinfo is None:
            raise AuthorizationError("expires_at must include a timezone")
        normalized = {
            "amount": self.amount,
            "claim_id": self.claim_id,
            "destination_account": self.destination_account,
            "epoch_id": self.epoch_id,
            "evidence_digest": self.evidence_digest,
            "expires_at": expiry.astimezone(timezone.utc).isoformat(),
            "purpose": self.purpose,
        }
        return json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def request_digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidatorApproval:
    validator_id: str
    signature_hex: str


@dataclass(frozen=True, slots=True)
class VerifiedIssuance:
    """Output of a successful verifier; the ledger still enforces epoch budget."""

    claim: IssuanceClaim
    request_digest: str
    approved_validator_ids: tuple[str, ...]
    policy_version: str


class IssuanceAuthorizationService:
    def __init__(
        self,
        validator_keys: Mapping[str, bytes],
        *,
        threshold: int,
        policy_version: str,
        max_claim_amount: int,
    ) -> None:
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
            raise AuthorizationError("threshold must be a positive integer")
        if not validator_keys or threshold > len(validator_keys):
            raise AuthorizationError("threshold exceeds configured validator set")
        if not policy_version or not policy_version.strip():
            raise AuthorizationError("policy_version is required")
        if isinstance(max_claim_amount, bool) or not isinstance(max_claim_amount, int) or max_claim_amount <= 0:
            raise AuthorizationError("max_claim_amount must be a positive integer")
        normalized: dict[str, bytes] = {}
        for validator_id, secret in validator_keys.items():
            if not validator_id or not validator_id.strip():
                raise AuthorizationError("validator_id must be non-empty")
            if not isinstance(secret, bytes) or len(secret) < 32:
                raise AuthorizationError("validator HMAC keys must contain at least 32 bytes")
            normalized[validator_id] = secret
        self._keys = normalized
        self.threshold = threshold
        self.policy_version = policy_version
        self.max_claim_amount = max_claim_amount

    @staticmethod
    def sign_for_testing(claim: IssuanceClaim, validator_id: str, secret: bytes) -> ValidatorApproval:
        """Convenience helper for fixtures/offline tooling; keep secrets offline."""
        message = b"SYNERGY_SDU_ISSUANCE_V1\\x00" + claim.canonical_payload()
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return ValidatorApproval(validator_id, signature)

    def verify(
        self,
        claim: IssuanceClaim,
        approvals: tuple[ValidatorApproval, ...] | list[ValidatorApproval],
        *,
        now: datetime | None = None,
    ) -> VerifiedIssuance:
        payload = claim.canonical_payload()
        if claim.amount > self.max_claim_amount:
            raise AuthorizationError("claim exceeds per-claim constitutional maximum")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise AuthorizationError("verification time must be timezone-aware")
        expiry = datetime.fromisoformat(claim.expires_at.replace("Z", "+00:00"))
        if expiry.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            raise AuthorizationError("issuance claim has expired")

        valid: set[str] = set()
        for approval in approvals:
            if approval.validator_id in valid:
                raise AuthorizationError("duplicate validator approval")
            secret = self._keys.get(approval.validator_id)
            if secret is None:
                raise AuthorizationError("approval from unknown or inactive validator")
            message = b"SYNERGY_SDU_ISSUANCE_V1\\x00" + payload
            expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, approval.signature_hex):
                raise AuthorizationError("invalid validator signature")
            valid.add(approval.validator_id)
        if len(valid) < self.threshold:
            raise AuthorizationError("validator approval threshold not met")
        return VerifiedIssuance(
            claim=claim,
            request_digest=claim.request_digest,
            approved_validator_ids=tuple(sorted(valid)),
            policy_version=self.policy_version,
        )
