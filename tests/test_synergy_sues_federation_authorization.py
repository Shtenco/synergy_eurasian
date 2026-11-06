from dataclasses import dataclass, replace
from datetime import datetime, timezone
import pytest

from synergy_sues.event_transport import DurableEventStore
from synergy_sues.federation_identity import (
    ALGORITHM, FederationIdentity, TrustedKeyRegistry, TrustedSigningKey,
    generate_ed25519_keypair, sign_event,
)
from synergy_sues.federation_authorization import (
    AuthorizationRule, FederationAuthorizationPolicy,
)


@dataclass(frozen=True)
class AuthorizationEvent:
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


def signed_event(tmp_path, identity_id, tenant_id, key_id, private_key,
                 event_type, payload, suffix, signed_at="2026-11-06T10:00:00+00:00"):
    event_id = "evt-" + suffix
    source = AuthorizationEvent(event_id, "AUTHORIZATION", payload.get("request_id", suffix),
        1, event_type, "2026-11-06T09:00:00+00:00", "2026-11-06T09:01:00+00:00",
        payload, "source:" + event_id, ("evidence:" + suffix,), "idem:" + suffix)
    stored = DurableEventStore(str(tmp_path / (suffix + ".db"))).append(
        source, now=datetime(2026, 11, 6, 9, 1, tzinfo=timezone.utc))
    return sign_event(stored, identity_id, tenant_id, key_id, private_key, signed_at)


def setup_registry():
    registry = TrustedKeyRegistry()
    keys = {}
    for identity_id in ("org:requester", "org:approver", "org:outsider"):
        private, public = generate_ed25519_keypair()
        keys[identity_id] = private
        registry.register_identity(FederationIdentity(identity_id, "tenant:one", "ORGANIZATION"))
        registry.register_key(TrustedSigningKey(identity_id, "tenant:one", "key-1",
            ALGORITHM, public, "2026-01-01T00:00:00+00:00"))
    return registry, keys


def request_payload():
    return {"request_id": "req-1", "action": "JOURNAL_POST",
        "resource_type": "LEDGER", "resource_id": "ledger:alpha"}


def approval_payload(decision="APPROVE"):
    return {"request_id": "req-1", "action": "JOURNAL_POST",
        "resource_type": "LEDGER", "resource_id": "ledger:alpha",
        "requester_identity_id": "org:requester", "decision": decision}


def policy(min_approvals=1, approvers=("org:approver",), resource_id="ledger:alpha"):
    engine = FederationAuthorizationPolicy()
    engine.register_rule(AuthorizationRule("rule:journal", "tenant:one", "ALLOW",
        "JOURNAL_POST", "LEDGER", ("org:requester",), tuple(approvers),
        min_approvals, resource_id))
    return engine


def test_signed_request_and_distinct_signed_approval_authorize(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    approval = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", approval_payload(), "approval",
        "2026-11-06T10:01:00+00:00")
    decision = policy().authorize(request, [approval], registry, "2026-11-06T10:02:00+00:00")
    assert decision.allowed is True
    assert decision.reason == "authorized_by_policy"
    assert decision.matched_rule_ids == ("rule:journal",)
    assert decision.approval_identity_ids == ("org:approver",)


def test_authorization_is_deny_by_default_and_requires_quorum(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    assert FederationAuthorizationPolicy().authorize(
        request, [], registry, "2026-11-06T10:02:00+00:00").reason == "no_matching_allow_rule"
    decision = policy().authorize(request, [], registry, "2026-11-06T10:02:00+00:00")
    assert decision.allowed is False
    assert decision.reason == "insufficient_approvals"


def test_requester_cannot_approve_own_action(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    self_approval = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_APPROVAL", approval_payload(), "self",
        "2026-11-06T10:01:00+00:00")
    decision = policy(min_approvals=1, approvers=("org:requester",)).authorize(
        request, [self_approval], registry, "2026-11-06T10:02:00+00:00")
    assert decision.allowed is False
    assert decision.reason == "insufficient_approvals"


def test_authorized_rejection_vetoes_but_unlisted_identity_cannot(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    outsider_reject = signed_event(tmp_path, "org:outsider", "tenant:one", "key-1",
        keys["org:outsider"], "AUTHORIZATION_APPROVAL", approval_payload("REJECT"), "outsider",
        "2026-11-06T10:01:00+00:00")
    approved = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", approval_payload(), "approval",
        "2026-11-06T10:01:00+00:00")
    assert policy().authorize(request, [outsider_reject, approved], registry,
        "2026-11-06T10:02:00+00:00").allowed
    authorized_reject = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", approval_payload("REJECT"), "reject",
        "2026-11-06T10:01:00+00:00")
    result = policy().authorize(request, [approved, authorized_reject], registry,
        "2026-11-06T10:02:00+00:00")
    assert result.allowed is False
    assert result.reason == "approval_veto"


