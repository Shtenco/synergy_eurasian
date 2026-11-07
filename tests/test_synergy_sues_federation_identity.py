import pytest
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from synergy_sues.event_transport import DurableEventStore
from synergy_sues.federation_identity import (
    ALGORITHM, FederationIdentity, TrustedKeyRegistry, TrustedSigningKey,
    generate_ed25519_keypair, sign_event,
)

@dataclass(frozen=True)
class E:
    event_id: str = "e1"
    aggregate_type: str = "PROJECT"
    aggregate_id: str = "p1"
    sequence: int = 1
    event_type: str = "NODE_REGISTERED"
    effective_at: str = "2026-11-06T09:00:00+00:00"
    recorded_at: str = "2026-11-06T09:01:00+00:00"
    payload: dict = None
    source_ref: str = "src:e1"
    evidence_ids: tuple = ("ev1",)
    idempotency_key: str = "i1"
    previous_hash: str = ""
    event_hash: str = ""

    def __post_init__(self):
        if self.payload is None:
            object.__setattr__(self, "payload", {"node": "p1"})

def event(tmp_path, filename="e.db"):
    return DurableEventStore(str(tmp_path/filename)).append(
        E(), now=datetime(2026,11,6,9,1,tzinfo=timezone.utc))

def setup(valid_from="2026-01-01T00:00:00+00:00"):
    private, public = generate_ed25519_keypair()
    registry = TrustedKeyRegistry()
    registry.register_identity(FederationIdentity("org:a","tenant:a","ORGANIZATION"))
    registry.register_key(TrustedSigningKey("org:a","tenant:a","k1",ALGORITHM,
        public,valid_from))
    return private, registry

def envelope(tmp_path):
    private, registry = setup()
    signed = sign_event(event(tmp_path),"org:a","tenant:a","k1",private,
        "2026-11-06T10:00:00+00:00")
    return signed, registry

def test_signature_verifies(tmp_path):
    signed, registry = envelope(tmp_path)
    assert registry.verify(signed,"2026-11-06T10:01:00+00:00").identity_id == "org:a"

def test_tampered_payload_and_hash_rejected(tmp_path):
    signed, registry = envelope(tmp_path)
    with pytest.raises(ValueError,match="event hash"):
        registry.verify(replace(signed,event={**signed.event,"payload":{"x":1}}),
            "2026-11-06T10:01:00+00:00")
    with pytest.raises(ValueError,match="event hash"):
        registry.verify(replace(signed,event={**signed.event,"event_hash":"f"*64}),
            "2026-11-06T10:01:00+00:00")

def test_unknown_key_identity_and_tenant_rejected(tmp_path):
    signed, registry = envelope(tmp_path)
    with pytest.raises(ValueError,match="unknown signing key"):
        registry.verify(replace(signed,key_id="missing"),"2026-11-06T10:01:00+00:00")
    with pytest.raises(ValueError,match="unknown federation identity"):
        registry.verify(replace(signed,identity_id="org:other"),"2026-11-06T10:01:00+00:00")
    with pytest.raises(ValueError,match="tenant"):
        registry.verify(replace(signed,tenant_id="tenant:other"),"2026-11-06T10:01:00+00:00")

def test_revocation_and_key_window(tmp_path):
    signed, registry = envelope(tmp_path)
    registry.revoke_key("org:a","k1","2026-11-06T10:00:30+00:00")
    with pytest.raises(ValueError,match="revoked"):
        registry.verify(signed,"2026-11-06T10:01:00+00:00")
    private, registry = setup(valid_from="2026-11-06T10:00:30+00:00")
    early = sign_event(event(tmp_path,"early.db"),"org:a","tenant:a","k1",private,
        "2026-11-06T10:00:00+00:00")
    with pytest.raises(ValueError,match="outside key validity"):
        registry.verify(early,"2026-11-06T10:01:00+00:00")

def test_algorithm_downgrade_duplicate_keys_and_canonicalization(tmp_path):
    signed, registry = envelope(tmp_path)
    with pytest.raises(ValueError,match="algorithm"):
        registry.verify(replace(signed,algorithm="none"),"2026-11-06T10:01:00+00:00")
    key = registry.resolve("org:a","k1")
    with pytest.raises(ValueError,match="already exists"):
        registry.register_key(key)
    from synergy_sues.federation_identity import _canonical
    assert _canonical({"b":1,"a":2}) == _canonical({"a":2,"b":1})

def test_future_signature_timestamp_and_unsigned_extension_fields_rejected(tmp_path):
    signed, registry = envelope(tmp_path)
    with pytest.raises(ValueError, match="future"):
        registry.verify(signed, "2026-11-06T09:59:00+00:00")
    extended = replace(signed, event={**signed.event, "unhashed_extension": "not-allowed"})
    with pytest.raises(ValueError, match="unsupported fields"):
        registry.verify(extended, "2026-11-06T10:01:00+00:00")

