from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_productivity_flywheel_monte_carlo_v3 import (
    build_report,
    load_config,
    simulate_paths,
)


def test_monte_carlo_is_reproducible_and_probabilities_are_bounded():
    cfg = load_config()
    cfg["paths"] = 500
    a = simulate_paths(cfg, 0.03)
    b = simulate_paths(cfg, 0.03)
    assert a == b
    assert 0.0 <= a["reserve_exhaustion_probability"] <= 1.0
    assert a["paths"] == 500


def test_no_correlated_shocks_has_no_reserve_exhaustion_in_reference_seed():
    cfg = load_config()
    cfg["paths"] = 1000
    result = simulate_paths(cfg, 0.0)
    assert result["reserve_exhaustion_probability"] == 0.0
    assert result["probability_of_any_unfunded_gap"] == 0.0


def test_shock_probability_increases_tail_risk_in_reference_seed():
    cfg = load_config()
    cfg["paths"] = 2000
    low = simulate_paths(cfg, 0.0)
    high = simulate_paths(cfg, 0.10)
    assert high["reserve_exhaustion_probability"] > low["reserve_exhaustion_probability"]
    assert high["cumulative_unfunded_gap_usd_quantiles"]["p95"] >= low["cumulative_unfunded_gap_usd_quantiles"]["p95"]


def test_report_contains_five_shock_scenarios():
    cfg = load_config()
    cfg["paths"] = 100
    report = build_report(cfg)
    assert len(report["shock_sensitivity"]) == 5
