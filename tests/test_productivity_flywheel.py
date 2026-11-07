from pathlib import Path
import copy
import pytest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_productivity_flywheel import calculate, load_config


def test_productivity_scenarios_reconcile_and_allocate_only_real_residual():
    result = calculate(load_config())
    rows = result["productivity_scenarios"]
    assert len(rows) == 4
    assert abs(rows[0]["residual_after_replacement_usd"] - 22092.5) < 1e-6
    assert abs(rows[1]["residual_after_replacement_usd"] - 48792.8125) < 1e-6
    assert abs(rows[2]["residual_after_replacement_usd"] - 75493.125) < 1e-6
    assert abs(rows[3]["residual_after_replacement_usd"] - 128893.75) < 1e-6
    for row in rows:
        allocated = sum(row["fund_allocations_usd"].values())
        assert abs(allocated - max(0.0, row["residual_after_replacement_usd"])) < 1e-6


def test_fund_shares_sum_to_one_and_no_r_and_d_return_is_assumed():
    result = calculate(load_config())
    assert abs(sum(result["fund_allocation_shares"].values()) - 1.0) < 1e-9
    assert "No R&D return" in result["interpretation"]


def test_combined_stress_cases_reveal_gap_and_required_recovery():
    result = calculate(load_config())
    stress = result["stress_scenarios"]
    assert len(stress) == 9
    mild = next(x for x in stress if x["name"] == "cashflow_minus_5_replacement_inflation_2")
    severe = next(x for x in stress if x["name"] == "cashflow_minus_15_replacement_inflation_10")
    assert abs(mild["stressed_residual_usd"] - (-52226.52)) < 0.02
    assert abs(severe["stressed_residual_usd"] - (-242701.38)) < 0.02
    assert mild["required_additional_productivity_uplift_for_break_even"] > 0
    assert severe["required_additional_productivity_uplift_for_break_even"] > mild["required_additional_productivity_uplift_for_break_even"]


def test_productivity_flywheel_rejects_nonfinite_negative_and_zero_denominator_inputs():
    base = load_config()

    bad = copy.deepcopy(base)
    bad["baseline"]["gross_cashflow_usd"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        calculate(bad)

    bad = copy.deepcopy(base)
    bad["baseline"]["replacement_capex_usd"] = 0
    with pytest.raises(ValueError, match="must be positive"):
        calculate(bad)

    bad = copy.deepcopy(base)
    bad["baseline"]["initial_operating_cashflow_uplift"] = -1.0
    with pytest.raises(ValueError, match="greater than -100%"):
        calculate(bad)

    bad = copy.deepcopy(base)
    bad["residual_fund_allocation"]["productive_automation_and_capacity"] = -0.1
    with pytest.raises(ValueError, match="shares must be in"):
        calculate(bad)

    bad = copy.deepcopy(base)
    bad["additional_productivity_uplift_scenarios"][0] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        calculate(bad)

    bad = copy.deepcopy(base)
    bad["stress_scenarios"][0]["cashflow_shock"] = 1.0
    with pytest.raises(ValueError, match="cashflow shock"):
        calculate(bad)
