"""Deterministic seven-cell compatibility experiment for SYNERGY V6.6.1.

This deliberately narrow model replays a small make-to-order supply chain.
It excludes persistent inventory, debt, FX, lead times and legal insolvency;
those are later increments, not silently approximated here.
"""
from __future__ import annotations

import math
import random
from typing import Any

NODES = ("R1", "R2", "C1", "C2", "A1", "A2", "L")
FIXED_COST = {
    "R1": 2.0, "R2": 2.0, "C1": 3.0, "C2": 3.0,
    "A1": 4.0, "A2": 4.0, "L": 3.0,
}
BASE_CAPACITY = {
    "R1": 9.0, "R2": 9.0, "C1": 8.0, "C2": 8.0,
    "A1": 5.0, "A2": 5.0, "L": 40.0,
}
INITIAL_CASH_PER_CELL = 200.0
BATCH = 0.25
RAW_PER_FINAL = 1.25 * 1.15
COMP_PER_FINAL = 1.25
RAW_TRANSFER_PRICE = 4.0
COMP_TRANSFER_PRICE = 7.5
RAW_INPUT_COST = 1.2
COMP_PROCESS_COST = 2.2
ASSEMBLY_COST = 2.5
FREIGHT_PER_UNIT = 0.25
FUEL_PER_TRANSPORT_UNIT = 0.10
FINAL_PRICE = 15.0
POLICIES = ("independent", "market", "dao", "ca", "ca_t50", "hybrid")


def make_environment(seed: int, regime: str = "severe", days: int = 60) -> list[dict[str, Any]]:
    """Create one immutable exogenous path shared by every policy in a paired run."""
    if days < 1:
        raise ValueError("days must be >= 1")
    if regime not in {"normal", "volatile", "severe"}:
        raise ValueError("regime must be normal, volatile, or severe")
    rng = random.Random(seed)
    node_cost = {node: rng.uniform(0.94, 1.08) for node in NODES}
    node_capacity = {node: rng.uniform(0.90, 1.10) for node in NODES}
    path: list[dict[str, Any]] = []
    for _ in range(days):
        if regime == "normal":
            demand = [max(0.0, rng.gauss(4.0, 0.55)) for _ in range(2)]
            shock_range, common_probability, common_low = (0.78, 1.0), 0.03, 0.35
        elif regime == "volatile":
            demand = [max(0.0, rng.gauss(4.0, 1.0)) for _ in range(2)]
            shock_range, common_probability, common_low = (0.50, 1.0), 0.10, 0.20
        else:
            demand = [max(0.0, rng.gauss(3.7, 1.35)) for _ in range(2)]
            shock_range, common_probability, common_low = (0.10, 1.0), 0.18, 0.0
        common = 1.0 if rng.random() > common_probability else rng.uniform(common_low, 0.65 if regime != "severe" else 0.30)
        caps = {}
        for node in NODES:
            local = rng.uniform(*shock_range)
            if regime == "severe" and node in {"R1", "R2"} and rng.random() < 0.12:
                local *= rng.uniform(0.0, 0.20)
            caps[node] = node_capacity[node] * local * common
        path.append({
            "demand": demand,
            "capacity_factor": caps,
            "cost_factor": dict(node_cost),
        })
    return path


def _choose_supplier(
    policy: str,
    candidates: tuple[str, str],
    remaining: dict[str, float],
    unit_cost: dict[str, float],
    preferred: str,
) -> str | None:
    available = [node for node in candidates if remaining[node] > 1e-9]
    if not available:
        return None
    if policy == "independent":
        return preferred if preferred in available else None
    if policy == "ca":
        if preferred in available:
            return preferred
        return next((node for node in candidates if node in available), None)
    if policy in {"ca_t50", "hybrid"}:
        threshold = 0.50 if policy == "ca_t50" else 0.35
        total = sum(max(0.0, remaining[node]) for node in candidates)
        if preferred in available and remaining[preferred] >= threshold * total:
            return preferred
        if policy == "ca_t50":
            return max(available, key=lambda node: (remaining[node], -unit_cost[node]))
    if policy in {"market", "hybrid"}:
        max_remaining = max(remaining[node] for node in available)
        return min(
            available,
            key=lambda node: (
                unit_cost[node] + 3.0 * (1.0 - remaining[node] / max_remaining),
                -remaining[node],
            ),
        )
    if policy == "dao":
        return max(available, key=lambda node: (remaining[node], -unit_cost[node]))
    raise ValueError(f"unknown policy: {policy}")


