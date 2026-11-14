"""Externally anchored Ed25519 checkpoints for SLE award-registry history.

The anchor store is deliberately injected: production deployments must implement it
using an independently administered durability/failure domain. The in-memory adapter
below exists only for deterministic tests and examples.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any, Mapping, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)


class CheckpointError(ValueError):
    """Invalid checkpoint, signature, or external anchor history."""


GENESIS_HASH = "0" * 64
SCHEMA = "sle.registry-checkpoint/v1"


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise CheckpointError("checkpoint is not canonical-JSON compatible") from None


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(dict(value))).hexdigest()


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise CheckpointError("checkpoint timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CheckpointError("checkpoint timestamp must be an ISO-8601 string") from None
    if parsed.tzinfo is None:
        raise CheckpointError("checkpoint timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _public_key(entry: Mapping[str, Any]) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(entry["public_key_b64"], validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (KeyError, TypeError, ValueError):
        raise CheckpointError("trusted checkpoint public key is malformed") from None


class CheckpointAnchorStore(Protocol):
    """Independent append-only store contract; deploy outside the registry trust domain."""

    def list_checkpoints(self, registry_id: str) -> Sequence[Mapping[str, Any]]: ...
    def append_checkpoint(self, checkpoint: Mapping[str, Any]) -> None: ...


class InMemoryCheckpointAnchorStore:
    """Test-only anchor adapter. It is NOT durable or an independent production anchor."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, list[dict[str, Any]]] = {}

    def list_checkpoints(self, registry_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._records.get(registry_id, [])]

    def append_checkpoint(self, checkpoint: Mapping[str, Any]) -> None:
        record = dict(checkpoint)
        registry_id = record.get("registry_id")
        if not isinstance(registry_id, str) or not registry_id:
            raise CheckpointError("registry_id is required")
        with self._lock:
            records = self._records.setdefault(registry_id, [])
            if records:
                previous = records[-1]
                if int(record["event_seq"]) <= int(previous["event_seq"]):
                    raise CheckpointError("checkpoint sequence must increase monotonically")
                if record["previous_checkpoint_digest"] != _digest(previous):
                    raise CheckpointError("checkpoint does not extend the latest anchor")
            elif record["previous_checkpoint_digest"] != GENESIS_HASH:
                raise CheckpointError("first checkpoint must reference the genesis anchor")
            records.append(record)


def _registry_snapshot(registry: Any) -> tuple[int, str]:
    # Keep the event-chain audit and head read in one SQLite snapshot.
    with registry._lock:
        owns_transaction = not registry._db.in_transaction
        if owns_transaction:
            registry._db.execute("BEGIN")
        try:
            audit = registry.verify_event_chain()
            if not audit.get("valid"):
                raise CheckpointError("registry event chain is invalid")
            row = registry._db.execute(
                "SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            result = (0, GENESIS_HASH) if row is None else (
                int(row["seq"]), str(row["event_hash"])
            )
        except Exception:
            if owns_transaction and registry._db.in_transaction:
                registry._db.execute("ROLLBACK")
            raise
        if owns_transaction and registry._db.in_transaction:
            registry._db.execute("COMMIT")
        return result


