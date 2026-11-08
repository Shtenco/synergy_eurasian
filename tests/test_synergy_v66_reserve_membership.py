from __future__ import annotations

import pytest

from synergy_v66.credit import CreditLedger
from synergy_v66.network_topology import CELLS
from synergy_v66.reserve_recovery import execute_reserve_recovery, plan_reserve_recovery


def _zero_map():
    return {cell.cell_id: 0.0 for cell in CELLS}


def _ledger():
    return CreditLedger(
        initial_cash_per_cell=100.0,
        minimum_post_contribution_cash=10.0,
        reserve_recovery_contribution_fraction=0.50,
        regional_reserve_members_by_region={
            "WEST": ("WEST-PR1",),
            "EAST": ("EAST-PR1",),
        },
        federation_reserve_members=("WEST-AG1", "EAST-AG1"),
    )


def test_legacy_membership_defaults_preserve_all_cell_eligibility():
    ledger = CreditLedger()
    assert ledger.regional_reserve_members_by_region["WEST"] == frozenset(
        cell.cell_id for cell in CELLS if cell.region == "WEST"
    )
    assert ledger.federation_reserve_members == frozenset(cell.cell_id for cell in CELLS)


def test_regional_and_federation_membership_are_independent():
    ledger = _ledger()
    assert "WEST-PR1" in ledger.regional_reserve_members_by_region["WEST"]
    assert "WEST-PR1" not in ledger.federation_reserve_members
    assert "WEST-AG1" in ledger.federation_reserve_members
    assert "WEST-AG1" not in ledger.regional_reserve_members_by_region["WEST"]


def test_membership_validation_rejects_cross_region_unknown_and_duplicate_ids():
    with pytest.raises(ValueError, match="belong to region"):
        CreditLedger(regional_reserve_members_by_region={
            "WEST": ("EAST-PR1",), "EAST": ("EAST-PR1",)
        })
    with pytest.raises(ValueError, match="unknown cell"):
        CreditLedger(regional_reserve_members_by_region={
            "WEST": ("WEST-UNKNOWN",), "EAST": ()
        })
    with pytest.raises(ValueError, match="duplicate"):
        CreditLedger(federation_reserve_members=("WEST-PR1", "WEST-PR1"))


def test_planner_uses_only_explicit_regional_members_for_local_fund():
    ledger = _ledger()
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 20.0, "EAST": 0.0},
        target_federation=0.0,
        allocation_rule="equal",
    )
    assert plan["regional_contributions_by_cell"]["WEST-PR1"] == pytest.approx(20.0)
    assert sum(plan["regional_contributions_by_cell"].values()) == pytest.approx(20.0)
    assert plan["regional_contributions_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert plan["regional_contributions_by_cell"]["EAST-PR1"] == pytest.approx(0.0)


def test_planner_uses_independent_federation_membership():
    ledger = _ledger()
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 0.0, "EAST": 0.0},
        target_federation=20.0,
        allocation_rule="equal",
    )
    assert sum(plan["federation_contributions_by_cell"].values()) == pytest.approx(20.0)
    assert plan["federation_contributions_by_cell"]["WEST-AG1"] == pytest.approx(10.0)
    assert plan["federation_contributions_by_cell"]["EAST-AG1"] == pytest.approx(10.0)
    assert plan["federation_contributions_by_cell"]["WEST-PR1"] == pytest.approx(0.0)


def test_direct_replenishment_rejects_unauthorized_member_atomically():
    ledger = _ledger()
    ledger.process_day(0)
    regional = _zero_map()
    federation = _zero_map()
    regional["WEST-AG1"] = 1.0  # wrong: not a WEST reserve member
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="not a member of its regional reserve"):
        ledger.replenish_reserves(
            regional, federation, day=0, replenishment_id="UNAUTHORIZED-LOCAL",
            recovery_period_id="day-window-0",
            contribution_limit_by_cell={cell.cell_id: 50.0 for cell in CELLS},
        )
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after["federation_pool_reserve_balance"] == before["federation_pool_reserve_balance"]


def test_direct_replenishment_rejects_unauthorized_federation_member_atomically():
    ledger = _ledger()
    ledger.process_day(0)
    regional = _zero_map()
    federation = _zero_map()
    federation["WEST-PR1"] = 1.0  # regional-only participant
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="not a federation reserve member"):
        ledger.replenish_reserves(
            regional, federation, day=0, replenishment_id="UNAUTHORIZED-FED",
            recovery_period_id="day-window-0",
            contribution_limit_by_cell={cell.cell_id: 50.0 for cell in CELLS},
        )
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after["federation_pool_reserve_balance"] == before["federation_pool_reserve_balance"]


def test_defaulted_member_is_never_assessed_for_reserve_recovery():
    ledger = _ledger()
    ledger.process_day(0)
    ledger.accounts["WEST-PR1"].defaulted = True
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 20.0, "EAST": 0.0},
        target_federation=0.0,
    )
    assert plan["regional_contributions_by_cell"]["WEST-PR1"] == pytest.approx(0.0)


def test_one_member_shared_cash_floor_and_period_cap_apply_across_both_funds():
    ledger = CreditLedger(
        initial_cash_per_cell=100.0,
        minimum_post_contribution_cash=50.0,
        reserve_recovery_contribution_fraction=0.50,
        regional_reserve_members_by_region={"WEST": ("WEST-PR1",), "EAST": ()},
        federation_reserve_members=("WEST-PR1",),
    )
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 30.0, "EAST": 0.0},
        target_federation=30.0,
        allocation_rule="equal",
    )
    local = plan["regional_contributions_by_cell"]["WEST-PR1"]
    federal = plan["federation_contributions_by_cell"]["WEST-PR1"]
    assert local == pytest.approx(30.0)
    assert federal == pytest.approx(20.0)
    assert local + federal <= 50.0
    execute_reserve_recovery(ledger, plan, "SHARED-CAP", day=0)
    assert ledger.accounts["WEST-PR1"].cash == pytest.approx(50.0)
    assert ledger.snapshot()["cash_conservation_error"] == pytest.approx(0.0)


def test_recovery_fingerprint_binds_membership_configuration():
    ledger = _ledger()
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 10.0, "EAST": 0.0},
        target_federation=0.0,
    )
    ledger.regional_reserve_members_by_region = {
        "WEST": frozenset({"WEST-AG1"}),
        "EAST": frozenset({"EAST-PR1"}),
    }
    with pytest.raises(ValueError, match="ledger state changed"):
        execute_reserve_recovery(ledger, plan, "MEMBERSHIP-CHANGED", day=0)
