from pathlib import Path
import copy
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



def test_leontief_rejects_nonproductive_or_invalid_input_output_matrices():
    cfg = config()
    unstable = copy.deepcopy(cfg)
    unstable["input_output_matrix"][0][0] = 1.1
    try:
        leontief_results(unstable)
    except ValueError as exc:
        assert "spectral radius" in str(exc)
    else:
        raise AssertionError("Unstable Leontief matrix was accepted")

    negative = copy.deepcopy(cfg)
    negative["input_output_matrix"][0][0] = -0.01
    try:
        leontief_results(negative)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("Negative input-output coefficient was accepted")

    malformed = copy.deepcopy(cfg)
    malformed["input_output_matrix"].pop()
    try:
        leontief_results(malformed)
    except ValueError as exc:
        assert "square" in str(exc) or "dimensions" in str(exc) or "rectangular" in str(exc)
    else:
        raise AssertionError("Non-square Leontief matrix was accepted")


def test_supply_solver_rejects_invalid_capacity_multipliers():
    cfg = config()
    for multipliers in ([1, 1], [1, 1, -0.1, 1, 1, 1, 1], [1, 1, float("nan"), 1, 1, 1, 1]):
        try:
            solve_supply(cfg, multipliers)
        except ValueError as exc:
            assert "Capacity multiplier" in str(exc) or "finite and non-negative" in str(exc)
        else:
            raise AssertionError(f"Invalid capacity multipliers were accepted: {multipliers}")



def test_portfolio_simulation_never_creates_negative_productive_capital():
    cfg = config()
    cfg["replacement_rate"] = [10.0] * len(cfg["sectors"])
    result = simulate_portfolio(cfg, years=1, gross_yield=0.0, include_crises=False)
    assert result["final_productive_capital_usd"] == 0.0
    assert result["annual"][0]["unfunded_renewal_gap_usd"] > 0.0
    assert result["cumulative_unfunded_renewal_gap_usd"] == result["annual"][0]["unfunded_renewal_gap_usd"]


def test_portfolio_simulation_rejects_invalid_horizon_yield_and_allocation():
    cfg = config()
    for years in (0, -1, True, 1.5):
        try:
            simulate_portfolio(cfg, years=years)
        except ValueError as exc:
            assert "positive integer" in str(exc)
        else:
            raise AssertionError(f"Invalid simulation horizon accepted: {years!r}")
    for gross_yield in (float("nan"), float("inf"), -0.1):
        try:
            simulate_portfolio(cfg, gross_yield=gross_yield)
        except ValueError as exc:
            assert "gross_yield" in str(exc)
        else:
            raise AssertionError(f"Invalid gross yield accepted: {gross_yield!r}")
    bad_allocation = copy.deepcopy(cfg)
    bad_allocation["surplus_allocation"] = {
        "growth": 1.2, "reserve": -0.1, "dividends": -0.1
    }
    try:
        simulate_portfolio(bad_allocation)
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("Out-of-range allocation shares were accepted")



def test_economic_model_rejects_invalid_portfolio_and_productivity_assumptions():
    cfg = config()
    bad_capital = copy.deepcopy(cfg)
    bad_capital["capital_usd"][0] = float("nan")
    try:
        portfolio_accounting(bad_capital)
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("Non-finite productive capital was accepted")

    bad_ownership = copy.deepcopy(cfg)
    bad_ownership["public_ownership_share"][0] = 1.01
    try:
        portfolio_accounting(bad_ownership)
    except ValueError as exc:
        assert "public_ownership_share" in str(exc)
    else:
        raise AssertionError("Public ownership share above 100% was accepted")

    bad_adoption = copy.deepcopy(cfg)
    bad_adoption["automation_adoption"][0] = 1.1
    try:
        productivity_results(bad_adoption)
    except ValueError as exc:
        assert "automation_adoption" in str(exc)
    else:
        raise AssertionError("Automation adoption above 100% was accepted")

    bad_basket = copy.deepcopy(cfg)
    bad_basket["basket_share"][0] = 0.5
    try:
        productivity_results(bad_basket)
    except ValueError as exc:
        assert "must each sum to 1" in str(exc)
    else:
        raise AssertionError("Basket shares that do not sum to 1 were accepted")


def test_supply_solver_rejects_boolean_controls_and_indices():
    cfg = config()
    for multipliers in ([True, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1]):
        if multipliers[0] is True:
            try:
                solve_supply(cfg, multipliers)
            except ValueError as exc:
                assert "not booleans" in str(exc)
            else:
                raise AssertionError("Boolean capacity multiplier was accepted")
    bad_indices = copy.deepcopy(cfg)
    bad_indices["critical_sector_indices"] = [True, 1, 2]
    try:
        solve_supply(bad_indices, [1, 1, 1, 1, 1, 1, 1])
    except ValueError as exc:
        assert "not booleans" in str(exc)
    else:
        raise AssertionError("Boolean critical sector index was accepted")
    try:
        solve_supply(cfg, [1, 1, 1, 1, 1, 1, 1], enforce_critical_floor="false")
    except ValueError as exc:
        assert "must be a boolean" in str(exc)
    else:
        raise AssertionError("String critical-floor switch was accepted")
