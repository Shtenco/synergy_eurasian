"""Fail-closed economic authority scopes for SUES federation (V1).

This evaluator constrains an already-authorized signed request. Evaluation is
stateless, while reserve/release operations append reservation events through the
executor's SQLite transaction. Callers must read committed usage from the
authoritative ledger in that same transaction; this module never executes actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    committed_period_total must come from an authoritative ledger query in the
    same SQLite transaction passed to reserve_in_transaction().
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

    def reserve_in_transaction(
        self,
        connection: Any,
        evaluation: ScopeEvaluation,
        committed_period_total: str,
        source_ref: str,
        now: datetime | None = None,
    ) -> bool:
        """Atomically reserve a passing scope evaluation inside the executor transaction.

        committed_period_total MUST be queried from the authoritative ledger using
        this same SQLite transaction. Active reservations are added before the
        limit check, preventing two concurrent requests from spending the same
        remaining headroom. Returns False only for an exact idempotent retry.
        """
        if not evaluation.allowed or not evaluation.scope_id:
            raise ValueError("only an allowed scope evaluation can be reserved")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("reservation source_ref must be non-empty")
        scope = self._scopes.get(evaluation.scope_id)
        if scope is None:
            raise ValueError("scope evaluation references an unknown scope")
        if not all((evaluation.request_id, evaluation.amount, evaluation.currency, evaluation.period_key)):
            raise ValueError("scope evaluation is missing reservation dimensions")
        amount = _decimal(evaluation.amount, "reservation amount")
        committed = _decimal(committed_period_total, "committed_period_total")
        if amount <= 0 or committed < 0:
            raise ValueError("reservation amount must be positive and committed total non-negative")
        if evaluation.currency not in scope.currencies:
            raise ValueError("reservation currency is outside the authority scope")
        if amount > _decimal(scope.max_per_transaction, "max_per_transaction"):
            raise ValueError("reservation exceeds per-transaction authority limit")
        if now is None:
            instant = datetime.now(timezone.utc)
        elif isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None:
            instant = now.astimezone(timezone.utc)
        else:
            raise ValueError("reservation timestamp must be timezone-aware")

        existing = connection.execute(
            "SELECT event_type,scope_id,tenant_id,period_key,currency,amount,source_ref "
            "FROM authority_scope_reservation_events WHERE request_id=? ORDER BY rowid",
            (evaluation.request_id,),
        ).fetchall()
        if existing:
            first = existing[0]
            if (len(existing) == 1 and first[0] == "RESERVED"
                    and first[1] == scope.scope_id and first[2] == scope.tenant_id
                    and first[3] == evaluation.period_key and first[4] == evaluation.currency
                    and Decimal(first[5]) == amount and first[6] == source_ref):
                return False
            raise ValueError("scope reservation request_id has already been used")

        active_rows = connection.execute(
            "SELECT request_id,event_type,amount FROM authority_scope_reservation_events "
            "WHERE scope_id=? AND tenant_id=? AND period_key=? AND currency=? ORDER BY rowid",
            (scope.scope_id, scope.tenant_id, evaluation.period_key, evaluation.currency),
        ).fetchall()
        latest_by_request = {}
        for row in active_rows:
            latest_by_request[row[0]] = (row[1], row[2])
        reserved = sum(
            (Decimal(value[1]) for value in latest_by_request.values() if value[0] == "RESERVED"),
            Decimal("0"),
        )
        if committed + reserved + amount > _decimal(scope.period_limit, "period_limit"):
            raise ValueError("period_limit_exceeded_including_active_reservations")

        connection.execute(
            """INSERT INTO authority_scope_reservation_events
            (event_id,request_id,event_type,scope_id,tenant_id,period_key,currency,
             amount,source_ref,created_at)
            VALUES(?,?,'RESERVED',?,?,?,?,?,?,?)""",
            (f"reserve:{evaluation.request_id}", evaluation.request_id, scope.scope_id,
             scope.tenant_id, evaluation.period_key, evaluation.currency,
             format(amount, "f"), source_ref, instant.isoformat()),
        )
        return True

    def release_in_transaction(
        self,
        connection: Any,
        request_id: str,
        settlement_ref: str,
        now: datetime | None = None,
        *,
        settlement_verifier: object | None = None,
    ) -> None:
        """Release only after a trusted verifier finds the exact settlement in this transaction.

        The verifier receives (connection, request_id, settlement_ref, scope_id,
        tenant_id, currency, amount) and must query the authoritative settlement
        ledger on this same connection. Returning anything other than literal
        True keeps the reservation active.
        """
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id is required to release a scope reservation")
        if not isinstance(settlement_ref, str) or not settlement_ref.strip():
            raise ValueError("settlement_ref is required to release a scope reservation")
        if not callable(settlement_verifier):
            raise ValueError("a trusted same-transaction settlement_verifier is required")
        if now is None:
            instant = datetime.now(timezone.utc)
        elif isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None:
            instant = now.astimezone(timezone.utc)
        else:
            raise ValueError("reservation release timestamp must be timezone-aware")
        rows = connection.execute(
            "SELECT event_type,scope_id,tenant_id,period_key,currency,amount "
            "FROM authority_scope_reservation_events WHERE request_id=? ORDER BY rowid",
            (request_id,),
        ).fetchall()
        if not rows or rows[-1][0] != "RESERVED":
            raise ValueError("only an active scope reservation can be released")
        latest = rows[-1]
        if settlement_verifier(
            connection, request_id, settlement_ref, latest[1], latest[2],
            latest[4], latest[5],
        ) is not True:
            raise ValueError("settlement evidence does not match the active scope reservation")
        connection.execute(
            """INSERT INTO authority_scope_reservation_events
            (event_id,request_id,event_type,scope_id,tenant_id,period_key,currency,
             amount,source_ref,created_at)
            VALUES(?,?,'RELEASED',?,?,?,?,?,?,?)""",
            (f"release:{request_id}", request_id, latest[1], latest[2], latest[3],
             latest[4], latest[5], settlement_ref, instant.isoformat()),
        )

    def evaluate(
        self,
        request: SignedEventEnvelope,
        decision: AuthorizationDecision,
        committed_period_total: str,
        period_reference_at: datetime | str | None = None,
        committed_period_key: str | None = None,
        committed_period_currency: str | None = None,
    ) -> ScopeEvaluation:
        """Return a fail-closed scope result; no funds are reserved here."""
        payload = request.event.get("payload", {}) if isinstance(request.event, dict) else {}
        request_id = payload.get("request_id", "") if isinstance(payload, dict) else ""
        if not decision.allowed:
            return ScopeEvaluation(False, "authorization_not_allowed", None, str(request_id))
        try:
            if not isinstance(request.event, dict) or not isinstance(payload, dict):
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
            if (
                decision.request_event_id != request.event.get("event_id")
                or decision.request_event_hash != request.event.get("event_hash")
                or decision.action != payload["action"]
                or decision.resource_type != payload["resource_type"]
                or decision.resource_id != payload["resource_id"]
                or decision.tenant_id != request.tenant_id
            ):
                raise ValueError("authorization decision is not bound to this signed event and exact action/resource")
            if period_reference_at is None or not committed_period_key or not committed_period_currency:
                raise ValueError("authoritative period context is required")
            if isinstance(period_reference_at, str):
                try:
                    period_instant = datetime.fromisoformat(period_reference_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError("period_reference_at must be an ISO timestamp") from exc
            elif isinstance(period_reference_at, datetime):
                period_instant = period_reference_at
            else:
                raise ValueError("period_reference_at must be a timezone-aware datetime")
            if period_instant.tzinfo is None or period_instant.utcoffset() is None:
                raise ValueError("period_reference_at must be timezone-aware")
            period_instant = period_instant.astimezone(timezone.utc)
            amount = _decimal(payload["amount"], "amount")
            # Period usage is a same-currency bucket. Cross-currency totals require
            # a separately governed FX conversion and are never added implicitly.
            usage = _decimal(committed_period_total, "committed_period_total")
            if amount <= 0 or usage < 0:
                raise ValueError("amount must be positive and period usage non-negative")
            currency = payload["currency"]
            if currency != currency.upper() or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError("currency must use a canonical uppercase three-letter code")
            if committed_period_currency != currency:
                raise ValueError("committed period currency does not match request currency")
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
            if scope.period_window == "DAY":
                authoritative_period_key = period_instant.date().isoformat()
            elif scope.period_window == "WEEK":
                iso_year, iso_week, _ = period_instant.isocalendar()
                authoritative_period_key = f"{iso_year}-W{iso_week:02d}"
            elif scope.period_window == "MONTH":
                authoritative_period_key = period_instant.strftime("%Y-%m")
            else:
                authoritative_period_key = period_instant.strftime("%Y")
            if (payload["period_key"] != authoritative_period_key
                    or committed_period_key != authoritative_period_key):
                raise ValueError("period_key does not match authoritative execution period")
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
                format(amount, "f"), currency, authoritative_period_key, approvers,
            )
        except (ValueError, TypeError, InvalidOperation) as exc:
            return ScopeEvaluation(False, str(exc) or "invalid_scope_request", None, str(request_id))
