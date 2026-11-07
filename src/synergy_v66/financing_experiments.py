"""Paired financing-policy experiments for the SYNERGY V6.6.3 network."""
from __future__ import annotations

from statistics import mean, median
import math
from typing import Any, Iterable

from .network import make_environment, simulate
from .network_topology import CELLS
from .credit import CreditLedger

EPS = 1e-9

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
    "federation_pool_reserve_balance",
    "federation_pool_guarantee_paid",
    "regional_member_assessment_paid",
    "regional_member_assessment_attempts",
    "regional_assessment_requested",
    "regional_assessment_eligible_capacity",
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
            "federation_pool_reserve_balance": 0.0,
            "federation_pool_guarantee_paid": 0.0,
            "regional_assessment_paid_by_region": {},
            "regional_assessment_attempt_count": 0,
            "regional_assessment_requested_by_region": {},
            "regional_assessment_eligible_capacity_by_region": {},
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
        "federation_pool_reserve_balance": float(credit["federation_pool_reserve_balance"]),
        "federation_pool_guarantee_paid": float(credit["federation_pool_guarantee_paid"]),
        "regional_member_assessment_paid": sum(credit["regional_assessment_paid_by_region"].values()),
        "regional_member_assessment_attempts": float(credit["regional_assessment_attempt_count"]),
        "regional_assessment_requested": sum(credit["regional_assessment_requested_by_region"].values()),
        "regional_assessment_eligible_capacity": sum(credit["regional_assessment_eligible_capacity_by_region"].values()),
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
                else:
                    mode_config.pop("regional_pool_reserve_per_region", None)
                    mode_config.pop("regional_reserve_contributions_by_cell", None)
                    mode_config.pop("regional_assessment_rate", None)
                    mode_config.pop("regional_assessment_limit_per_cell", None)
                    mode_config.pop("federation_pool_reserve_total", None)
                    mode_config.pop("federation_reserve_contributions_by_cell", None)
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




def run_targeted_regional_default_stress_cases() -> dict[str, Any]:
    """Force local and cross-region defaults to verify each loss-waterfall boundary."""
    cases = {
        "local_reserve_only": {
            "seller": "WEST-AG1", "assessment_rate": 0.0, "assessment_cap": 2.0,
        },
        "local_reserve_plus_assessment": {
            "seller": "WEST-AG1", "assessment_rate": 0.10, "assessment_cap": 2.0,
        },
        "local_tightly_capped_assessment": {
            "seller": "WEST-AG1", "assessment_rate": 0.10, "assessment_cap": 0.25,
        },
        "cross_region_assessment_ineligible": {
            "seller": "EAST-AG1", "assessment_rate": 0.10, "assessment_cap": 2.0,
            "federation_reserve": 0.0,
        },
        "cross_region_federation_pool": {
            "seller": "EAST-AG1", "assessment_rate": 0.0, "assessment_cap": 0.0,
            "federation_reserve": 5.0,
        },
    }
    reports = {}
    for name, settings in cases.items():
        ledger = CreditLedger(
            initial_cash_per_cell=20.0,
            trade_credit_limit_per_cell=50.0,
            regional_pool_limit_per_region=100.0,
            regional_pool_reserve_per_region=5.0,
            federation_pool_reserve_total=settings.get("federation_reserve", 0.0),
            regional_assessment_rate=settings["assessment_rate"],
            regional_assessment_limit_per_cell=settings["assessment_cap"],
            grace_days=0,
        )
        purchase = ledger.authorize_purchase(
            "WEST-PR1", settings["seller"], 30.0, 0, 0, f"TARGETED-{name.upper()}"
        )
        if not purchase["authorized"]:
            raise RuntimeError(f"targeted stress purchase was unexpectedly rejected: {name}")
        ledger.process_day(0)
        snapshot = ledger.snapshot()
        invoice = ledger.payables[purchase["invoice_id"]]
        reports[name] = {
            "seller": settings["seller"],
            "purchase": purchase,
            "guarantee_paid": invoice.guarantee_paid,
            "federation_guarantee_paid": invoice.federation_guarantee_paid,
            "member_assessment_paid": invoice.member_assessment_paid,
            "written_off": invoice.written_off,
            "regional_assessment_attempt_count": snapshot["regional_assessment_attempt_count"],
            "regional_assessment_requested_by_region": snapshot["regional_assessment_requested_by_region"],
            "regional_assessment_eligible_capacity_by_region": snapshot["regional_assessment_eligible_capacity_by_region"],
            "regional_assessment_contributed_by_cell": snapshot["regional_assessment_contributed_by_cell"],
            "trade_bad_debt_by_cell": snapshot["trade_bad_debt_by_cell"],
            "external_supplier_bad_debt": snapshot["external_supplier_bad_debt"],
            "regional_pool_reserve_by_region": snapshot["regional_pool_reserve_by_region"],
            "federation_pool_reserve_balance": snapshot["federation_pool_reserve_balance"],
            "federation_pool_guarantee_paid": snapshot["federation_pool_guarantee_paid"],
            "cash_conservation_error": snapshot["cash_conservation_error"],
        }
    return {
        "model_id": "SYNERGY_V6.6.4F_TARGETED_DEFAULT_STRESS",
        "synthetic_fixture": True,
        "days": 1,
        "cases": reports,
        "interpretation_guard": (
            "Deliberately forced deterministic defaults verify ledger mechanics only; they are not "
            "probability estimates or evidence about real regional default frequency."
        ),
    }

