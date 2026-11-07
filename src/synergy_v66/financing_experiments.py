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
    initial_cash_by_cell: dict[str, float] | None = None,
) -> dict[str, float]:
    """Build explicit per-cell reserve contributions for an auditable allocation rule."""
    supported = {
        "equal_all_members",
        "production_capacity_weighted",
        "opening_cash_weighted",
    }
    if scheme not in supported:
        raise ValueError("unsupported reserve contribution scheme")
    if isinstance(reserve_per_region, bool) or not isinstance(reserve_per_region, (int, float)):
        raise ValueError("reserve_per_region must be a finite non-negative number")
    if not math.isfinite(float(reserve_per_region)) or reserve_per_region < 0:
        raise ValueError("reserve_per_region must be a finite non-negative number")

    if initial_cash_by_cell is None:
        cash = {cell.cell_id: 200.0 for cell in CELLS}
    else:
        if set(initial_cash_by_cell) != {cell.cell_id for cell in CELLS}:
            raise ValueError("initial_cash_by_cell must contain every known cell exactly once")
        cash = {}
        for cell_id, amount in initial_cash_by_cell.items():
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise ValueError("opening cash must be finite non-negative numbers")
            if not math.isfinite(float(amount)) or amount < 0:
                raise ValueError("opening cash must be finite non-negative numbers")
            cash[cell_id] = float(amount)

    contributions: dict[str, float] = {}
    for region in sorted({cell.region for cell in CELLS}):
        members = [cell for cell in CELLS if cell.region == region]
        if scheme == "equal_all_members":
            weights = {cell.cell_id: 1.0 for cell in members}
        elif scheme == "production_capacity_weighted":
            weights = {
                cell.cell_id: cell.capacity if cell.sector in {"primary", "processing", "manufacturing"} else 0.0
                for cell in members
            }
        else:
            weights = {cell.cell_id: cash[cell.cell_id] for cell in members}
        total_weight = sum(weights.values())
        if total_weight <= 0 and reserve_per_region > 0:
            raise ValueError(f"no positive contribution weights in region {region}")
        for cell in members:
            contribution = (
                float(reserve_per_region) * weights[cell.cell_id] / total_weight
                if total_weight > 0 else 0.0
            )
            if contribution > cash[cell.cell_id] + 1e-9:
                raise ValueError(
                    f"reserve contribution exceeds opening cash for {cell.cell_id}"
                )
            contributions[cell.cell_id] = contribution
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
    for scheme in (
        "equal_all_members",
        "production_capacity_weighted",
        "opening_cash_weighted",
    ):
        config = dict(base_config or {})
        config["regional_pool_reserve_per_region"] = float(reserve_per_region)
        opening_cash = config.get("initial_cash_by_cell")
        if opening_cash is None:
            uniform_cash = float(config.get("initial_cash_per_cell", 200.0))
            opening_cash = {cell.cell_id: uniform_cash for cell in CELLS}
        config["regional_reserve_contributions_by_cell"] = build_regional_reserve_contributions(
            scheme, reserve_per_region, opening_cash
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
            "Synthetic burden-allocation comparison only. Production-capacity weighting may exclude "
            "support cells; opening-cash weighting scales dues with initial liquidity but does not "
            "establish benefit, risk or normative fairness."
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
    minimum_post_contribution_cash: float = 0.0,
) -> dict[str, float]:
    """Allocate a regional reserve without breaching fractional or absolute cash floors."""
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
    if (
        isinstance(minimum_post_contribution_cash, bool)
        or not isinstance(minimum_post_contribution_cash, (int, float))
        or not math.isfinite(float(minimum_post_contribution_cash))
        or minimum_post_contribution_cash < 0
    ):
        raise ValueError("minimum_post_contribution_cash must be finite and non-negative")
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
            cell.cell_id: min(
                cash[cell.cell_id] * float(max_contribution_fraction),
                max(0.0, cash[cell.cell_id] - float(minimum_post_contribution_cash)),
            )
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


