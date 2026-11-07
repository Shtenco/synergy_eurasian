"""Monte Carlo stress model for the SYNERGY productivity flywheel.

All distributions are illustrative and uncalibrated. The output is conditional
on assumptions, not a forecast or empirical probability of failure.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_productivity_flywheel_monte_carlo_v3.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite JSON number")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _strict_int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def simulate_paths(cfg: dict[str, Any], shock_probability: float) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        raise ValueError("Monte Carlo config must be an object")
    shock_probability = _finite_number(shock_probability, "shock_probability")
    if not 0.0 <= shock_probability <= 1.0:
        raise ValueError("Shock probability must be between 0 and 1.")
    rng = np.random.default_rng(_strict_int(cfg["random_seed"], "random_seed", 0))
    n_paths = _strict_int(cfg["paths"], "paths", 1)
    years = _strict_int(cfg["horizon_years"], "horizon_years", 1)
    start = cfg["starting_point"]
    uncertainty = cfg["annual_uncertainty"]
    shock = cfg["correlated_shock"]
    auto = cfg["automation_projects"]
    rd = cfg["rd_projects"]
    allocation = cfg["fund_allocation"]
    required_funds = {"productive_automation", "breakthrough_rd", "resilience_reserve"}
    if not isinstance(allocation, dict) or set(allocation) != required_funds:
        raise ValueError("Fund allocation must contain exactly the three modeled funds")
    allocation_values = {
        name: _finite_number(value, f"fund_allocation.{name}")
        for name, value in allocation.items()
    }
    if any(not 0.0 <= value <= 1.0 for value in allocation_values.values()):
        raise ValueError("Fund allocation shares must be between 0 and 1.")
    if abs(sum(allocation_values.values()) - 1.0) > 1e-9:
        raise ValueError("Fund allocation shares must sum to 1.0.")

    productive_capital = _finite_number(start["productive_capital_usd"], "productive_capital_usd")
    reserve_share = _finite_number(
        start["initial_reserve_share_of_productive_capital"],
        "initial_reserve_share_of_productive_capital",
    )
    gross0 = _finite_number(
        start["gross_cashflow_after_opex_before_replacement_usd"],
        "gross_cashflow_after_opex_before_replacement_usd",
    )
    replacement0 = _finite_number(start["replacement_capex_usd"], "replacement_capex_usd")
    if productive_capital <= 0 or gross0 <= 0 or replacement0 <= 0:
        raise ValueError("Starting productive capital, cashflow and replacement capex must be positive")
    if not 0.0 <= reserve_share <= 1.0:
        raise ValueError("Initial reserve share must be between 0 and 1")
    initial_reserve = _finite_number(
        productive_capital * reserve_share, "initial reserve"
    )

    uncertainty_fields = (
        "cashflow_growth_mean", "cashflow_growth_std",
        "cashflow_growth_min", "cashflow_growth_max",
        "replacement_inflation_mean", "replacement_inflation_std",
        "replacement_inflation_min", "replacement_inflation_max",
    )
    uncertainty_values = {
        key: _finite_number(uncertainty[key], f"annual_uncertainty.{key}")
        for key in uncertainty_fields
    }
    if uncertainty_values["cashflow_growth_std"] < 0 or uncertainty_values["replacement_inflation_std"] < 0:
        raise ValueError("Annual uncertainty standard deviations must be non-negative")
    if uncertainty_values["cashflow_growth_min"] > uncertainty_values["cashflow_growth_max"]:
        raise ValueError("Cashflow growth minimum cannot exceed maximum")
    if uncertainty_values["replacement_inflation_min"] > uncertainty_values["replacement_inflation_max"]:
        raise ValueError("Replacement inflation minimum cannot exceed maximum")
    if uncertainty_values["cashflow_growth_min"] < -1.0 or uncertainty_values["replacement_inflation_min"] < -1.0:
        raise ValueError("Annual growth and inflation bounds cannot be below -100%")

    shock_cash = _finite_number(
        shock["cashflow_growth_additive_shock"], "cashflow_growth_additive_shock"
    )
    shock_replacement = _finite_number(
        shock["replacement_inflation_additive_shock"], "replacement_inflation_additive_shock"
    )
    auto_lag = _strict_int(auto["deployment_lag_years"], "automation deployment lag", 0)
    auto_life = _strict_int(auto["benefit_life_years"], "automation benefit life", 1)
    auto_mean = _finite_number(auto["annual_net_residual_yield_mean"], "automation yield mean")
    auto_std = _finite_number(auto["annual_net_residual_yield_std"], "automation yield std")
    auto_min = _finite_number(auto["yield_min"], "automation yield minimum")
    if auto_mean < 0 or auto_std < 0 or auto_min < 0:
        raise ValueError("Automation yield assumptions must be non-negative")
    rd_count = _strict_int(rd["independent_projects_per_year"], "independent_projects_per_year", 1)
    rd_lag = _strict_int(rd["deployment_lag_years"], "R&D deployment lag", 0)
    rd_life = _strict_int(rd["benefit_life_years"], "R&D benefit life", 1)
    rd_probability = _finite_number(
        rd["success_probability_per_project"], "success_probability_per_project"
    )
    rd_yield = _finite_number(
        rd["annual_net_residual_yield_if_success"], "annual_net_residual_yield_if_success"
    )
    if not 0.0 <= rd_probability <= 1.0 or rd_yield < 0:
        raise ValueError("R&D success probability must be in [0, 1] and yield non-negative")

    final_reserves = np.zeros(n_paths)
    total_unfunded = np.zeros(n_paths)
    ever_exhausted = np.zeros(n_paths, dtype=bool)
    first_exhaustion_year = np.zeros(n_paths, dtype=int)
    final_year_residual = np.zeros(n_paths)

    for path in range(n_paths):
        gross = gross0
        replacement = replacement0
        reserve = initial_reserve
        auto_cohorts: list[tuple[int, float, float]] = []
        rd_cohorts: list[tuple[int, float, int]] = []
        unfunded = 0.0
        exhausted_year = 0

        for year in range(1, years + 1):
            growth = float(np.clip(
                rng.normal(
                    uncertainty_values["cashflow_growth_mean"],
                    uncertainty_values["cashflow_growth_std"],
                ),
                uncertainty_values["cashflow_growth_min"],
                uncertainty_values["cashflow_growth_max"],
            ))
            inflation = float(np.clip(
                rng.normal(
                    uncertainty_values["replacement_inflation_mean"],
                    uncertainty_values["replacement_inflation_std"],
                ),
                uncertainty_values["replacement_inflation_min"],
                uncertainty_values["replacement_inflation_max"],
            ))
            if rng.random() < shock_probability:
                growth = max(-0.50, growth + shock_cash)
                inflation = max(-0.50, min(0.50, inflation + shock_replacement))
            gross = _finite_number(gross * (1.0 + growth), f"path {path} year {year} gross cashflow")
            replacement = _finite_number(
                replacement * (1.0 + inflation), f"path {path} year {year} replacement capex"
            )

            automation_return = sum(
                amount * yield_rate
                for deployed, amount, yield_rate in auto_cohorts
                if deployed + auto_lag <= year
                < deployed + auto_lag + auto_life
            )
            rd_return = sum(
                amount * successes / rd_count
                * rd_yield
                for deployed, amount, successes in rd_cohorts
                if deployed + rd_lag <= year
                < deployed + rd_lag + rd_life
            )
            automation_return = _finite_number(automation_return, f"path {path} year {year} automation return")
            rd_return = _finite_number(rd_return, f"path {path} year {year} R&D return")
            residual = _finite_number(
                gross - replacement + automation_return + rd_return,
                f"path {path} year {year} residual",
            )
            if residual >= 0.0:
                auto_amount = residual * allocation_values["productive_automation"]
                rd_amount = residual * allocation_values["breakthrough_rd"]
                reserve = _finite_number(
                    reserve + residual * allocation_values["resilience_reserve"],
                    f"path {path} year {year} reserve",
                )
                auto_yield = _finite_number(
                    max(auto_min, float(rng.normal(auto_mean, auto_std))),
                    f"path {path} year {year} automation yield",
                )
                successes = int(rng.binomial(rd_count, rd_probability))
                auto_cohorts.append((year, auto_amount, auto_yield))
                rd_cohorts.append((year, rd_amount, successes))
            else:
                shortfall = -residual
                reserve_draw = min(reserve, shortfall)
                reserve = _finite_number(
                    reserve - reserve_draw, f"path {path} year {year} reserve after draw"
                )
                unfunded = _finite_number(
                    unfunded + shortfall - reserve_draw,
                    f"path {path} cumulative unfunded gap",
                )
                if reserve <= 1e-9 and unfunded > 0.0 and exhausted_year == 0:
                    exhausted_year = year

            if reserve <= 1e-9 and exhausted_year == 0 and unfunded > 0.0:
                exhausted_year = year
            if year == years:
                final_year_residual[path] = residual

        final_reserves[path] = reserve
        total_unfunded[path] = unfunded
        ever_exhausted[path] = exhausted_year > 0
        first_exhaustion_year[path] = exhausted_year

    def quantiles(values: np.ndarray) -> dict[str, float]:
        if not np.isfinite(values).all():
            raise ValueError("Monte Carlo output values must remain finite")
        q = np.quantile(values, [0.05, 0.50, 0.95])
        return {"p05": float(q[0]), "median": float(q[1]), "p95": float(q[2])}

    exhausted_years = first_exhaustion_year[first_exhaustion_year > 0]
    return {
        "shock_probability_per_year": shock_probability,
        "paths": n_paths,
        "horizon_years": years,
        "reserve_exhaustion_probability": float(ever_exhausted.mean()),
        "reserve_end_usd_quantiles": quantiles(final_reserves),
        "cumulative_unfunded_gap_usd_quantiles": quantiles(total_unfunded),
        "mean_cumulative_unfunded_gap_usd": float(total_unfunded.mean()),
        "probability_of_any_unfunded_gap": float((total_unfunded > 0).mean()),
        "median_first_exhaustion_year_conditioned_on_exhaustion": (
            float(np.median(exhausted_years)) if len(exhausted_years) else None
        ),
        "final_year_residual_usd_quantiles": quantiles(final_year_residual),
        "year_10_residual_usd_quantiles": quantiles(final_year_residual) if years == 10 else None,
    }


def build_report(cfg: dict[str, Any]) -> dict[str, Any]:
    scenarios = [
        simulate_paths(cfg, p)
        for p in cfg["correlated_shock"]["annual_probability_sensitivity"]
    ]
    return {
        "model_id": cfg["model_id"],
        "status": cfg["status"],
        "horizon_years": cfg["horizon_years"],
        "paths_per_scenario": cfg["paths"],
        "random_seed": cfg["random_seed"],
        "initial_reserve_usd": (
            float(cfg["starting_point"]["productive_capital_usd"])
            * float(cfg["starting_point"]["initial_reserve_share_of_productive_capital"])
        ),
        "shock_sensitivity": scenarios,
        "accounting_rules": cfg["accounting_rules"],
        "interpretation": (
            "These are conditional simulated frequencies under hypothetical distributions. "
            "They are not empirical forecasts, credit ratings, or guarantees."
        ),
    }
