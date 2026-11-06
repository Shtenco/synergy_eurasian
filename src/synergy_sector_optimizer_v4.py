"""Sector-level capital allocator for the SYNERGY productive network.

This is a transparent linear-programming scenario model. All project inputs are
illustrative until replaced by measured enterprise data. Internal transfers are
not counted as consolidated value.
"""
from __future__ import annotations

import json
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


def _validate(cfg: dict[str, Any], budget: float) -> None:
    if budget <= 0:
        raise ValueError("Investment budget must be positive.")
    weights = cfg["objective_weights"]
    if any(float(weights[k]) < 0 for k in METRICS):
        raise ValueError("Objective weights cannot be negative.")
    if abs(sum(float(weights[k]) for k in METRICS) - 1.0) > 1e-9:
        raise ValueError("Objective weights must sum to 1.0.")
    projects = cfg["projects"]
    if not projects:
        raise ValueError("At least one project is required.")
    ids = [p["project_id"] for p in projects]
    if len(ids) != len(set(ids)):
        raise ValueError("Project IDs must be unique.")
    for p in projects:
        if float(p["max_investment_usd"]) < 0:
            raise ValueError("Project investment limits cannot be negative.")
        if float(p["annual_net_residual_yield"]) < 0:
            raise ValueError("Net residual yield cannot be negative.")


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
