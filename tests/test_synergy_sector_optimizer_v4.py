import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from synergy_sector_optimizer_v4 import load_config, optimize_portfolio, build_report


def test_budget_and_sector_floors_are_respected():
    cfg = load_config(ROOT / "data" / "synergy_sector_optimizer_v4.json")
    result = optimize_portfolio(cfg, 250_000)
    assert result["invested_usd"] <= 250_000 + 1e-5
    for sector, floor in cfg["sector_min_investment_usd"].items():
        assert result["sector_investment_usd"].get(sector, 0) + 1e-5 >= floor
    for sector, share in cfg["sector_max_share_of_budget"].items():
        assert result["sector_investment_usd"].get(sector, 0) <= 250_000 * share + 1e-5
    assert sum(x["investment_usd"] for x in result["allocations"]) == pytest.approx(result["invested_usd"])


def test_shared_spillover_is_reported_separately_from_direct_value():
    cfg = load_config(ROOT / "data" / "synergy_sector_optimizer_v4.json")
    result = optimize_portfolio(cfg, 250_000)
    m = result["portfolio_metrics"]
    assert m["network_spillover_annual_net_residual_usd"] >= 0
    assert m["direct_annual_net_residual_usd"] >= 0
    assert m["weighted_objective_value"] > 0


def test_all_budget_sensitivities_are_feasible():
    cfg = load_config(ROOT / "data" / "synergy_sector_optimizer_v4.json")
    report = build_report(cfg)
    assert [x["budget_usd"] for x in report["budget_sensitivity"]] == [100000, 250000, 500000]
    assert all(x["invested_usd"] <= x["budget_usd"] + 1e-5 for x in report["budget_sensitivity"])


def test_infeasible_sector_floor_is_rejected():
    cfg = load_config(ROOT / "data" / "synergy_sector_optimizer_v4.json")
    cfg["sector_min_investment_usd"]["FOOD"] = 1_000_000
    with pytest.raises(ValueError, match="No feasible"):
        optimize_portfolio(cfg, 100_000)


def test_weights_must_sum_to_one():
    cfg = load_config(ROOT / "data" / "synergy_sector_optimizer_v4.json")
    cfg["objective_weights"]["annual_net_residual_yield"] = 0.9
    with pytest.raises(ValueError, match="sum to 1.0"):
        optimize_portfolio(cfg, 100_000)
