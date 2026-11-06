"""Sensitivity model for the SYNERGY AI / automation / R&D productivity flywheel.

This is an illustrative scenario engine, not a forecast. It does not assume
that AI, cellular automata, or R&D automatically produce a financial return.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_productivity_flywheel_v1.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def calculate(cfg: dict[str, Any]) -> dict[str, Any]:
    base = cfg["baseline"]
    gross0 = float(base["gross_cashflow_usd"])
    replacement0 = float(base["replacement_capex_usd"])
    first_uplift = float(base["initial_operating_cashflow_uplift"])
    replacement_saving = float(base["replacement_cost_reduction"])
    repaired_gross = gross0 * (1.0 + first_uplift)
    repaired_replacement = replacement0 * (1.0 - replacement_saving)
    allocation = cfg["residual_fund_allocation"]
    allocation_total = sum(float(v) for v in allocation.values())
    if abs(allocation_total - 1.0) > 1e-9:
        raise ValueError("Residual fund allocations must sum to 1.0.")

    scenarios = []
    for extra in cfg["additional_productivity_uplift_scenarios"]:
        extra = float(extra)
        gross = repaired_gross * (1.0 + extra)
        residual = gross - repaired_replacement
        positive_residual = max(0.0, residual)
        fund_allocations = {
            name: positive_residual * float(share)
            for name, share in allocation.items()
        }
        scenarios.append({
            "additional_productivity_uplift": extra,
            "gross_cashflow_usd": gross,
            "replacement_capex_usd": repaired_replacement,
            "residual_after_replacement_usd": residual,
            "replacement_coverage": gross / repaired_replacement,
            "fund_allocations_usd": fund_allocations,
            "unfunded_gap_usd": max(0.0, -residual),
        })

    stress = []
    for item in cfg["stress_scenarios"]:
        cash_shock = float(item["cashflow_shock"])
        replacement_inflation = float(item["replacement_inflation"])
        stressed_gross = repaired_gross * (1.0 - cash_shock)
        stressed_replacement = repaired_replacement * (1.0 + replacement_inflation)
        stressed_residual = stressed_gross - stressed_replacement
        required_extra_uplift = (
            stressed_replacement / (repaired_gross * (1.0 - cash_shock))
        ) - 1.0
        # This is the extra uplift required on top of the first repair package,
        # before applying the cashflow shock.
        stress.append({
            "name": item["name"],
            "cashflow_shock": cash_shock,
            "replacement_inflation": replacement_inflation,
            "stressed_gross_cashflow_usd": stressed_gross,
            "stressed_replacement_capex_usd": stressed_replacement,
            "stressed_residual_usd": stressed_residual,
            "required_additional_productivity_uplift_for_break_even": required_extra_uplift,
        })

    return {
        "model_id": cfg["model_id"],
        "status": cfg["status"],
        "baseline_repaired_gross_cashflow_usd": repaired_gross,
        "baseline_repaired_replacement_capex_usd": repaired_replacement,
        "baseline_repaired_residual_usd": repaired_gross - repaired_replacement,
        "fund_allocation_shares": allocation,
        "productivity_scenarios": scenarios,
        "stress_scenarios": stress,
        "accounting_rules": cfg["accounting_rules"],
        "interpretation": (
            "The flywheel is conditional: measured productivity gains create "
            "residual; residual funds capacity, R&D and reserves; R&D creates "
            "additional value only after validated deployment. No R&D return "
            "is credited in this model."
        ),
    }
