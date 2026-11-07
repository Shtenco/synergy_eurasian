"""Paired financing-policy experiments for the SYNERGY V6.6.3 network."""
from __future__ import annotations

from statistics import mean, median
import math
from typing import Any, Iterable

from .network import make_environment, simulate
from .network_topology import CELLS

FINANCING_MODES = {
    "unconstrained_reference": None,
    "cash_only": {"bank_limit_per_cell": 0.0, "trade_credit_limit_per_cell": 0.0},
    "bank_only": {"bank_limit_per_cell": 80.0, "trade_credit_limit_per_cell": 0.0},
    "mutual_credit": {
        "bank_limit_per_cell": 0.0, "trade_credit_limit_per_cell": 80.0,
        "regional_pool_reserve_per_region": 20.0,
    },
    "hybrid": {
        "bank_limit_per_cell": 80.0, "trade_credit_limit_per_cell": 80.0,
        "regional_pool_reserve_per_region": 20.0,
    },
}

BASE_CONFIG = {
    "initial_cash_per_cell": 150.0,
    "trade_receivable_limit_per_cell": 100.0,
    "regional_pool_limit_per_region": 150.0,
    "regional_member_debit_limit_per_cell": 80.0,
    "regional_member_credit_limit_per_cell": 80.0,
    "customer_receivable_limit_per_cell": 250.0,
    "customer_recovery_rate": 0.90,
    "customer_grace_days": 2,
    "grace_days": 2,
    "customer_terms_days": 2,
    "local_terms_days": 3,
    "cross_border_terms_days": 5,
}

METRICS = (
    "finished_output",
    "sold_units",
    "unmet_demand_units",
    "service_level",
    "expired_units",
    "closing_inventory_units",
    "defaulted_cells",
    "bank_debt",
    "bank_draws",
    "trade_payables",
    "customer_bad_debt",
    "production_rejections",
    "purchase_rejections",
    "customer_invoice_rejections",
    "regional_pool_outstanding",
    "regional_pool_rejections",
    "regional_pool_net_position_error",
    "regional_pool_utilization_max",
    "regional_pool_reserve_balance",
    "regional_pool_guarantee_paid",
    "trade_bad_debt",
    "external_supplier_bad_debt",
    "physical_balance_error",
    "cash_conservation_error",
)


def _metrics(result: dict[str, Any]) -> dict[str, float]:
    credit = result.get("credit_ledger")
    if credit is None:
        credit = {
            "defaulted_cells": [],
            "bank_debt_by_cell": {},
            "bank_draws": 0.0,
            "trade_payable_by_cell": {},
            "customer_bad_debt": 0.0,
            "production_rejection_count": 0,
            "purchase_rejection_count": 0,
            "customer_invoice_rejection_count": 0,
            "regional_pool_outstanding_by_region": {},
            "regional_pool_rejection_count": 0,
            "regional_pool_net_position_by_region": {},
            "regional_pool_utilization_by_region": {},
            "regional_pool_reserve_by_region": {},
            "regional_pool_guarantee_paid_by_region": {},
            "trade_bad_debt_by_cell": {},
            "external_supplier_bad_debt": 0.0,
            "cash_conservation_error": 0.0,
        }
    sold = sum(result["sold_by_sku"].values())
    unmet = sum(result["unmet_demand_by_sku"].values())
    return {
        "finished_output": result["produced_by_sku"]["bread"] + result["produced_by_sku"]["packed_food"],
        "sold_units": sold,
        "unmet_demand_units": unmet,
        "service_level": sold / (sold + unmet) if sold + unmet > 0 else 1.0,
        "expired_units": sum(result["expired_by_sku"].values()),
        "closing_inventory_units": result["closing_stock"],
        "defaulted_cells": float(len(credit["defaulted_cells"])),
        "bank_debt": sum(credit["bank_debt_by_cell"].values()),
        "bank_draws": float(credit["bank_draws"]),
        "trade_payables": sum(credit["trade_payable_by_cell"].values()),
        "customer_bad_debt": float(credit["customer_bad_debt"]),
        "production_rejections": float(credit["production_rejection_count"]),
        "purchase_rejections": float(credit["purchase_rejection_count"]),
        "customer_invoice_rejections": float(credit["customer_invoice_rejection_count"]),
        "regional_pool_outstanding": sum(credit["regional_pool_outstanding_by_region"].values()),
        "regional_pool_rejections": float(credit["regional_pool_rejection_count"]),
        "regional_pool_net_position_error": max((abs(v) for v in credit["regional_pool_net_position_by_region"].values()), default=0.0),
        "regional_pool_utilization_max": max(credit["regional_pool_utilization_by_region"].values(), default=0.0),
        "regional_pool_reserve_balance": sum(credit["regional_pool_reserve_by_region"].values()),
        "regional_pool_guarantee_paid": sum(credit["regional_pool_guarantee_paid_by_region"].values()),
        "trade_bad_debt": sum(credit["trade_bad_debt_by_cell"].values()),
        "external_supplier_bad_debt": float(credit["external_supplier_bad_debt"]),
        "physical_balance_error": abs(float(result["physical_balance_error"])),
        "cash_conservation_error": abs(float(credit["cash_conservation_error"])),
    }


