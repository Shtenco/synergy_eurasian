from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_award_authorization import canonical_award_authorization_payload
from synergy_labor_award_registry import (
    AwardRegistryError,
    SLEAwardRegistry,
    issue_authorized_credit,
)
from synergy_labor_credit_ledger import LaborCreditLedger


NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def setup(database=":memory:"):
    ledger = LaborCreditLedger()
    ledger.register_issuer("issuer-a", "field-service", "service-hour", "100", "issuer-policy")
    ledger.add_capacity("issuer-a", "field-service", "service-hour", "capacity-a",
                        "50", "a" * 64, "independent-verifier", "capacity-a")
    registry = SLEAwardRegistry(database)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys = {
        "reward-key-1": {
            "principal_id": "reward-authorizer-1",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
    }
    return ledger, registry, private, keys


def signed_award(private, *, award_id="award-global-1",
                 contribution_id="contribution-global-1",
                 result_digest=None, expires_at="2026-12-01T00:00:00Z",
                 beneficiary_id="worker-b"):
    envelope = {
        "schema": "sle.award-authorization/v1",
        "award_id": award_id,
        "source_contribution_id": contribution_id,
        "result_digest": result_digest or hashlib.sha256(b"verified labor result").hexdigest(),
        "beneficiary_id": beneficiary_id,
        "issuer_id": "issuer-a",
        "service_code": "field-service",
        "unit": "service-hour",
        "quantity": "5",
        "capacity_id": "capacity-a",
        "policy_version": "SLE-AWARD-AUTH-ED25519-1.0",
        "budget_ref": "budget-cycle-2026",
        "issued_at": "2026-11-13T18:00:00Z",
        "expires_at": expires_at,
        "signer_id": "reward-authorizer-1",
        "signer_role": "REWARD_AUTHORIZER",
        "key_id": "reward-key-1",
    }
    envelope["signature"] = base64.b64encode(
        private.sign(canonical_award_authorization_payload(envelope))
    ).decode("ascii")
    return envelope


def close_all(ledger, registry):
    ledger.close()
    registry.close()


def test_global_reservation_is_idempotent_and_blocks_same_contribution_under_new_award_id():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    first = registry.reserve(envelope, keys, now=NOW)
    replay = registry.reserve(envelope, keys, now=NOW)
    assert first["status"] == "RESERVED"
    assert replay["idempotent_replay"] is True
    competing = signed_award(
        private, award_id="award-global-2",
        contribution_id="contribution-global-1",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(competing, keys, now=NOW)
    same_result = signed_award(
        private, award_id="award-global-3",
        contribution_id="contribution-global-3",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(same_result, keys, now=NOW)
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_shared_database_enforces_uniqueness_across_registry_instances(tmp_path):
    path = tmp_path / "shared-awards.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    first = signed_award(private)
    second = signed_award(
        private, award_id="award-other",
        contribution_id="contribution-global-1",
    )
    registry_a.reserve(first, keys, now=NOW)
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry_b.reserve(second, keys, now=NOW)
    assert registry_a.verify_event_chain()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_authorized_credit_issue_reserves_then_consumes_global_award():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    result = issue_authorized_credit(
        ledger, registry, envelope, keys, now=NOW,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    assert result["status"] == "ACTIVE"
    assert result["registry_status"] == "CONSUMED"
    award = registry.get_award("award-global-1")
    assert award["credit_id"] == "credit-global-1"
    assert award["ledger_event_id"]
    assert award["ledger_event_hash"]
    assert registry.verify_event_chain()["valid"] is True
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["valid"] is True
    close_all(ledger, registry)


def test_issue_retry_is_idempotent_and_does_not_consume_award_twice():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    args = dict(now=NOW, due_at="2030-01-01T00:00:00Z",
                credit_id="credit-global-1", idempotency_key="issue-global-1")
    first = issue_authorized_credit(ledger, registry, envelope, keys, **args)
    second = issue_authorized_credit(ledger, registry, envelope, keys, **args)
    assert first["credit_id"] == second["credit_id"]
    assert second["registry_status"] == "CONSUMED"
    assert ledger.verify_event_chain()["events_checked"] == 3
    assert registry.verify_projection_consistency()["valid"] is True
    assert registry.verify_authorization_history(keys)["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_crash_after_local_issue_is_reconciled_without_requiring_unexpired_authorization():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-before-crash",
    )
    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    recovered = issue_authorized_credit(
        ledger, registry, envelope, keys, now=after_expiry,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-before-crash",
    )
    assert recovered["reconciled_after_local_issue"] is True
    assert recovered["registry_status"] == "CONSUMED"
    assert ledger.verify_projection_consistency()["valid"] is True
    close_all(ledger, registry)


def test_reservation_is_not_released_or_reused_when_local_issue_never_happens():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    competing = signed_award(
        private, award_id="award-global-2",
        contribution_id="contribution-global-1",
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        registry.reserve(competing, keys, now=NOW)
    with pytest.raises(AwardRegistryError, match="outside its validity interval"):
        registry.reserve(envelope, keys, now=datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert registry.get_award("award-global-1")["status"] == "RESERVED"
    close_all(ledger, registry)


def test_registry_refuses_local_credit_with_mismatched_economic_terms():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "4", "2030-01-01T00:00:00Z", "credit-global-1", "wrong-units",
    )
    with pytest.raises(AwardRegistryError, match="issued_units"):
        registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    assert registry.get_award("award-global-1")["status"] == "RESERVED"
    close_all(ledger, registry)


def test_registry_projection_replay_detects_direct_record_tampering():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    registry._db.execute(
        "UPDATE awards SET status='CONSUMED' WHERE award_id='award-global-1'"
    )
    audit = registry.verify_projection_consistency()
    assert audit["valid"] is False
    assert "projection differs" in audit["issues"][0]
    with pytest.raises(AwardRegistryError, match="projection is inconsistent"):
        registry.reserve(signed_award(private), keys, now=NOW)
    close_all(ledger, registry)


def test_award_registry_record_matches_strict_schema():
    import jsonschema
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    record = registry.get_award("award-global-1")
    schema = json.loads(
        (ROOT / "interfaces" / "sle_award_registry_record.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(record, schema)
    close_all(ledger, registry)

def test_award_authorization_history_survives_later_key_revocation():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    keys["reward-key-1"]["revoked_at"] = "2026-11-15T00:00:00Z"
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is True
    assert audit["authorizations_checked"] == 1
    close_all(ledger, registry)


def test_award_authorization_history_detects_trusted_key_mismatch():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    replacement = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys["reward-key-1"]["public_key_b64"] = base64.b64encode(replacement).decode("ascii")
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is False
    assert "Ed25519 award authorization signature verification failed" in audit["issues"][0]
    close_all(ledger, registry)


def test_consumption_fails_closed_if_registry_projection_was_tampered():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-global-1",
    )
    registry._db.execute(
        "UPDATE awards SET status='CONSUMED' WHERE award_id='award-global-1'"
    )
    with pytest.raises(AwardRegistryError, match="projection is inconsistent"):
        registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    close_all(ledger, registry)


def test_registry_reconciles_original_issue_after_credit_is_transferred():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-before-transfer",
    )
    ledger.transfer("credit-global-1", "worker-b", "worker-c", 0, "transfer-before-reconcile")
    consumed = registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    assert consumed["status"] == "CONSUMED"
    assert ledger.get_credit("credit-global-1")["holder_id"] == "worker-c"
    assert registry.verify_projection_consistency()["valid"] is True
    close_all(ledger, registry)


def test_completed_issue_retry_after_authorization_expiry_is_idempotent():
    ledger, registry, private, keys = setup()
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    args = dict(
        due_at="2030-01-01T00:00:00Z",
        credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    first = issue_authorized_credit(
        ledger, registry, envelope, keys, now=NOW, **args
    )
    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    replay = issue_authorized_credit(
        ledger, registry, envelope, keys, now=after_expiry, **args
    )
    assert first["registry_status"] == "CONSUMED"
    assert replay["registry_status"] == "CONSUMED"
    assert replay["idempotent_replay"] is True
    assert replay["reconciled_after_local_issue"] is False
    assert ledger.verify_event_chain()["events_checked"] == 3
    close_all(ledger, registry)


def test_recovery_rejects_different_signed_envelope_for_existing_award_id():
    ledger, registry, private, keys = setup()
    original = signed_award(private)
    issue_authorized_credit(
        ledger, registry, original, keys, now=NOW,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
        idempotency_key="issue-global-1",
    )
    substituted = signed_award(private, beneficiary_id="attacker")
    with pytest.raises(AwardRegistryError, match="does not match"):
        issue_authorized_credit(
            ledger, registry, substituted, keys, now=NOW,
            due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
            idempotency_key="issue-global-1",
        )
    assert registry.get_award("award-global-1")["status"] == "CONSUMED"
    close_all(ledger, registry)


def test_award_authorization_history_detects_revocation_before_reservation_time():
    ledger, registry, private, keys = setup()
    registry.reserve(signed_award(private), keys, now=NOW)
    keys["reward-key-1"]["revoked_at"] = "2026-11-14T11:00:00Z"
    audit = registry.verify_authorization_history(keys)
    assert audit["valid"] is False
    assert "revoked" in audit["issues"][0]
    close_all(ledger, registry)

def test_concurrent_competing_reservations_across_connections_have_one_winner(tmp_path):
    path = tmp_path / "racing-awards.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    envelopes = [
        signed_award(private, award_id="award-race-a"),
        signed_award(private, award_id="award-race-b"),
    ]
    barrier = threading.Barrier(2)

    def reserve(registry, envelope):
        barrier.wait()
        try:
            return registry.reserve(envelope, keys, now=NOW)
        except AwardRegistryError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda pair: reserve(*pair),
            [(registry_a, envelopes[0]), (registry_b, envelopes[1])],
        ))

    winners = [result for result in results if isinstance(result, dict)]
    losers = [result for result in results if isinstance(result, AwardRegistryError)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert "already reserved" in str(losers[0])
    assert registry_a.verify_event_chain()["events_checked"] == 1
    assert registry_a.verify_projection_consistency()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_concurrent_identical_reservations_are_idempotent_across_connections(tmp_path):
    path = tmp_path / "racing-identical-awards.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    envelope = signed_award(private)
    barrier = __import__("threading").Barrier(2)

    def reserve(registry):
        barrier.wait()
        return registry.reserve(envelope, keys, now=NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [registry_a, registry_b]))

    assert all(result["status"] == "RESERVED" for result in results)
    assert sorted(result["idempotent_replay"] for result in results) == [False, True]
    assert registry_a.verify_event_chain()["events_checked"] == 1
    assert registry_a.verify_projection_consistency()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_concurrent_consumption_is_single_transition_and_idempotent_replay(tmp_path):
    path = tmp_path / "racing-consume.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    envelope = signed_award(private)
    registry_a.reserve(envelope, keys, now=NOW)
    ledger.issue(
        "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
        envelope["result_digest"], "field-service", "service-hour", "capacity-a",
        "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-before-racing-consume",
    )
    barrier = __import__("threading").Barrier(2)

    def consume(registry):
        barrier.wait()
        return registry.consume_from_ledger(
            "award-global-1", ledger, "credit-global-1"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, [registry_a, registry_b]))

    assert sorted(result["idempotent_replay"] for result in results) == [False, True]
    award = registry_a.get_award("award-global-1")
    assert award["status"] == "CONSUMED"
    assert award["credit_id"] == "credit-global-1"
    assert registry_a.verify_event_chain()["events_checked"] == 2
    assert registry_a.verify_projection_consistency()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)

@pytest.mark.parametrize("timestamp_field", ["reserved_at", "consumed_at"])
def test_registry_projection_replay_detects_timestamp_tampering(tmp_path, timestamp_field):
    ledger, registry, private, keys = setup(tmp_path / f"timestamp-{timestamp_field}.sqlite")
    envelope = signed_award(private)
    registry.reserve(envelope, keys, now=NOW)
    if timestamp_field == "consumed_at":
        ledger.issue(
            "issuer-a", "worker-b", "contribution-global-1", "award-global-1",
            envelope["result_digest"], "field-service", "service-hour", "capacity-a",
            "5", "2030-01-01T00:00:00Z", "credit-global-1", "issue-for-timestamp-audit",
        )
        registry.consume_from_ledger("award-global-1", ledger, "credit-global-1")
    registry._db.execute(
        f"UPDATE awards SET {timestamp_field}='2099-01-01T00:00:00+00:00' "
        "WHERE award_id='award-global-1'"
    )
    audit = registry.verify_projection_consistency()
    assert audit["valid"] is False
    assert "projection differs" in audit["issues"][0]
    close_all(ledger, registry)

def test_registry_honors_configured_sqlite_busy_timeout():
    registry = SLEAwardRegistry(timeout=0.125)
    assert registry._db.execute("PRAGMA busy_timeout").fetchone()[0] == 125
    registry.close()


@pytest.mark.parametrize("timeout", [True, -0.1, float("nan"), float("inf"), "1", 2_147_483.648, 10 ** 1000])
def test_registry_rejects_invalid_busy_timeout(timeout):
    with pytest.raises(ValueError, match="timeout must be a finite number"):
        SLEAwardRegistry(timeout=timeout)


def test_concurrent_identical_end_to_end_issuance_creates_one_credit_event(tmp_path):
    path = tmp_path / "racing-end-to-end.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    envelope = signed_award(private)
    barrier = threading.Barrier(2)

    def issue(registry):
        barrier.wait()
        return issue_authorized_credit(
            ledger, registry, envelope, keys, now=NOW,
            due_at="2030-01-01T00:00:00Z", credit_id="credit-global-1",
            idempotency_key="issue-global-race",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(issue, [registry_a, registry_b]))

    assert {result["credit_id"] for result in results} == {"credit-global-1"}
    assert {result["registry_status"] for result in results} == {"CONSUMED"}
    assert ledger.verify_event_chain()["events_checked"] == 3
    assert registry_a.verify_event_chain()["events_checked"] == 2
    assert registry_a.get_award("award-global-1")["status"] == "CONSUMED"
    assert registry_a.verify_projection_consistency()["valid"] is True
    assert ledger.verify_projection_consistency()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_concurrent_competing_end_to_end_issuance_cannot_double_award(tmp_path):
    path = tmp_path / "racing-end-to-end-conflict.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    envelopes = [
        signed_award(private, award_id="award-race-a"),
        signed_award(private, award_id="award-race-b"),
    ]
    barrier = threading.Barrier(2)

    def issue(pair):
        registry, envelope = pair
        barrier.wait()
        try:
            return issue_authorized_credit(
                ledger, registry, envelope, keys, now=NOW,
                due_at="2030-01-01T00:00:00Z",
                credit_id="credit-" + envelope["award_id"],
                idempotency_key="issue-" + envelope["award_id"],
            )
        except AwardRegistryError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(issue, [(registry_a, envelopes[0]), (registry_b, envelopes[1])]))

    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, AwardRegistryError) for result in results) == 1
    assert ledger.verify_event_chain()["events_checked"] == 3
    assert registry_a.verify_event_chain()["events_checked"] == 2
    assert registry_a.verify_projection_consistency()["valid"] is True
    assert ledger.verify_projection_consistency()["valid"] is True
    registry_b.close()
    close_all(ledger, registry_a)


