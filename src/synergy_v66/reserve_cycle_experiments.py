"""Paired 100-cycle reserve recovery stress experiments.

Claims are exogenous synthetic guarantee demands, not simulated borrower defaults.
The ledger's stress-only claim hook transfers existing reserve cash to a member
beneficiary; it creates no cash, credit, bank funding or external inflow.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from statistics import mean, median
from typing import Any, Iterable

from .credit import CreditLedger, EPS
from .network_topology import CELLS, REGIONS
from .reserve_recovery import execute_reserve_recovery, plan_reserve_recovery

ALLOCATION_RULES = (
    "no_replenishment",
    "equal",
    "production_capacity",
    "opening_cash",
    "adaptive_liquidity",
)
SHOCK_RANGES = {
    "moderate": (1.0, 2.0),
    "severe": (4.0, 6.0),
    "systemic": (7.0, 10.0),
}
REGIONAL_TARGET = 20.0
FEDERATION_TARGET = 40.0
MINIMUM_CASH_FLOOR = 20.0
PERIOD_CONTRIBUTION_FRACTION = 0.10


def _gini(values: list[float]) -> float:
    ordered = sorted(max(0.0, float(value)) for value in values)
    total = sum(ordered)
    if not ordered or total <= EPS:
        return 0.0
    n = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return max(0.0, min(1.0, (2.0 * weighted) / (n * total) - (n + 1) / n))


def _paired_path(seed: int, cycles: int, shock_regime: str) -> tuple[dict[str, float], list[dict[str, float]], str]:
    rng = random.Random(seed)
    opening_cash = {cell.cell_id: round(rng.uniform(80.0, 120.0), 8) for cell in CELLS}
    low, high = SHOCK_RANGES[shock_regime]
    shocks = [
        {region: round(rng.uniform(low, high), 8) for region in REGIONS}
        for _ in range(cycles)
    ]
    payload = {"opening_cash": opening_cash, "claims_by_day": shocks}
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return opening_cash, shocks, fingerprint


def _new_ledger(opening_cash: dict[str, float]) -> CreditLedger:
    return CreditLedger(
        initial_cash_by_cell=opening_cash,
        regional_pool_reserve_per_region=REGIONAL_TARGET,
        federation_pool_reserve_total=FEDERATION_TARGET,
        minimum_post_contribution_cash=MINIMUM_CASH_FLOOR,
        reserve_recovery_contribution_fraction=PERIOD_CONTRIBUTION_FRACTION,
    )


def _run_one_path(
    seed: int,
    cycles: int,
    shock_regime: str,
    allocation_rule: str,
    opening_cash: dict[str, float],
    shocks: list[dict[str, float]],
    path_fingerprint: str,
) -> dict[str, Any]:
    ledger = _new_ledger(opening_cash)
    ledger.process_day(0)
    total_requested = 0.0
    total_paid = 0.0
    total_uncovered = 0.0
    total_replenished = 0.0
    total_recovery_requested = 0.0
    total_recovery_unfunded = 0.0
    reserve_exhaustion_cycles = 0
    regional_reserve_exhaustion_cycles = 0
    federation_reserve_exhaustion_cycles = 0
    cycles_at_target_after_recovery = 0
    cash_floor_breach_count = 0
    max_cash_conservation_error = 0.0
    max_period_cap_excess = 0.0
    cumulative_contributions = {cell.cell_id: 0.0 for cell in CELLS}
    cycle_rows: list[dict[str, float]] = []

    for day, region_claims in enumerate(shocks):
        if day > 0:
            ledger.process_day(day)
        day_requested = 0.0
        day_paid = 0.0
        day_uncovered = 0.0
        for region in REGIONS:
            beneficiary = f"{region}-MF1"
            claim = ledger.apply_exogenous_guarantee_claim(
                claim_id=f"SEED-{seed}-{allocation_rule}-DAY-{day}-{region}",
                region=region,
                beneficiary_cell=beneficiary,
                amount=region_claims[region],
                day=day,
            )
            day_requested += float(claim["requested"])
            day_paid += float(claim["paid"])
            day_uncovered += float(claim["uncovered"])

        post_claim_snapshot = ledger.snapshot()
        reserves_after_claim = (
            float(post_claim_snapshot["regional_pool_reserve_by_region"]["WEST"]),
            float(post_claim_snapshot["regional_pool_reserve_by_region"]["EAST"]),
            float(post_claim_snapshot["federation_pool_reserve_balance"]),
        )
        max_cash_conservation_error = max(
            max_cash_conservation_error,
            abs(float(post_claim_snapshot["cash_conservation_error"])),
        )
        day_replenished = 0.0
        day_recovery_requested = 0.0
        day_recovery_unfunded = 0.0
        if allocation_rule != "no_replenishment":
            plan = plan_reserve_recovery(
                ledger,
                target_regional_by_region={region: REGIONAL_TARGET for region in REGIONS},
                target_federation=FEDERATION_TARGET,
                allocation_rule=allocation_rule,
            )
            day_recovery_requested = float(plan["requested_total"])
            day_recovery_unfunded = float(plan["unfunded_total"])
            if float(plan["funded_total"]) > EPS:
                settled = execute_reserve_recovery(
                    ledger,
                    plan,
                    replenishment_id=f"RECOVERY-{seed}-{allocation_rule}-{day}",
                    day=day,
                )
                day_replenished = float(settled["total_amount"])
                for cell_id in cumulative_contributions:
                    cumulative_contributions[cell_id] += (
                        float(plan["regional_contributions_by_cell"][cell_id])
                        + float(plan["federation_contributions_by_cell"][cell_id])
                    )

        snapshot = ledger.snapshot()
        member_cash = list(snapshot["cash_by_cell"].values())
        floor_breaches = sum(value < MINIMUM_CASH_FLOOR - EPS for value in member_cash)
        cash_error = abs(float(snapshot["cash_conservation_error"]))
        cash_floor_breach_count += floor_breaches
        max_cash_conservation_error = max(max_cash_conservation_error, cash_error)
        period_caps = {
            cell_id: opening_cash[cell_id] * PERIOD_CONTRIBUTION_FRACTION
            for cell_id in opening_cash
        }
        period_used = {
            cell_id: sum(
                float(event["amount"])
                for event in ledger.events
                if event.get("recovery_period_id") == f"day-window-{day // 30}"
                and event.get("cell_id") == cell_id
                and event.get("type") in {
                    "regional_reserve_replenishment_contribution",
                    "federation_reserve_replenishment_contribution",
                }
            )
            for cell_id in opening_cash
        }
        max_period_cap_excess = max(
            max_period_cap_excess,
            max((period_used[key] - period_caps[key] for key in opening_cash), default=0.0),
        )
        regional_exhausted = any(value <= EPS for value in reserves_after_claim[:2])
        federation_exhausted = reserves_after_claim[2] <= EPS
        if regional_exhausted or federation_exhausted:
            reserve_exhaustion_cycles += 1
        if regional_exhausted:
            regional_reserve_exhaustion_cycles += 1
        if federation_exhausted:
            federation_reserve_exhaustion_cycles += 1
        if (
            all(abs(snapshot["regional_pool_reserve_by_region"][region] - REGIONAL_TARGET) <= EPS for region in REGIONS)
            and abs(snapshot["federation_pool_reserve_balance"] - FEDERATION_TARGET) <= EPS
        ):
            cycles_at_target_after_recovery += 1

        total_requested += day_requested
        total_paid += day_paid
        total_uncovered += day_uncovered
        total_replenished += day_replenished
        total_recovery_requested += day_recovery_requested
        total_recovery_unfunded += day_recovery_unfunded
        cycle_rows.append({
            "day": float(day),
            "claim_requested": day_requested,
            "claim_paid": day_paid,
            "claim_uncovered": day_uncovered,
            "replenished": day_replenished,
            "recovery_unfunded": day_recovery_unfunded,
            "member_cash_total": sum(member_cash),
            "member_cash_min": min(member_cash),
            "regional_reserve_total": sum(snapshot["regional_pool_reserve_by_region"].values()),
            "federation_reserve": float(snapshot["federation_pool_reserve_balance"]),
            "cash_conservation_error": cash_error,
        })

    final = ledger.snapshot()
    final_cash = list(final["cash_by_cell"].values())
    # Opening cash is the total member funding before initial reserve allocations;
    # adding initial reserves again would double-count the same contributed money.
    total_initial_cash_and_reserves = sum(opening_cash.values())
    final_cash_and_reserves = (
        sum(final_cash)
        + sum(final["regional_pool_reserve_by_region"].values())
        + float(final["federation_pool_reserve_balance"])
    )
    return {
        "seed": seed,
        "cycles": cycles,
        "shock_regime": shock_regime,
        "allocation_rule": allocation_rule,
        "paired_path_fingerprint": path_fingerprint,
        "total_claim_requested": total_requested,
        "total_claim_paid": total_paid,
        "total_claim_uncovered": total_uncovered,
        "claim_coverage_ratio": total_paid / total_requested if total_requested > EPS else 1.0,
        "total_replenished": total_replenished,
        "total_recovery_requested": total_recovery_requested,
        "total_recovery_unfunded": total_recovery_unfunded,
        "recovery_funding_ratio": (
            (total_recovery_requested - total_recovery_unfunded) / total_recovery_requested
            if total_recovery_requested > EPS else 1.0
        ),
        "reserve_exhaustion_cycles": reserve_exhaustion_cycles,
        "regional_reserve_exhaustion_cycles": regional_reserve_exhaustion_cycles,
        "federation_reserve_exhaustion_cycles": federation_reserve_exhaustion_cycles,
        "cycles_at_target_after_recovery": cycles_at_target_after_recovery,
        "cash_floor_breach_count": cash_floor_breach_count,
        "minimum_final_member_cash": min(final_cash),
        "mean_final_member_cash": mean(final_cash),
        "final_member_cash_gini": _gini(final_cash),
        "final_regional_reserve_total": sum(final["regional_pool_reserve_by_region"].values()),
        "final_federation_reserve": float(final["federation_pool_reserve_balance"]),
        "max_cash_conservation_error": max_cash_conservation_error,
        "max_period_cap_excess": max(0.0, max_period_cap_excess),
        "initial_system_cash": total_initial_cash_and_reserves,
        "final_system_cash": final_cash_and_reserves,
        "system_cash_change": final_cash_and_reserves - total_initial_cash_and_reserves,
        "bank_draws": float(final["bank_draws"]),
        "external_inflows": 0.0,
        "cycle_rows": cycle_rows,
        "interpretation_guard": (
            "Synthetic exogenous claim stress only, not borrower-default simulation. Claims transfer "
            "existing reserve cash to member beneficiaries. No external inflows, bank draws, new "
            "credit or money creation are permitted. Results are not empirical EAEU estimates."
        ),
    }


def run_paired_reserve_recovery_experiment(
    seeds: Iterable[int] = (11, 23, 37),
    cycles: int = 100,
    shock_regime: str = "severe",
    allocation_rules: Iterable[str] = ALLOCATION_RULES,
) -> dict[str, Any]:
    """Compare no-replenishment and four recovery rules on identical 100-cycle paths."""
    seed_list = list(seeds)
    rules = list(allocation_rules)
    if not seed_list or len(set(seed_list)) != len(seed_list):
        raise ValueError("seeds must be non-empty and unique")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seed_list):
        raise ValueError("seeds must be integers")
    if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 1:
        raise ValueError("cycles must be a positive integer")
    if shock_regime not in SHOCK_RANGES:
        raise ValueError(f"shock_regime must be one of {sorted(SHOCK_RANGES)}")
    if not rules or len(set(rules)) != len(rules) or any(rule not in ALLOCATION_RULES for rule in rules):
        raise ValueError("allocation_rules must be a non-empty unique subset of supported rules")

    observations: dict[str, list[dict[str, Any]]] = {rule: [] for rule in rules}
    paired_paths = []
    for seed in seed_list:
        opening_cash, shocks, fingerprint = _paired_path(seed, cycles, shock_regime)
        paired_paths.append({"seed": seed, "path_fingerprint": fingerprint})
        for rule in rules:
            observations[rule].append(
                _run_one_path(seed, cycles, shock_regime, rule, opening_cash, shocks, fingerprint)
            )

    scalar_metrics = (
        "total_claim_requested",
        "total_claim_paid",
        "total_claim_uncovered",
        "claim_coverage_ratio",
        "total_replenished",
        "total_recovery_unfunded",
        "reserve_exhaustion_cycles",
        "regional_reserve_exhaustion_cycles",
        "federation_reserve_exhaustion_cycles",
        "cycles_at_target_after_recovery",
        "cash_floor_breach_count",
        "minimum_final_member_cash",
        "final_member_cash_gini",
        "final_regional_reserve_total",
        "final_federation_reserve",
        "max_cash_conservation_error",
        "max_period_cap_excess",
        "system_cash_change",
    )
    summary = {
        rule: {
            metric: {
                "mean": mean(float(row[metric]) for row in rows),
                "median": median(float(row[metric]) for row in rows),
                "min": min(float(row[metric]) for row in rows),
                "max": max(float(row[metric]) for row in rows),
            }
            for metric in scalar_metrics
        }
        for rule, rows in observations.items()
    }
    return {
        "model_id": "SYNERGY_V6.6.4O_100_CYCLE_RESERVE_SURVIVAL",
        "cycles": cycles,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "allocation_rules": rules,
        "paired_paths": paired_paths,
        "observations": observations,
        "summary": summary,
        "invariants": {
            "zero_external_inflows": True,
            "zero_bank_draws_expected": True,
            "cash_floor_enforced": True,
            "period_contribution_cap_enforced": True,
            "cash_conservation_checked_each_cycle": True,
        },
        "interpretation_guard": (
            "A synthetic 100-cycle liquidity and reserve-recovery stress test. It is not a full "
            "default-resolution experiment: exogenous claims bypass debtor default status while "
            "preserving the local-first/federation-second cash waterfall."
        ),
    }
