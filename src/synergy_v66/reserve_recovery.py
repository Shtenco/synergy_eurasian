"""Adaptive multi-level reserve recovery planning for SYNERGY V6.6.4-N.

The planner is deliberately separate from settlement: planning is pure with
respect to the ledger; execution revalidates the captured ledger state and
uses CreditLedger.replenish_reserves for the atomic cash transfer.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .credit import CreditLedger, EPS, RECOVERY_PERIOD_DAYS


ALLOCATION_RULES = {
    "equal",
    "production_capacity",
    "opening_cash",
    "adaptive_liquidity",
}


def _period_contributions(ledger: CreditLedger, period_id: str) -> dict[str, float]:
    used = {cell_id: 0.0 for cell_id in ledger.cell_by_id}
    contribution_types = {
        "regional_reserve_replenishment_contribution",
        "federation_reserve_replenishment_contribution",
    }
    for event in ledger.events:
        if event.get("recovery_period_id") == period_id and event.get("type") in contribution_types:
            used[event["cell_id"]] += float(event["amount"])
    return used


def _state_fingerprint(ledger: CreditLedger, period_id: str) -> str:
    state = {
        "current_day": ledger.current_day,
        "cash": {key: ledger.accounts[key].cash for key in sorted(ledger.accounts)},
        "initial_cash_by_cell": {key: ledger.initial_cash_by_cell[key] for key in sorted(ledger.initial_cash_by_cell)},
        "defaulted": {key: ledger.accounts[key].defaulted for key in sorted(ledger.accounts)},
        "regional_reserve_members_by_region": {
            region: sorted(ledger.regional_reserve_members_by_region[region])
            for region in ledger.regions
        },
        "federation_reserve_members": sorted(ledger.federation_reserve_members),
        "regional_reserves": {key: ledger.regional_pool_reserve_by_region[key] for key in ledger.regions},
        "federation_reserve": ledger.federation_pool_reserve_balance,
        "reserve_recovery_contribution_fraction": ledger.reserve_recovery_contribution_fraction,
        "minimum_post_contribution_cash": ledger.minimum_post_contribution_cash,
        "period_contributions": _period_contributions(ledger, period_id),
    }
    raw = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _weights(rule: str, capacities: dict[str, float], ledger: CreditLedger) -> dict[str, float]:
    if rule == "equal":
        return {cell_id: 1.0 for cell_id in capacities}
    if rule == "production_capacity":
        return {cell.cell_id: max(0.0, float(cell.capacity)) for cell in ledger.cells}
    if rule == "opening_cash":
        return {cell_id: max(0.0, float(ledger.initial_cash_by_cell[cell_id])) for cell_id in capacities}
    return {cell_id: max(0.0, value) for cell_id, value in capacities.items()}


def _waterfill(
    requested: float,
    capacities: dict[str, float],
    weights: dict[str, float],
) -> dict[str, float]:
    """Deterministic capped weighted allocation; returns partial funding if needed."""
    allocation = {cell_id: 0.0 for cell_id in capacities}
    remaining = max(0.0, float(requested))
    active = {cell_id for cell_id, cap in capacities.items() if cap > EPS}
    while remaining > EPS and active:
        positive_weight_total = sum(max(0.0, weights.get(cell_id, 0.0)) for cell_id in sorted(active))
        effective_weights = {
            cell_id: (
                max(0.0, weights.get(cell_id, 0.0))
                if positive_weight_total > EPS else capacities[cell_id] - allocation[cell_id]
            )
            for cell_id in sorted(active)
        }
        weight_total = sum(effective_weights[cell_id] for cell_id in sorted(effective_weights))
        if weight_total <= EPS:
            break
        round_remaining = remaining
        capped: set[str] = set()
        proposed: dict[str, float] = {}
        for cell_id in sorted(active):
            share = round_remaining * effective_weights[cell_id] / weight_total
            available = capacities[cell_id] - allocation[cell_id]
            proposed[cell_id] = min(available, share)
            if share >= available - EPS:
                capped.add(cell_id)
        paid = sum(proposed.values())
        for cell_id, amount in proposed.items():
            allocation[cell_id] += amount
        remaining = max(0.0, remaining - paid)
        if not capped:
            break
        active -= capped
    return allocation


def _plan_fingerprint(plan: dict[str, Any]) -> str:
    payload = {key: value for key, value in plan.items() if key != "plan_fingerprint"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def plan_reserve_recovery(
    ledger: CreditLedger,
    target_regional_by_region: dict[str, float],
    target_federation: float,
    allocation_rule: str = "adaptive_liquidity",
    contribution_fraction_per_period: float | None = None,
    recovery_period_id: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating recovery plan with local reserves funded first."""
    if allocation_rule not in ALLOCATION_RULES:
        raise ValueError(f"allocation_rule must be one of {sorted(ALLOCATION_RULES)}")
    if ledger.current_day < 0:
        raise ValueError("ledger must be initialized with process_day before reserve recovery planning")
    if not isinstance(target_regional_by_region, dict) or set(target_regional_by_region) != set(ledger.regions):
        raise ValueError("target_regional_by_region must contain every known region exactly once")
    if isinstance(target_federation, bool) or not isinstance(target_federation, (int, float)) or not math.isfinite(float(target_federation)) or target_federation < 0:
        raise ValueError("target_federation must be finite and non-negative")
    fraction = (
        ledger.reserve_recovery_contribution_fraction
        if contribution_fraction_per_period is None
        else contribution_fraction_per_period
    )
    if (
        isinstance(fraction, bool)
        or not isinstance(fraction, (int, float))
        or not math.isfinite(float(fraction))
        or not 0 <= fraction <= ledger.reserve_recovery_contribution_fraction
    ):
        raise ValueError("contribution_fraction_per_period cannot exceed the ledger policy cap")
    expected_period_id = f"day-window-{ledger.current_day // RECOVERY_PERIOD_DAYS}"
    if recovery_period_id is not None and recovery_period_id != expected_period_id:
        raise ValueError(f"recovery_period_id must be the ledger-defined {expected_period_id}")
    recovery_period_id = expected_period_id

    targets: dict[str, float] = {}
    for region, target in target_regional_by_region.items():
        if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(float(target)) or target < 0:
            raise ValueError("regional reserve targets must be finite and non-negative")
        targets[region] = float(target)

    period_used = _period_contributions(ledger, recovery_period_id)
    cash_capacity: dict[str, float] = {}
    period_limits: dict[str, float] = {}
    for cell_id in ledger.cell_by_id:
        opening = float(ledger.initial_cash_by_cell[cell_id])
        period_limit = opening * float(fraction)
        period_limits[cell_id] = period_limit
        remaining_period_limit = max(0.0, period_limit - period_used[cell_id])
        cash_after_floor = max(
            0.0,
            ledger.accounts[cell_id].cash - ledger.minimum_post_contribution_cash,
        )
        cash_capacity[cell_id] = (
            min(cash_after_floor, remaining_period_limit)
            if not ledger.accounts[cell_id].defaulted else 0.0
        )

    weights = _weights(allocation_rule, cash_capacity, ledger)
    regional_plan = {cell_id: 0.0 for cell_id in ledger.cell_by_id}
    remaining_capacity = dict(cash_capacity)
    regional_deficits = {
        region: max(0.0, targets[region] - ledger.regional_pool_reserve_by_region[region])
        for region in ledger.regions
    }
    regional_allocated: dict[str, float] = {}
    for region in ledger.regions:
        members = sorted(ledger.regional_reserve_members_by_region[region])
        caps = {cell_id: remaining_capacity[cell_id] for cell_id in members}
        region_weights = {cell_id: weights[cell_id] for cell_id in members}
        allocated = _waterfill(regional_deficits[region], caps, region_weights)
        regional_plan.update(allocated)
        regional_allocated[region] = sum(allocated.values())
        for cell_id, amount in allocated.items():
            remaining_capacity[cell_id] = max(0.0, remaining_capacity[cell_id] - amount)

    federation_deficit = max(0.0, float(target_federation) - ledger.federation_pool_reserve_balance)
    federation_caps = {
        cell_id: remaining_capacity[cell_id]
        for cell_id in sorted(ledger.federation_reserve_members)
    }
    federation_weights = {cell_id: weights[cell_id] for cell_id in federation_caps}
    federation_plan = _waterfill(federation_deficit, federation_caps, federation_weights)
    requested_total = sum(regional_deficits.values()) + federation_deficit
    funded_total = sum(regional_plan.values()) + sum(federation_plan.values())
    unfunded_total = max(0.0, requested_total - funded_total)

    plan = {
        "model_id": "SYNERGY_V6.6.4N_ADAPTIVE_MULTI_LEVEL_RESERVE_RECOVERY",
        "recovery_period_id": recovery_period_id,
        "ledger_day": ledger.current_day,
        "allocation_rule": allocation_rule,
        "contribution_fraction_per_period": float(fraction),
        "target_regional_by_region": targets,
        "target_federation": float(target_federation),
        "current_regional_by_region": dict(ledger.regional_pool_reserve_by_region),
        "current_federation": float(ledger.federation_pool_reserve_balance),
        "regional_deficit_by_region": regional_deficits,
        "regional_allocated_by_region": regional_allocated,
        "federation_deficit": federation_deficit,
        "regional_contributions_by_cell": regional_plan,
        "federation_contributions_by_cell": federation_plan,
        "period_limit_by_cell": period_limits,
        "period_used_by_cell": period_used,
        "remaining_capacity_by_cell": {
            cell_id: cash_capacity[cell_id] - regional_plan[cell_id] - federation_plan[cell_id]
            for cell_id in ledger.cell_by_id
        },
        "requested_total": requested_total,
        "funded_total": funded_total,
        "unfunded_total": unfunded_total,
        "funding_complete": unfunded_total <= EPS,
        "state_fingerprint": _state_fingerprint(ledger, recovery_period_id),
        "interpretation_guard": (
            "Synthetic reserve recovery plan only. Contribution fractions, reserve targets and "
            "allocation weights are policy assumptions, not empirically calibrated EAEU rules."
        ),
    }
    plan["plan_fingerprint"] = _plan_fingerprint(plan)
    return plan