def allocate_federation_reserve_claims(
    claims: Iterable[dict[str, Any]],
    reserve_available: float,
    rule: str = "first_come_first_served",
    priority_order: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Allocate finite reserve cash under FCFS, batch pro-rata or explicit class priorities."""
    supported = {
        "first_come_first_served",
        "batch_pro_rata",
        "priority_class_then_first_come_first_served",
        "priority_class_then_batch_pro_rata",
    }
    if rule not in supported:
        raise ValueError("unsupported federation reserve allocation rule")
    if (
        isinstance(reserve_available, bool) or not isinstance(reserve_available, (int, float))
        or not math.isfinite(float(reserve_available)) or reserve_available < 0
    ):
        raise ValueError("reserve_available must be finite and non-negative")
    normalized = []
    seen: set[str] = set()
    for claim in list(claims):
        if not isinstance(claim, dict):
            raise ValueError("each claim must be a mapping")
        invoice_id = claim.get("invoice_id")
        amount = claim.get("eligible_amount")
        due_day = claim.get("due_day", 0)
        claim_class = claim.get("claim_class", "standard")
        if not isinstance(invoice_id, str) or not invoice_id.strip() or invoice_id in seen:
            raise ValueError("claim invoice IDs must be non-empty and unique")
        if not isinstance(due_day, int) or isinstance(due_day, bool) or due_day < 0:
            raise ValueError("claim due_day must be a non-negative integer")
        if (
            isinstance(amount, bool) or not isinstance(amount, (int, float))
            or not math.isfinite(float(amount)) or amount < 0
        ):
            raise ValueError("claim eligible_amount must be finite and non-negative")
        if not isinstance(claim_class, str) or not claim_class.strip():
            raise ValueError("claim_class must be a non-empty string")
        seen.add(invoice_id)
        normalized.append({
            "invoice_id": invoice_id,
            "due_day": due_day,
            "eligible_amount": float(amount),
            "claim_class": claim_class,
        })

    normalized.sort(key=lambda x: (x["due_day"], x["invoice_id"]))
    classes = {item["claim_class"] for item in normalized}
    if priority_order is None:
        ordered_classes = sorted(classes)
    else:
        ordered_classes = list(priority_order)
        if (
            any(not isinstance(name, str) or not name.strip() for name in ordered_classes)
            or len(set(ordered_classes)) != len(ordered_classes)
            or set(ordered_classes) != classes
        ):
            raise ValueError("priority_order must list every claim class exactly once")
    reserve = float(reserve_available)
    allocations = {item["invoice_id"]: 0.0 for item in normalized}

    if rule == "first_come_first_served":
        remaining = reserve
        for item in normalized:
            paid = min(item["eligible_amount"], remaining)
            allocations[item["invoice_id"]] = paid
            remaining -= paid
    elif rule == "batch_pro_rata":
        total = sum(item["eligible_amount"] for item in normalized)
        if total > EPS:
            coverage = min(1.0, reserve / total)
            for item in normalized:
                allocations[item["invoice_id"]] = item["eligible_amount"] * coverage
    else:
        remaining = reserve
        for claim_class in ordered_classes:
            group = [item for item in normalized if item["claim_class"] == claim_class]
            group_total = sum(item["eligible_amount"] for item in group)
            if group_total <= EPS or remaining <= EPS:
                continue
            group_paid = min(group_total, remaining)
            if rule == "priority_class_then_first_come_first_served":
                for item in group:
                    paid = min(item["eligible_amount"], remaining)
                    allocations[item["invoice_id"]] = paid
                    remaining -= paid
                    if remaining <= EPS:
                        break
            else:
                coverage = group_paid / group_total
                for item in group:
                    allocations[item["invoice_id"]] = item["eligible_amount"] * coverage
                remaining -= group_paid

    paid_total = sum(allocations.values())
    reserve_remaining = max(0.0, reserve - paid_total)
    return {
        "rule": rule,
        "priority_order": ordered_classes,
        "reserve_opening": reserve,
        "eligible_claim_total": sum(item["eligible_amount"] for item in normalized),
        "allocated_total": paid_total,
        "reserve_remaining": reserve_remaining,
        "allocations_by_invoice": allocations,
        "uncovered_by_invoice": {
            item["invoice_id"]: item["eligible_amount"] - allocations[item["invoice_id"]]
            for item in normalized
        },
        "allocation_order": [item["invoice_id"] for item in normalized],
        "allocation_conservation_error": reserve - paid_total - reserve_remaining,
        "interpretation_guard": (
            "Batch pro-rata treats claims within a clearing batch as simultaneous. Priority rules "
            "apply explicit claim classes before due-day/invoice-ID ordering or within-class pro-rata. "
            "None of these rules is a legal creditor-priority rule."
        ),
    }


def compare_federation_reserve_allocation_rules(
    claims: Iterable[dict[str, Any]],
    reserve_available: float,
    priority_order: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Side-by-side allocation comparison on the exact same claim batch."""
    claim_list = list(claims)
    classes = {claim.get("claim_class", "standard") for claim in claim_list if isinstance(claim, dict)}
    order = list(priority_order) if priority_order is not None else sorted(classes)
    rules = (
        "first_come_first_served",
        "batch_pro_rata",
        "priority_class_then_first_come_first_served",
        "priority_class_then_batch_pro_rata",
    )
    return {
        "model_id": "SYNERGY_V6.6.4L_FEDERATION_CLAIM_PRIORITY",
        "claims": claim_list,
        "reserve_available": reserve_available,
        "priority_order": order,
        "reports_by_rule": {
            rule: allocate_federation_reserve_claims(claim_list, reserve_available, rule, order)
            for rule in rules
        },
        "interpretation_guard": (
            "Allocation-rule comparison only. Priority classes are synthetic labels and are not legal "
            "seniority. The operational ledger supports FCFS and batch pro-rata; class-priority rules "
            "remain analytical alternatives."
        ),
    }


def build_liquidity_capped_federation_contributions(
    reserve_total: float,
    initial_cash_by_cell: dict[str, float],
    max_combined_contribution_fraction: float = 0.10,
    scheme: str = "equal_all_members",
    regional_contributions_by_cell: dict[str, float] | None = None,
    minimum_post_contribution_cash: float = 0.0,
) -> dict[str, float]:
    """Allocate a federation reserve within combined fractional and absolute member cash floors."""
    cell_ids = {cell.cell_id for cell in CELLS}
    if set(initial_cash_by_cell) != cell_ids:
        raise ValueError("initial cash map must contain every known cell exactly once")
    if scheme not in {"equal_all_members", "production_capacity_weighted"}:
        raise ValueError("unsupported federation contribution scheme")
    if (
        isinstance(reserve_total, bool) or not isinstance(reserve_total, (int, float))
        or not math.isfinite(float(reserve_total)) or reserve_total < 0
    ):
        raise ValueError("federation reserve total must be finite and non-negative")
    if (
        isinstance(max_combined_contribution_fraction, bool)
        or not isinstance(max_combined_contribution_fraction, (int, float))
        or not math.isfinite(float(max_combined_contribution_fraction))
        or not 0.0 <= max_combined_contribution_fraction <= 1.0
    ):
        raise ValueError("combined contribution cap fraction must be finite and in [0, 1]")

    if (
        isinstance(minimum_post_contribution_cash, bool)
        or not isinstance(minimum_post_contribution_cash, (int, float))
        or not math.isfinite(float(minimum_post_contribution_cash))
        or minimum_post_contribution_cash < 0
    ):
        raise ValueError("minimum_post_contribution_cash must be finite and non-negative")
    cash: dict[str, float] = {}
    for cell_id, amount in initial_cash_by_cell.items():
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount < 0:
            raise ValueError("member opening cash must be finite and non-negative")
        cash[cell_id] = float(amount)

    regional = {cell_id: 0.0 for cell_id in cell_ids}
    if regional_contributions_by_cell is not None:
        if set(regional_contributions_by_cell) != cell_ids:
            raise ValueError("regional contribution map must contain every known cell exactly once")
        for cell_id, amount in regional_contributions_by_cell.items():
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount < 0:
                raise ValueError("regional contributions must be finite and non-negative")
            regional[cell_id] = float(amount)

    combined_caps = {
        cell_id: min(
            cash[cell_id] * float(max_combined_contribution_fraction),
            max(0.0, cash[cell_id] - float(minimum_post_contribution_cash)),
        )
        for cell_id in cell_ids
    }
    caps = {
        cell_id: max(0.0, combined_caps[cell_id] - regional[cell_id])
        for cell_id in cell_ids
    }
    if any(regional[cell_id] > combined_caps[cell_id] + 1e-9 for cell_id in cell_ids):
        raise ValueError("regional contributions already exceed the declared combined member cap")
    if sum(caps.values()) + 1e-9 < float(reserve_total):
        raise ValueError("remaining member liquidity caps cannot fund the federation reserve")

    weights = {}
    for cell in CELLS:
        if scheme == "equal_all_members":
            weights[cell.cell_id] = 1.0
        else:
            weights[cell.cell_id] = (
                cell.capacity if cell.sector in {"primary", "processing", "manufacturing"} else 0.0
            )
    allocations = {cell_id: 0.0 for cell_id in cell_ids}
    active = {cell_id for cell_id in cell_ids if weights[cell_id] > 0 and caps[cell_id] > 0}
    remaining = float(reserve_total)
    while remaining > 1e-10:
        total_weight = sum(weights[cell_id] for cell_id in active)
        if total_weight <= 0:
            raise ValueError("no eligible weighted federation contributors remain")
        saturated = []
        for cell_id in sorted(active):
            proposed = remaining * weights[cell_id] / total_weight
            room = caps[cell_id] - allocations[cell_id]
            if proposed >= room - 1e-12:
                saturated.append(cell_id)
        if not saturated:
            for cell_id in active:
                allocations[cell_id] += remaining * weights[cell_id] / total_weight
            remaining = 0.0
        else:
            for cell_id in saturated:
                room = max(0.0, caps[cell_id] - allocations[cell_id])
                allocations[cell_id] += room
                remaining -= room
                active.remove(cell_id)

    residual = float(reserve_total) - sum(allocations.values())
    if abs(residual) > 1e-10:
        candidates = [
            cell_id for cell_id in cell_ids
            if caps[cell_id] - allocations[cell_id] >= residual - 1e-12
        ] if residual > 0 else [
            cell_id for cell_id in cell_ids if allocations[cell_id] >= -residual - 1e-12
        ]
        if not candidates:
            raise ArithmeticError("cannot reconcile federation reserve contribution allocation")
        allocations[sorted(candidates)[-1]] += residual
    return allocations


def compare_liquidity_capped_federation_contributions(
    seeds: Iterable[int],
    initial_cash_by_cell: dict[str, float],
    reserve_total: float = 20.0,
    max_combined_contribution_fraction: float = 0.10,
    scheme: str = "equal_all_members",
    days: int = 45,
    shock_regime: str = "severe",
    base_config: dict[str, Any] | None = None,
    minimum_post_contribution_cash: float = 0.0,
) -> dict[str, Any]:
    """Paired federation reserve experiment under combined member liquidity constraints."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    config = dict(base_config or {})
    regional_map = config.get("regional_reserve_contributions_by_cell")
    federal_map = build_liquidity_capped_federation_contributions(
        reserve_total,
        initial_cash_by_cell,
        max_combined_contribution_fraction,
        scheme,
        regional_map,
        minimum_post_contribution_cash,
    )
    config.update({
        "initial_cash_by_cell": dict(initial_cash_by_cell),
        "federation_pool_reserve_total": float(reserve_total),
        "federation_reserve_contributions_by_cell": federal_map,
        "minimum_post_contribution_cash": float(minimum_post_contribution_cash),
    })
    report = compare_financing_modes(seed_list, days, shock_regime, config)
    return {
        "model_id": "SYNERGY_V6.6.4I_LIQUIDITY_CAPPED_FEDERATION_RESERVE",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "reserve_total": float(reserve_total),
        "max_combined_contribution_fraction": float(max_combined_contribution_fraction),
        "minimum_post_contribution_cash": float(minimum_post_contribution_cash),
        "scheme": scheme,
        "initial_cash_by_cell": dict(initial_cash_by_cell),
        "regional_contributions_by_cell": regional_map or {cell.cell_id: 0.0 for cell in CELLS},
        "federation_contributions_by_cell": federal_map,
        "comparison": report,
        "interpretation_guard": (
            "Synthetic federation funding experiment. The combined cap limits reserve contributions "
            "as a share of opening cash; it does not establish fairness, benefit or legal authority."
        ),
    }


def compare_liquidity_capped_reserve_contributions(
    seeds: Iterable[int],
    initial_cash_by_cell: dict[str, float],
    days: int = 45,
    shock_regime: str = "severe",
    reserve_per_region: float = 10.0,
    max_contribution_fraction: float = 0.10,
    scheme: str = "production_capacity_weighted",
    base_config: dict[str, Any] | None = None,
    minimum_post_contribution_cash: float = 0.0,
) -> dict[str, Any]:
    """Paired experiment bounded by fractional contribution caps and absolute cash floors."""
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    contributions = build_liquidity_capped_reserve_contributions(
        scheme, reserve_per_region, initial_cash_by_cell,
        max_contribution_fraction, minimum_post_contribution_cash,
    )
    config = dict(base_config or {})
    config.update({
        "initial_cash_by_cell": dict(initial_cash_by_cell),
        "regional_pool_reserve_per_region": float(reserve_per_region),
        "regional_reserve_contributions_by_cell": contributions,
        "minimum_post_contribution_cash": float(minimum_post_contribution_cash),
    })
    report = compare_financing_modes(seed_list, days, shock_regime, config)
    return {
        "model_id": "SYNERGY_V6.6.4F_LIQUIDITY_CAPPED_RESERVE",
        "days": days,
        "shock_regime": shock_regime,
        "seeds": seed_list,
        "reserve_per_region": float(reserve_per_region),
        "max_contribution_fraction": float(max_contribution_fraction),
        "minimum_post_contribution_cash": float(minimum_post_contribution_cash),
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
    minimum_post_contribution_cash: float = 0.0,
) -> dict[str, Any]:
    """Measure reserve coverage against member-liquidity cost under an optional cash floor."""
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
    if (
        isinstance(minimum_post_contribution_cash, bool)
        or not isinstance(minimum_post_contribution_cash, (int, float))
        or not math.isfinite(float(minimum_post_contribution_cash))
        or minimum_post_contribution_cash < 0
    ):
        raise ValueError("minimum_post_contribution_cash must be finite and non-negative")

    config_base = dict(base_config or {})
    config_base.pop("regional_reserve_contributions_by_cell", None)
    initial_cash = config_base.get("initial_cash_by_cell")
    if initial_cash is None:
        scalar_cash = float(config_base.get("initial_cash_per_cell", BASE_CONFIG["initial_cash_per_cell"]))
        initial_cash = {cell.cell_id: scalar_cash for cell in CELLS}
    reports = []
    for level in levels:
        if max_contribution_fraction is None and minimum_post_contribution_cash <= 0:
            contributions = build_regional_reserve_contributions(contribution_scheme, float(level))
        else:
            effective_fraction = (
                1.0 if max_contribution_fraction is None
                else float(max_contribution_fraction)
            )
            contributions = build_liquidity_capped_reserve_contributions(
                contribution_scheme, float(level), initial_cash,
                effective_fraction, float(minimum_post_contribution_cash),
            )
        config = dict(config_base)
        config["regional_pool_reserve_per_region"] = float(level)
        config["regional_reserve_contributions_by_cell"] = contributions
        config["minimum_post_contribution_cash"] = float(minimum_post_contribution_cash)
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
        "minimum_post_contribution_cash": float(minimum_post_contribution_cash),
        "sensitivity_reports": reports,
        "interpretation_guard": (
            "Synthetic reserve sizing sensitivity. Larger reserves improve nominal claim capacity "
            "but reduce member cash at initialization; service-level and default outcomes need not "
            "improve monotonically. Results are not empirical reserve recommendations."
        ),
    }