def compare_financing_modes(
    seeds: Iterable[int],
    days: int = 45,
    shock_regime: str = "volatile",
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all funding modes on identical exogenous environments for each seed."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    if len(set(seed_list)) != len(seed_list):
        raise ValueError("seeds must be unique")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seed_list):
        raise ValueError("seeds must be integers")
    config = dict(BASE_CONFIG)
    if base_config:
        config.update(base_config)

    observations: dict[str, list[dict[str, Any]]] = {mode: [] for mode in FINANCING_MODES}
    paired: list[dict[str, Any]] = []
    for seed in seed_list:
        environment = make_environment(seed, days, shock_regime)
        hashes: dict[str, str] = {}
        for mode, overrides in FINANCING_MODES.items():
            if overrides is None:
                result = simulate(environment)
            else:
                mode_config = dict(config)
                mode_config.update(overrides)
                if mode in {"mutual_credit", "hybrid"}:
                    mode_config["regional_pool_reserve_per_region"] = config.get(
                        "regional_pool_reserve_per_region", 20.0
                    )
                result = simulate(environment, credit_config=mode_config)
            hashes[mode] = result["environment_hash"]
            metrics = _metrics(result)
            observations[mode].append({"seed": seed, **metrics})
        paired.append({"seed": seed, "environment_hashes": hashes})

    summary = {}
    for mode, rows in observations.items():
        summary[mode] = {
            metric: {
                "mean": mean(row[metric] for row in rows),
                "median": median(row[metric] for row in rows),
                "min": min(row[metric] for row in rows),
                "max": max(row[metric] for row in rows),
            }
            for metric in METRICS
        }

    reference_by_seed = {row["seed"]: row for row in observations["unconstrained_reference"]}
    paired_deltas = {}
    delta_summary = {}
    for mode, rows in observations.items():
        if mode == "unconstrained_reference":
            continue
        deltas = []
        for row in rows:
            reference = reference_by_seed[row["seed"]]
            deltas.append({
                "seed": row["seed"],
                **{metric: row[metric] - reference[metric] for metric in METRICS},
            })
        paired_deltas[mode] = deltas
        delta_summary[mode] = {
            metric: {
                "mean": mean(row[metric] for row in deltas),
                "median": median(row[metric] for row in deltas),
                "min": min(row[metric] for row in deltas),
                "max": max(row[metric] for row in deltas),
            }
            for metric in METRICS
        }

    return {
        "model_id": "SYNERGY_V6.6.3D_PAIRED_FINANCING_EXPERIMENT",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "base_config": config,
        "financing_modes": list(FINANCING_MODES),
        "paired_environment_hashes": paired,
        "observations": observations,
        "summary": summary,
        "paired_deltas_vs_unconstrained_reference": paired_deltas,
        "paired_delta_summary_vs_unconstrained_reference": delta_summary,
        "interpretation_guard": (
            "Synthetic paired experiment only. Do not infer causal superiority from a single seed. "
            "Compare distributions across seeds and regimes; validate parameters against observed data."
        ),
    }



def compare_all_shock_regimes(
    seeds: Iterable[int],
    days: int = 45,
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run paired financing comparisons under normal, volatile and severe shocks."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    reports = {
        regime: compare_financing_modes(seed_list, days, regime, base_config)
        for regime in ("normal", "volatile", "severe")
    }
    return {
        "model_id": "SYNERGY_V6.6.3E_MULTI_REGIME_FINANCING_STRESS",
        "days": days,
        "seeds": seed_list,
        "shock_regimes": list(reports),
        "reports_by_regime": reports,
        "interpretation_guard": (
            "Synthetic paired multi-regime experiment. Compare paired distributions and downside "
            "metrics; this report does not establish real-world policy superiority."
        ),
    }



