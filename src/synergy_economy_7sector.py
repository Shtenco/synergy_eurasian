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


def _number(
    value: Any, field: str, minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a numeric value, not a boolean or string")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return result


def _validated_vector(
    cfg: dict[str, Any], field: str, length: int | None = None,
    minimum: float | None = None, maximum: float | None = None,
) -> np.ndarray:
    raw = cfg.get(field)
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{field} must be a numeric vector")
    if length is not None and len(raw) != length:
        raise ValueError(f"{field} length must match sector count")
    result = np.asarray([
        _number(value, f"{field}[{index}]", minimum, maximum)
        for index, value in enumerate(raw)
    ], dtype=float)
    if result.ndim != 1:
        raise ValueError(f"{field} must be a finite one-dimensional vector")
    return result


def _validated_leontief_components(cfg: dict[str, Any]) -> tuple[np.ndarray, float, float]:
    try:
        a = _arrays(cfg)["A"]
    except (TypeError, ValueError) as exc:
        raise ValueError("Input-output matrix A must be a rectangular numeric matrix") from exc
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError("Input-output matrix A must be square")
    if not np.isfinite(a).all():
        raise ValueError("Input-output matrix A must contain only finite values")
    if np.any(a < 0):
        raise ValueError("Input-output coefficients must be non-negative")
    n = a.shape[0]
    if len(cfg["sectors"]) != n:
        raise ValueError("Sector count must match input-output matrix dimensions")
    rho = float(max(abs(np.linalg.eigvals(a))))
    if not np.isfinite(rho) or rho >= 1.0:
        raise ValueError(f"Leontief system is not productive: spectral radius must be < 1, got {rho}")
    matrix = np.eye(n) - a
    condition_number = float(np.linalg.cond(matrix))
    if not np.isfinite(condition_number) or condition_number > 1e12:
        raise ValueError(f"Leontief system is numerically ill-conditioned: cond(I-A)={condition_number}")
    inverse = np.linalg.solve(matrix, np.eye(n))
    return inverse, rho, condition_number


def leontief_results(cfg: dict[str, Any]) -> dict[str, Any]:
    inverse, rho, condition_number = _validated_leontief_components(cfg)
    demand = np.ones(inverse.shape[0], dtype=float)
    gross_output = inverse @ demand
    return {
        "spectral_radius": rho,
        "condition_number_I_minus_A": condition_number,
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
    inverse, rho, condition_number = _validated_leontief_components(cfg)
    n = inverse.shape[0]
    if not isinstance(enforce_critical_floor, bool):
        raise ValueError("enforce_critical_floor must be a boolean")
    if (not isinstance(capacity_multipliers, (list, tuple, np.ndarray))
            or any(isinstance(value, (bool, np.bool_))
                   or not isinstance(value, (int, float, np.integer, np.floating))
                   for value in capacity_multipliers)):
        raise ValueError("Capacity multipliers must be numeric values, not booleans or strings")
    multipliers = np.asarray(capacity_multipliers, dtype=float)
    if multipliers.ndim != 1 or len(multipliers) != n:
        raise ValueError("Capacity multiplier count must match sector count")
    if not np.isfinite(multipliers).all() or np.any(multipliers < 0):
        raise ValueError("Capacity multipliers must be finite and non-negative")
    raw_critical = cfg["critical_sector_indices"]
    if (not isinstance(raw_critical, (list, tuple))
            or any(isinstance(i, bool) or not isinstance(i, int) for i in raw_critical)):
        raise ValueError("Critical sector indices must be integer indices, not booleans")
    critical = set(raw_critical)
    if any(i < 0 or i >= n for i in critical):
        raise ValueError("Critical sector indices must be valid integer indices")
    floor = _number(
        cfg["critical_minimum_service_share"],
        "critical_minimum_service_share", 0.0, 1.0,
    )
    baseline_capacity = inverse @ np.ones(n)
    available_capacity = baseline_capacity * multipliers
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
            "leontief_spectral_radius": rho,
            "condition_number_I_minus_A": condition_number,
        }
    return {
        "feasible": True,
        "status": result.message,
        "service": result.x.tolist(),
        "average_service_share": float(result.x.mean()),
        "capacity": available_capacity.tolist(),
        "leontief_spectral_radius": rho,
        "condition_number_I_minus_A": condition_number,
    }


def portfolio_accounting(cfg: dict[str, Any]) -> dict[str, Any]:
    sectors = cfg.get("sectors")
    if (not isinstance(sectors, (list, tuple)) or not sectors
            or any(not isinstance(name, str) or not name.strip() for name in sectors)
            or len(sectors) != len(set(sectors))):
        raise ValueError("sectors must be unique non-empty names")
    n = len(sectors)
    capital = _validated_vector(cfg, "capital_usd", n, minimum=0.0)
    gross_yield = _validated_vector(cfg, "gross_cash_yield", n, minimum=0.0)
    replacement_rate = _validated_vector(cfg, "replacement_rate", n, minimum=0.0)
    public_share = _validated_vector(cfg, "public_ownership_share", n, minimum=0.0, maximum=1.0)
    if capital.sum() <= 0:
        raise ValueError("total productive capital must be positive")
    gross_cf = capital * gross_yield
    replacement = capital * replacement_rate
    net_after_replacement = gross_cf - replacement
    public_capital = capital * public_share
    public_gross_cf = gross_cf * public_share
    public_replacement = replacement * public_share
    public_net = public_gross_cf - public_replacement
    if public_capital.sum() <= 0:
        raise ValueError("public ownership share must allocate positive capital for public portfolio metrics")
    return {
        "sectors": [
            {
                "sector": name,
                "capital_usd": float(capital[i]),
                "gross_cash_yield": float(gross_yield[i]),
                "gross_cashflow_usd": float(gross_cf[i]),
                "replacement_rate": float(replacement_rate[i]),
                "replacement_capex_usd": float(replacement[i]),
                "net_after_replacement_usd": float(net_after_replacement[i]),
                "public_ownership_share": float(public_share[i]),
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



def reproduction_repair_results(cfg: dict[str, Any]) -> dict[str, Any]:
    """Calculate a transparent operating-improvement scenario for the replacement gap.

    The scenario is a target, not an observed result. It applies an operating
    cashflow uplift and a replacement-cost reduction, then reconciles public,
    private and sector balances. Internal cross-subsidies are not new value.
    """
    portfolio_accounting(cfg)  # Validate all sector capital/yield/ownership vectors first.
    a = _arrays(cfg)
    plan = cfg["reproduction_repair_plan"]
    uplift = _number(plan["operating_cashflow_uplift_target"], "operating_cashflow_uplift_target", 0.0)
    replacement_reduction = _number(
        plan["replacement_cost_reduction_target"], "replacement_cost_reduction_target", 0.0, 1.0
    )
    capital = a["capital"]
    gross = capital * a["yield"]
    replacement = capital * a["replacement"]
    public_share = a["public_share"]

    target_gross = gross * (1.0 + uplift)
    target_replacement = replacement * (1.0 - replacement_reduction)
    target_residual = target_gross - target_replacement
    public_residual = target_residual * public_share
    private_residual = target_residual * (1.0 - public_share)

    sectors = []
    for i, name in enumerate(cfg["sectors"]):
        sectors.append({
            "sector": name,
            "baseline_residual_usd": float(gross[i] - replacement[i]),
            "target_gross_cashflow_usd": float(target_gross[i]),
            "target_replacement_capex_usd": float(target_replacement[i]),
            "target_residual_usd": float(target_residual[i]),
            "public_target_residual_usd": float(public_residual[i]),
            "private_target_residual_usd": float(private_residual[i]),
        })

    def pool(values: np.ndarray) -> dict[str, float]:
        positive = float(np.maximum(values, 0.0).sum())
        negative = float(np.minimum(values, 0.0).sum())
        return {
            "positive_sector_surplus_usd": positive,
            "negative_sector_gap_usd": negative,
            "net_residual_usd": positive + negative,
            "internal_cross_subsidy_required_usd": -negative,
            "surplus_after_covering_sector_gaps_usd": positive + negative,
        }

    public_pool = pool(public_residual)
    private_pool = pool(private_residual)
    total_pool = pool(target_residual)
    base_gross = float(gross.sum())
    base_replacement = float(replacement.sum())
    target_gross_total = float(target_gross.sum())
    target_replacement_total = float(target_replacement.sum())
    target_replacement_coverage = (
        target_gross_total / target_replacement_total
        if target_replacement_total > 0 else None
    )
    baseline_replacement_coverage = (
        base_gross / base_replacement if base_replacement > 0 else None
    )
    target_replacement_margin = (
        (target_gross_total - target_replacement_total) / target_replacement_total
        if target_replacement_total > 0 else None
    )
    return {
        "status": plan["status"],
        "operating_cashflow_uplift_target": uplift,
        "replacement_cost_reduction_target": replacement_reduction,
        "baseline_gap_usd": float(base_replacement - base_gross),
        "operating_cashflow_uplift_usd": float(target_gross_total - base_gross),
        "replacement_cost_savings_usd": float(base_replacement - target_replacement_total),
        "target_gross_cashflow_usd": target_gross_total,
        "target_replacement_capex_usd": target_replacement_total,
        "target_residual_after_replacement_usd": float(target_gross_total - target_replacement_total),
        "target_replacement_coverage": (
            float(target_replacement_coverage) if target_replacement_coverage is not None else None
        ),
        "baseline_replacement_coverage": (
            float(baseline_replacement_coverage) if baseline_replacement_coverage is not None else None
        ),
        "target_residual_margin_pct_of_replacement": (
            float(target_replacement_margin) if target_replacement_margin is not None else None
        ),
        "replacement_coverage_defined": target_replacement_coverage is not None,
        "public_target_residual_usd": float(public_residual.sum()),
        "private_target_residual_usd": float(private_residual.sum()),
        "public_sector_pool": public_pool,
        "private_sector_pool": private_pool,
        "whole_system_sector_pool": total_pool,
        "sectors": sectors,
        "reserve_policy": plan["reserve_policy"],
        "accounting_rules": plan["accounting_rules"],
        "operational_levers": plan["operational_levers"],
    }


def productivity_results(cfg: dict[str, Any]) -> dict[str, Any]:
    sectors = cfg.get("sectors")
    if not isinstance(sectors, (list, tuple)) or not sectors:
        raise ValueError("sectors must be a non-empty list")
    n = len(sectors)
    basket = _validated_vector(cfg, "basket_share", n, minimum=0.0, maximum=1.0)
    labor = _validated_vector(cfg, "labor_share", n, minimum=0.0, maximum=1.0)
    adoption = _validated_vector(cfg, "automation_adoption", n, minimum=0.0, maximum=1.0)
    employment = _validated_vector(cfg, "employment_share", n, minimum=0.0, maximum=1.0)
    if not np.isclose(basket.sum(), 1.0) or not np.isclose(employment.sum(), 1.0):
        raise ValueError("basket_share and employment_share must each sum to 1")
    efficacy = _number(cfg["automation_effectiveness"], "automation_effectiveness", 0.0, 1.0)
    tech_cost = _number(
        cfg["technology_cost_share_of_gross_labor_saving"],
        "technology_cost_share_of_gross_labor_saving", 0.0, 1.0,
    )
    rebound = _number(cfg["rebound_share"], "rebound_share", 0.0, 1.0)
    supply_rebound = _number(
        cfg["supply_chain_rebound_share"], "supply_chain_rebound_share", 0.0, 1.0
    )
    baseline_hours = _number(cfg["baseline_weekly_hours"], "baseline_weekly_hours", 0.0)

    gross_basket_saving = float(np.sum(basket * labor * adoption * efficacy))
    net_basket_saving = gross_basket_saving * (1.0 - tech_cost)
    labor_release = float(np.sum(
        employment * labor * adoption * efficacy
        * (1.0 - rebound) * (1.0 - supply_rebound)
    ))
    weekly_hours = float(baseline_hours * (1.0 - labor_release))
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
    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError("years must be a positive integer")
    if not isinstance(include_crises, bool):
        raise ValueError("include_crises must be a boolean")
    account = portfolio_accounting(cfg)
    k = float(account["total_productive_capital_usd"])
    replacement_rate = float(account["weighted_replacement_rate"])
    gross_yield = _number(
        cfg["target_gross_cash_yield"] if gross_yield is None else gross_yield,
        "gross_yield", 0.0,
    )
    reserve_share = _number(
        cfg["initial_financial_reserve_share"], "initial_financial_reserve_share", 0.0, 1.0
    )
    reserve = k * reserve_share
    initial_reserve = reserve
    allocation = cfg["surplus_allocation"]
    shares = np.asarray([
        _number(allocation[key], f"surplus_allocation.{key}", 0.0, 1.0)
        for key in ("growth", "reserve", "dividends")
    ], dtype=float)
    if not np.isclose(shares.sum(), 1.0):
        raise ValueError("Surplus allocation shares must be finite, between 0 and 1, and sum to 1.")

    events = cfg["crisis_events"] if include_crises else {}
    cumulative_dividends = 0.0
    cumulative_reserve_contributions = 0.0
    cumulative_reserve_draws = 0.0
    cumulative_unfunded_renewal_gap = 0.0
    rows = []

    for year in range(1, years + 1):
        event = events.get(str(year), {})
        physical_loss_share = _number(
            event.get("physical_capital_loss_share", 0.0),
            f"year {year} physical_capital_loss_share", 0.0, 1.0,
        )
        cash_multiplier = _number(
            event.get("gross_cashflow_multiplier", 1.0),
            f"year {year} gross_cashflow_multiplier", 0.0,
        )
        physical_loss = k * physical_loss_share
        if physical_loss:
            k -= physical_loss
            repair = min(reserve, physical_loss)
            reserve -= repair
            k += repair
            cumulative_reserve_draws += repair

        gross_cashflow = k * gross_yield * cash_multiplier
        replacement_capex = k * replacement_rate
        surplus = gross_cashflow - replacement_capex

        unfunded_renewal_gap = 0.0
        if surplus < 0:
            shortfall = -surplus
            reserve_used = min(reserve, shortfall)
            reserve -= reserve_used
            cumulative_reserve_draws += reserve_used
            unfunded = shortfall - reserve_used
            # Unfunded renewal erodes productive capital, but productive capital
            # cannot become negative. Any residual remains an explicit unmet gap.
            capital_erosion = min(k, unfunded)
            k -= capital_erosion
            unfunded_renewal_gap = unfunded - capital_erosion
            cumulative_unfunded_renewal_gap += unfunded_renewal_gap
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
            "unfunded_renewal_gap_usd": unfunded_renewal_gap,
            "cumulative_unfunded_renewal_gap_usd": cumulative_unfunded_renewal_gap,
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
        "cumulative_unfunded_renewal_gap_usd": cumulative_unfunded_renewal_gap,
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
        "reproduction_repair": reproduction_repair_results(cfg),
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
        "repair_target_residual_usd": report["reproduction_repair"]["target_residual_after_replacement_usd"],
        "repair_target_replacement_coverage": report["reproduction_repair"]["target_replacement_coverage"],
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
