from dataclasses import dataclass, replace
from datetime import datetime, timezone, timedelta
import json
import sqlite3

import pytest

from synergy_sues.event_transport import DurableEventStore
from synergy_sues.federation_identity import (
    ALGORITHM, FederationIdentity, TrustedKeyRegistry, TrustedSigningKey,
    generate_ed25519_keypair, sign_event,
)
from synergy_sues.v7_adapter import adapt_v7_event_store


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: str
    recorded_at: str
    payload: dict
    source_ref: str
    evidence_ids: tuple = ()
    idempotency_key: str = ""
    previous_hash: str = ""
    event_hash: str = ""


def event(event_id="evt-1", sequence=1, previous_hash="", idem="idem-1"):
    return DomainEvent(
        event_id, "PROJECT", "project-1", sequence, "NODE_REGISTERED",
        "2026-11-06T09:00:00+00:00", "2026-11-06T09:01:00+00:00",
        {"node_id": "project-1", "node_type": "PROJECT"},
        f"source:{event_id}", ("evidence:1",), idem, previous_hash, "",
    )


def utc(hour=9, minute=0, second=0):
    return datetime(2026, 11, 6, hour, minute, second, tzinfo=timezone.utc)


def trusted_authenticator(_message):
    # Test seam only; production adapters must verify SignedEventEnvelope
    # against a configured TrustedKeyRegistry.
    return True


def test_event_and_outbox_are_durable_and_atomic_across_restart(tmp_path):
    path = str(tmp_path / "sues.db")
    store = DurableEventStore(path)
    sealed = store.append(event(), now=utc())
    assert sealed.event_hash
    assert store.verify()
    assert len(store.events) == 1

    reopened = DurableEventStore(path)
    assert reopened.events == (sealed,)
    claimed = reopened.claim_outbox(now=utc(), lease_seconds=30)
    assert len(claimed) == 1
    assert claimed[0].event_hash == sealed.event_hash
    assert json.loads(claimed[0].payload_json)["event_id"] == "evt-1"
    assert reopened.outbox_status(claimed[0].message_id)["status"] == "INFLIGHT"


def test_append_rejects_sequence_gap_and_duplicate_idempotency_without_partial_write(tmp_path):
    store = DurableEventStore(str(tmp_path / "sues.db"))
    store.append(event(), now=utc())
    with pytest.raises(ValueError, match="Expected aggregate sequence"):
        store.append(event("evt-gap", 3, idem="idem-gap"), now=utc())
    with pytest.raises(sqlite3.IntegrityError):
        store.append(event("evt-2", 2, idem="idem-1"), now=utc())
    assert len(store.events) == 1
    assert store.verify()


def test_independent_store_instances_serialize_aggregate_writers(tmp_path):
    path = str(tmp_path / "shared.db")
    first = DurableEventStore(path)
    second = DurableEventStore(path)
    first.append(event(), now=utc())
    with pytest.raises(ValueError, match="Expected aggregate sequence"):
        second.append(event("evt-race", 1, idem="idem-race"), now=utc())
    assert len(DurableEventStore(path).events) == 1


def test_outbox_lease_expiry_fencing_retry_and_ack(tmp_path):
    store = DurableEventStore(str(tmp_path / "sues.db"))
    store.append(event(), now=utc())
    first = store.claim_outbox(now=utc(), lease_seconds=10)[0]
    assert store.claim_outbox(now=utc(9, 0, 5)) == ()

    second = store.claim_outbox(now=utc(9, 0, 11), lease_seconds=10)[0]
    assert second.message_id == first.message_id
    assert second.attempts == 2
    assert second.lease_token != first.lease_token
    with pytest.raises(ValueError, match="stale lease"):
        store.ack_outbox(first.message_id, first.lease_token, now=utc(9, 0, 12))

    status = store.fail_outbox(
        second.message_id, second.lease_token, "temporary network failure",
        retry_delay_seconds=5, max_attempts=5, now=utc(9, 0, 12),
    )
    assert status == "PENDING"
    assert store.claim_outbox(now=utc(9, 0, 16)) == ()
    third = store.claim_outbox(now=utc(9, 0, 17), lease_seconds=10)[0]
    store.ack_outbox(third.message_id, third.lease_token, now=utc(9, 0, 18))
    assert store.outbox_status(third.message_id)["status"] == "DELIVERED"


def test_outbox_moves_to_dead_after_max_attempts(tmp_path):
    store = DurableEventStore(str(tmp_path / "sues.db"))
    store.append(event(), now=utc())
    first = store.claim_outbox(now=utc(), lease_seconds=1)[0]
    assert store.fail_outbox(first.message_id, first.lease_token, "down", max_attempts=1, now=utc()) == "DEAD"
    assert store.claim_outbox(now=utc(9, 1)) == ()