import sqlite3
from synergy_sues.federation_identity import SQLiteTrustedKeyRegistry


def test_sqlite_trust_registry_persists_and_reloads_across_instances(tmp_path):
    path = str(tmp_path / "trust.db")
    private, public = generate_ed25519_keypair()
    first = SQLiteTrustedKeyRegistry(path)
    first.register_identity(FederationIdentity("org:persist", "tenant:persist", "ORGANIZATION"))
    first.register_key(TrustedSigningKey("org:persist", "tenant:persist", "key-1",
        ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    second = SQLiteTrustedKeyRegistry(path)
    assert second.resolve("org:persist", "key-1").public_key_b64 == public
    assert second.verify(sign_event(event(tmp_path, "persist-event.db"), "org:persist",
        "tenant:persist", "key-1", private, "2026-11-06T10:00:00+00:00"),
        "2026-11-06T10:01:00+00:00").identity_id == "org:persist"
    assert second.verify_audit()
    assert [x["action"] for x in second.audit_events()] == ["IDENTITY_REGISTERED", "KEY_REGISTERED"]


def test_sqlite_revocation_is_durable_and_visible_to_existing_registry_instance(tmp_path):
    path = str(tmp_path / "trust.db")
    private, public = generate_ed25519_keypair()
    first = SQLiteTrustedKeyRegistry(path)
    first.register_identity(FederationIdentity("org:revoked", "tenant:r", "ORGANIZATION"))
    first.register_key(TrustedSigningKey("org:revoked", "tenant:r", "key-1",
        ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    second = SQLiteTrustedKeyRegistry(path)
    signed = sign_event(event(tmp_path), "org:revoked", "tenant:r", "key-1",
        private, "2026-11-06T10:00:00+00:00")
    assert second.verify(signed, "2026-11-06T10:01:00+00:00")
    first.revoke_key("org:revoked", "key-1", "2026-11-06T10:00:30+00:00")
    with pytest.raises(ValueError, match="revoked"):
        second.verify(signed, "2026-11-06T10:01:00+00:00")
    reopened = SQLiteTrustedKeyRegistry(path)
    assert reopened.resolve("org:revoked", "key-1").revoked_at == "2026-11-06T10:00:30+00:00"
    assert reopened.verify_audit()
    assert [x["action"] for x in reopened.audit_events()] == [
        "IDENTITY_REGISTERED", "KEY_REGISTERED", "KEY_REVOKED"]


def test_sqlite_trust_registry_audit_is_append_only_and_hash_chained(tmp_path):
    path = str(tmp_path / "trust.db")
    registry = SQLiteTrustedKeyRegistry(path)
    registry.register_identity(FederationIdentity("org:audit", "tenant:a", "ORGANIZATION"))
    assert registry.verify_audit()
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE trust_audit SET action='FORGED' WHERE sequence=1")
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER trust_audit_no_update")
        db.execute("UPDATE trust_audit SET action='FORGED' WHERE sequence=1")
    assert not registry.verify_audit()


def test_sqlite_trust_registry_rejects_memory_database_and_conflicting_records(tmp_path):
    with pytest.raises(ValueError, match="file-backed"):
        SQLiteTrustedKeyRegistry(":memory:")
    registry = SQLiteTrustedKeyRegistry(str(tmp_path / "trust.db"))
    registry.register_identity(FederationIdentity("org:one", "tenant:one", "ORGANIZATION"))
    with pytest.raises(ValueError, match="different attributes"):
        registry.register_identity(FederationIdentity("org:one", "tenant:two", "ORGANIZATION"))
    private, public = generate_ed25519_keypair()
    with pytest.raises(ValueError, match="not registered"):
        registry.register_key(TrustedSigningKey("org:missing", "tenant:one", "key",
            ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    assert [x["action"] for x in registry.audit_events()] == ["IDENTITY_REGISTERED"]
    assert registry.verify_audit()

def test_sqlite_registry_protects_trust_records_from_application_level_mutation(tmp_path):
    path = str(tmp_path / "immutable.db")
    private, public = generate_ed25519_keypair()
    registry = SQLiteTrustedKeyRegistry(path)
    registry.register_identity(FederationIdentity("org:immutable", "tenant:i", "ORGANIZATION"))
    registry.register_key(TrustedSigningKey("org:immutable", "tenant:i", "key-1",
        ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE trust_keys SET key_id='forged' WHERE key_id='key-1'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM trust_identities WHERE identity_id='org:immutable'")
    assert registry.verify_audit()


def test_historical_signature_remains_verifiable_after_later_key_revocation(tmp_path):
    signed, registry = envelope(tmp_path)
    registry.revoke_key("org:a", "k1", "2026-11-06T10:00:30+00:00")
    with pytest.raises(ValueError, match="revoked"):
        registry.verify(signed, "2026-11-06T10:01:00+00:00")
    assert registry.verify_historical(
        signed, verified_at="2026-11-06T10:01:00+00:00"
    ).identity_id == "org:a"
