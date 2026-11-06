"""Fail-closed economic authority scopes for SUES federation (V1).

This evaluator constrains an already-authorized signed request. It is deliberately
stateless: callers must supply period usage from a trusted ledger read. It does
not reserve funds or execute actions; those guarantees require a transactional
integration with the executor and the authoritative economic ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from .federation_authorization import AuthorizationDecision
from .federation_identity import SignedEventEnvelope


@dataclass(frozen=True)
class ScopeRoleRequirement:
    role_id: str
    minimum_approvals: int = 1


@dataclass(frozen=True)
class AuthorityScope:
    scope_id: str
    tenant_id: str
    action: str
    resource_type: str
    subject_ids: tuple[str, ...]
    currencies: tuple[str, ...]
    max_per_transaction: str
    period_limit: str
    period_window: str
    resource_id: str | None = None
    allowed_organization_ids: tuple[str, ...] = ()
    allowed_account_ids: tuple[str, ...] = ()
    allowed_counterparty_ids: tuple[str, ...] = ()
    initiator_role: str | None = None
    approval_roles: tuple[ScopeRoleRequirement, ...] = ()


@dataclass(frozen=True)
class ScopeEvaluation:
    allowed: bool
    reason: str
    scope_id: str | None
    request_id: str
    amount: str | None = None
    currency: str | None = None
    period_key: str | None = None
    approval_identity_ids: tuple[str, ...] = ()


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a valid decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


class AuthorityScopeEngine:
    """Evaluate exact economic limits using explicitly provisioned scopes.

    identity_roles is trusted deployment configuration, not request input.
    committed_period_total must come from an authoritative ledger query and
    must be read consistently with the eventual execution transaction.
    """

    def __init__(
        self,
        scopes: Sequence[AuthorityScope],
        identity_roles: Mapping[str, Sequence[str]],
    ) -> None:
        if not isinstance(scopes, (tuple, list)) or not scopes:
            raise ValueError("at least one explicit authority scope is required")
        if not isinstance(identity_roles, Mapping):
            raise ValueError("identity_roles must be trusted configuration")
        self._scopes: dict[str, AuthorityScope] = {}
        self._identity_roles = {}
        for identity, roles in identity_roles.items():
            if not isinstance(identity, str) or not identity.strip():
                raise ValueError("role identity keys must be non-empty strings")
            if not isinstance(roles, (tuple, list)) or any(
                not isinstance(role, str) or not role.strip() for role in roles
            ):
                raise ValueError("identity roles must be non-empty strings")
            self._identity_roles[identity] = frozenset(roles)
        for scope in scopes:
            self._validate_scope(scope)
            if scope.scope_id in self._scopes:
                raise ValueError("duplicate authority scope_id")
            self._scopes[scope.scope_id] = scope

    @staticmethod
    def _validate_scope(scope: AuthorityScope) -> None:
        if not isinstance(scope, AuthorityScope):
            raise ValueError("scope must be an AuthorityScope")
        for name in ("scope_id", "tenant_id", "action", "resource_type"):
            value = getattr(scope, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if scope.resource_id is not None and (
            not isinstance(scope.resource_id, str) or not scope.resource_id.strip()
        ):
            raise ValueError("resource_id must be a non-empty string or None")
        for name in ("subject_ids", "currencies"):
            values = getattr(scope, name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{name} must be a non-empty tuple")
            if len(values) != len(set(values)) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise ValueError(f"{name} must contain unique non-empty strings")
        if any(code != code.upper() or len(code) != 3 or not code.isascii() or not code.isalpha()
               for code in scope.currencies):
            raise ValueError("currencies must be uppercase three-letter ASCII codes")
        for name in (
            "allowed_organization_ids", "allowed_account_ids",
            "allowed_counterparty_ids",
        ):
            values = getattr(scope, name)
            if not isinstance(values, tuple) or len(values) != len(set(values)):
                raise ValueError(f"{name} must be a unique tuple")
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{name} must contain non-empty strings")
        maximum = _decimal(scope.max_per_transaction, "max_per_transaction")
        period_limit = _decimal(scope.period_limit, "period_limit")
        if maximum <= 0 or period_limit <= 0 or maximum > period_limit:
            raise ValueError("scope monetary limits must be positive and transaction limit <= period limit")
        if scope.period_window not in {"DAY", "WEEK", "MONTH", "YEAR"}:
            raise ValueError("period_window must be DAY, WEEK, MONTH or YEAR")
        if scope.initiator_role is not None and (
            not isinstance(scope.initiator_role, str) or not scope.initiator_role.strip()
        ):
            raise ValueError("initiator_role must be a non-empty string or None")
        if not isinstance(scope.approval_roles, tuple):
            raise ValueError("approval_roles must be an immutable tuple")
        seen_roles: set[str] = set()
        for requirement in scope.approval_roles:
            if not isinstance(requirement, ScopeRoleRequirement):
                raise ValueError("approval_roles entries must be ScopeRoleRequirement")
            if not isinstance(requirement.role_id, str) or not requirement.role_id.strip():
                raise ValueError("approval role_id is required")
            if requirement.role_id in seen_roles:
                raise ValueError("approval roles must be unique")
            if (isinstance(requirement.minimum_approvals, bool)
                    or not isinstance(requirement.minimum_approvals, int)
                    or requirement.minimum_approvals < 1):
                raise ValueError("minimum_approvals must be an integer >= 1")
            seen_roles.add(requirement.role_id)

    def evaluate(
        self,
        request: SignedEventEnvelope,
        decision: AuthorizationDecision,
        committed_period_total: str,
    ) -> ScopeEvaluation:
        """Return a fail-closed scope result; no funds are reserved here."""
        payload = request.event.get("payload", {}) if isinstance(request.event, dict) else {}
        request_id = payload.get("request_id", "") if isinstance(payload, dict) else ""
        if not decision.allowed:
            return ScopeEvaluation(False, "authorization_not_allowed", None, str(request_id))
        try:
            if not isinstance(payload, dict):
                raise ValueError("request payload must be an object")
            if request.event.get("event_type") != "AUTHORIZATION_REQUEST":
                raise ValueError("expected AUTHORIZATION_REQUEST event")
            required = (
                "request_id", "action", "resource_type", "resource_id",
                "amount", "currency", "period_key", "organization_id",
                "account_id", "counterparty_id",
            )
            missing = [key for key in required if key not in payload]
            if missing:
                raise ValueError("scope request missing fields: " + ", ".join(missing))
            if any(not isinstance(payload[key], str) or not payload[key].strip()
                   for key in required if key != "amount"):
                raise ValueError("scope request identifiers must be non-empty strings")
            if request.identity_id != decision.requester_identity_id:
                raise ValueError("authorization decision requester does not match signed request")
            if decision.request_id != payload["request_id"]:
                raise ValueError("authorization decision request_id does not match signed request")
            amount = _decimal(payload["amount"], "amount")
            # Period usage is a same-currency bucket. Cross-currency totals require
            # a separately governed FX conversion and are never added implicitly.
            usage = _decimal(committed_period_total, "committed_period_total")
            if amount <= 0 or usage < 0:
                raise ValueError("amount must be positive and period usage non-negative")
            currency = payload["currency"]
            if currency != currency.upper() or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError("currency must use a canonical uppercase three-letter code")
            candidates = [
                scope for scope in self._scopes.values()
                if scope.tenant_id == request.tenant_id
                and scope.action == payload["action"]
                and scope.resource_type == payload["resource_type"]
                and (scope.resource_id is None or scope.resource_id == payload["resource_id"])
                and decision.requester_identity_id in scope.subject_ids
            ]
            if not candidates:
                return ScopeEvaluation(False, "no_matching_authority_scope", None, str(request_id))
            specificity = lambda item: sum(bool(x) for x in (
                item.resource_id, item.allowed_organization_ids,
                item.allowed_account_ids, item.allowed_counterparty_ids,
                item.initiator_role,
            ))
            candidates.sort(key=lambda item: (-specificity(item), item.scope_id))
            if len(candidates) > 1 and specificity(candidates[0]) == specificity(candidates[1]):
                raise ValueError("ambiguous_authority_scope")
            scope = candidates[0]
            if currency not in scope.currencies:
                raise ValueError("currency_not_permitted")
            if amount > _decimal(scope.max_per_transaction, "max_per_transaction"):
                raise ValueError("transaction_limit_exceeded")
            if usage + amount > _decimal(scope.period_limit, "period_limit"):
                raise ValueError("period_limit_exceeded")
            for field, allowed in (
                ("organization_id", scope.allowed_organization_ids),
                ("account_id", scope.allowed_account_ids),
                ("counterparty_id", scope.allowed_counterparty_ids),
            ):
                if allowed and payload[field] not in allowed:
                    raise ValueError(field + "_not_permitted")
            requester = decision.requester_identity_id
            requester_roles = self._identity_roles.get(requester, frozenset())
            if scope.initiator_role and scope.initiator_role not in requester_roles:
                raise ValueError("initiator_role_not_permitted")
            approvers = tuple(sorted(set(decision.approval_identity_ids)))
            if requester in approvers:
                raise ValueError("initiator_cannot_approve")
            used_approvers: set[str] = set()
            for requirement in scope.approval_roles:
                eligible = sorted(
                    identity for identity in approvers
                    if identity not in used_approvers
                    and requirement.role_id in self._identity_roles.get(identity, frozenset())
                )
                if len(eligible) < requirement.minimum_approvals:
                    raise ValueError("approval_role_quorum_not_met:" + requirement.role_id)
                used_approvers.update(eligible[:requirement.minimum_approvals])
            return ScopeEvaluation(
                True, "within_authority_scope", scope.scope_id, str(request_id),
                format(amount, "f"), currency, payload["period_key"], approvers,
            )
        except (ValueError, TypeError, InvalidOperation) as exc:
            return ScopeEvaluation(False, str(exc) or "invalid_scope_request", None, str(request_id))
