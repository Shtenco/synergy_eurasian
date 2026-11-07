"""Federation identity and Ed25519-signed event envelopes (V1).

Trust is provisioned out-of-band. A public key carried by an event is never
accepted as its own trust anchor. Signature verification authenticates a key
holder; it does not grant economic, accounting, payment, or governance rights.
"""
from __future__ import annotations
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import base64
import json
from typing import Any, Mapping

ALGORITHM = "Ed25519"
SCHEMA_VERSION = "synergy.signed-event.v1"
_EVENT_FIELDS = ("event_id", "aggregate_type", "aggregate_id", "sequence", "event_type",
    "effective_at", "recorded_at", "payload", "source_ref", "evidence_ids",
    "idempotency_key", "previous_hash", "event_hash")

def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

def _mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("event must be a dataclass or mapping")

def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return result.astimezone(timezone.utc)

def _event_hash(event: Mapping[str, Any]) -> str:
    missing = [field for field in _EVENT_FIELDS if field not in event]
    if missing:
        raise ValueError(f"event missing fields: {', '.join(missing)}")
    extra = set(event) - set(_EVENT_FIELDS)
    if extra:
        raise ValueError(f"event contains unsupported fields: {', '.join(sorted(extra))}")
    if not isinstance(event["payload"], dict):
        raise ValueError("event payload must be an object")
    evidence = event["evidence_ids"]
    if not isinstance(evidence, (list, tuple)) or any(not isinstance(x, str) or not x for x in evidence):
        raise ValueError("event evidence_ids must be non-empty strings")
    if len(evidence) != len(set(evidence)):
        raise ValueError("event evidence_ids must be unique")
    sequence = event["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("event sequence must be an integer >= 1")
    for name in ("event_id", "aggregate_type", "aggregate_id", "event_type", "source_ref"):
        if not isinstance(event[name], str) or not event[name].strip():
            raise ValueError(f"{name} must be a non-empty string")
    _utc(event["effective_at"], "effective_at")
    _utc(event["recorded_at"], "recorded_at")
    if not isinstance(event["idempotency_key"], str):
        raise ValueError("idempotency_key must be a string")
    previous = event["previous_hash"]
    if not isinstance(previous, str) or (previous and (len(previous) != 64 or any(ch not in "0123456789abcdef" for ch in previous))):
        raise ValueError("previous_hash must be empty or a lowercase SHA-256 digest")
    unsigned = {name: event[name] for name in _EVENT_FIELDS[:-1]}
    unsigned["evidence_ids"] = list(evidence)
    digest = sha256(_canonical(unsigned)).hexdigest()
    if event["event_hash"] != digest:
        raise ValueError("event hash verification failed")
    return digest

@dataclass(frozen=True)
class FederationIdentity:
    identity_id: str
    tenant_id: str
    identity_type: str
    display_name: str = ""

@dataclass(frozen=True)
class TrustedSigningKey:
    identity_id: str
    tenant_id: str
    key_id: str
    algorithm: str
    public_key_b64: str
    valid_from: str
    valid_until: str | None = None
    revoked_at: str | None = None

@dataclass(frozen=True)
class SignedEventEnvelope:
    schema_version: str
    algorithm: str
    identity_id: str
    tenant_id: str
    key_id: str
    signed_at: str
    event: dict[str, Any]
    signature_b64: str

    def signing_document(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "algorithm": self.algorithm,
            "identity_id": self.identity_id, "tenant_id": self.tenant_id,
            "key_id": self.key_id, "signed_at": self.signed_at, "event": self.event}

    def as_dict(self) -> dict[str, Any]:
        return {**self.signing_document(), "signature_b64": self.signature_b64}

class TrustedKeyRegistry:
    """Explicit local trust allowlist; never learns trust from incoming envelopes."""
    def __init__(self) -> None:
        self._identities: dict[str, FederationIdentity] = {}
        self._keys: dict[tuple[str, str], TrustedSigningKey] = {}

    def register_identity(self, identity: FederationIdentity) -> None:
        if not isinstance(identity, FederationIdentity):
            raise ValueError("identity must be a FederationIdentity")
        if not identity.identity_id.strip() or not identity.tenant_id.strip() or not identity.identity_type.strip():
            raise ValueError("identity_id, tenant_id and identity_type are required")
        existing = self._identities.get(identity.identity_id)
        if existing is not None and existing != identity:
            raise ValueError("identity ID is already registered with different attributes")
        self._identities[identity.identity_id] = identity

    def register_key(self, key: TrustedSigningKey) -> None:
        if not isinstance(key, TrustedSigningKey):
            raise ValueError("key must be a TrustedSigningKey")
        identity = self._identities.get(key.identity_id)
        if identity is None:
            raise ValueError("key identity is not registered")
        if identity.tenant_id != key.tenant_id:
            raise ValueError("key tenant does not match registered identity")
        if key.algorithm != ALGORITHM:
            raise ValueError("unsupported signing algorithm; Ed25519 is required")
        if not key.key_id.strip():
            raise ValueError("key_id is required")
        _utc(key.valid_from, "valid_from")
        if key.valid_until is not None and _utc(key.valid_until, "valid_until") <= _utc(key.valid_from, "valid_from"):
            raise ValueError("valid_until must be after valid_from")
        if key.revoked_at is not None:
            _utc(key.revoked_at, "revoked_at")
        try:
            raw = base64.b64decode(key.public_key_b64, validate=True)
        except Exception as exc:
            raise ValueError("public_key_b64 must be valid base64") from exc
        if len(raw) != 32:
            raise ValueError("Ed25519 public key must be exactly 32 bytes")
        index = (key.identity_id, key.key_id)
        if index in self._keys:
            raise ValueError("key ID already exists for this identity")
        self._keys[index] = key

    def revoke_key(self, identity_id: str, key_id: str, revoked_at: str) -> None:
        index = (identity_id, key_id)
        key = self._keys.get(index)
        if key is None:
            raise ValueError("unknown signing key")
        if key.revoked_at is not None:
            raise ValueError("signing key is already revoked")
        _utc(revoked_at, "revoked_at")
        self._keys[index] = TrustedSigningKey(key.identity_id, key.tenant_id, key.key_id,
            key.algorithm, key.public_key_b64, key.valid_from, key.valid_until, revoked_at)

    def resolve(self, identity_id: str, key_id: str) -> TrustedSigningKey:
        try:
            return self._keys[(identity_id, key_id)]
        except KeyError as exc:
            raise ValueError("unknown signing key") from exc

    def verify(self, envelope: SignedEventEnvelope | Mapping[str, Any],
               received_at: datetime | str | None = None, *,
               allow_historical: bool = False) -> FederationIdentity:
        if isinstance(envelope, Mapping):
            try:
                envelope = SignedEventEnvelope(**dict(envelope))
            except TypeError as exc:
                raise ValueError("invalid signed envelope shape") from exc
        if not isinstance(envelope, SignedEventEnvelope):
            raise ValueError("envelope must be SignedEventEnvelope or mapping")
        if envelope.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported signed envelope schema version")
        if envelope.algorithm != ALGORITHM:
            raise ValueError("algorithm downgrade or unsupported algorithm rejected")
        identity = self._identities.get(envelope.identity_id)
        if identity is None:
            raise ValueError("unknown federation identity")
        if identity.tenant_id != envelope.tenant_id:
            raise ValueError("signer tenant does not match registered identity")
        key = self.resolve(envelope.identity_id, envelope.key_id)
        if key.tenant_id != envelope.tenant_id or key.algorithm != envelope.algorithm:
            raise ValueError("signing key identity/tenant/algorithm mismatch")
        signed_at = _utc(envelope.signed_at, "signed_at")
        now = _utc(received_at, "received_at") if isinstance(received_at, str) else (received_at or datetime.now(timezone.utc))
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        now = now.astimezone(timezone.utc)
        if signed_at > now:
            raise ValueError("signature timestamp is in the future")
        start = _utc(key.valid_from, "valid_from")
        end = _utc(key.valid_until, "valid_until") if key.valid_until else None
        revoked = _utc(key.revoked_at, "revoked_at") if key.revoked_at else None
        if signed_at < start or (end is not None and signed_at >= end):
            raise ValueError("signature timestamp is outside key validity window")
        if revoked is not None and signed_at >= revoked:
            raise ValueError("signing key was revoked at signing time")
        if not isinstance(allow_historical, bool):
            raise ValueError("allow_historical must be a boolean")
        if not allow_historical:
            if now < start or (end is not None and now >= end):
                raise ValueError("signing key is not currently valid")
            if revoked is not None and now >= revoked:
                raise ValueError("signing key is revoked")
        _event_hash(envelope.event)
        try:
            public_bytes = base64.b64decode(key.public_key_b64, validate=True)
            signature = base64.b64decode(envelope.signature_b64, validate=True)
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, _canonical(envelope.signing_document()))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("signed event signature verification failed") from exc
        return identity

    def verify_historical(
        self,
        envelope: SignedEventEnvelope | Mapping[str, Any],
        received_at: datetime | str | None = None,
    ) -> FederationIdentity:
        """Verify signature authenticity at signing time after key expiry/revocation.

        Revocation still invalidates signatures at or after the recorded revoked_at
        instant. Callers must set revoked_at to the effective compromise cutoff when
        a key compromise is known to have started earlier than its discovery.
        This method is for audit/replay only, never authorization of new actions.
        """
        return self.verify(envelope, received_at, allow_historical=True)