def test_registry_lock_timeout_fails_closed_while_another_connection_holds_write_lock(tmp_path):
    path = tmp_path / "locked-awards.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path, timeout=0)
    registry_a._db.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            registry_b.reserve(signed_award(private), keys, now=NOW)
        assert registry_a._db.execute("SELECT COUNT(*) FROM awards").fetchone()[0] == 0
        assert registry_a._db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    finally:
        registry_a._db.execute("ROLLBACK")
    registry_b.close()
    close_all(ledger, registry_a)


def test_public_event_audit_uses_one_snapshot_during_concurrent_commit(tmp_path):
    path = tmp_path / "audit-snapshot.sqlite"
    ledger, registry_a, private, keys = setup(path)
    registry_b = SLEAwardRegistry(path)
    registry_a.reserve(signed_award(private), keys, now=NOW)

    entered_head = threading.Event()
    release_head = threading.Event()
    original_head = registry_a._head

    def delayed_head():
        entered_head.set()
        if not release_head.wait(timeout=5):
            raise RuntimeError("test synchronization timed out")
        return original_head()

    registry_a._head = delayed_head
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            audit_future = pool.submit(registry_a.verify_event_chain)
            assert entered_head.wait(timeout=5)
            write_future = pool.submit(
                registry_b.reserve,
                signed_award(private, award_id="award-snapshot-2",
                             contribution_id="contribution-snapshot-2",
                             result_digest=hashlib.sha256(b"second result").hexdigest()),
                keys,
                now=NOW,
            )
            try:
                write_future.result(timeout=5)
            finally:
                release_head.set()
            audit = audit_future.result(timeout=5)
        assert audit["valid"] is True
        assert audit["events_checked"] == 1
        assert registry_a.verify_event_chain()["events_checked"] == 2
        assert registry_a.verify_projection_consistency()["valid"] is True
    finally:
        release_head.set()
        registry_a._head = original_head
        registry_b.close()
        close_all(ledger, registry_a)