def compare_regional_loss_waterfalls(
    seeds: Iterable[int],
    days: int = 45,
    shock_regime: str = "severe",
    reserve_per_region: float = 20.0,
    assessment_rate: float = 0.10,
    assessment_limit_per_cell: float = 2.0,
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare reserve-only loss coverage with a capped pro-rata member assessment."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    if (
        isinstance(assessment_rate, bool)
        or not math.isfinite(float(assessment_rate))
        or not 0.0 <= assessment_rate <= 1.0
        or isinstance(assessment_limit_per_cell, bool)
        or not math.isfinite(float(assessment_limit_per_cell))
        or assessment_limit_per_cell < 0
    ):
        raise ValueError("assessment rate must be finite and in [0, 1]; member cap must be finite and >= 0")
    cases = {
        "reserve_only": {
            "regional_assessment_rate": 0.0,
            "regional_assessment_limit_per_cell": 0.0,
        },
        "reserve_plus_capped_assessment": {
            "regional_assessment_rate": float(assessment_rate),
            "regional_assessment_limit_per_cell": float(assessment_limit_per_cell),
        },
    }
    reports = {}
    for case_name, assessment_config in cases.items():
        config = dict(base_config or {})
        config.update({
            "regional_pool_reserve_per_region": float(reserve_per_region),
            **assessment_config,
        })
        reports[case_name] = compare_financing_modes(seed_list, days, shock_regime, config)
    return {
        "model_id": "SYNERGY_V6.6.4E_REGIONAL_LOSS_WATERFALL",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "reserve_per_region": float(reserve_per_region),
        "assessment_rate": float(assessment_rate),
        "assessment_limit_per_cell": float(assessment_limit_per_cell),
        "reports_by_waterfall": reports,
        "targeted_default_stress": run_targeted_regional_default_stress_cases(),
        "interpretation_guard": (
            "Synthetic loss-waterfall comparison. Member assessments are cash transfers, not new "
            "money; the model does not establish legal authority or normative fairness."
        ),
    }


def make_synthetic_heterogeneous_cash_fixture(
    base_cash: float = 80.0,
    increment_per_cell: float = 5.0,
) -> dict[str, float]:
    """Deterministic synthetic opening-cash fixture for liquidity-cap stress tests."""
    if (
        isinstance(base_cash, bool) or not isinstance(base_cash, (int, float))
        or not math.isfinite(float(base_cash)) or base_cash < 0
        or isinstance(increment_per_cell, bool) or not isinstance(increment_per_cell, (int, float))
        or not math.isfinite(float(increment_per_cell)) or increment_per_cell < 0
    ):
        raise ValueError("synthetic cash fixture parameters must be finite and non-negative")
    return {
        cell.cell_id: float(base_cash) + index * float(increment_per_cell)
        for index, cell in enumerate(CELLS)
    }