def generate_ed25519_keypair() -> tuple[bytes, str]:
    """Generate raw private key bytes and a base64 public key; do not persist private material."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption())
    public_raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private_raw, base64.b64encode(public_raw).decode("ascii")

def sign_event(event: Any, identity_id: str, tenant_id: str, key_id: str,
               private_key: bytes, signed_at: str) -> SignedEventEnvelope:
    """Sign an already-hashed immutable event using an Ed25519 private key."""
    row = _mapping(event)
    _event_hash(row)
    _utc(signed_at, "signed_at")
    if not all(isinstance(x, str) and x.strip() for x in (identity_id, tenant_id, key_id)):
        raise ValueError("identity_id, tenant_id and key_id are required")
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise ValueError("Ed25519 private key must be exactly 32 raw bytes")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    event_copy = json.loads(_canonical(row))
    unsigned = SignedEventEnvelope(SCHEMA_VERSION, ALGORITHM, identity_id, tenant_id,
        key_id, signed_at, event_copy, "")
    signature = Ed25519PrivateKey.from_private_bytes(private_key).sign(_canonical(unsigned.signing_document()))
    return SignedEventEnvelope(unsigned.schema_version, unsigned.algorithm, unsigned.identity_id,
        unsigned.tenant_id, unsigned.key_id, unsigned.signed_at, unsigned.event,
        base64.b64encode(signature).decode("ascii"))

import sqlite3
from contextlib import contextmanager


class SQLiteTrustedKeyRegistry(TrustedKeyRegistry):
    """File-backed trust registry with atomic administration and hash-chained audit.

    The database is a single-host reference implementation. Protect the file and
    its backups with OS permissions; the local hash chain is tamper-evident, not
    a remote/WORM trust anchor. Verification refreshes trust state on every call
    so a revocation by another process is not hidden by a stale in-memory cache.
    """

    def __init__(self, database_path: str, busy_timeout_ms: int = 5000) -> None:
        if not isinstance(database_path, str) or not database_path.strip() or database_path == ":memory:":
            raise ValueError("SQLite trust registry requires a file-backed database")
        if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int) or busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be a non-negative integer")
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        super().__init__()
        with self._session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS trust_identities (
                    identity_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    identity_type TEXT NOT NULL,
                    display_name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trust_keys (
                    identity_id TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    public_key_b64 TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_until TEXT,
                    PRIMARY KEY(identity_id, key_id),
                    FOREIGN KEY(identity_id) REFERENCES trust_identities(identity_id)
                );
                CREATE TABLE IF NOT EXISTS trust_revocations (
                    identity_id TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    revoked_at TEXT NOT NULL,
                    PRIMARY KEY(identity_id, key_id),
                    FOREIGN KEY(identity_id, key_id) REFERENCES trust_keys(identity_id, key_id)
                );
                CREATE TABLE IF NOT EXISTS trust_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TRIGGER IF NOT EXISTS trust_identity_no_update
                BEFORE UPDATE ON trust_identities BEGIN SELECT RAISE(ABORT, 'trust identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_identity_no_delete
                BEFORE DELETE ON trust_identities BEGIN SELECT RAISE(ABORT, 'trust identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_keys_no_update
                BEFORE UPDATE ON trust_keys BEGIN SELECT RAISE(ABORT, 'trusted keys are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_keys_no_delete
                BEFORE DELETE ON trust_keys BEGIN SELECT RAISE(ABORT, 'trusted keys are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_revocations_no_update
                BEFORE UPDATE ON trust_revocations BEGIN SELECT RAISE(ABORT, 'trust revocations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_revocations_no_delete
                BEFORE DELETE ON trust_revocations BEGIN SELECT RAISE(ABORT, 'trust revocations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trust_audit_no_update
                BEFORE UPDATE ON trust_audit BEGIN SELECT RAISE(ABORT, 'trust audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS trust_audit_no_delete
                BEFORE DELETE ON trust_audit BEGIN SELECT RAISE(ABORT, 'trust audit is append-only'); END;
            """)
        self._refresh()
        if not self.verify_audit():
            raise ValueError("trust registry administrative audit chain verification failed")

    @contextmanager
    def _session(self):
        db = sqlite3.connect(self.database_path, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()

    @staticmethod
    def _audit_hash(sequence: int, action: str, subject_id: str, details_json: str,
                    occurred_at: str, previous_hash: str) -> str:
        document = {"sequence": sequence, "action": action, "subject_id": subject_id,
                    "details_json": details_json, "occurred_at": occurred_at,
                    "previous_hash": previous_hash}
        return sha256(_canonical(document)).hexdigest()

    def _append_audit(self, db: sqlite3.Connection, action: str, subject_id: str,
                      details: Mapping[str, Any], occurred_at: str) -> None:
        prior = db.execute("SELECT sequence,event_hash FROM trust_audit ORDER BY sequence DESC LIMIT 1").fetchone()
        sequence = 1 if prior is None else int(prior["sequence"]) + 1
        previous_hash = "" if prior is None else str(prior["event_hash"])
        details_json = _canonical(dict(details)).decode("utf-8")
        digest = self._audit_hash(sequence, action, subject_id, details_json, occurred_at, previous_hash)
        db.execute("""INSERT INTO trust_audit
            (sequence,action,subject_id,details_json,occurred_at,previous_hash,event_hash)
            VALUES(?,?,?,?,?,?,?)""",
            (sequence, action, subject_id, details_json, occurred_at, previous_hash, digest))

    def _refresh(self) -> None:
        with self._session() as db:
            identities = db.execute("SELECT * FROM trust_identities ORDER BY identity_id").fetchall()
            keys = db.execute("""
                SELECT k.*, r.revoked_at FROM trust_keys k
                LEFT JOIN trust_revocations r USING(identity_id,key_id)
                ORDER BY k.identity_id,k.key_id
            """).fetchall()
        self._identities = {
            row["identity_id"]: FederationIdentity(row["identity_id"], row["tenant_id"],
                row["identity_type"], row["display_name"])
            for row in identities
        }
        self._keys = {
            (row["identity_id"], row["key_id"]): TrustedSigningKey(
                row["identity_id"], row["tenant_id"], row["key_id"], row["algorithm"],
                row["public_key_b64"], row["valid_from"], row["valid_until"], row["revoked_at"])
            for row in keys
        }

    def register_identity(self, identity: FederationIdentity) -> None:
        # Validate through the base contract before touching durable state.
        if not isinstance(identity, FederationIdentity):
            raise ValueError("identity must be a FederationIdentity")
        if not identity.identity_id.strip() or not identity.tenant_id.strip() or not identity.identity_type.strip():
            raise ValueError("identity_id, tenant_id and identity_type are required")
        stamp = datetime.now(timezone.utc).isoformat()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute("SELECT * FROM trust_identities WHERE identity_id=?",
                    (identity.identity_id,)).fetchone()
                if existing is not None:
                    current = FederationIdentity(existing["identity_id"], existing["tenant_id"],
                        existing["identity_type"], existing["display_name"])
                    if current != identity:
                        raise ValueError("identity ID is already registered with different attributes")
                else:
                    db.execute("INSERT INTO trust_identities VALUES(?,?,?,?)",
                        (identity.identity_id, identity.tenant_id, identity.identity_type, identity.display_name))
                    self._append_audit(db, "IDENTITY_REGISTERED", identity.identity_id,
                        {"tenant_id": identity.tenant_id, "identity_type": identity.identity_type}, stamp)
                db.commit()
            except Exception:
                db.rollback()
                raise
        self._refresh()

    def register_key(self, key: TrustedSigningKey) -> None:
        if not isinstance(key, TrustedSigningKey):
            raise ValueError("key must be a TrustedSigningKey")
        _utc(key.valid_from, "valid_from")
        if key.valid_until is not None and _utc(key.valid_until, "valid_until") <= _utc(key.valid_from, "valid_from"):
            raise ValueError("valid_until must be after valid_from")
        if key.algorithm != ALGORITHM or not key.key_id.strip():
            raise ValueError("Ed25519 and a non-empty key_id are required")
        try:
            raw = base64.b64decode(key.public_key_b64, validate=True)
        except Exception as exc:
            raise ValueError("public_key_b64 must be valid base64") from exc
        if len(raw) != 32:
            raise ValueError("Ed25519 public key must be exactly 32 bytes")
        stamp = datetime.now(timezone.utc).isoformat()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                identity = db.execute("SELECT tenant_id FROM trust_identities WHERE identity_id=?",
                    (key.identity_id,)).fetchone()
                if identity is None:
                    raise ValueError("key identity is not registered")
                if identity["tenant_id"] != key.tenant_id:
                    raise ValueError("key tenant does not match registered identity")
                if db.execute("SELECT 1 FROM trust_keys WHERE identity_id=? AND key_id=?",
                    (key.identity_id, key.key_id)).fetchone():
                    raise ValueError("key ID already exists for this identity")
                if key.revoked_at is not None:
                    raise ValueError("new key cannot be registered as already revoked")
                db.execute("INSERT INTO trust_keys VALUES(?,?,?,?,?,?,?)",
                    (key.identity_id, key.key_id, key.tenant_id, key.algorithm,
                     key.public_key_b64, key.valid_from, key.valid_until))
                self._append_audit(db, "KEY_REGISTERED", f"{key.identity_id}/{key.key_id}",
                    {"tenant_id": key.tenant_id, "algorithm": key.algorithm,
                     "public_key_sha256": sha256(raw).hexdigest(),
                     "valid_from": key.valid_from, "valid_until": key.valid_until}, stamp)
                db.commit()
            except Exception:
                db.rollback()
                raise
        self._refresh()

    def revoke_key(self, identity_id: str, key_id: str, revoked_at: str) -> None:
        _utc(revoked_at, "revoked_at")
        stamp = datetime.now(timezone.utc).isoformat()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                key = db.execute("SELECT * FROM trust_keys WHERE identity_id=? AND key_id=?",
                    (identity_id, key_id)).fetchone()
                if key is None:
                    raise ValueError("unknown signing key")
                if db.execute("SELECT 1 FROM trust_revocations WHERE identity_id=? AND key_id=?",
                    (identity_id, key_id)).fetchone():
                    raise ValueError("signing key is already revoked")
                db.execute("INSERT INTO trust_revocations VALUES(?,?,?)",
                    (identity_id, key_id, revoked_at))
                self._append_audit(db, "KEY_REVOKED", f"{identity_id}/{key_id}",
                    {"revoked_at": revoked_at}, stamp)
                db.commit()
            except Exception:
                db.rollback()
                raise
        self._refresh()

    def verify(self, envelope: SignedEventEnvelope | Mapping[str, Any],
               received_at: datetime | str | None = None) -> FederationIdentity:
        self._refresh()
        return super().verify(envelope, received_at)

    def audit_events(self) -> tuple[dict[str, Any], ...]:
        with self._session() as db:
            rows = db.execute("SELECT * FROM trust_audit ORDER BY sequence").fetchall()
        return tuple(dict(row) for row in rows)

    def verify_audit(self) -> bool:
        rows = self.audit_events()
        previous = ""
        for expected_sequence, row in enumerate(rows, start=1):
            if row["sequence"] != expected_sequence or row["previous_hash"] != previous:
                return False
            try:
                details = json.loads(row["details_json"])
                if not isinstance(details, dict):
                    return False
                canonical_details = _canonical(details).decode("utf-8")
            except (TypeError, ValueError):
                return False
            if canonical_details != row["details_json"]:
                return False
            digest = self._audit_hash(row["sequence"], row["action"], row["subject_id"],
                row["details_json"], row["occurred_at"], previous)
            if digest != row["event_hash"]:
                return False
            previous = digest
        return True
