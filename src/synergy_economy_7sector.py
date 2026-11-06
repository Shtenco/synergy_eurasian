"""Seven-sector SYNERGY Economy research model.

This module is deliberately separate from EIIOM-2045. It is a transparent,
illustrative accounting/supply-chain model, not a calibrated macro forecast.
It does not issue money, approve financing, or recognize tokens as wealth.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "synergy_economy_7sector_v1_assumptions.json"


def load_assumptions(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _arrays(cfg: dict[str, Any]) -> dict[str, np.ndarray]:
    return {
        "capital": np.asarray(cfg["capital_usd"], dtype=float),
        "yield": np.asarray(cfg["gross_cash_yield"], dtype=float),
        "replacement": np.asarray(cfg["replacement_rate"], dtype=float),
        "public_share": np.asarray(cfg["public_ownership_share"], dtype=float),
        "A": np.asarray(cfg["input_output_matrix"], dtype=float),
    }


def leontief_results(cfg: dict[str, Any]) -> dict[str, Any]:
    a = _arrays(cfg)["A"]
    identity = np.eye(a.shape[0])
    inverse = np.linalg.inv(identity - a)
    demand = np.ones(a.shape[0], dtype=float)
    gross_output = inverse @ demand
    rho = float(max(abs(np.linalg.eigvals(a))))
    return {
        "spectral_radius": rho,
        "leontief_inverse": inverse.tolist(),
        "final_demand": demand.tolist(),
        "gross_output": gross_output.tolist(),
        "total_final_demand": float(demand.sum()),
        "total_gross_output": float(gross_output.sum()),
        "intermediate_output": float(gross_output.sum() - demand.sum()),
        "intermediate_share_of_gross_output": float(
            (gross_output.sum() - demand.sum()) / gross_output.sum()
        ),
    }


def solve_supply(
    cfg: dict[str, Any],
    capacity_multipliers: list[float],
    enforce_critical_floor: bool = False,
) -> dict[str, Any]:
    a = _arrays(cfg)["A"]
    inverse = np.linalg.inv(np.eye(a.shape[0]) - a)
    baseline_capacity = inverse @ np.ones(a.shape[0])
    available_capacity = baseline_capacity * np.asarray(capacity_multipliers, dtype=float)
    n = len(cfg["sectors"])
    critical = set(cfg["critical_sector_indices"])
    floor = float(cfg["critical_minimum_service_share"])
    bounds = [
        (floor, 1.0) if enforce_critical_floor and i in critical else (0.0, 1.0)
        for i in range(n)
    ]
    result = linprog(
        c=-np.ones(n),
        A_ub=inverse,
        b_ub=available_capacity,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        return {
            "feasible": False,
            "status": result.message,
            "service": None,
            "average_service_share": None,
        }
    return {
        "feasible": True,
        "status": result.message,
        "service": result.x.tolist(),
        "average_service_share": float(result.x.mean()),
        "capacity": available_capacity.tolist(),
    }


def portfolio_accounting(cfg: dict[str, Any]) -> dict[str, Any]:
    a = _arrays(cfg)
    capital = a["capital"]
    gross_cf = capital * a["yield"]
    replacement = capital * a["replacement"]
    net_after_replacement = gross_cf - replacement
    public_capital = capital * a["public_share"]
    public_gross_cf = gross_cf * a["public_share"]
    public_replacement = replacement * a["public_share"]
    public_net = public_gross_cf - public_replacement
    return {
        "sectors": [
            {
                "sector": name,
                "capital_usd": float(capital[i]),
                "gross_cash_yield": float(a["yield"][i]),
                "gross_cashflow_usd": float(gross_cf[i]),
                "replacement_rate": float(a["replacement"][i]),
                "replacement_capex_usd": float(replacement[i]),
                "net_after_replacement_usd": float(net_after_replacement[i]),
                "public_ownership_share": float(a["public_share"][i]),
                "public_capital_usd": float(public_capital[i]),
                "public_gross_cashflow_usd": float(public_gross_cf[i]),
                "public_replacement_capex_usd": float(public_replacement[i]),
                "public_net_after_replacement_usd": float(public_net[i]),
            }
            for i, name in enumerate(cfg["sectors"])
        ],
        "total_productive_capital_usd": float(capital.sum()),
        "total_gross_cashflow_usd": float(gross_cf.sum()),
        "total_replacement_capex_usd": float(replacement.sum()),
        "total_net_after_replacement_usd": float(net_after_replacement.sum()),
        "weighted_gross_cash_yield": float(gross_cf.sum() / capital.sum()),
        "weighted_replacement_rate": float(replacement.sum() / capital.sum()),
        "public_productive_capital_usd": float(public_capital.sum()),
        "public_share_of_total_capital": float(public_capital.sum() / capital.sum()),
        "public_gross_cashflow_usd": float(public_gross_cf.sum()),
        "public_replacement_capex_usd": float(public_replacement.sum()),
        "public_net_after_replacement_usd": float(public_net.sum()),
        "public_weighted_gross_cash_yield": float(public_gross_cf.sum() / public_capital.sum()),
        "public_weighted_replacement_rate": float(public_replacement.sum() / public_capital.sum()),
    }


def productivity_results(cfg: dict[str, Any]) -> dict[str, Any]:
    basket = np.asarray(cfg["basket_share"], dtype=float)
    labor = np.asarray(cfg["labor_share"], dtype=float)
    adoption = np.asarray(cfg["automation_adoption"], dtype=float)
    employment = np.asarray(cfg["employment_share"], dtype=float)
    efficacy = float(cfg["automation_effectiveness"])
    tech_cost = float(cfg["technology_cost_share_of_gross_labor_saving"])
    rebound = float(cfg["rebound_share"])
    supply_rebound = float(cfg["supply_chain_rebound_share"])

    gross_basket_saving = float(np.sum(basket * labor * adoption * efficacy))
    net_basket_saving = gross_basket_saving * (1.0 - tech_cost)
    labor_release = float(np.sum(
        employment * labor * adoption * efficacy
        * (1.0 - rebound) * (1.0 - supply_rebound)
    ))
    weekly_hours = float(cfg["baseline_weekly_hours"] * (1.0 - labor_release))
    return {
        "gross_labor_cost_saving_share_of_basket": gross_basket_saving,
        "technology_cost_share": tech_cost,
        "net_basket_cost_reduction_share": net_basket_saving,
        "net_saving_per_1000_usd_basket": 1000.0 * net_basket_saving,
        "net_basket_cost_after_automation_usd": 1000.0 * (1.0 - net_basket_saving),
        "net_labor_hours_released_share": labor_release,
        "weekly_hours_after_modelled_release": weekly_hours,
        "monthly_hours_released_for_1000_people_at_160_hours_each": (
            1000.0 * 160.0 * labor_release
        ),
    }


def simulate_portfolio(
    cfg: dict[str, Any],
    years: int = 30,
    gross_yield: float | None = None,
    include_crises: bool = True,
) -> dict[str, Any]:
    account = portfolio_accounting(cfg)
    k = float(account["total_productive_capital_usd"])
    replacement_rate = float(account["weighted_replacement_rate"])
    gross_yield = float(
        cfg["target_gross_cash_yield"] if gross_yield is None else gross_yield
    )
    reserve = k * float(cfg["initial_financial_reserve_share"])
    initial_reserve = reserve
    allocation = cfg["surplus_allocation"]
    shares = np.asarray(
        [allocation["growth"], allocation["reserve"], allocation["dividends"]],
        dtype=float,
    )
    if not np.isclose(shares.sum(), 1.0):
        raise ValueError("Surplus allocation shares must sum to 1.")

    events = cfg["crisis_events"] if include_crises else {}
    cumulative_dividends = 0.0
    cumulative_reserve_contributions = 0.0
    cumulative_reserve_draws = 0.0
    rows = []

    for year in range(1, years + 1):
        event = events.get(str(year), {})
        physical_loss = k * float(event.get("physical_capital_loss_share", 0.0))
        if physical_loss:
            k -= physical_loss
            repair = min(reserve, physical_loss)
            reserve -= repair
            k += repair
            cumulative_reserve_draws += repair

        cash_multiplier = float(event.get("gross_cashflow_multiplier", 1.0))
        gross_cashflow = k * gross_yield * cash_multiplier
        replacement_capex = k * replacement_rate
        surplus = gross_cashflow - replacement_capex

        if surplus < 0:
            shortfall = -surplus
            reserve_used = min(reserve, shortfall)
            reserve -= reserve_used
            cumulative_reserve_draws += reserve_used
            unfunded = shortfall - reserve_used
            # Unfunded renewal is represented as productive-capital erosion.
            k -= unfunded
            surplus = 0.0

        growth_investment = shares[0] * surplus
        reserve_contribution = shares[1] * surplus
        dividend = shares[2] * surplus
        k += growth_investment
        reserve += reserve_contribution
        cumulative_reserve_contributions += reserve_contribution
        cumulative_dividends += dividend

        rows.append({
            "year": year,
            "productive_capital_usd": k,
            "financial_reserve_usd": reserve,
            "gross_cashflow_usd": gross_cashflow,
            "replacement_capex_usd": replacement_capex,
            "surplus_after_replacement_usd": surplus,
            "growth_investment_usd": growth_investment,
            "reserve_contribution_usd": reserve_contribution,
            "dividend_usd": dividend,
            "cumulative_dividends_usd": cumulative_dividends,
            "cumulative_reserve_contributions_usd": cumulative_reserve_contributions,
            "cumulative_reserve_draws_usd": cumulative_reserve_draws,
        })

    return {
        "years": years,
        "gross_cash_yield_assumption": gross_yield,
        "weighted_replacement_rate": replacement_rate,
        "initial_productive_capital_usd": account["total_productive_capital_usd"],
        "initial_financial_reserve_usd": initial_reserve,
        "final_productive_capital_usd": k,
        "final_financial_reserve_usd": reserve,
        "cumulative_dividends_usd": cumulative_dividends,
        "cumulative_reserve_contributions_usd": cumulative_reserve_contributions,
        "cumulative_reserve_draws_usd": cumulative_reserve_draws,
        "include_crises": include_crises,
        "annual": rows,
    }


def build_report(cfg: dict[str, Any]) -> dict[str, Any]:
    stress = {}
    for name, multipliers in cfg["supply_stress_scenarios"].items():
        unconstrained = solve_supply(cfg, multipliers, False)
        with_floor = solve_supply(cfg, multipliers, True)
        stress[name] = {
            "capacity_multipliers": multipliers,
            "unconstrained": unconstrained,
            "critical_70pct_floor": with_floor,
        }
    return {
        "model_id": cfg["model_id"],
        "status": cfg["status"],
        "currency": cfg["currency"],
        "population": cfg["population"],
        "accounting": portfolio_accounting(cfg),
        "productivity": productivity_results(cfg),
        "leontief": leontief_results(cfg),
        "supply_stress": stress,
        "portfolio_30y_target_with_crises": simulate_portfolio(cfg, 30, include_crises=True),
        "portfolio_30y_target_without_crises": simulate_portfolio(cfg, 30, include_crises=False),
        "interpretation": [
            "Gross cashflow is not free cash flow.",
            "Replacement CAPEX is deducted before growth, reserves, or dividends.",
            "Public portfolio cashflows are a subset of whole-system cashflows.",
            "Modelled value, token issuance, market capitalization, and internal transfers are not external real-economy value.",
            "All sector assumptions require empirical calibration before operational or investment use."
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "synergy_economy_7sector_v1.json")
    args = parser.parse_args()
    cfg = load_assumptions(args.config)
    report = build_report(cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "model_id": report["model_id"],
        "total_productive_capital_usd": report["accounting"]["total_productive_capital_usd"],
        "gross_cashflow_usd": report["accounting"]["total_gross_cashflow_usd"],
        "replacement_capex_usd": report["accounting"]["total_replacement_capex_usd"],
        "net_after_replacement_usd": report["accounting"]["total_net_after_replacement_usd"],
        "public_capital_usd": report["accounting"]["public_productive_capital_usd"],
        "public_net_after_replacement_usd": report["accounting"]["public_net_after_replacement_usd"],
        "leontief_spectral_radius": report["leontief"]["spectral_radius"],
        "basket_cost_reduction_pct": 100 * report["productivity"]["net_basket_cost_reduction_share"],
        "labor_release_pct": 100 * report["productivity"]["net_labor_hours_released_share"],
        "capital_30y_with_crises_usd": report["portfolio_30y_target_with_crises"]["final_productive_capital_usd"],
        "dividends_30y_with_crises_usd": report["portfolio_30y_target_with_crises"]["cumulative_dividends_usd"],
        "reserve_30y_with_crises_usd": report["portfolio_30y_target_with_crises"]["final_financial_reserve_usd"]
    }, indent=2))


if __name__ == "__main__":
    main()