def simulate(policy: str, environment: list[dict[str, Any]], final_price: float = FINAL_PRICE) -> dict[str, Any]:
    """Run one policy on a shared environment and enforce consolidated cash conservation."""
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}")
    cash = {node: INITIAL_CASH_PER_CELL for node in NODES}
    sales = external_costs = fixed_due = fixed_paid = 0.0
    output = unmet = 0.0

    for day in environment:
        caps = {
            node: BASE_CAPACITY[node] * day["capacity_factor"][node]
            for node in NODES
        }
        used = {node: 0.0 for node in NODES}
        for assembler, preferred_component in (("A1", "C1"), ("A2", "C2")):
            demand = float(day["demand"][0 if assembler == "A1" else 1])
            unmet += demand
            batches = int(math.floor(demand / BATCH + 1e-9))
            for _ in range(batches):
                q_final = BATCH
                q_component = q_final * COMP_PER_FINAL
                q_raw = q_final * RAW_PER_FINAL
                if caps[assembler] - used[assembler] + 1e-9 < q_final:
                    break
                if caps["L"] - used["L"] + 1e-9 < q_component + q_raw:
                    break

                component_costs = {
                    node: COMP_PROCESS_COST * day["cost_factor"][node]
                    for node in ("C1", "C2")
                }
                raw_costs = {
                    node: RAW_INPUT_COST * day["cost_factor"][node]
                    for node in ("R1", "R2")
                }
                component_remaining = {node: caps[node] - used[node] for node in ("C1", "C2")}
                component_supplier = _choose_supplier(
                    policy, ("C1", "C2"), component_remaining,
                    component_costs, preferred_component,
                )
                if component_supplier is None or component_remaining[component_supplier] + 1e-9 < q_component:
                    break

                preferred_raw = "R1" if component_supplier == "C1" else "R2"
                raw_remaining = {node: caps[node] - used[node] for node in ("R1", "R2")}
                raw_supplier = _choose_supplier(
                    policy, ("R1", "R2"), raw_remaining, raw_costs, preferred_raw,
                )
                if raw_supplier is None or raw_remaining[raw_supplier] + 1e-9 < q_raw:
                    break

                raw_external = q_raw * raw_costs[raw_supplier]
                component_external = q_component * component_costs[component_supplier]
                assembly_external = q_final * ASSEMBLY_COST * day["cost_factor"][assembler]
                fuel_external = (q_raw + q_component) * FUEL_PER_TRANSPORT_UNIT * day["cost_factor"]["L"]
                raw_freight = q_raw * FREIGHT_PER_UNIT
                component_freight = q_component * FREIGHT_PER_UNIT
                raw_payment = q_raw * RAW_TRANSFER_PRICE
                component_payment = q_component * COMP_TRANSFER_PRICE

                if cash[assembler] + 1e-9 < component_payment + component_freight + assembly_external:
                    break
                if cash[component_supplier] + component_payment + 1e-9 < raw_payment + raw_freight + component_external:
                    break
                if cash[raw_supplier] + raw_payment + 1e-9 < raw_external:
                    break
                if cash["L"] + raw_freight + component_freight + 1e-9 < fuel_external:
                    break

                # Internal transfers: assembler -> component maker -> raw maker;
                # both suppliers pay the logistics cell, which pays external fuel.
                cash[assembler] -= component_payment + component_freight + assembly_external
                cash[component_supplier] += component_payment
                cash[component_supplier] -= raw_payment + raw_freight + component_external
                cash[raw_supplier] += raw_payment
                cash[raw_supplier] -= raw_external
                cash["L"] += raw_freight + component_freight
                cash["L"] -= fuel_external
                cash[assembler] += q_final * final_price

                sales += q_final * final_price
                external_costs += raw_external + component_external + assembly_external + fuel_external
                output += q_final
                unmet -= q_final
                used[raw_supplier] += q_raw
                used[component_supplier] += q_component
                used[assembler] += q_final
                used["L"] += q_raw + q_component

        for node in NODES:
            fixed_due += FIXED_COST[node]
            paid = min(cash[node], FIXED_COST[node])
            cash[node] -= paid
            fixed_paid += paid

    opening_cash = INITIAL_CASH_PER_CELL * len(NODES)
    closing_cash = sum(cash.values())
    expected_cash = opening_cash + sales - external_costs - fixed_paid
    conservation_error = closing_cash - expected_cash
    return {
        "policy": policy,
        "days": len(environment),
        "output_units": output,
        "unmet_demand_units": unmet,
        "external_sales": sales,
        "external_variable_costs": external_costs,
        "fixed_costs_due": fixed_due,
        "fixed_costs_paid": fixed_paid,
        "operating_accrual_result": sales - external_costs - fixed_due,
        "cash_change": closing_cash - opening_cash,
        "opening_cash": opening_cash,
        "closing_cash": closing_cash,
        "cash_by_cell": dict(cash),
        "conservation_error": conservation_error,
        "internal_transfer_net_at_system_level": 0.0,
    }


def run_paired(seed: int, regime: str = "severe", days: int = 60) -> dict[str, Any]:
    """Run every policy against exactly the same exogenous path."""
    environment = make_environment(seed=seed, regime=regime, days=days)
    results = [simulate(policy, environment) for policy in POLICIES]
    return {
        "model_id": "SYNERGY_V6.6.1_7_CELL_COMPATIBILITY",
        "seed": seed,
        "regime": regime,
        "policies": results,
        "paired_environment_hash": _environment_fingerprint(environment),
    }


def _environment_fingerprint(environment: list[dict[str, Any]]) -> str:
    import hashlib
    import json

    payload = json.dumps(environment, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
