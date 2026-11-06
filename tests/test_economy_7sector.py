from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_economy_7sector import (
    load_assumptions,
    leontief_results,
    portfolio_accounting,
    productivity_results,
    simulate_portfolio,
    solve_supply,
)


def config():
    return load_assumptions(ROOT / "data" / "synergy_economy_7sector_v1_assumptions.json")


def test_whole_system_and_public_portfolio_are_not_conflated():
    report = portfolio_accounting(config())
    assert abs(report["total_productive_capital_usd"] - 32_900_000) < 1e-6
    assert abs(report["total_gross_cashflow_usd"] - 993_500) < 1e-6
    assert abs(report["total_replacement_capex_usd"] - 1_089_500) < 1e-6
    assert abs(report["total_net_after_replacement_usd"] + 96_000) < 1e-6
    assert abs(report["public_productive_capital_usd"] - 15_805_000) < 1e-6
    assert abs(report["public_gross_cashflow_usd"] - 489_150) < 1e-6
    assert abs(report["public_replacement_capex_usd"] - 538_250) < 1e-6
    assert abs(report["public_net_after_replacement_usd"] + 49_100) < 1e-6


def test_leontief_matrix_is_productive_and_baseline_is_feasible():
    cfg = config()
    result = leontief_results(cfg)
    assert result["spectral_radius"] < 1
    baseline = solve_supply(cfg, [1, 1, 1, 1, 1, 1, 1])
    assert baseline["feasible"]
    assert abs(baseline["average_service_share"] - 1.0) < 1e-8


def test_energy_shocks_and_critical_floor():
    cfg = config()
    energy_40 = solve_supply(cfg, [1, 1, 0.6, 1, 1, 1, 1], True)
    energy_60 = solve_supply(cfg, [1, 1, 0.4, 1, 1, 1, 1], True)
    assert energy_40["feasible"]
    assert not energy_60["feasible"]


def test_automation_assumptions_reproduce_reference_outputs():
    result = productivity_results(config())
    assert abs(result["gross_labor_cost_saving_share_of_basket"] - 0.1026375) < 1e-10
    assert abs(result["net_basket_cost_reduction_share"] - 0.066714375) < 1e-10
    assert abs(result["net_labor_hours_released_share"] - 0.0743155) < 1e-10
    assert abs(result["weekly_hours_after_modelled_release"] - 37.02738) < 1e-8


def test_30y_crisis_projection_reconciles():
    result = simulate_portfolio(config(), 30, include_crises=True)
    assert abs(result["final_productive_capital_usd"] - 41_762_343.9191) < 1.0
    assert abs(result["cumulative_dividends_usd"] - 5_317_406.3515) < 1.0
    assert abs(result["final_financial_reserve_usd"] - 2_548_202.7596) < 1.0


def test_30y_no_crisis_projection_reconciles():
    result = simulate_portfolio(config(), 30, include_crises=False)
    assert abs(result["final_productive_capital_usd"] - 42_337_661.8282) < 1.0
    assert abs(result["cumulative_dividends_usd"] - 5_662_597.0969) < 1.0
    assert abs(result["final_financial_reserve_usd"] - 5_420_064.7313) < 1.0



def test_reproduction_repair_plan_closes_whole_and_public_gaps():
    from synergy_economy_7sector import reproduction_repair_results
    result = reproduction_repair_results(config())
    assert abs(result["baseline_gap_usd"] - 96_000) < 1e-6
    assert abs(result["operating_cashflow_uplift_usd"] - 74_512.5) < 1e-6
    assert abs(result["replacement_cost_savings_usd"] - 43_580) < 1e-6
    assert abs(result["target_residual_after_replacement_usd"] - 22_092.5) < 1e-6
    assert abs(result["public_target_residual_usd"] - 9_116.25) < 1e-6
    assert abs(result["private_target_residual_usd"] - 12_976.25) < 1e-6
    assert result["target_replacement_coverage"] > 1.0


def test_reproduction_repair_sector_pools_reconcile():
    from synergy_economy_7sector import reproduction_repair_results
    result = reproduction_repair_results(config())
    whole = result["whole_system_sector_pool"]
    public = result["public_sector_pool"]
    private = result["private_sector_pool"]
    assert abs(whole["positive_sector_surplus_usd"] - 162_160) < 1e-6
    assert abs(whole["negative_sector_gap_usd"] + 140_067.5) < 1e-6
    assert abs(whole["net_residual_usd"] - 22_092.5) < 1e-6
    assert abs(public["net_residual_usd"] - 9_116.25) < 1e-6
    assert abs(private["net_residual_usd"] - 12_976.25) < 1e-6
    assert abs(public["net_residual_usd"] + private["net_residual_usd"] - whole["net_residual_usd"]) < 1e-6
