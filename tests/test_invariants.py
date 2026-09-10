from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eiiom_optimizer import load_config, solve, validate_invariants


def test_base_scenario_solves_and_respects_invariants():
    config = load_config(ROOT / "config" / "base_scenario.json")
    solution = solve(config)
    assert solution["status"] == "optimal"
    validate_invariants(config, solution)


def test_total_capex_equals_stage_envelopes():
    config = load_config(ROOT / "config" / "base_scenario.json")
    solution = solve(config)
    expected = sum(v["budget_bn_usd"] for v in config["stages"].values())
    assert abs(solution["total_capex_bn_usd"] - expected) < 1e-6


def test_compute_is_backed_by_data_center_shell():
    config = load_config(ROOT / "config" / "base_scenario.json")
    solution = solve(config)
    assert solution["compute_it_mw"] <= solution["dc_shell_mw"] + 1e-5


def test_geographic_compute_concentration_limit():
    config = load_config(ROOT / "config" / "base_scenario.json")
    solution = solve(config)
    total = solution["compute_it_mw"]
    limit = config["policy_constraints"]["max_country_compute_share"]
    assert total > 0
    assert max(solution["compute_mw_by_country"].values()) / total <= limit + 1e-5


def test_real_economy_repo_cannot_implement_productive_escrow_minting():
    config = json.loads((ROOT / "config" / "base_scenario.json").read_text(encoding="utf-8"))
    assert config["productive_escrow"]["implemented_in_this_repo"] is False


def test_modelled_gva_is_not_exposed_as_cash_field():
    config = load_config(ROOT / "config" / "base_scenario.json")
    solution = solve(config)
    forbidden = {"cash", "revenue", "free_cash_flow", "profit"}
    assert not forbidden.intersection(solution.keys())