def build_liquidity_capped_reserve_contributions(
    scheme: str,
    reserve_per_region: float,
    initial_cash_by_cell: dict[str, float],
    max_contribution_fraction: float = 0.10,
) -> dict[str, float]:
    """Allocate a regional reserve by weights without exceeding member liquidity caps."""
    if scheme not in {"equal_all_members", "production_capacity_weighted"}:
        raise ValueError("unsupported reserve contribution scheme")
    if set(initial_cash_by_cell) != {cell.cell_id for cell in CELLS}:
        raise ValueError("initial cash map must contain every known cell exactly once")
    if (
        isinstance(reserve_per_region, bool)
        or not isinstance(reserve_per_region, (int, float))
        or not math.isfinite(float(reserve_per_region))
        or reserve_per_region < 0
    ):
        raise ValueError("reserve_per_region must be finite and non-negative")
    if (
        isinstance(max_contribution_fraction, bool)
        or not isinstance(max_contribution_fraction, (int, float))
        or not math.isfinite(float(max_contribution_fraction))
        or not 0.0 <= max_contribution_fraction <= 1.0
    ):
        raise ValueError("max_contribution_fraction must be finite and in [0, 1]")
    cash: dict[str, float] = {}
    for cell_id, amount in initial_cash_by_cell.items():
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(float(amount))
            or amount < 0
        ):
            raise ValueError("member opening cash must be finite and non-negative")
        cash[cell_id] = float(amount)

    result = {cell.cell_id: 0.0 for cell in CELLS}
    for region in sorted({cell.region for cell in CELLS}):
        members = [cell for cell in CELLS if cell.region == region]
        if scheme == "equal_all_members":
            weights = {cell.cell_id: 1.0 for cell in members}
        else:
            weights = {
                cell.cell_id: cell.capacity
                if cell.sector in {"primary", "processing", "manufacturing"} else 0.0
                for cell in members
            }
        caps = {
            cell.cell_id: cash[cell.cell_id] * float(max_contribution_fraction)
            for cell in members
        }
        target = float(reserve_per_region)
        if sum(caps.values()) + 1e-9 < target:
            raise ValueError(f"member liquidity caps cannot fund the requested reserve in {region}")
        active = {cell.cell_id for cell in members if weights[cell.cell_id] > 0 and caps[cell.cell_id] > 0}
        remaining = target
        while remaining > 1e-10:
            total_weight = sum(weights[cell_id] for cell_id in active)
            if total_weight <= 0:
                raise ValueError(f"no eligible weighted contributors remain in {region}")
            saturated = []
            for cell_id in sorted(active):
                proposed = remaining * weights[cell_id] / total_weight
                room = caps[cell_id] - result[cell_id]
                if proposed >= room - 1e-12:
                    saturated.append(cell_id)
            if not saturated:
                for cell_id in active:
                    result[cell_id] += remaining * weights[cell_id] / total_weight
                remaining = 0.0
            else:
                for cell_id in saturated:
                    room = max(0.0, caps[cell_id] - result[cell_id])
                    result[cell_id] += room
                    remaining -= room
                    active.remove(cell_id)
        # Correct floating-point drift on a member with remaining headroom.
        residual = target - sum(result[cell.cell_id] for cell in members)
        if abs(residual) > 1e-10:
            if residual > 0:
                candidates = [
                    cell.cell_id for cell in members
                    if caps[cell.cell_id] - result[cell.cell_id] >= residual - 1e-12
                ]
            else:
                candidates = [
                    cell.cell_id for cell in members
                    if result[cell.cell_id] >= -residual - 1e-12
                ]
            if not candidates:
                raise ArithmeticError(f"cannot reconcile reserve allocation for {region}")
            result[sorted(candidates)[-1]] += residual
    return result


def compare_liquidity_capped_reserve_contributions(
    seeds: Iterable[int],
    initial_cash_by_cell: dict[str, float],
    days: int = 45,
    shock_regime: str = "severe",
    reserve_per_region: float = 10.0,
    max_contribution_fraction: float = 0.10,
    scheme: str = "production_capacity_weighted",
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Paired experiment for a contribution rule bounded by each member's opening liquidity."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    contributions = build_liquidity_capped_reserve_contributions(
        scheme, reserve_per_region, initial_cash_by_cell, max_contribution_fraction
    )
    config = dict(base_config or {})
    config.update({
        "initial_cash_by_cell": dict(initial_cash_by_cell),
        "regional_pool_reserve_per_region": float(reserve_per_region),
        "regional_reserve_contributions_by_cell": contributions,
    })
    report = compare_financing_modes(seed_list, days, shock_regime, config)
    return {
        "model_id": "SYNERGY_V6.6.4F_LIQUIDITY_CAPPED_RESERVE",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "reserve_per_region": float(reserve_per_region),
        "max_contribution_fraction": float(max_contribution_fraction),
        "scheme": scheme,
        "initial_cash_by_cell": dict(initial_cash_by_cell),
        "contributions_by_cell": contributions,
        "comparison": report,
        "interpretation_guard": (
            "Synthetic contribution-cap experiment. A cash-fraction cap limits initial burden, "
            "but does not establish fairness, ability to pay, benefit received or legal enforceability."
        ),
    }


