"""Signed, externally anchorable SDU ledger checkpoints.

This module uses HMAC-SHA256 for a dependency-free prototype. The checkpoint
key must be held outside the database and outside the application database
administrator's trust boundary. HMAC does not provide public verifiability;
production should use an asymmetric signing key and publish checkpoints to an
independent append-only store.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json


class CheckpointError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LedgerCheckpoint:
    sequence: int
    event_hash: str
    created_at: str
    digest: str
    signature: str
    algorithm: str = "HMAC-SHA256"

    def payload(self) -> bytes:
        return canonical_checkpoint_payload(self.sequence, self.event_hash, self.created_at)


def canonical_checkpoint_payload(sequence: int, event_hash: str, created_at: str) -> bytes:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise CheckpointError("checkpoint sequence must be a non-negative integer")
    if len(event_hash) != 64 or any(c not in "0123456789abcdef" for c in event_hash):
        raise CheckpointError("event_hash must be lowercase SHA-256 hex")
    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise CheckpointError("created_at must be ISO-8601") from exc
    if timestamp.tzinfo is None:
        raise CheckpointError("created_at must include timezone")
    normalized = {
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
        "event_hash": event_hash,
        "sequence": sequence,
    }
    return json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_checkpoint(
    sequence: int,
    event_hash: str,
    signing_key: bytes,
    *,
    created_at: datetime | None = None,
) -> LedgerCheckpoint:
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise CheckpointError("checkpoint HMAC key must contain at least 32 bytes")
    timestamp = (created_at or datetime.now(timezone.utc))
    if timestamp.tzinfo is None:
        raise CheckpointError("created_at must include timezone")
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
    payload = canonical_checkpoint_payload(sequence, event_hash, timestamp_text)
    digest = hashlib.sha256(payload).hexdigest()
    signature = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    return LedgerCheckpoint(sequence, event_hash, timestamp_text, digest, signature)


def verify_checkpoint(checkpoint: LedgerCheckpoint, verification_key: bytes) -> bool:
    if not isinstance(verification_key, bytes) or len(verification_key) < 32:
        raise CheckpointError("checkpoint verification key must contain at least 32 bytes")
    payload = checkpoint.payload()
    expected_digest = hashlib.sha256(payload).hexdigest()
    expected_signature = hmac.new(verification_key, payload, hashlib.sha256).hexdigest()
    return (
        checkpoint.algorithm == "HMAC-SHA256"
        and hmac.compare_digest(expected_digest, checkpoint.digest)
        and hmac.compare_digest(expected_signature, checkpoint.signature)
    )


def verify_checkpoint_progression(
    previous: LedgerCheckpoint | None,
    current: LedgerCheckpoint,
    verification_key: bytes,
) -> bool:
    if not verify_checkpoint(current, verification_key):
        return False
    if previous is None:
        return True
    if not verify_checkpoint(previous, verification_key):
        return False
    if current.sequence <= previous.sequence:
        return False
    # A later checkpoint's event hash is not cryptographically derivable from
    # the previous event hash alone; the ledger audit must verify the intervening
    # chain. This function checks monotonic sequence and both signatures only.
    return True
