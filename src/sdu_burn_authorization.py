"""Authorization for voluntary holder burns and explicit protocol-reserve burns.

Research implementation uses HMAC-SHA256. Holder and validator secrets must
remain in separate custody domains. Replace HMAC with asymmetric signatures
and a hardware-backed identity/key registry before production.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Mapping

from sdu_issuance_authorization import ValidatorApproval


class BurnAuthorizationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BurnClaim:
    burn_id: str
    source_account: str
    amount: int
    burn_scope: str
    actor_id: str
    expires_at: str
    purpose: str

    def canonical_payload(self) -> bytes:
        if not self.burn_id or not self.burn_id.strip():
            raise BurnAuthorizationError("burn_id is required")
        if not self.source_account or not self.source_account.strip():
            raise BurnAuthorizationError("source_account is required")
        if isinstance(self.amount, bool) or not isinstance(self.amount, int) or self.amount <= 0:
            raise BurnAuthorizationError("burn amount must be a positive integer")
        if self.burn_scope not in {"holder", "protocol_reserve"}:
            raise BurnAuthorizationError("burn_scope must be holder or protocol_reserve")
        if not self.actor_id or not self.actor_id.strip():
            raise BurnAuthorizationError("actor_id is required")
        if not self.purpose or not self.purpose.strip():
            raise BurnAuthorizationError("burn purpose is required")
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise BurnAuthorizationError("expires_at must be ISO-8601") from exc
        if expiry.tzinfo is None:
            raise BurnAuthorizationError("expires_at must include timezone")
        value = {
            "actor_id": self.actor_id,
            "amount": self.amount,
            "burn_id": self.burn_id,
            "burn_scope": self.burn_scope,
            "expires_at": expiry.astimezone(timezone.utc).isoformat(),
            "purpose": self.purpose,
            "source_account": self.source_account,
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class VerifiedBurn:
    claim: BurnClaim
    claim_digest: str
    approved_validator_ids: tuple[str, ...]


class BurnAuthorizationService:
    def __init__(
        self,
        holder_keys: Mapping[str, bytes],
        validator_keys: Mapping[str, bytes],
        *,
        protocol_threshold: int,
        max_burn_amount: int,
    ) -> None:
        if isinstance(protocol_threshold, bool) or not isinstance(protocol_threshold, int):
            raise BurnAuthorizationError("protocol_threshold must be an integer")
        if protocol_threshold < 1 or protocol_threshold > len(validator_keys):
            raise BurnAuthorizationError("invalid protocol validator threshold")
        if isinstance(max_burn_amount, bool) or not isinstance(max_burn_amount, int) or max_burn_amount <= 0:
            raise BurnAuthorizationError("max_burn_amount must be positive")
        for account, key in holder_keys.items():
            if not account or not isinstance(key, bytes) or len(key) < 32:
                raise BurnAuthorizationError("holder keys need account IDs and at least 32 bytes")
        for validator, key in validator_keys.items():
            if not validator or not isinstance(key, bytes) or len(key) < 32:
                raise BurnAuthorizationError("validator keys need IDs and at least 32 bytes")
        self._holder_keys = dict(holder_keys)
        self._validator_keys = dict(validator_keys)
        self.protocol_threshold = protocol_threshold
        self.max_burn_amount = max_burn_amount

    @staticmethod
    def sign_holder_for_testing(claim: BurnClaim, secret: bytes) -> str:
        message = b"SYNERGY_SDU_HOLDER_BURN_V1\\x00" + claim.canonical_payload()
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    @staticmethod
    def sign_protocol_for_testing(
        claim: BurnClaim, validator_id: str, secret: bytes
    ) -> ValidatorApproval:
        message = b"SYNERGY_SDU_PROTOCOL_BURN_V1\\x00" + claim.canonical_payload()
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return ValidatorApproval(validator_id, signature)

    def verify(
        self,
        claim: BurnClaim,
        *,
        holder_signature: str | None = None,
        validator_approvals: tuple[ValidatorApproval, ...] | list[ValidatorApproval] = (),
        now: datetime | None = None,
    ) -> VerifiedBurn:
        payload = claim.canonical_payload()
        if claim.amount > self.max_burn_amount:
            raise BurnAuthorizationError("burn exceeds configured per-command maximum")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise BurnAuthorizationError("verification time must be timezone-aware")
        expiry = datetime.fromisoformat(claim.expires_at.replace("Z", "+00:00"))
        if expiry.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            raise BurnAuthorizationError("burn claim has expired")

        approved: tuple[str, ...]
        if claim.burn_scope == "holder":
            secret = self._holder_keys.get(claim.source_account)
            if secret is None or not holder_signature:
                raise BurnAuthorizationError("holder signature is required for this source account")
            message = b"SYNERGY_SDU_HOLDER_BURN_V1\\x00" + payload
            expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, holder_signature):
                raise BurnAuthorizationError("invalid holder burn signature")
            if validator_approvals:
                raise BurnAuthorizationError("holder burn must not consume protocol validator approvals")
            approved = ()
        else:
            if holder_signature is not None:
                raise BurnAuthorizationError("protocol reserve burn uses validator threshold, not holder signature")
            valid: set[str] = set()
            for approval in validator_approvals:
                if approval.validator_id in valid:
                    raise BurnAuthorizationError("duplicate protocol validator approval")
                secret = self._validator_keys.get(approval.validator_id)
                if secret is None:
                    raise BurnAuthorizationError("unknown or inactive protocol validator")
                message = b"SYNERGY_SDU_PROTOCOL_BURN_V1\\x00" + payload
                expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, approval.signature_hex):
                    raise BurnAuthorizationError("invalid protocol burn validator signature")
                valid.add(approval.validator_id)
            if len(valid) < self.protocol_threshold:
                raise BurnAuthorizationError("protocol reserve burn threshold not met")
            approved = tuple(sorted(valid))

        return VerifiedBurn(
            claim=claim,
            claim_digest=hashlib.sha256(payload).hexdigest(),
            approved_validator_ids=approved,
        )
