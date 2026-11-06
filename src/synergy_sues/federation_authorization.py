"""Fail-closed action/resource authorization for SUES federation events.

Authentication is delegated to the trusted Ed25519 identity registry. This
module evaluates explicit policy; it does not execute the requested action.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .federation_identity import SignedEventEnvelope, TrustedKeyRegistry, _utc


@dataclass(frozen=True)
class AuthorizationRule:
    rule_id: str
    tenant_id: str
    effect: str
    action: str
    resource_type: str
    subject_ids: tuple[str, ...]
    approver_ids: tuple[str, ...] = ()
    min_approvals: int = 0
    resource_id: str | None = None
    valid_from: str = "1970-01-01T00:00:00+00:00"
    valid_until: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    request_id: str
    requester_identity_id: str
    matched_rule_ids: tuple[str, ...] = ()
    approval_identity_ids: tuple[str, ...] = ()
    approval_event_refs: tuple[tuple[str, str], ...] = ()


class FederationAuthorizationPolicy:
    """Explicit exact-scope policy; deny-by-default with deny-rule precedence."""

    def __init__(self) -> None:
        self._rules: dict[str, AuthorizationRule] = {}

    def register_rule(self, rule: AuthorizationRule) -> None:
        if not isinstance(rule, AuthorizationRule):
            raise ValueError("rule must be an AuthorizationRule")
        required = (rule.rule_id, rule.tenant_id, rule.effect, rule.action, rule.resource_type)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("rule identity, tenant, effect, action and resource_type are required")
        if rule.effect not in {"ALLOW", "DENY"}:
            raise ValueError("rule effect must be ALLOW or DENY")
        if not isinstance(rule.subject_ids, tuple) or not isinstance(rule.approver_ids, tuple):
            raise ValueError("subject_ids and approver_ids must be immutable tuples")
        if isinstance(rule.min_approvals, bool) or not isinstance(rule.min_approvals, int) or rule.min_approvals < 0:
            raise ValueError("min_approvals must be a non-negative integer")
        if rule.effect == "DENY" and rule.min_approvals:
            raise ValueError("DENY rules cannot require approvals")
        if rule.effect == "ALLOW" and not rule.subject_ids:
            raise ValueError("ALLOW rules require an explicit subject allowlist")
        if rule.min_approvals > len(set(rule.approver_ids)):
            raise ValueError("min_approvals exceeds the number of distinct approvers")
        if len(rule.subject_ids) != len(set(rule.subject_ids)) or len(rule.approver_ids) != len(set(rule.approver_ids)):
            raise ValueError("subject_ids and approver_ids must be unique")
        if any(not isinstance(x, str) or not x.strip() for x in rule.subject_ids + rule.approver_ids):
            raise ValueError("subject and approver identities must be non-empty strings")
        _utc(rule.valid_from, "valid_from")
        if rule.valid_until is not None and _utc(rule.valid_until, "valid_until") <= _utc(rule.valid_from, "valid_from"):
            raise ValueError("valid_until must be after valid_from")
        if rule.rule_id in self._rules:
            raise ValueError("authorization rule ID already exists")
        self._rules[rule.rule_id] = rule

    @staticmethod
    def _payload_fields(envelope: SignedEventEnvelope, event_type: str,
                        fields: tuple[str, ...]) -> dict:
        if envelope.event.get("event_type") != event_type:
            raise ValueError(f"expected signed {event_type} event")
        payload = envelope.event.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("authorization event payload must be an object")
        missing = [field for field in fields if field not in payload]
        if missing:
            raise ValueError(f"authorization event missing fields: {', '.join(missing)}")
        return payload

    def authorize(self, request: SignedEventEnvelope,
                  approvals: Iterable[SignedEventEnvelope],
                  registry: TrustedKeyRegistry,
                  received_at: datetime | str | None = None) -> AuthorizationDecision:
        """Verify signed request and approvals, then evaluate policy without execution."""
        requester = registry.verify(request, received_at)
        payload = self._payload_fields(request, "AUTHORIZATION_REQUEST",
            ("request_id", "action", "resource_type", "resource_id"))
        request_id = payload["request_id"]
        action, resource_type, resource_id = payload["action"], payload["resource_type"], payload["resource_id"]
        if any(not isinstance(x, str) or not x.strip() for x in (request_id, action, resource_type, resource_id)):
            raise ValueError("authorization request scope fields must be non-empty strings")
        requested_at = _utc(request.signed_at, "signed_at")
        now = _utc(received_at, "received_at") if isinstance(received_at, str) else (
            received_at or datetime.now(timezone.utc))
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        now = now.astimezone(timezone.utc)

        matching = []
        for rule in self._rules.values():
            if (rule.tenant_id != requester.tenant_id or rule.action != action
                    or rule.resource_type != resource_type
                    or (rule.resource_id is not None and rule.resource_id != resource_id)):
                continue
            start = _utc(rule.valid_from, "valid_from")
            end = _utc(rule.valid_until, "valid_until") if rule.valid_until else None
            if requested_at < start or (end is not None and requested_at >= end):
                continue
            if now < start or (end is not None and now >= end):
                continue
            if rule.subject_ids and requester.identity_id not in rule.subject_ids:
                continue
            matching.append(rule)

        denies = tuple(sorted(rule.rule_id for rule in matching if rule.effect == "DENY"))
        if denies:
            return AuthorizationDecision(False, "explicit_deny_rule", request_id,
                requester.identity_id, denies)
        allows = [rule for rule in matching if rule.effect == "ALLOW"]
        if not allows:
            return AuthorizationDecision(False, "no_matching_allow_rule", request_id,
                requester.identity_id)

        verified_approvals: dict[str, tuple[str, str]] = {}
        vetoes: list[tuple[str, str, str]] = []
        seen_events: set[str] = set()
        for approval in approvals:
            approver = registry.verify(approval, received_at)
            approval_payload = self._payload_fields(approval, "AUTHORIZATION_APPROVAL",
                ("request_id", "request_event_id", "request_event_hash", "action", "resource_type", "resource_id", "requester_identity_id", "decision"))
            if approval.event["event_id"] in seen_events:
                continue
            seen_events.add(approval.event["event_id"])
            scope_matches = (
                approval_payload["request_id"] == request_id
                and approval_payload["request_event_id"] == request.event["event_id"]
                and approval_payload["request_event_hash"] == request.event["event_hash"]
                and approval_payload["action"] == action
                and approval_payload["resource_type"] == resource_type
                and approval_payload["resource_id"] == resource_id
                and approval_payload["requester_identity_id"] == requester.identity_id
                and approver.tenant_id == requester.tenant_id
                and _utc(approval.signed_at, "signed_at") >= requested_at
            )
            if not scope_matches:
                continue
            authorized_approver = any(
                approver.identity_id in rule.approver_ids for rule in allows
            )
            if not authorized_approver or approver.identity_id == requester.identity_id:
                continue
            if approval_payload["decision"] not in {"APPROVE", "REJECT"}:
                raise ValueError("approval decision must be APPROVE or REJECT")
            if approval_payload["decision"] == "REJECT":
                vetoes.append((approver.identity_id, approval.event["event_id"], approval.event["event_hash"]))
            else:
                verified_approvals[approver.identity_id] = (
                    approval.event["event_id"], approval.event["event_hash"])

        if vetoes:
            return AuthorizationDecision(False, "approval_veto", request_id,
                requester.identity_id, tuple(sorted(rule.rule_id for rule in allows)),
                tuple(sorted({item[0] for item in vetoes})),
                tuple(sorted({(item[1], item[2]) for item in vetoes})))

        # Rules are evaluated independently: approvals never combine across policies.
        eligible = []
        for rule in allows:
            if requester.identity_id not in rule.subject_ids:
                continue
            approvals_for_rule = tuple(sorted(
                identity_id for identity_id in verified_approvals
                if identity_id in rule.approver_ids and identity_id != requester.identity_id
            ))
            if len(approvals_for_rule) >= rule.min_approvals:
                eligible.append((rule, approvals_for_rule))
        if not eligible:
            return AuthorizationDecision(False, "insufficient_approvals", request_id,
                requester.identity_id, tuple(sorted(rule.rule_id for rule in allows)),
                tuple(sorted(verified_approvals)),
                tuple(sorted(set(verified_approvals.values()))))
        # Prefer the narrowest resource scope; rule IDs provide deterministic tie-break.
        eligible.sort(key=lambda item: (item[0].resource_id is None, item[0].rule_id))
        selected, selected_approvals = eligible[0]
        approval_refs = tuple(sorted(verified_approvals[identity_id] for identity_id in selected_approvals))
        return AuthorizationDecision(True, "authorized_by_policy", request_id,
            requester.identity_id, (selected.rule_id,), selected_approvals, approval_refs)