def _reserve_award_in_separate_process(database, envelope, key_registry, barrier, result_queue):
    """Process entry point: exercise SQLite coordination without shared Python locks."""
    registry = SLEAwardRegistry(database, timeout=10)
    try:
        barrier.wait(timeout=15)
        try:
            result = registry.reserve(
                envelope, key_registry,
                now=datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc),
            )
            result_queue.put(("reserved", result["award_id"]))
        except AwardRegistryError as exc:
            result_queue.put(("rejected", str(exc)))
    finally:
        registry.close()


def test_separate_processes_cannot_reserve_one_contribution_twice(tmp_path):
    """SQLite uniqueness must hold across OS processes, not just threads/connections."""
    import multiprocessing

    path = tmp_path / "multiprocess-awards.sqlite"
    _, registry, private, keys = setup(path)
    envelopes = [
        signed_award(private, award_id="award-process-a"),
        signed_award(private, award_id="award-process-b"),
    ]
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_reserve_award_in_separate_process,
            args=(str(path), envelope, keys, barrier, result_queue),
        )
        for envelope in envelopes
    ]
    try:
        for process in processes:
            process.start()
        results = [result_queue.get(timeout=25) for _ in processes]
        for process in processes:
            process.join(timeout=25)
            assert process.exitcode == 0
        assert sum(result[0] == "reserved" for result in results) == 1
        assert sum(result[0] == "rejected" for result in results) == 1
        rejected = next(result[1] for result in results if result[0] == "rejected")
        assert "already reserved" in rejected
        assert registry.verify_event_chain()["events_checked"] == 1
        assert registry.verify_projection_consistency()["valid"] is True
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        result_queue.close()
        close_all(_, registry)


