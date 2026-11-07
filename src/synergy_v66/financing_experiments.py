"""Paired financing-policy experiments for the SYNERGY V6.6.3 network."""
from __future__ import annotations

from statistics import mean, median
from typing import Any, Iterable

from .network import make_environment, simulate

FINANCING_MODES = {
    "unconstrained_reference": None,
    "cash_only": {"bank_limit_per_cell": 0.0, "trade_credit_limit_per_cell": 0.0},
    "bank_only": {"bank_limit_per_cell": 80.0, "trade_credit_limit_per_cell": 0.0},
    "mutual_credit": {"bank_limit_per_cell": 0.0, "trade_credit_limit_per_cell": 80.0},
    "hybrid": {"bank_limit_per_cell": 80.0, "trade_credit_limit_per_cell": 80.0},
}

BASE_CONFIG = {
    "initial_cash_per_cell": 150.0,
    "trade_receivable_limit_per_cell": 100.0,
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
