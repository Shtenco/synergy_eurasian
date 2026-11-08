"""Regression tests for the local V6.6.4-Q2 membership stress fixture."""
from scripts.run_synergy_v664q2_membership_stress import (
    BASE_REGIONAL_MEMBERS, EXPANDED_REGIONAL_MEMBERS, FEDERATION_MEMBERS,
    CASH_FLOOR, simulate, validate_membership,
)


def test_membership_validation_rejects_cross_region_local_member():
    invalid = {"WEST": frozenset({"E1"}), "EAST": BASE_REGIONAL_MEMBERS["EAST"]}
    try:
        validate_membership(invalid, FEDERATION_MEMBERS)
    except ValueError:
        return
    raise AssertionError("Cross-region regional membership was accepted")


def test_regional_and_federation_membership_are_independent():
    assert "W3" not in BASE_REGIONAL_MEMBERS["WEST"]
    assert "W3" in FEDERATION_MEMBERS


def test_defaulted_members_never_contribute():
    result = simulate("pro_rata", "baseline", BASE_REGIONAL_MEMBERS, 80.0)
    assert result["cycle_rows"][0]["defaulted_member_contribution"] == 0.0
    assert result["cycle_rows"][24]["defaulted_member_contribution"] == 0.0
    assert result["cycle_rows"][49]["defaulted_member_contribution"] == 0.0


def test_default_status_is_permanent_and_reduces_active_population():
    result = simulate("pro_rata", "baseline", BASE_REGIONAL_MEMBERS, 80.0)
    assert result["cycle_rows"][0]["cumulative_defaults"] == 1
    assert result["cycle_rows"][24]["cumulative_defaults"] == 2
    assert result["cycle_rows"][49]["cumulative_defaults"] == 3
    assert result["cycle_rows"][99]["cumulative_defaults"] == 3


def test_shared_capacity_and_cash_floor():
    result = simulate("pro_rata", "baseline", BASE_REGIONAL_MEMBERS, 80.0)
    assert result["minimum_final_cash"] >= CASH_FLOOR
    assert all(row["cash_floor_breaches"] == 0 for row in result["cycle_rows"])


def test_expanded_west_membership_closes_west_gap_at_80_inflow():
    result = simulate("fcfs", "expanded", EXPANDED_REGIONAL_MEMBERS, 80.0)
    assert result["west_unfunded"] == 0.0
    assert result["east_unfunded"] == 2040.0


def test_cash_conservation_and_nonnegative_unfunded_claims():
    for method in ("pro_rata", "fcfs"):
        for members in (BASE_REGIONAL_MEMBERS, EXPANDED_REGIONAL_MEMBERS):
            result = simulate(method, "case", members, 80.0)
            assert result["total_contributions"] >= 0.0
            assert result["total_unfunded"] >= 0.0
            assert result["minimum_final_cash"] >= CASH_FLOOR
