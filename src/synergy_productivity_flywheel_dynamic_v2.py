"""Ten-year expected-value model for the SYNERGY productivity flywheel.

Scenario assumptions are explicit and uncalibrated. Project yields are incremental
net residual yields after incremental OPEX and replacement obligations.
"""
from __future__ import annotations

import json
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
    if abs(sum(float(v) for v in alloc.values()) - 1.0) > 1e-9:
        raise ValueError("Fund allocation shares must sum to 1.0.")
    if not 0.0 <= annual_cashflow_growth:
        raise ValueError("Cashflow growth cannot be negative in this scenario engine.")
    if not 0.0 <= annual_replacement_inflation:
        raise ValueError("Replacement inflation cannot be negative.")
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


def build_report(cfg: dict[str, Any]) -> dict[str, Any]:
    start = cfg["starting_point"]
    scenarios = []
    for case in cfg["macro_scenarios"]:
        result = simulate_case(
            cfg,
            float(case["annual_cashflow_growth"]),
            float(case["annual_replacement_inflation"]),
        )
        scenarios.append({"name": case["name"], **result})
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