def execute_reserve_recovery(
    ledger: CreditLedger,
    plan: dict[str, Any],
    replenishment_id: str,
    day: int,
) -> dict[str, Any]:
    """Execute a plan only against the exact ledger state from which it was built."""
    if not isinstance(plan, dict) or plan.get("model_id") != "SYNERGY_V6.6.4N_ADAPTIVE_MULTI_LEVEL_RESERVE_RECOVERY":
        raise ValueError("unsupported reserve recovery plan")
    period_id = plan.get("recovery_period_id")
    if plan.get("plan_fingerprint") != _plan_fingerprint(plan):
        raise ValueError("recovery plan was modified after planning")
    if day != ledger.current_day or day != plan.get("ledger_day"):
        raise ValueError("ledger day changed; advance ledger and create a fresh recovery plan")
    if plan.get("state_fingerprint") != _state_fingerprint(ledger, period_id):
        raise ValueError("ledger state changed; create a fresh reserve recovery plan")
    return ledger.replenish_reserves(
        regional_contributions_by_cell=plan["regional_contributions_by_cell"],
        federation_contributions_by_cell=plan["federation_contributions_by_cell"],
        day=day,
        replenishment_id=replenishment_id,
        recovery_period_id=period_id,
        contribution_limit_by_cell=plan["period_limit_by_cell"],
    )
