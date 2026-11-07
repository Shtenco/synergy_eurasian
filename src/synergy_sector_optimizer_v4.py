"""Sector-level capital allocator for the SYNERGY productive network.

This is a transparent linear-programming scenario model. All project inputs are
illustrative until replaced by measured enterprise data. Internal transfers are
not counted as consolidated value.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_sector_optimizer_v4.json"
METRICS = (
    "annual_net_residual_yield",
    "output_gain_per_1000",
    "unit_cost_reduction_per_1000",
    "labor_hours_released_per_1000",
)


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a numeric value, not a boolean or string")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _validate(cfg: dict[str, Any], budget: float) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("Sector optimizer config must be an object")
    try:
        budget = _number(budget, "investment budget")
    except ValueError as exc:
        raise ValueError("Investment budget must be finite and positive.") from exc
    if budget <= 0:
        raise ValueError("Investment budget must be finite and positive.")
    weights = cfg.get("objective_weights")
    if not isinstance(weights, dict) or set(weights) != set(METRICS):
        raise ValueError("objective_weights must define exactly the modeled metrics")
    weight_values = {}
    for key in METRICS:
        try:
            value = _number(weights[key], f"objective_weights.{key}")
        except ValueError as exc:
            raise ValueError(f"Objective weight {key} must be finite and non-negative.") from exc
        if value < 0:
            raise ValueError(f"Objective weight {key} must be finite and non-negative.")
        weight_values[key] = value
    if abs(sum(weight_values.values()) - 1.0) > 1e-9:
        raise ValueError("Objective weights must sum to 1.0.")

    norms = cfg.get("normalization")
    if not isinstance(norms, dict) or set(norms) != set(METRICS):
        raise ValueError("normalization must define exactly the modeled metrics")
    for key in METRICS:
        try:
            value = _number(norms[key], f"normalization.{key}")
        except ValueError as exc:
            raise ValueError(f"Normalization value {key} must be finite and strictly positive.") from exc
        if value <= 0:
            raise ValueError(f"Normalization value {key} must be finite and strictly positive.")

    projects = cfg.get("projects")
    if not isinstance(projects, list) or not projects or any(not isinstance(p, dict) for p in projects):
        raise ValueError("projects must be a non-empty array of project objects")
    ids = [p.get("project_id") for p in projects]
    if any(not isinstance(project_id, str) or not project_id.strip() for project_id in ids):
        raise ValueError("Every project requires a non-empty project_id.")
    if len(ids) != len(set(ids)):
        raise ValueError("Project IDs must be unique.")

    sectors = set()
    for p in projects:
        sector = p.get("sector")
        if not isinstance(sector, str) or not sector.strip():
            raise ValueError(f"Project {p['project_id']} requires a sector.")
        sectors.add(sector)
        numeric_fields = (
            "max_investment_usd", "annual_net_residual_yield", "network_spillover_yield",
            "output_gain_per_1000", "unit_cost_reduction_per_1000",
            "labor_hours_released_per_1000", "criticality_weight",
        )
        for field in numeric_fields:
            value = _number(p[field], f"project {p['project_id']} field {field}")
        if _number(p["max_investment_usd"], "max_investment_usd") < 0:
            raise ValueError("Project investment limits cannot be negative.")
        if _number(p["annual_net_residual_yield"], "annual_net_residual_yield") < 0:
            raise ValueError("Net residual yield cannot be negative.")
        if _number(p["criticality_weight"], "criticality_weight") <= 0:
            raise ValueError("Project criticality_weight must be positive.")
        for field in ("deployment_lag_months", "diffusion_reach_enterprises"):
            value = p[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"Project {p['project_id']} field {field} must be a non-negative integer.")

    sector_caps = cfg.get("sector_max_share_of_budget", {})
    if not isinstance(sector_caps, dict):
        raise ValueError("sector_max_share_of_budget must be an object")
    for sector, raw_share in sector_caps.items():
        share = _number(raw_share, f"sector_max_share_of_budget.{sector}")
        if sector not in sectors or not 0 <= share <= 1:
            raise ValueError(f"Invalid sector maximum budget share for {sector}.")

    shared_cap = cfg.get("shared_projects_max_share_of_budget")
    if shared_cap is not None:
        shared_cap = _number(shared_cap, "shared_projects_max_share_of_budget")
        if not 0 <= shared_cap <= 1:
            raise ValueError("Shared project budget share must be between 0 and 1.")

    minimums = cfg.get("sector_min_investment_usd", {})
    if not isinstance(minimums, dict):
        raise ValueError("sector_min_investment_usd must be an object")
    total_minimum = 0.0
    for sector, raw_minimum in minimums.items():
        minimum = _number(raw_minimum, f"sector_min_investment_usd.{sector}")
        capacity = sum(_number(p["max_investment_usd"], "max_investment_usd") for p in projects if p["sector"] == sector)
        if minimum < 0:
            raise ValueError(f"Sector minimum for {sector} must be finite and non-negative.")
        if sector not in sectors or minimum > capacity + 1e-9:
            raise ValueError(f"Sector minimum for {sector} exceeds available project capacity.")
        total_minimum += minimum
    if total_minimum > budget + 1e-9:
        raise ValueError("Sector minimum investments exceed the total budget.")


def optimize_portfolio(cfg: dict[str, Any], budget_usd: float) -> dict[str, Any]:
    """Allocate a budget to maximize weighted network value subject to floors/caps.

    Variables are dollars allocated to each project. Project metrics are assumed
    linear up to max_investment_usd; this is a simplifying assumption to replace
    with measured marginal-return curves as deployment data accumulates.
    """
    _validate(cfg, budget_usd)
    projects = cfg["projects"]
    n = len(projects)
    weights = cfg["objective_weights"]
    norms = cfg["normalization"]
    c = []
    for p in projects:
        effective_yield = float(p["annual_net_residual_yield"]) + float(p["network_spillover_yield"])
        metrics = {
            "annual_net_residual_yield": effective_yield / float(norms["annual_net_residual_yield"]),
            "output_gain_per_1000": float(p["output_gain_per_1000"]) / float(norms["output_gain_per_1000"]),
            "unit_cost_reduction_per_1000": float(p["unit_cost_reduction_per_1000"]) / float(norms["unit_cost_reduction_per_1000"]),
            "labor_hours_released_per_1000": float(p["labor_hours_released_per_1000"]) / float(norms["labor_hours_released_per_1000"]),
        }
        utility_per_dollar = float(p["criticality_weight"]) * sum(
            float(weights[k]) * metrics[k] for k in METRICS
        ) / 1000.0
        c.append(-utility_per_dollar)

    A_ub: list[list[float]] = [[1.0] * n]
    b_ub: list[float] = [float(budget_usd)]
    for sector, share in cfg.get("sector_max_share_of_budget", {}).items():
        A_ub.append([1.0 if p["sector"] == sector else 0.0 for p in projects])
        b_ub.append(float(share) * budget_usd)
    shared_cap = cfg.get("shared_projects_max_share_of_budget")
    if shared_cap is not None:
        A_ub.append([1.0 if p["sector"] == "SHARED" else 0.0 for p in projects])
        b_ub.append(float(shared_cap) * budget_usd)

    # Sector reproduction floors are hard constraints, not soft objective bonuses.
    for sector, minimum in cfg.get("sector_min_investment_usd", {}).items():
        A_ub.append([-1.0 if p["sector"] == sector else 0.0 for p in projects])
        b_ub.append(-float(minimum))

    result = linprog(
        np.asarray(c), A_ub=np.asarray(A_ub), b_ub=np.asarray(b_ub),
        bounds=[(0.0, float(p["max_investment_usd"])) for p in projects],
        method="highs",
    )
    if not result.success:
        raise ValueError(f"No feasible investment portfolio: {result.message}")

    allocations = []
    sector_totals: dict[str, float] = {}
    totals = {
        "direct_annual_net_residual_usd": 0.0,
        "network_spillover_annual_net_residual_usd": 0.0,
        "output_gain_index": 0.0,
        "unit_cost_reduction_index": 0.0,
        "labor_hours_released_index": 0.0,
        "weighted_objective_value": 0.0,
    }
    for p, amount_raw, utility_raw in zip(projects, result.x, -np.asarray(c)):
        amount = float(amount_raw)
        if amount <= 1e-6:
            continue
        sector_totals[p["sector"]] = sector_totals.get(p["sector"], 0.0) + amount
        direct = amount * float(p["annual_net_residual_yield"])
        spill = amount * float(p["network_spillover_yield"])
        output = amount / 1000.0 * float(p["output_gain_per_1000"])
        cost = amount / 1000.0 * float(p["unit_cost_reduction_per_1000"])
        hours = amount / 1000.0 * float(p["labor_hours_released_per_1000"])
        weighted = amount * utility_raw
        totals["direct_annual_net_residual_usd"] += direct
        totals["network_spillover_annual_net_residual_usd"] += spill
        totals["output_gain_index"] += output
        totals["unit_cost_reduction_index"] += cost
        totals["labor_hours_released_index"] += hours
        totals["weighted_objective_value"] += weighted
        allocations.append({
            "project_id": p["project_id"], "sector": p["sector"], "investment_usd": amount,
            "direct_annual_net_residual_usd": direct,
            "network_spillover_annual_net_residual_usd": spill,
            "total_annual_net_residual_usd": direct + spill,
            "output_gain_index": output, "unit_cost_reduction_index": cost,
            "labor_hours_released_index": hours,
            "deployment_lag_months": int(p["deployment_lag_months"]),
            "diffusion_reach_enterprises": int(p["diffusion_reach_enterprises"]),
        })

    invested = float(sum(x["investment_usd"] for x in allocations))
    return {
        "model_id": cfg["model_id"], "status": cfg["status"],
        "budget_usd": float(budget_usd), "invested_usd": invested,
        "unallocated_budget_usd": float(budget_usd) - invested,
        "budget_utilization": invested / float(budget_usd),
        "allocations": sorted(allocations, key=lambda x: x["investment_usd"], reverse=True),
        "sector_investment_usd": sector_totals,
        "sector_minimums_usd": cfg.get("sector_min_investment_usd", {}),
        "portfolio_metrics": totals,
        "assumptions_and_limits": cfg["accounting_rules"],
        "solver": "scipy.optimize.linprog(method='highs')",
        "objective_weights": weights,
    }


def build_report(cfg: dict[str, Any]) -> dict[str, Any]:
    cases = [optimize_portfolio(cfg, float(b)) for b in cfg["budget_sensitivity_usd"]]
    return {"model_id": cfg["model_id"], "status": cfg["status"], "budget_sensitivity": cases}


if __name__ == "__main__":
    print(json.dumps(build_report(load_config()), indent=2))