def test_inbox_handler_effect_and_receipt_commit_atomically_and_deduplicate(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver.db"))
    sender.append(event(), now=utc())
    claimed = sender.claim_outbox(now=utc())[0]
    message = {
        "message_id": claimed.message_id,
        "event_id": claimed.event_id,
        "event_hash": claimed.event_hash,
        "payload_json": claimed.payload_json,
    }
    with sqlite3.connect(receiver.database_path) as db:
        db.execute("CREATE TABLE applied(event_id TEXT PRIMARY KEY, effect_count INTEGER NOT NULL)")

    def apply(db, incoming):
        db.execute(
            "INSERT INTO applied(event_id,effect_count) VALUES(?,1)",
            (incoming["event_id"],),
        )

    assert receiver.consume_inbox("graph-projector", message, apply, received_at=utc(), authenticator=trusted_authenticator)
    assert not receiver.consume_inbox("graph-projector", message, apply, received_at=utc(9, 1), authenticator=trusted_authenticator)
    with sqlite3.connect(receiver.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM applied").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0] == 1


def test_inbox_handler_failure_rolls_back_effect_and_receipt(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver.db"))
    sender.append(event(), now=utc())
    claimed = sender.claim_outbox(now=utc())[0]
    message = {
        "message_id": claimed.message_id, "event_id": claimed.event_id,
        "event_hash": claimed.event_hash, "payload_json": claimed.payload_json,
    }
    with sqlite3.connect(receiver.database_path) as db:
        db.execute("CREATE TABLE applied(event_id TEXT PRIMARY KEY)")

    def fail_after_write(db, incoming):
        db.execute("INSERT INTO applied VALUES(?)", (incoming["event_id"],))
        raise RuntimeError("consumer failed")

    with pytest.raises(RuntimeError, match="consumer failed"):
        receiver.consume_inbox("consumer", message, fail_after_write, received_at=utc(), authenticator=trusted_authenticator)
    assert not receiver.inbox_contains("consumer", claimed.message_id)
    with sqlite3.connect(receiver.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM applied").fetchone()[0] == 0


def test_inbox_rejects_tampered_payload_and_message_id_hash_reuse(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver.db"))
    sender.append(event(), now=utc())
    claimed = sender.claim_outbox(now=utc())[0]
    message = {
        "message_id": claimed.message_id, "event_id": claimed.event_id,
        "event_hash": claimed.event_hash, "payload_json": claimed.payload_json,
    }
    handler = lambda db, incoming: None
    tampered = {**message, "payload_json": message["payload_json"].replace("project-1", "changed")}
    with pytest.raises(ValueError, match="hash verification"):
        receiver.consume_inbox("consumer", tampered, handler, received_at=utc(), authenticator=trusted_authenticator)

    assert receiver.consume_inbox("consumer", message, handler, received_at=utc(), authenticator=trusted_authenticator)
    conflicting = {**message, "event_hash": "f" * 64}
    with pytest.raises(ValueError, match="identity does not match"):
        receiver.consume_inbox("consumer", conflicting, handler, received_at=utc(), authenticator=trusted_authenticator)


def test_inbox_message_id_reuse_with_another_valid_event_hash_is_rejected(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver.db"))
    first = sender.append(event(), now=utc())
    second = sender.append(event("evt-2", 2, first.event_hash, "idem-2"), now=utc(9, 2))
    messages = sender.claim_outbox(now=utc(9, 2), limit=2)
    handler = lambda db, incoming: None
    one = next(x for x in messages if x.event_id == first.event_id)
    two = next(x for x in messages if x.event_id == second.event_id)
    message_one = {"message_id": "forced-id", "event_id": one.event_id, "event_hash": one.event_hash, "payload_json": one.payload_json}
    message_two = {"message_id": "forced-id", "event_id": two.event_id, "event_hash": two.event_hash, "payload_json": two.payload_json}
    assert receiver.consume_inbox("consumer", message_one, handler, received_at=utc(), authenticator=trusted_authenticator)
    with pytest.raises(ValueError, match="reused with a different event hash"):
        receiver.consume_inbox("consumer", message_two, handler, received_at=utc(9, 3), authenticator=trusted_authenticator)


def test_event_store_requires_file_backed_database(tmp_path):
    with pytest.raises(ValueError, match="persistent SQLite"):
        DurableEventStore(":memory:")


def test_durable_store_remains_compatible_with_v7_sues_event_adapter(tmp_path):
    store = DurableEventStore(str(tmp_path / "v7-compat.db"))
    stored = store.append(event(), now=utc())
    adapted = adapt_v7_event_store(store)
    assert len(adapted) == 1
    assert adapted[0].source_event_id == stored.event_id
    assert adapted[0].source_event_hash == stored.event_hash
    assert adapted[0].payload_json == json.dumps(
        stored.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def test_inbox_deduplicates_by_event_id_and_rejects_conflicting_event_hash(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender-event-id.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver-event-id.db"))
    original = sender.append(event(), now=utc())
    message = {
        "message_id": "message-original", "event_id": original.event_id,
        "event_hash": original.event_hash,
        "payload_json": json.dumps({
            **original.unsigned(), "event_hash": original.event_hash
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
    }
    applied = []
    assert receiver.consume_inbox("consumer", message,
        lambda db, incoming: applied.append(incoming["event_id"]), received_at=utc(), authenticator=trusted_authenticator)
    duplicate_message = {**message, "message_id": "message-redelivered"}
    assert not receiver.consume_inbox("consumer", duplicate_message,
        lambda db, incoming: applied.append("duplicate"), received_at=utc(9, 1), authenticator=trusted_authenticator)
    assert applied == [original.event_id]

    conflicting_source = replace(
        event(), payload={"node_id": "tampered", "node_type": "PROJECT"},
        source_ref="source:conflicting-same-event-id",
    )
    conflicting_sender = DurableEventStore(str(tmp_path / "sender-conflicting.db"))
    conflicting = conflicting_sender.append(conflicting_source, now=utc())
    conflicting_message = {
        "message_id": "message-conflicting", "event_id": conflicting.event_id,
        "event_hash": conflicting.event_hash,
        "payload_json": json.dumps({
            **conflicting.unsigned(), "event_hash": conflicting.event_hash
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
    }
    assert conflicting.event_id == original.event_id
    assert conflicting.event_hash != original.event_hash
    with pytest.raises(ValueError, match="event ID reused with a different event hash"):
        receiver.consume_inbox("consumer", conflicting_message, lambda *_: None, received_at=utc(9, 2), authenticator=trusted_authenticator)
    assert len(applied) == 1


def test_inbox_handler_cannot_mutate_receipt_identity_and_receipts_are_append_only(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender-handler-mutation.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver-handler-mutation.db"))
    stored = sender.append(event(), now=utc())
    message = {
        "message_id": "message-safe", "event_id": stored.event_id,
        "event_hash": stored.event_hash, "payload_json": json.dumps(
            {**stored.unsigned(), "event_hash": stored.event_hash},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
    }

    def mutate(db, incoming):
        incoming["event_id"] = "forged-event-id"
        incoming["payload_json"] = "{}"

    assert receiver.consume_inbox("consumer", message, mutate, received_at=utc(), authenticator=trusted_authenticator)
    assert not receiver.consume_inbox("consumer", {**message, "message_id": "message-replay"},
        lambda *_: None, received_at=utc(9, 1), authenticator=trusted_authenticator)
    with sqlite3.connect(receiver.database_path) as db:
        row = db.execute("SELECT event_id,event_hash FROM inbox").fetchone()
        assert row == (stored.event_id, stored.event_hash)
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE inbox SET event_id='forged' WHERE consumer='consumer'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("DELETE FROM inbox WHERE consumer='consumer'")



def test_inbox_requires_authentication_and_rejects_false_or_mutating_authenticators(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender-auth.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver-auth.db"))
    stored = sender.append(event(), now=utc())
    claimed = sender.claim_outbox(now=utc())[0]
    message = {
        "message_id": claimed.message_id,
        "event_id": claimed.event_id,
        "event_hash": claimed.event_hash,
        "payload_json": claimed.payload_json,
    }
    handler = lambda *_: None
    with pytest.raises(ValueError, match="trusted signed-message authenticator"):
        receiver.consume_inbox("consumer", message, handler, received_at=utc())
    with pytest.raises(ValueError, match="authentication failed"):
        receiver.consume_inbox(
            "consumer", message, handler, received_at=utc(),
            authenticator=lambda _: False,
        )

    def mutating_authenticator(snapshot):
        snapshot["event_hash"] = "f" * 64
        return True

    with pytest.raises(ValueError, match="mutated the signed message"):
        receiver.consume_inbox(
            "consumer", message, handler, received_at=utc(),
            authenticator=mutating_authenticator,
        )
    assert not receiver.inbox_contains("consumer", claimed.message_id)
    assert receiver.verify()



def test_inbox_authenticates_signed_publisher_with_trusted_key_registry(tmp_path):
    sender = DurableEventStore(str(tmp_path / "sender-signed.db"))
    receiver = DurableEventStore(str(tmp_path / "receiver-signed.db"))
    stored = sender.append(event(), now=utc())
    claimed = sender.claim_outbox(now=utc())[0]
    private_key, public_key = generate_ed25519_keypair()
    registry = TrustedKeyRegistry()
    registry.register_identity(FederationIdentity(
        "org:publisher", "tenant:publisher", "ORGANIZATION"
    ))
    registry.register_key(TrustedSigningKey(
        "org:publisher", "tenant:publisher", "publisher-key",
        ALGORITHM, public_key, "2026-01-01T00:00:00+00:00",
    ))
    signed = sign_event(
        stored, "org:publisher", "tenant:publisher", "publisher-key",
        private_key, "2026-11-06T09:01:00+00:00",
    )
    message = {
        "message_id": claimed.message_id,
        "event_id": claimed.event_id,
        "event_hash": claimed.event_hash,
        "payload_json": claimed.payload_json,
        "signed_envelope": signed.as_dict(),
    }

    def verify_publisher(incoming):
        identity = registry.verify(
            incoming["signed_envelope"], received_at="2026-11-06T09:02:00+00:00"
        )
        return identity.identity_id == "org:publisher"

    applied = []
    assert receiver.consume_inbox(
        "signed-consumer", message,
        lambda db, incoming: applied.append(incoming["event_id"]),
        received_at=utc(9, 2), authenticator=verify_publisher,
    )
    assert applied == [stored.event_id]
