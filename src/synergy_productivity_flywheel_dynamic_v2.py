"""Ten-year expected-value model for the SYNERGY productivity flywheel.

Scenario assumptions are explicit and uncalibrated. Project yields are incremental
net residual yields after incremental OPEX and replacement obligations.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_productivity_flywheel_dynamic_v2.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def simulate_case(
    cfg: dict[str, Any],
    annual_cashflow_growth: float,
    annual_replacement_inflation: float,
    *,
    automation_yield: float | None = None,
    rd_success_probability: float | None = None,
    rd_yield_if_success: float | None = None,
) -> dict[str, Any]:
    start = cfg["starting_point"]
    tech = cfg["technology_projects"]
    alloc = cfg["allocation"]
    allocation_values = [float(v) for v in alloc.values()]
    if not all(math.isfinite(v) and v >= 0 for v in allocation_values):
        raise ValueError("Fund allocation shares must be finite and non-negative.")
    if abs(sum(allocation_values) - 1.0) > 1e-9:
        raise ValueError("Fund allocation shares must sum to 1.0.")
    if not math.isfinite(float(annual_cashflow_growth)) or annual_cashflow_growth < -1.0:
        raise ValueError("Cashflow growth must be finite and at least -100%.")
    if not math.isfinite(float(annual_replacement_inflation)) or annual_replacement_inflation < -1.0:
        raise ValueError("Replacement inflation must be finite and at least -100%.")
    auto_yield = float(tech["automation_net_residual_yield_per_year"] if automation_yield is None else automation_yield)
    rd_success = float(tech["rd_success_probability"] if rd_success_probability is None else rd_success_probability)
    rd_yield = float(tech["rd_net_residual_yield_if_success_per_year"] if rd_yield_if_success is None else rd_yield_if_success)
    if not 0 <= rd_success <= 1:
        raise ValueError("R&D success probability must be between 0 and 1.")

    gross = float(start["gross_cashflow_after_opex_before_replacement_usd"])
    replacement = float(start["replacement_capex_usd"])
    reserve = float(start["productive_capital_usd"]) * float(start["initial_reserve_share_of_productive_capital"])
    initial_reserve = reserve
    auto_projects: list[tuple[int, float]] = []
    rd_projects: list[tuple[int, float]] = []
    rows: list[dict[str, float | int]] = []

    auto_lag = int(tech["automation_deployment_lag_years"])
    auto_life = int(tech["automation_benefit_life_years"])
    rd_lag = int(tech["rd_deployment_lag_years"])
    rd_life = int(tech["rd_benefit_life_years"])
    horizon = int(cfg["horizon_years"])

    for year in range(1, horizon + 1):
        gross *= 1.0 + annual_cashflow_growth
        replacement *= 1.0 + annual_replacement_inflation
        automation_return = sum(
            amount * auto_yield
            for deployed_year, amount in auto_projects
            if deployed_year + auto_lag <= year < deployed_year + auto_lag + auto_life
        )
        rd_expected_return = sum(
            amount * rd_success * rd_yield
            for deployed_year, amount in rd_projects
            if deployed_year + rd_lag <= year < deployed_year + rd_lag + rd_life
        )
        operating_residual = gross - replacement
        residual = operating_residual + automation_return + rd_expected_return
        automation_contribution = rd_contribution = reserve_contribution = 0.0
        reserve_draw = unfunded_gap = 0.0

        if residual >= 0:
            automation_contribution = residual * float(alloc["productive_automation"])
            rd_contribution = residual * float(alloc["breakthrough_rd"])
            reserve_contribution = residual * float(alloc["resilience_reserve"])
            auto_projects.append((year, automation_contribution))
            rd_projects.append((year, rd_contribution))
            reserve += reserve_contribution
        else:
            shortfall = -residual
            reserve_draw = min(reserve, shortfall)
            reserve -= reserve_draw
            unfunded_gap = shortfall - reserve_draw

        rows.append({
            "year": year,
            "cashflow_after_opex_before_replacement_usd": gross,
            "replacement_capex_usd": replacement,
            "operating_residual_before_project_returns_usd": operating_residual,
            "automation_project_net_return_usd": automation_return,
            "rd_expected_net_return_usd": rd_expected_return,
            "residual_after_replacement_and_project_returns_usd": residual,
            "automation_fund_contribution_usd": automation_contribution,
            "rd_fund_contribution_usd": rd_contribution,
            "reserve_contribution_usd": reserve_contribution,
            "reserve_draw_usd": reserve_draw,
            "unfunded_reproduction_gap_usd": unfunded_gap,
            "reserve_end_usd": reserve,
            "cumulative_automation_deployed_usd": sum(x[1] for x in auto_projects),
            "cumulative_rd_deployed_usd": sum(x[1] for x in rd_projects),
        })

    def total(field: str) -> float:
        return float(sum(float(row[field]) for row in rows))

    return {
        "annual_cashflow_growth": annual_cashflow_growth,
        "annual_replacement_inflation": annual_replacement_inflation,
        "automation_net_residual_yield": auto_yield,
        "rd_success_probability": rd_success,
        "rd_net_residual_yield_if_success": rd_yield,
        "initial_reserve_usd": initial_reserve,
        "final_reserve_usd": reserve,
        "year_10_residual_usd": float(rows[-1]["residual_after_replacement_and_project_returns_usd"]),
        "cumulative_automation_contributions_usd": total("automation_fund_contribution_usd"),
        "cumulative_rd_contributions_usd": total("rd_fund_contribution_usd"),
        "cumulative_reserve_contributions_usd": total("reserve_contribution_usd"),
        "cumulative_reserve_draws_usd": total("reserve_draw_usd"),
        "cumulative_unfunded_gap_usd": total("unfunded_reproduction_gap_usd"),
        "annual": rows,
    }


def break_even_cashflow_growth(
    starting_cashflow: float,
    starting_replacement: float,
    replacement_inflation: float,
    years: int,
) -> float:
    """Constant annual cashflow growth needed to cover year-N replacement,
    ignoring project returns and reserve draws.
    """
    return (
        (starting_replacement * (1.0 + replacement_inflation) ** years / starting_cashflow)
        ** (1.0 / years)
        - 1.0
    )



def sector_reconciliation(
    cfg: dict[str, Any],
    annual_cashflow_growth: float,
    annual_replacement_inflation: float,
) -> dict[str, Any]:
    """Sector-level year-N residuals before portfolio-level project returns."""
    years = int(cfg["horizon_years"])
    rows = []
    for item in cfg["sector_starting_point"]:
        cash = float(item["cashflow_after_opex_before_replacement_usd"]) * (1.0 + annual_cashflow_growth) ** years
        replacement = float(item["replacement_capex_usd"]) * (1.0 + annual_replacement_inflation) ** years
        residual = cash - replacement
        required_growth = (
            (float(item["replacement_capex_usd"]) * (1.0 + annual_replacement_inflation) ** years
             / float(item["cashflow_after_opex_before_replacement_usd"])) ** (1.0 / years)
            - 1.0
        )
        rows.append({
            "sector": item["sector"],
            "year_n_cashflow_usd": cash,
            "year_n_replacement_capex_usd": replacement,
            "year_n_residual_usd": residual,
            "required_annual_cashflow_growth_for_sector_break_even": required_growth,
        })
    positive_pool = sum(max(0.0, row["year_n_residual_usd"]) for row in rows)
    negative_gap = sum(max(0.0, -row["year_n_residual_usd"]) for row in rows)
    return {
        "sectors": rows,
        "positive_sector_pool_usd": positive_pool,
        "negative_sector_gap_usd": negative_gap,
        "net_residual_usd": positive_pool - negative_gap,
        "reconciliation_error_usd": (
            positive_pool - negative_gap - sum(row["year_n_residual_usd"] for row in rows)
        ),
    }


def build_report(cfg: dict[str, Any]) -> dict[str, Any]:
    start = cfg["starting_point"]
    scenarios = []
    for case in cfg["macro_scenarios"]:
        result = simulate_case(
            cfg,
            float(case["annual_cashflow_growth"]),
            float(case["annual_replacement_inflation"]),
        )
        sectors = sector_reconciliation(
            cfg,
            float(case["annual_cashflow_growth"]),
            float(case["annual_replacement_inflation"]),
        )
        scenarios.append({"name": case["name"], **result, "sector_reconciliation_before_project_returns": sectors})
    break_even = {
        f"replacement_inflation_{int(rate * 100)}pct": break_even_cashflow_growth(
            float(start["gross_cashflow_after_opex_before_replacement_usd"]),
            float(start["replacement_capex_usd"]),
            float(rate),
            int(cfg["horizon_years"]),
        )
        for rate in (0.02, 0.05, 0.10)
    }
    return {
        "model_id": cfg["model_id"],
        "status": cfg["status"],
        "horizon_years": cfg["horizon_years"],
        "allocation": cfg["allocation"],
        "macro_scenarios": scenarios,
        "break_even_cashflow_growth_without_project_returns": break_even,
        "accounting_rules": cfg["accounting_rules"],
        "interpretation": (
            "This is a deterministic expected-value scenario engine, not a forecast. "
            "The R&D probability-weighted return hides project-level variance; a "
            "separate Monte Carlo / cohort-risk model is required before funding decisions."
        ),
    }