def _crash_after_durable_local_issue(
    registry_path, ledger_path, envelope, key_registry, credit_id, idempotency_key,
):
    """Commit reservation and local issue, then simulate abrupt process death."""
    import os

    registry = SLEAwardRegistry(registry_path)
    ledger = LaborCreditLedger(ledger_path)
    registry.reserve(
        envelope, key_registry,
        now=datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc),
    )
    ledger.issue(
        "issuer-a", envelope["beneficiary_id"], envelope["source_contribution_id"],
        envelope["award_id"], envelope["result_digest"], envelope["service_code"],
        envelope["unit"], envelope["capacity_id"], envelope["quantity"],
        "2030-01-01T00:00:00Z", credit_id, idempotency_key,
    )
    # Both APIs have committed their own SQLite transactions. Do not run Python
    # cleanup handlers: this models SIGKILL/power-loss timing after local issuance.
    os._exit(73)


def test_process_death_after_local_issue_recovers_from_reopened_wal_databases(tmp_path):
    """A hard process exit between the two DB commits must not duplicate an award."""
    import multiprocessing

    registry_path = tmp_path / "crash-recovery-registry.sqlite"
    ledger_path = tmp_path / "crash-recovery-ledger.sqlite"
    ledger = LaborCreditLedger(ledger_path)
    ledger.register_issuer(
        "issuer-a", "field-service", "service-hour", "100", "issuer-policy"
    )
    ledger.add_capacity(
        "issuer-a", "field-service", "service-hour", "capacity-a",
        "50", "a" * 64, "independent-verifier", "capacity-a",
    )
    ledger.close()

    registry = SLEAwardRegistry(registry_path)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys = {
        "reward-key-1": {
            "principal_id": "reward-authorizer-1",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
    }
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    registry.close()

    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_crash_after_durable_local_issue,
        args=(
            str(registry_path), str(ledger_path), envelope, keys,
            "credit-crash-recovery", "issue-crash-recovery",
        ),
    )
    process.start()
    process.join(timeout=25)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("crash simulation process did not terminate")
    assert process.exitcode == 73

    # Reopen both WAL databases in a fresh process context after the unclean exit.
    recovered_registry = SLEAwardRegistry(registry_path)
    recovered_ledger = LaborCreditLedger(ledger_path)
    award_before = recovered_registry.get_award("award-global-1")
    assert award_before["status"] == "RESERVED"
    assert recovered_ledger.get_credit("credit-crash-recovery")["status"] == "ACTIVE"
    assert recovered_registry.verify_event_chain()["valid"] is True
    assert recovered_registry.verify_projection_consistency()["valid"] is True
    assert recovered_ledger.verify_event_chain()["valid"] is True
    assert recovered_ledger.verify_projection_consistency()["valid"] is True

    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    result = issue_authorized_credit(
        recovered_ledger, recovered_registry, envelope, keys,
        now=after_expiry, due_at="2030-01-01T00:00:00Z",
        credit_id="credit-crash-recovery", idempotency_key="issue-crash-recovery",
    )
    assert result["registry_status"] == "CONSUMED"
    assert result["reconciled_after_local_issue"] is True
    assert recovered_ledger.verify_event_chain()["events_checked"] == 3
    assert recovered_registry.verify_event_chain()["events_checked"] == 2
    assert recovered_registry.verify_projection_consistency()["valid"] is True
    assert recovered_ledger.verify_projection_consistency()["valid"] is True

    # A further retry after recovery is a replay, not a second credit/event.
    replay = issue_authorized_credit(
        recovered_ledger, recovered_registry, envelope, keys,
        now=after_expiry, due_at="2030-01-01T00:00:00Z",
        credit_id="credit-crash-recovery", idempotency_key="issue-crash-recovery",
    )
    assert replay["registry_status"] == "CONSUMED"
    assert replay["idempotent_replay"] is True
    assert recovered_ledger.verify_event_chain()["events_checked"] == 3
    assert recovered_registry.verify_event_chain()["events_checked"] == 2
    close_all(recovered_ledger, recovered_registry)


