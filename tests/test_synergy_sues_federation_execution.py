from dataclasses import dataclass
import json
from datetime import datetime, timezone
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest

from synergy_sues.event_transport import DurableEventStore
from synergy_sues.federation_identity import (
    ALGORITHM, FederationIdentity, TrustedKeyRegistry, TrustedSigningKey,
    generate_ed25519_keypair, sign_event,
)
from synergy_sues.federation_authorization import AuthorizationRule, FederationAuthorizationPolicy
from synergy_sues.federation_execution import AuthorizedActionExecutor


@dataclass(frozen=True)
class Event:
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


def setup(tmp_path):
    registry = TrustedKeyRegistry()
    keys = {}
    for identity_id in ("org:requester", "org:approver"):
        private, public = generate_ed25519_keypair()
        keys[identity_id] = private
        registry.register_identity(FederationIdentity(identity_id, "tenant:one", "ORGANIZATION"))
        registry.register_key(TrustedSigningKey(identity_id, "tenant:one", "key-1",
            ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    policy = FederationAuthorizationPolicy()
    policy.register_rule(AuthorizationRule("rule:execute", "tenant:one", "ALLOW",
        "JOURNAL_POST", "LEDGER", ("org:requester",), ("org:approver",), 1, "ledger:alpha"))
    return registry, keys, policy


def make_event(tmp_path, suffix, event_type, payload, identity, key, signed_at):
    event_id = "event:" + suffix
    source = Event(event_id, "AUTHORIZATION", payload.get("request_id", suffix), 1,
        event_type, "2026-11-06T09:00:00+00:00", "2026-11-06T09:01:00+00:00",
        payload, "source:" + event_id, ("evidence:" + suffix,), "idem:" + suffix)
    stored = DurableEventStore(str(tmp_path / (suffix + ".db"))).append(
        source, now=datetime(2026, 11, 6, 9, 1, tzinfo=timezone.utc))
    return sign_event(stored, identity, "tenant:one", "key-1", key, signed_at)


def make_pair(tmp_path, keys, request_id="req-1", suffix="one"):
    request_payload = {"request_id": request_id, "action": "JOURNAL_POST",
        "resource_type": "LEDGER", "resource_id": "ledger:alpha"}
    request = make_event(tmp_path, "request-" + suffix, "AUTHORIZATION_REQUEST",
        request_payload, "org:requester", keys["org:requester"], "2026-11-06T10:00:00+00:00")
    approval_payload = {"request_id": request_id, "request_event_id": request.event["event_id"],
        "request_event_hash": request.event["event_hash"], "action": "JOURNAL_POST",
        "resource_type": "LEDGER", "resource_id": "ledger:alpha",
        "requester_identity_id": "org:requester", "decision": "APPROVE"}
    approval = make_event(tmp_path, "approval-" + suffix, "AUTHORIZATION_APPROVAL",
        approval_payload, "org:approver", keys["org:approver"], "2026-11-06T10:01:00+00:00")
    return request, approval


def now():
    return "2026-11-06T10:02:00+00:00"


def insert_effect(db, request, decision):
    db.execute("CREATE TABLE IF NOT EXISTS protected_effects (request_id TEXT NOT NULL)")
    db.execute("INSERT INTO protected_effects VALUES(?)", (request.event["payload"]["request_id"],))
    return {"accepted": True, "effect": "local_sql_commit"}


def test_executor_consumes_request_once_and_commits_receipt_with_effect(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    executor = AuthorizedActionExecutor(str(tmp_path / "executor.db"))
    first = executor.execute(request, [approval], policy, registry, insert_effect, now())
    second = executor.execute(request, [approval], policy, registry, insert_effect, now())
    assert first.executed and first.status == "EXECUTED"
    assert first.result == {"accepted": True, "effect": "local_sql_commit"}
    assert not second.executed and second.status == "ALREADY_EXECUTED"
    with sqlite3.connect(tmp_path / "executor.db") as db:
        assert db.execute("SELECT COUNT(*) FROM protected_effects").fetchone()[0] == 1
    assert len(executor.receipts()) == 1
    decision_record = json.loads(executor.receipts()[0]["decision_json"])
    assert decision_record["approval_identity_ids"] == ["org:approver"]
    assert decision_record["approval_event_refs"] == [[approval.event["event_id"], approval.event["event_hash"]]]
    assert executor.verify()


def test_executor_rejects_request_id_reuse_with_different_event_hash(tmp_path):
    registry, keys, policy = setup(tmp_path)
    first, first_approval = make_pair(tmp_path, keys, "req-reuse", "first")
    second, second_approval = make_pair(tmp_path, keys, "req-reuse", "second")
    executor = AuthorizedActionExecutor(str(tmp_path / "executor.db"))
    assert executor.execute(first, [first_approval], policy, registry, insert_effect, now()).executed
    with pytest.raises(ValueError, match="different signed event hash"):
        executor.execute(second, [second_approval], policy, registry, insert_effect, now())
    with sqlite3.connect(tmp_path / "executor.db") as db:
        assert db.execute("SELECT COUNT(*) FROM protected_effects").fetchone()[0] == 1


def test_denied_request_never_calls_handler_or_creates_receipt(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, _ = make_pair(tmp_path, keys)
    executor = AuthorizedActionExecutor(str(tmp_path / "executor.db"))
    called = []
    result = executor.execute(request, [], policy, registry,
        lambda *_: called.append(True), now())
    assert not result.executed and result.status == "DENIED"
    assert called == []
    assert executor.receipts() == ()


def test_handler_failure_rolls_back_effect_and_request_consumption(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    executor = AuthorizedActionExecutor(str(tmp_path / "executor.db"))

    def failing(db, request, decision):
        db.execute("CREATE TABLE IF NOT EXISTS protected_effects (request_id TEXT)")
        db.execute("INSERT INTO protected_effects VALUES('partial')")
        AuthorizedActionExecutor.enqueue_outbox(db, "idem:external", "PAY_SYSTEM", "PAYMENT_RELEASE",
            {"payment_id": "p-1"})
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        executor.execute(request, [approval], policy, registry, failing, now())
    assert executor.receipts() == ()
    with sqlite3.connect(tmp_path / "executor.db") as db:
        assert db.execute("SELECT COUNT(*) FROM execution_outbox").fetchone()[0] == 0
    assert executor.execute(request, [approval], policy, registry, insert_effect, now()).executed
    with sqlite3.connect(tmp_path / "executor.db") as db:
        assert db.execute("SELECT COUNT(*) FROM protected_effects").fetchone()[0] == 1


def test_concurrent_executor_instances_commit_only_one_effect(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    path = str(tmp_path / "executor.db")
    executors = [AuthorizedActionExecutor(path), AuthorizedActionExecutor(path)]
    def invoke(executor):
        return executor.execute(request, [approval], policy, registry, insert_effect, now())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, executors))
    assert sum(result.executed for result in results) == 1
    assert sum(result.status == "ALREADY_EXECUTED" for result in results) == 1
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM protected_effects").fetchone()[0] == 1
    assert executors[0].verify()


def test_execution_receipts_are_append_only_and_hash_chained(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    path = str(tmp_path / "executor.db")
    executor = AuthorizedActionExecutor(path)
    assert executor.execute(request, [approval], policy, registry, insert_effect, now()).executed
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE execution_receipts SET action='FORGED' WHERE sequence=1")
        db.execute("DROP TRIGGER execution_receipts_no_update")
        db.execute("UPDATE execution_receipts SET action='FORGED' WHERE sequence=1")
    with pytest.raises(ValueError, match="chain verification"):
        AuthorizedActionExecutor(path)


def test_executor_requires_file_backed_database_and_json_safe_result(tmp_path):
    with pytest.raises(ValueError, match="file-backed"):
        AuthorizedActionExecutor(":memory:")
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    executor = AuthorizedActionExecutor(str(tmp_path / "executor.db"))
    with pytest.raises(ValueError):
        executor.execute(request, [approval], policy, registry,
            lambda *_: float("nan"), now())
    assert executor.receipts() == ()


def test_external_intent_is_transactionally_enqueued_and_idempotent(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    path = str(tmp_path / "executor.db")
    executor = AuthorizedActionExecutor(path)

    def handler(db, request, decision):
        payload = {"payment_id": "p-1", "amount": "10.00", "currency": "USD"}
        first = AuthorizedActionExecutor.enqueue_outbox(
            db, "idem:payment:p-1", "PAY_SYSTEM", "PAYMENT_RELEASE", payload)
        second = AuthorizedActionExecutor.enqueue_outbox(
            db, "idem:payment:p-1", "PAY_SYSTEM", "PAYMENT_RELEASE", payload)
        assert first == second
        return {"outbox_message_id": first}

    result = executor.execute(request, [approval], policy, registry, handler, now())
    assert result.executed
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT message_id,status,payload_json FROM execution_outbox").fetchone()
    assert row[1] == "PENDING"
    assert '"payment_id":"p-1"' in row[2]


def test_outbox_idempotency_conflict_rolls_back_protected_action(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    path = str(tmp_path / "executor.db")
    executor = AuthorizedActionExecutor(path)

    def conflicting(db, request, decision):
        AuthorizedActionExecutor.enqueue_outbox(db, "idem:one", "PAY_SYSTEM",
            "PAYMENT_RELEASE", {"payment_id": "p-1"})
        AuthorizedActionExecutor.enqueue_outbox(db, "idem:one", "PAY_SYSTEM",
            "PAYMENT_RELEASE", {"payment_id": "p-2"})
        return {"unexpected": True}

    with pytest.raises(ValueError, match="different payload"):
        executor.execute(request, [approval], policy, registry, conflicting, now())
    assert executor.receipts() == ()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM execution_outbox").fetchone()[0] == 0


def test_outbox_payload_is_immutable_while_delivery_state_can_advance(tmp_path):
    registry, keys, policy = setup(tmp_path)
    request, approval = make_pair(tmp_path, keys)
    path = str(tmp_path / "executor.db")
    executor = AuthorizedActionExecutor(path)

    def handler(db, request, decision):
        return {"message_id": AuthorizedActionExecutor.enqueue_outbox(
            db, "idem:immutable", "META_BANK", "TRANSFER", {"transfer_id": "t-1"})}

    executor.execute(request, [approval], policy, registry, handler, now())
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
            db.execute("UPDATE execution_outbox SET payload_json='{}'")
        db.execute("UPDATE execution_outbox SET status='DELIVERED', attempts=1")
        assert db.execute("SELECT status,attempts FROM execution_outbox").fetchone() == ("DELIVERED", 1)