def test_deny_rule_overrides_allow_rule(tmp_path):
    registry, keys = setup_registry()
    engine = policy(min_approvals=0)
    engine.register_rule(AuthorizationRule("rule:deny", "tenant:one", "DENY",
        "JOURNAL_POST", "LEDGER", ("org:requester",), (), 0, "ledger:alpha"))
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    result = engine.authorize(request, [], registry, "2026-11-06T10:02:00+00:00")
    assert result.allowed is False
    assert result.reason == "explicit_deny_rule"


def test_approval_must_match_request_scope_and_be_signed_after_request(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    wrong_scope = approval_payload()
    wrong_scope["resource_id"] = "ledger:other"
    approval = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", wrong_scope, "wrong",
        "2026-11-06T10:01:00+00:00")
    early = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", approval_payload(), "early",
        "2026-11-06T09:59:00+00:00")
    result = policy().authorize(request, [approval, early], registry, "2026-11-06T10:02:00+00:00")
    assert result.reason == "insufficient_approvals"


def test_authorization_rejects_tampered_or_wrong_event_type(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    altered = replace(request, event={**request.event, "payload": {**request.event["payload"], "action": "PAYMENT_SEND"}})
    with pytest.raises(ValueError, match="event hash"):
        policy().authorize(altered, [], registry, "2026-11-06T10:02:00+00:00")
    approval_as_request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_APPROVAL", approval_payload(), "not-request")
    with pytest.raises(ValueError, match="AUTHORIZATION_REQUEST"):
        policy().authorize(approval_as_request, [], registry, "2026-11-06T10:02:00+00:00")


def test_rule_validation_rejects_ambiguous_or_overbroad_allow():
    engine = FederationAuthorizationPolicy()
    with pytest.raises(ValueError, match="explicit subject allowlist"):
        engine.register_rule(AuthorizationRule("r", "t", "ALLOW", "A", "R", ()))
    with pytest.raises(ValueError, match="exceeds"):
        engine.register_rule(AuthorizationRule("r", "t", "ALLOW", "A", "R",
            ("subject",), ("approver",), 2))
    with pytest.raises(ValueError, match="already exists"):
        engine.register_rule(AuthorizationRule("r", "t", "ALLOW", "A", "R",
            ("subject",)))

def test_unlisted_identity_cannot_disrupt_authorization_with_malformed_decision(tmp_path):
    registry, keys = setup_registry()
    request = signed_event(tmp_path, "org:requester", "tenant:one", "key-1",
        keys["org:requester"], "AUTHORIZATION_REQUEST", request_payload(), "request")
    malformed = approval_payload("MAYBE")
    outsider = signed_event(tmp_path, "org:outsider", "tenant:one", "key-1",
        keys["org:outsider"], "AUTHORIZATION_APPROVAL", malformed, "outsider-invalid",
        "2026-11-06T10:01:00+00:00")
    approval = signed_event(tmp_path, "org:approver", "tenant:one", "key-1",
        keys["org:approver"], "AUTHORIZATION_APPROVAL", approval_payload(), "approval",
        "2026-11-06T10:01:00+00:00")
    assert policy().authorize(request, [outsider, approval], registry,
        "2026-11-06T10:02:00+00:00").allowed