def _crash_after_reservation_before_local_issue(
    registry_path, envelope, key_registry,
):
    """Commit only the global reservation and terminate before local issuance."""
    import os

    registry = SLEAwardRegistry(registry_path)
    registry.reserve(
        envelope, key_registry,
        now=datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc),
    )
    os._exit(74)


def test_process_death_after_reservation_keeps_award_locked_fail_closed(tmp_path):
    """An expired stranded reservation cannot be silently released or re-awarded."""
    import multiprocessing

    registry_path = tmp_path / "stranded-reservation.sqlite"
    registry = SLEAwardRegistry(registry_path)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys = {
        "reward-key-1": {
            "principal_id": "reward-authorizer-1",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
    }
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    registry.close()

    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_crash_after_reservation_before_local_issue,
        args=(str(registry_path), envelope, keys),
    )
    process.start()
    process.join(timeout=25)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("reservation crash simulation process did not terminate")
    assert process.exitcode == 74

    recovered = SLEAwardRegistry(registry_path)
    ledger = LaborCreditLedger()
    after_expiry = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(AwardRegistryError):
        issue_authorized_credit(
            ledger, recovered, envelope, keys, now=after_expiry,
            due_at="2030-01-01T00:00:00Z", credit_id="never-issued-credit",
            idempotency_key="never-issued-request",
        )
    assert recovered.get_award("award-global-1")["status"] == "RESERVED"
    assert ledger.verify_event_chain()["events_checked"] == 0
    assert recovered.verify_event_chain()["events_checked"] == 1
    assert recovered.verify_projection_consistency()["valid"] is True

    competing = signed_award(
        private, award_id="award-after-stranded",
        contribution_id="contribution-global-1",
        result_digest=hashlib.sha256(b"different attempted award").hexdigest(),
    )
    with pytest.raises(AwardRegistryError, match="already reserved"):
        recovered.reserve(competing, keys, now=after_expiry)
    assert recovered.verify_event_chain()["events_checked"] == 1
    assert recovered.verify_projection_consistency()["valid"] is True
    close_all(ledger, recovered)



