from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import pytest

from synergy_sues.event_transport import DurableEventStore
from synergy_sues.federation_identity import (
    ALGORITHM, FederationIdentity, TrustedKeyRegistry, TrustedSigningKey,
    generate_ed25519_keypair, sign_event,
)
from synergy_sues.federation_authorization import AuthorizationRule
from synergy_sues.federation_policy_store import SQLiteAuthorizationPolicyStore


@dataclass(frozen=True)
class PolicyEvent:
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
    identities = ("admin:proposer", "admin:one", "admin:two", "admin:three", "user:operator")
    for identity_id in identities:
        private, public = generate_ed25519_keypair()
        keys[identity_id] = private
        registry.register_identity(FederationIdentity(identity_id, "tenant:one", "ORGANIZATION"))
        registry.register_key(TrustedSigningKey(identity_id, "tenant:one", "key-1",
            ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    store = SQLiteAuthorizationPolicyStore(
        str(tmp_path / "policy.db"),
        {"tenant:one": ("admin:proposer", "admin:one", "admin:two", "admin:three")},
    )
    return store, registry, keys


def make_signed(tmp_path, registry_keys, identity_id, event_type, payload, suffix, signed_at):
    event_id = "event:" + suffix
    source = PolicyEvent(event_id, "AUTHORIZATION_POLICY", payload.get("change_id", suffix),
        1, event_type, "2026-11-06T09:00:00+00:00", "2026-11-06T09:01:00+00:00",
        payload, "source:" + event_id, ("evidence:" + suffix,), "idem:" + suffix)
    stored = DurableEventStore(str(tmp_path / (suffix + ".db"))).append(
        source, now=datetime(2026, 11, 6, 9, 1, tzinfo=timezone.utc))
    return sign_event(stored, identity_id, "tenant:one", "key-1",
        registry_keys[identity_id], signed_at)


def rule_document(rule_id="rule:journal"):
    return {
        "rule_id": rule_id,
        "tenant_id": "tenant:one",
        "effect": "ALLOW",
        "action": "JOURNAL_POST",
        "resource_type": "LEDGER",
        "subject_ids": ["user:operator"],
        "approver_ids": ["admin:one"],
        "min_approvals": 0,
        "resource_id": "ledger:alpha",
        "valid_from": "2026-01-01T00:00:00+00:00",
        "valid_until": None,
    }


def make_change(tmp_path, keys, change_id="change:one", expected_version=0,
                operation="UPSERT_RULE", suffix="one", rule=None, rule_id="rule:journal",
                approver_ids=("admin:one", "admin:two"), decisions=None):
    payload = {
        "change_id": change_id,
        "tenant_id": "tenant:one",
        "expected_version": expected_version,
        "operation": operation,
    }
    if operation == "UPSERT_RULE":
        payload["rule"] = rule or rule_document(rule_id)
    else:
        payload["rule_id"] = rule_id
    request = make_signed(tmp_path, keys, "admin:proposer",
        "AUTHORIZATION_POLICY_CHANGE", payload, "change-request-" + suffix,
        "2026-11-06T10:00:00+00:00")
    approvals = []
    for index, identity_id in enumerate(approver_ids):
        approval_payload = {
            "change_id": change_id,
            "tenant_id": "tenant:one",
            "expected_version": expected_version,
            "policy_change_event_id": request.event["event_id"],
            "policy_change_event_hash": request.event["event_hash"],
            "decision": (decisions or {}).get(identity_id, "APPROVE"),
        }
        approvals.append(make_signed(tmp_path, keys, identity_id,
            "AUTHORIZATION_POLICY_APPROVAL", approval_payload,
            "approval-" + suffix + "-" + str(index),
            "2026-11-06T10:01:00+00:00"))
    return request, approvals


def test_two_person_signed_change_persists_and_loads_exact_policy(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys)
    result = store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")
    assert result.applied and result.status == "APPLIED" and result.version == 1
    snapshot = store.snapshot("tenant:one")
    assert snapshot.version == 1
    assert snapshot.policy_hash == result.policy_hash
    assert snapshot.rules[0].rule_id == "rule:journal"
    reopened = SQLiteAuthorizationPolicyStore(str(tmp_path / "policy.db"),
        {"tenant:one": ("admin:proposer", "admin:one", "admin:two", "admin:three")})
    assert reopened.snapshot("tenant:one") == snapshot
    assert reopened.verify()


def test_same_change_replay_is_idempotent_but_change_id_collision_is_rejected(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys)
    first = store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")
    replay = store.apply_change(request, approvals, registry, "2026-11-06T10:03:00+00:00")
    assert first.applied and not replay.applied and replay.status == "ALREADY_APPLIED"
    other, other_approvals = make_change(tmp_path, keys, suffix="collision")
    with pytest.raises(ValueError, match="change_id reused"):
        store.apply_change(other, other_approvals, registry, "2026-11-06T10:03:00+00:00")
    assert store.snapshot("tenant:one").version == 1


def test_change_requires_two_distinct_independent_admin_approvals(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, one_approval = make_change(tmp_path, keys, approver_ids=("admin:one",))
    with pytest.raises(ValueError, match="quorum"):
        store.apply_change(request, one_approval, registry, "2026-11-06T10:02:00+00:00")
    self_approval = make_signed(tmp_path, keys, "admin:proposer",
        "AUTHORIZATION_POLICY_APPROVAL", {
            "change_id": "change:self", "tenant_id": "tenant:one", "expected_version": 0,
            "policy_change_event_id": request.event["event_id"],
            "policy_change_event_hash": request.event["event_hash"], "decision": "APPROVE",
        }, "self-approval", "2026-11-06T10:01:00+00:00")
    with pytest.raises(ValueError, match="quorum"):
        store.apply_change(request, [one_approval[0], self_approval],
            registry, "2026-11-06T10:02:00+00:00")


def test_non_allowlisted_proposer_and_cross_tenant_rule_are_rejected(tmp_path):
    store, registry, keys = setup(tmp_path)
    payload = {"change_id": "bad", "tenant_id": "tenant:one",
        "expected_version": 0, "operation": "UPSERT_RULE", "rule": rule_document()}
    request = make_signed(tmp_path, keys, "user:operator",
        "AUTHORIZATION_POLICY_CHANGE", payload, "nonadmin", "2026-11-06T10:00:00+00:00")
    with pytest.raises(ValueError, match="administrator allowlist"):
        store.apply_change(request, [], registry, "2026-11-06T10:02:00+00:00")
    foreign_rule = rule_document()
    foreign_rule["tenant_id"] = "tenant:other"
    request, approvals = make_change(tmp_path, keys, suffix="foreign", rule=foreign_rule)
    with pytest.raises(ValueError, match="rule tenant"):
        store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")


def test_approval_is_cryptographically_bound_to_exact_change_event(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys)
    other_request, _ = make_change(tmp_path, keys, suffix="other")
    # Signatures are valid, but these approvals refer to the other request event.
    payloads = []
    for i, identity in enumerate(("admin:one", "admin:two")):
        payload = {
            "change_id": "change:one", "tenant_id": "tenant:one", "expected_version": 0,
            "policy_change_event_id": other_request.event["event_id"],
            "policy_change_event_hash": other_request.event["event_hash"], "decision": "APPROVE",
        }
        payloads.append(make_signed(tmp_path, keys, identity,
            "AUTHORIZATION_POLICY_APPROVAL", payload, "wrong-binding-" + str(i),
            "2026-11-06T10:01:00+00:00"))
    with pytest.raises(ValueError, match="quorum"):
        store.apply_change(request, payloads, registry, "2026-11-06T10:02:00+00:00")


def test_authorized_admin_veto_blocks_policy_mutation(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys,
        decisions={"admin:two": "REJECT"})
    with pytest.raises(ValueError, match="vetoed"):
        store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")
    assert store.snapshot("tenant:one").version == 0


def test_expected_version_compare_and_swap_and_rule_revocation(tmp_path):
    store, registry, keys = setup(tmp_path)
    first, first_approvals = make_change(tmp_path, keys, suffix="first")
    store.apply_change(first, first_approvals, registry, "2026-11-06T10:02:00+00:00")
    stale, stale_approvals = make_change(tmp_path, keys, change_id="change:stale",
        suffix="stale", expected_version=0, rule_id="rule:stale")
    with pytest.raises(ValueError, match="stale policy version"):
        store.apply_change(stale, stale_approvals, registry, "2026-11-06T10:02:00+00:00")
    revoke, revoke_approvals = make_change(tmp_path, keys, change_id="change:revoke",
        expected_version=1, operation="REVOKE_RULE", suffix="revoke")
    result = store.apply_change(revoke, revoke_approvals, registry, "2026-11-06T10:02:00+00:00")
    assert result.version == 2
    assert store.snapshot("tenant:one").rules == ()
    assert store.verify()


def test_concurrent_changes_with_same_expected_version_only_one_wins(tmp_path):
    store, registry, keys = setup(tmp_path)
    a, aa = make_change(tmp_path, keys, change_id="change:a", suffix="a", rule_id="rule:a")
    b, ba = make_change(tmp_path, keys, change_id="change:b", suffix="b", rule_id="rule:b")
    def apply(pair):
        request, approvals = pair
        try:
            return store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00").status
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(apply, ((a, aa), (b, ba))))
    assert sum(value == "APPLIED" for value in outcomes) == 1
    assert sum("stale policy version" in value for value in outcomes) == 1
    assert store.snapshot("tenant:one").version == 1


def test_policy_history_is_append_only_and_tamper_evident(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys)
    store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")
    path = str(tmp_path / "policy.db")
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE authorization_policy_changes SET operation='REVOKE_RULE'")
        db.execute("DROP TRIGGER authorization_policy_changes_no_update")
        db.execute("UPDATE authorization_policy_changes SET operation='REVOKE_RULE'")
    assert not store.verify()
    with pytest.raises(ValueError, match="integrity verification"):
        SQLiteAuthorizationPolicyStore(path,
            {"tenant:one": ("admin:proposer", "admin:one", "admin:two", "admin:three")})


def test_policy_snapshot_version_and_hash_are_attached_to_authorization_decision(tmp_path):
    store, registry, keys = setup(tmp_path)
    request, approvals = make_change(tmp_path, keys)
    store.apply_change(request, approvals, registry, "2026-11-06T10:02:00+00:00")
    auth_payload = {"request_id": "request:auth", "action": "JOURNAL_POST",
        "resource_type": "LEDGER", "resource_id": "ledger:alpha"}
    auth_request = make_signed(tmp_path, keys, "user:operator",
        "AUTHORIZATION_REQUEST", auth_payload, "auth-request", "2026-11-06T10:03:00+00:00")
    decision = store.authorize(auth_request, [], registry, "2026-11-06T10:04:00+00:00")
    assert decision.allowed
    assert decision.policy_version == 1
    assert decision.policy_hash == store.snapshot("tenant:one").policy_hash
