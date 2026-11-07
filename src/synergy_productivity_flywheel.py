"""Sensitivity model for the SYNERGY AI / automation / R&D productivity flywheel.

This is an illustrative scenario engine, not a forecast. It does not assume
that AI, cellular automata, or R&D automatically produce a financial return.
"""
from __future__ import annotations

import json
from pathlib import Path
import math
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_productivity_flywheel_v1.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def calculate(cfg: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        raise ValueError("Productivity flywheel config must be an object")
    base = cfg["baseline"]
    gross0 = _finite_number(base["gross_cashflow_usd"], "gross_cashflow_usd")
    replacement0 = _finite_number(base["replacement_capex_usd"], "replacement_capex_usd")
    first_uplift = _finite_number(
        base["initial_operating_cashflow_uplift"], "initial_operating_cashflow_uplift"
    )
    replacement_saving = _finite_number(
        base["replacement_cost_reduction"], "replacement_cost_reduction"
    )
    if gross0 <= 0 or replacement0 <= 0:
        raise ValueError("Baseline cashflow and replacement capex must be positive")
    if first_uplift < -1.0:
        raise ValueError("Initial operating cashflow uplift cannot be below -100%")
    if not 0.0 <= replacement_saving < 1.0:
        raise ValueError("Replacement cost reduction must be in [0, 1)")
    repaired_gross = gross0 * (1.0 + first_uplift)
    repaired_replacement = replacement0 * (1.0 - replacement_saving)
    allocation = cfg["residual_fund_allocation"]
    if not isinstance(allocation, Mapping) or not allocation:
        raise ValueError("Residual fund allocation must be a non-empty object")
    allocation_values = {
        name: _finite_number(value, f"residual_fund_allocation.{name}")
        for name, value in allocation.items()
    }
    if any(not 0.0 <= value <= 1.0 for value in allocation_values.values()):
        raise ValueError("Residual fund allocation shares must be in [0, 1]")
    allocation_total = sum(allocation_values.values())
    if abs(allocation_total - 1.0) > 1e-9:
        raise ValueError("Residual fund allocations must sum to 1.0.")
    additional_scenarios = cfg["additional_productivity_uplift_scenarios"]
    stress_scenarios = cfg["stress_scenarios"]
    if not isinstance(additional_scenarios, list) or not additional_scenarios:
        raise ValueError("At least one additional productivity scenario is required")
    if not isinstance(stress_scenarios, list):
        raise ValueError("Stress scenarios must be an array")

    scenarios = []
    for extra_raw in additional_scenarios:
        extra = _finite_number(extra_raw, "additional_productivity_uplift")
        if extra < -1.0:
            raise ValueError("Additional productivity uplift cannot be below -100%")
        gross = repaired_gross * (1.0 + extra)
        residual = gross - repaired_replacement
        positive_residual = max(0.0, residual)
        fund_allocations = {
            name: positive_residual * share
            for name, share in allocation_values.items()
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
    for item in stress_scenarios:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("Each stress scenario requires a non-empty name")
        cash_shock = _finite_number(item["cashflow_shock"], "stress cashflow_shock")
        replacement_inflation = _finite_number(
            item["replacement_inflation"], "stress replacement_inflation"
        )
        if not 0.0 <= cash_shock < 1.0:
            raise ValueError("Stress cashflow shock must be in [0, 1)")
        if replacement_inflation < -1.0:
            raise ValueError("Stress replacement inflation cannot be below -100%")
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
        "fund_allocation_shares": allocation_values,
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