def test_sqlite_online_backups_restore_registry_and_ledger_for_idempotent_recovery(tmp_path):
    """SQLite's backup API must preserve committed WAL state across restore."""
    source_registry = tmp_path / "source-registry.sqlite"
    source_ledger = tmp_path / "source-ledger.sqlite"
    backup_registry = tmp_path / "backup-registry.sqlite"
    backup_ledger = tmp_path / "backup-ledger.sqlite"

    ledger = LaborCreditLedger(source_ledger)
    ledger.register_issuer(
        "issuer-a", "field-service", "service-hour", "100", "issuer-policy"
    )
    ledger.add_capacity(
        "issuer-a", "field-service", "service-hour", "capacity-a",
        "50", "a" * 64, "independent-verifier", "capacity-a",
    )
    registry = SLEAwardRegistry(source_registry)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keys = {
        "reward-key-1": {
            "principal_id": "reward-authorizer-1",
            "roles": ["REWARD_AUTHORIZER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
    }
    envelope = signed_award(private, expires_at="2026-11-15T00:00:00Z")
    issued = issue_authorized_credit(
        ledger, registry, envelope, keys, now=NOW,
        due_at="2030-01-01T00:00:00Z", credit_id="credit-backup",
        idempotency_key="issue-backup",
    )
    assert issued["registry_status"] == "CONSUMED"

    # The online backup API includes committed WAL pages; copying only the main
    # database file while WAL is active is deliberately not used here.
    for source, target in (
        (registry._db, backup_registry),
        (ledger._db, backup_ledger),
    ):
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()

    close_all(ledger, registry)
    restored_registry = SLEAwardRegistry(backup_registry)
    restored_ledger = LaborCreditLedger(backup_ledger)
    try:
        assert restored_registry.get_award("award-global-1")["status"] == "CONSUMED"
        assert restored_registry.verify_event_chain()["valid"] is True
        assert restored_registry.verify_projection_consistency()["valid"] is True
        assert restored_registry.verify_authorization_history(keys)["valid"] is True
        assert restored_ledger.get_credit("credit-backup")["status"] == "ACTIVE"
        assert restored_ledger.verify_event_chain()["valid"] is True
        assert restored_ledger.verify_projection_consistency()["valid"] is True

        replay = issue_authorized_credit(
            restored_ledger, restored_registry, envelope, keys,
            now=datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc),
            due_at="2030-01-01T00:00:00Z", credit_id="credit-backup",
            idempotency_key="issue-backup",
        )
        assert replay["registry_status"] == "CONSUMED"
        assert replay["idempotent_replay"] is True
        assert restored_ledger.verify_event_chain()["events_checked"] == 3
        assert restored_registry.verify_event_chain()["events_checked"] == 2
        assert restored_registry.verify_projection_consistency()["valid"] is True
        assert restored_ledger.verify_projection_consistency()["valid"] is True
    finally:
        close_all(restored_ledger, restored_registry)
