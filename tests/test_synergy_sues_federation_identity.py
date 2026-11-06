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