def create_registry_checkpoint(
    registry: Any,
    anchor_store: CheckpointAnchorStore,
    private_key: Ed25519PrivateKey,
    *,
    registry_id: str,
    signer_key_id: str,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Sign and append a checkpoint for the current, audited registry event head."""
    if not isinstance(registry_id, str) or not registry_id.strip():
        raise CheckpointError("registry_id must be a non-empty stable identifier")
    if not isinstance(signer_key_id, str) or not signer_key_id.strip():
        raise CheckpointError("signer_key_id must be a non-empty string")
    if not isinstance(private_key, Ed25519PrivateKey):
        raise CheckpointError("private_key must be an Ed25519 private key")
    event_seq, event_hash = _registry_snapshot(registry)
    existing = list(anchor_store.list_checkpoints(registry_id))
    previous = _digest(existing[-1]) if existing else GENESIS_HASH
    if existing and event_seq <= int(existing[-1]["event_seq"]):
        raise CheckpointError("registry head has not advanced beyond the latest checkpoint")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise CheckpointError("created_at must include a timezone")
    body = {
        "schema": SCHEMA,
        "registry_id": registry_id,
        "event_seq": event_seq,
        "event_hash": event_hash,
        "created_at": timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        "signer_key_id": signer_key_id,
        "previous_checkpoint_digest": previous,
    }
    signature = base64.b64encode(private_key.sign(_canonical(body))).decode("ascii")
    checkpoint = {**body, "signature": signature}
    anchor_store.append_checkpoint(checkpoint)
    return {**checkpoint, "checkpoint_digest": _digest(checkpoint)}


def verify_registry_checkpoints(
    registry: Any,
    anchor_store: CheckpointAnchorStore,
    trusted_keys: Mapping[str, Mapping[str, Any]],
    *,
    registry_id: str,
) -> dict[str, Any]:
    """Verify signatures, anchor continuity, and every anchored hash against live history.

    This detects rewrites/rollback at or before the latest externally stored checkpoint.
    Events created after that checkpoint remain unanchored until the next checkpoint.
    """
    records = list(anchor_store.list_checkpoints(registry_id))
    if not records:
        return {
            "valid": False, "checkpoints_checked": 0,
            "issues": ["no external checkpoints are available"],
        }
    issues: list[str] = []
    previous = GENESIS_HASH
    previous_seq = -1
    with registry._lock:
        owns_transaction = not registry._db.in_transaction
        if owns_transaction:
            registry._db.execute("BEGIN")
        try:
            audit = registry.verify_event_chain()
            if not audit.get("valid"):
                issues.append("registry event chain is invalid")
            head = registry._db.execute(
                "SELECT seq FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            head_seq = 0 if head is None else int(head["seq"])
            for index, record in enumerate(records):
                try:
                    body = {key: record[key] for key in (
                        "schema", "registry_id", "event_seq", "event_hash",
                        "created_at", "signer_key_id", "previous_checkpoint_digest",
                    )}
                    if body["schema"] != SCHEMA or body["registry_id"] != registry_id:
                        raise CheckpointError("checkpoint schema or registry identity mismatch")
                    seq = body["event_seq"]
                    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
                        raise CheckpointError("checkpoint event_seq is invalid")
                    if seq <= previous_seq:
                        raise CheckpointError("checkpoint sequence is not strictly increasing")
                    if body["previous_checkpoint_digest"] != previous:
                        raise CheckpointError("checkpoint anchor chain is broken")
                    _timestamp(body["created_at"])
                    key_id = body["signer_key_id"]
                    entry = trusted_keys.get(key_id)
                    if not isinstance(entry, Mapping):
                        raise CheckpointError("checkpoint signer is not trusted")
                    roles = entry.get("roles", [])
                    if "REGISTRY_CHECKPOINTER" not in roles:
                        raise CheckpointError("trusted key lacks REGISTRY_CHECKPOINTER role")
                    signed_at = _timestamp(body["created_at"])
                    try:
                        valid_from = _timestamp(entry["valid_from"])
                        valid_until = _timestamp(entry["valid_until"])
                        revoked_at = (
                            None if entry.get("revoked_at") is None
                            else _timestamp(entry["revoked_at"])
                        )
                    except KeyError:
                        raise CheckpointError("trusted checkpoint key validity interval is incomplete") from None
                    if not valid_from <= signed_at <= valid_until:
                        raise CheckpointError("checkpoint signing key was outside its validity interval")
                    if revoked_at is not None and signed_at >= revoked_at:
                        raise CheckpointError("checkpoint signing key was revoked at signing time")
                    public = _public_key(entry)
                    signature = base64.b64decode(record["signature"], validate=True)
                    public.verify(signature, _canonical(body))
                    if seq > head_seq:
                        raise CheckpointError("registry rollback: current head is behind external checkpoint")
                    if seq == 0:
                        if body["event_hash"] != GENESIS_HASH:
                            raise CheckpointError("genesis checkpoint hash mismatch")
                    else:
                        row = registry._db.execute(
                            "SELECT event_hash FROM events WHERE seq=?", (seq,)
                        ).fetchone()
                        if row is None or row["event_hash"] != body["event_hash"]:
                            raise CheckpointError(
                                f"anchored history mismatch at event sequence {seq}"
                            )
                    previous = _digest(record)
                    previous_seq = seq
                except InvalidSignature:
                    issues.append(f"checkpoint {index}: Ed25519 signature verification failed")
                    break
                except (KeyError, TypeError, ValueError) as exc:
                    issues.append(f"checkpoint {index}: {exc}")
                    break
        except Exception:
            if owns_transaction and registry._db.in_transaction:
                registry._db.execute("ROLLBACK")
            raise
        if owns_transaction and registry._db.in_transaction:
            registry._db.execute("COMMIT")
    return {
        "valid": not issues,
        "checkpoints_checked": len(records) if not issues else min(len(records), index + 1),
        "latest_event_seq": previous_seq if not issues else None,
        "issues": issues,
    }