def compare_regional_pool_sensitivities(
    seeds: Iterable[int],
    days: int = 45,
    shock_regime: str = "volatile",
    pool_limits: Iterable[float] = (10.0, 25.0, 150.0),
    member_limits: Iterable[float] = (5.0, 15.0, 80.0),
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare mutual-credit/hybrid outcomes over regional pool and member caps."""
    seed_list = list(seeds)
    pool_values = list(pool_limits)
    member_values = list(member_limits)
    if not seed_list:
        raise ValueError("at least one seed is required")
    if not pool_values or not member_values:
        raise ValueError("pool_limits and member_limits must be non-empty")
    for value in pool_values + member_values:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError("pool and member limits must be non-negative numbers")

    reports = []
    for pool_limit in pool_values:
        for member_limit in member_values:
            config = dict(base_config or {})
            config.update({
                "regional_pool_limit_per_region": float(pool_limit),
                "regional_member_debit_limit_per_cell": float(member_limit),
                "regional_member_credit_limit_per_cell": float(member_limit),
            })
            report = compare_financing_modes(seed_list, days, shock_regime, config)
            reports.append({
                "pool_limit_per_region": float(pool_limit),
                "member_debit_and_credit_limit_per_cell": float(member_limit),
                "summary": report["summary"],
                "paired_delta_summary_vs_unconstrained_reference": report["paired_delta_summary_vs_unconstrained_reference"],
                "observations": report["observations"],
                "paired_environment_hashes": report["paired_environment_hashes"],
            })
    return {
        "model_id": "SYNERGY_V6.6.4B_REGIONAL_POOL_SENSITIVITY",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "pool_limits": [float(x) for x in pool_values],
        "member_limits": [float(x) for x in member_values],
        "sensitivity_reports": reports,
        "interpretation_guard": (
            "Synthetic sensitivity grid only. Pool ceilings and member caps are design parameters, "
            "not empirically calibrated limits or policy recommendations."
        ),
    }


def build_regional_reserve_contributions(
    scheme: str,
    reserve_per_region: float = 20.0,
) -> dict[str, float]:
    """Build explicit per-cell reserve contributions for a documented allocation rule."""
    if scheme not in {"equal_all_members", "production_capacity_weighted"}:
        raise ValueError("unsupported reserve contribution scheme")
    if isinstance(reserve_per_region, bool) or not isinstance(reserve_per_region, (int, float)):
        raise ValueError("reserve_per_region must be a finite non-negative number")
    if not math.isfinite(float(reserve_per_region)) or reserve_per_region < 0:
        raise ValueError("reserve_per_region must be a finite non-negative number")

    contributions: dict[str, float] = {}
    for region in sorted({cell.region for cell in CELLS}):
        members = [cell for cell in CELLS if cell.region == region]
        if scheme == "equal_all_members":
            weights = {cell.cell_id: 1.0 for cell in members}
        else:
            weights = {
                cell.cell_id: cell.capacity if cell.sector in {"primary", "processing", "manufacturing"} else 0.0
                for cell in members
            }
        total_weight = sum(weights.values())
        if total_weight <= 0 and reserve_per_region > 0:
            raise ValueError(f"no positive contribution weights in region {region}")
        for cell in members:
            contributions[cell.cell_id] = (
                float(reserve_per_region) * weights[cell.cell_id] / total_weight
                if total_weight > 0 else 0.0
            )
    return contributions


def compare_reserve_contribution_schemes(
    seeds: Iterable[int],
    days: int = 45,
    shock_regime: str = "severe",
    reserve_per_region: float = 20.0,
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Paired comparison of equal-member and production-capacity reserve funding."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    reports = {}
    for scheme in ("equal_all_members", "production_capacity_weighted"):
        config = dict(base_config or {})
        config["regional_pool_reserve_per_region"] = float(reserve_per_region)
        config["regional_reserve_contributions_by_cell"] = build_regional_reserve_contributions(
            scheme, reserve_per_region
        )
        report = compare_financing_modes(seed_list, days, shock_regime, config)
        reports[scheme] = {
            "contributions_by_cell": config["regional_reserve_contributions_by_cell"],
            "comparison": report,
        }
    return {
        "model_id": "SYNERGY_V6.6.4D_RESERVE_CONTRIBUTION_FAIRNESS",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "reserve_per_region": float(reserve_per_region),
        "reports_by_contribution_scheme": reports,
        "interpretation_guard": (
            "Synthetic burden-allocation comparison only. Capacity weighting is not a normative "
            "fairness rule; it may exclude support cells that still benefit from the guarantee."
        ),
    }
