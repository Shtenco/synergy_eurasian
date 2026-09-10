import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_scenarios():
    return json.loads((ROOT / "config" / "scenarios_v4.json").read_text(encoding="utf-8"))


def test_scenario_probabilities_sum_to_one():
    config = load_scenarios()
    total = sum(v["probability_weight"] for v in config["scenarios"].values())
    assert abs(total - 1.0) < 1e-12


def test_all_scenarios_have_same_parameter_surface():
    config = load_scenarios()
    values = list(config["scenarios"].values())
    keys = set(values[0])
    for scenario in values[1:]:
        assert set(scenario) == keys


def test_non_anticipativity_is_required():
    assert load_scenarios()["non_anticipativity_required"] is True


def test_cvar_is_explicit():
    tail = load_scenarios()["tail_risk"]
    assert tail["metric"] == "CVaR"
    assert 0.9 <= tail["alpha"] < 1.0
    assert tail["lambda"] >= 0


def test_stress_scenarios_are_not_all_optimistic():
    scenarios = load_scenarios()["scenarios"]
    assert scenarios["HIGH_WACC"]["wacc_add_bps"] > 0
    assert scenarios["CLIMATE_DRY"]["water_multiplier"] < 1
    assert scenarios["LOGISTICS_DISRUPTION"]["corridor_capacity_multiplier"] < 1
    assert scenarios["COMPUTE_SUPPLY_RESTRICTED"]["compute_hardware_availability_multiplier"] < 1
