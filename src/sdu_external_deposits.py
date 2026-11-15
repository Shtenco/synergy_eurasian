"""Quorum verification for external-asset deposit attestations.

This module does not connect to a blockchain node and does not independently
prove chain inclusion. It verifies that a configured quorum of independent
deposit verifiers attested to the exact chain transaction, asset, amount,
destination and confirmation count. Production must use independent chain
clients/light clients or audited bridge attestations, asymmetric signatures,
and a replay-protected chain registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Mapping

from sdu_issuance_authorization import ValidatorApproval


class ExternalDepositError(Exception):
    pass


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ExternalDepositClaim:
    deposit_id: str
    chain_id: str
    transaction_hash: str
    asset: str
    amount: int
    destination_account: str
    block_number: int
    confirmations: int
    proof_digest: str
    expires_at: str
    transfer_index: int = 0

    def canonical_payload(self) -> bytes:
        for name, value in (
            ("deposit_id", self.deposit_id),
            ("chain_id", self.chain_id),
            ("destination_account", self.destination_account),
        ):
            if not value or value.strip() != value:
                raise ExternalDepositError(f"{name} is required and must be trimmed")
        if not _HEX_64.fullmatch(self.transaction_hash):
            raise ExternalDepositError("transaction_hash must be lowercase 32-byte hex")
        if not _HEX_64.fullmatch(self.proof_digest):
            raise ExternalDepositError("proof_digest must be lowercase SHA-256 hex")
        if not self.asset or self.asset.strip() != self.asset:
            raise ExternalDepositError("asset is required")
        if isinstance(self.amount, bool) or not isinstance(self.amount, int) or self.amount <= 0:
            raise ExternalDepositError("deposit amount must be a positive integer")
        if isinstance(self.block_number, bool) or not isinstance(self.block_number, int) or self.block_number < 0:
            raise ExternalDepositError("block_number must be a non-negative integer")
        if isinstance(self.confirmations, bool) or not isinstance(self.confirmations, int) or self.confirmations < 0:
            raise ExternalDepositError("confirmations must be a non-negative integer")
        if isinstance(self.transfer_index, bool) or not isinstance(self.transfer_index, int) or self.transfer_index < 0:
            raise ExternalDepositError("transfer_index must be a non-negative integer")
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ExternalDepositError("expires_at must be ISO-8601") from exc
        if expiry.tzinfo is None:
            raise ExternalDepositError("expires_at must include timezone")
        payload = {
            "amount": self.amount,
            "asset": self.asset,
            "block_number": self.block_number,
            "chain_id": self.chain_id,
            "confirmations": self.confirmations,
            "deposit_id": self.deposit_id,
            "destination_account": self.destination_account,
            "expires_at": expiry.astimezone(timezone.utc).isoformat(),
            "proof_digest": self.proof_digest,
            "transaction_hash": self.transaction_hash,
            "transfer_index": self.transfer_index,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class VerifiedExternalDeposit:
    claim: ExternalDepositClaim
    claim_digest: str
    approved_verifier_ids: tuple[str, ...]


class ExternalDepositVerifier:
    def __init__(
        self,
        verifier_keys: Mapping[str, bytes],
        *,
        threshold: int,
        supported_chains: set[str],
        supported_assets: set[str],
        minimum_confirmations: Mapping[str, int],
        maximum_amounts: Mapping[str, int],
    ) -> None:
        if isinstance(threshold, bool) or not isinstance(threshold, int):
            raise ExternalDepositError("threshold must be an integer")
        if threshold < 1 or threshold > len(verifier_keys):
            raise ExternalDepositError("invalid external verifier threshold")
        for verifier_id, key in verifier_keys.items():
            if not verifier_id or not isinstance(key, bytes) or len(key) < 32:
                raise ExternalDepositError("verifier IDs and 32-byte keys are required")
        if not supported_chains or not supported_assets:
            raise ExternalDepositError("supported chain and asset allowlists are required")
        if any(not isinstance(chain, str) or not chain.strip() for chain in supported_chains):
            raise ExternalDepositError("supported chain IDs must be non-empty strings")
        if any(not isinstance(asset, str) or not asset.strip() for asset in supported_assets):
            raise ExternalDepositError("supported asset symbols must be non-empty strings")
        if not supported_chains.issubset(minimum_confirmations):
            raise ExternalDepositError("minimum confirmations must be configured for every supported chain")
        if not supported_assets.issubset(maximum_amounts):
            raise ExternalDepositError("maximum deposit amount must be configured for every supported asset")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in minimum_confirmations.values()
        ):
            raise ExternalDepositError("minimum confirmation counts must be non-negative integers")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in maximum_amounts.values()
        ):
            raise ExternalDepositError("maximum deposit amounts must be positive integers")
        self._keys = dict(verifier_keys)
        self.threshold = threshold
        self.supported_chains = set(supported_chains)
        self.supported_assets = set(supported_assets)
        self.minimum_confirmations = dict(minimum_confirmations)
        self.maximum_amounts = dict(maximum_amounts)

    @staticmethod
    def sign_for_testing(
        claim: ExternalDepositClaim, verifier_id: str, secret: bytes
    ) -> ValidatorApproval:
        message = b"SYNERGY_EXTERNAL_DEPOSIT_V1\\x00" + claim.canonical_payload()
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return ValidatorApproval(verifier_id, signature)

    def verify(
        self,
        claim: ExternalDepositClaim,
        attestations: tuple[ValidatorApproval, ...] | list[ValidatorApproval],
        *,
        now: datetime | None = None,
    ) -> VerifiedExternalDeposit:
        payload = claim.canonical_payload()
        if claim.chain_id not in self.supported_chains:
            raise ExternalDepositError("unsupported external chain")
        if claim.asset not in self.supported_assets:
            raise ExternalDepositError("unsupported external asset")
        if claim.confirmations < self.minimum_confirmations.get(claim.chain_id, 0):
            raise ExternalDepositError("deposit has insufficient confirmations")
        maximum = self.maximum_amounts.get(claim.asset)
        if maximum is None or claim.amount > maximum:
            raise ExternalDepositError("deposit exceeds configured asset limit")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ExternalDepositError("verification time must be timezone-aware")
        expiry = datetime.fromisoformat(claim.expires_at.replace("Z", "+00:00"))
        if expiry.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            raise ExternalDepositError("deposit attestation has expired")

        valid: set[str] = set()
        for attestation in attestations:
            if attestation.validator_id in valid:
                raise ExternalDepositError("duplicate external verifier attestation")
            secret = self._keys.get(attestation.validator_id)
            if secret is None:
                raise ExternalDepositError("unknown or inactive external verifier")
            message = b"SYNERGY_EXTERNAL_DEPOSIT_V1\\x00" + payload
            expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, attestation.signature_hex):
                raise ExternalDepositError("invalid external deposit attestation")
            valid.add(attestation.validator_id)
        if len(valid) < self.threshold:
            raise ExternalDepositError("external verifier threshold not met")
        return VerifiedExternalDeposit(
            claim, hashlib.sha256(payload).hexdigest(), tuple(sorted(valid))
        )