def compare_regional_reserve_size_sensitivities(
    seeds: Iterable[int],
    reserve_levels_per_region: Iterable[float],
    days: int = 45,
    shock_regime: str = "severe",
    contribution_scheme: str = "equal_all_members",
    max_contribution_fraction: float | None = None,
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure reserve coverage against the member-liquidity opportunity cost on paired paths."""
    seed_list = list(seeds)
    levels = list(reserve_levels_per_region)
    if not seed_list or not levels:
        raise ValueError("at least one seed and one reserve level are required")
    if len(set(seed_list)) != len(seed_list) or any(
        not isinstance(seed, int) or isinstance(seed, bool) for seed in seed_list
    ):
        raise ValueError("seeds must be unique integers")
    if any(
        isinstance(level, bool) or not isinstance(level, (int, float))
        or not math.isfinite(float(level)) or level < 0
        for level in levels
    ):
        raise ValueError("reserve levels must be finite non-negative numbers")
    if len(set(float(level) for level in levels)) != len(levels):
        raise ValueError("reserve levels must be unique")
    if contribution_scheme not in {"equal_all_members", "production_capacity_weighted"}:
        raise ValueError("unsupported reserve contribution scheme")
    if max_contribution_fraction is not None and (
        isinstance(max_contribution_fraction, bool)
        or not isinstance(max_contribution_fraction, (int, float))
        or not math.isfinite(float(max_contribution_fraction))
        or not 0.0 <= max_contribution_fraction <= 1.0
    ):
        raise ValueError("max_contribution_fraction must be finite and in [0, 1]")

    config_base = dict(base_config or {})
    config_base.pop("regional_reserve_contributions_by_cell", None)
    initial_cash = config_base.get("initial_cash_by_cell")
    if initial_cash is None:
        scalar_cash = float(config_base.get("initial_cash_per_cell", BASE_CONFIG["initial_cash_per_cell"]))
        initial_cash = {cell.cell_id: scalar_cash for cell in CELLS}
    reports = []
    for level in levels:
        if max_contribution_fraction is None:
            contributions = build_regional_reserve_contributions(contribution_scheme, float(level))
        else:
            contributions = build_liquidity_capped_reserve_contributions(
                contribution_scheme, float(level), initial_cash, float(max_contribution_fraction)
            )
        config = dict(config_base)
        config["regional_pool_reserve_per_region"] = float(level)
        config["regional_reserve_contributions_by_cell"] = contributions
        comparison = compare_financing_modes(seed_list, days, shock_regime, config)
        mode_diagnostics = {}
        for mode in ("mutual_credit", "hybrid"):
            rows = comparison["observations"][mode]
            initial_total = 2.0 * float(level)
            reserve_paid = [row["regional_pool_guarantee_paid"] for row in rows]
            reserve_remaining = [row["regional_pool_reserve_balance"] for row in rows]
            bad_debt = [row["trade_bad_debt"] for row in rows]
            mode_diagnostics[mode] = {
                "initial_reserve_total": initial_total,
                "reserve_paid_mean": mean(reserve_paid),
                "reserve_remaining_mean": mean(reserve_remaining),
                "reserve_exhaustion_rate": mean(
                    1.0 if initial_total > EPS and remaining <= EPS and paid > EPS else 0.0
                    for remaining, paid in zip(reserve_remaining, reserve_paid)
                ),
                "reserve_utilization_mean": (
                    mean(paid / initial_total for paid in reserve_paid)
                    if initial_total > EPS else 0.0
                ),
                "seller_trade_bad_debt_mean": mean(bad_debt),
                "service_level_mean": mean(row["service_level"] for row in rows),
                "defaults_mean": mean(row["defaulted_cells"] for row in rows),
                "cash_conservation_error_max": max(row["cash_conservation_error"] for row in rows),
            }
        reports.append({
            "reserve_per_region": float(level),
            "total_initial_reserve": 2.0 * float(level),
            "contributions_by_cell": contributions,
            "comparison": comparison,
            "diagnostics": mode_diagnostics,
        })
    return {
        "model_id": "SYNERGY_V6.6.4G_REGIONAL_RESERVE_ADEQUACY",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "contribution_scheme": contribution_scheme,
        "max_contribution_fraction": max_contribution_fraction,
        "sensitivity_reports": reports,
        "interpretation_guard": (
            "Synthetic reserve sizing sensitivity. Larger reserves improve nominal claim capacity "
            "but reduce member cash at initialization; service-level and default outcomes need not "
            "improve monotonically. Results are not empirical reserve recommendations."
        ),
    }
