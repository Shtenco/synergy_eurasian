import pytest

from synergy_v66.credit import CreditLedger
from synergy_v66.network_topology import CELLS
from synergy_v66.reserve_recovery import (
    execute_reserve_recovery,
    plan_reserve_recovery,
)


def _zero_map():
    return {cell.cell_id: 0.0 for cell in CELLS}


def test_multi_level_recovery_plan_is_non_mutating_and_settles_cash_exactly():
    ledger = CreditLedger(
        initial_cash_per_cell=100.0,
        regional_pool_reserve_per_region=10.0,
        federation_pool_reserve_total=10.0,
        minimum_post_contribution_cash=20.0,
    )
    ledger.process_day(0)
    before = ledger.snapshot()
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 15.0, "EAST": 15.0},
        target_federation=20.0,
        allocation_rule="adaptive_liquidity",
        contribution_fraction_per_period=0.10,
        recovery_period_id="day-window-0",
    )
    after_plan = ledger.snapshot()
    assert after_plan["cash_by_cell"] == before["cash_by_cell"]
    assert after_plan["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after_plan["federation_pool_reserve_balance"] == pytest.approx(before["federation_pool_reserve_balance"])
    assert plan["requested_total"] == pytest.approx(20.0)
    assert plan["funded_total"] == pytest.approx(20.0)
    assert plan["unfunded_total"] == pytest.approx(0.0)

    result = execute_reserve_recovery(ledger, plan, "RECOVERY-001", day=0)
    snapshot = ledger.snapshot()
    assert result["total_amount"] == pytest.approx(20.0)
    assert snapshot["regional_pool_reserve_by_region"] == {"WEST": 15.0, "EAST": 15.0}
    assert snapshot["federation_pool_reserve_balance"] == pytest.approx(20.0)
    assert sum(before["cash_by_cell"].values()) - sum(snapshot["cash_by_cell"].values()) == pytest.approx(20.0)
    assert snapshot["cash_conservation_error"] == pytest.approx(0.0)


def test_recovery_period_cap_cannot_be_reset_by_repeated_replenishment_ids():
    ledger = CreditLedger(
        initial_cash_per_cell=100.0,
        regional_pool_reserve_per_region=10.0,
        minimum_post_contribution_cash=10.0,
    )
    ledger.process_day(0)
    first = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 60.0, "EAST": 60.0},
        target_federation=0.0,
        allocation_rule="equal",
        contribution_fraction_per_period=0.05,
        recovery_period_id="day-window-0",
    )
    assert first["funded_total"] == pytest.approx(100.0)
    execute_reserve_recovery(ledger, first, "RECOVERY-PERIOD-A", day=0)

    second = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 100.0, "EAST": 100.0},
        target_federation=0.0,
        allocation_rule="equal",
        contribution_fraction_per_period=0.05,
        recovery_period_id="day-window-0",
    )
    assert second["funded_total"] == pytest.approx(0.0)
    assert second["unfunded_total"] == pytest.approx(80.0)
    assert all(value == pytest.approx(0.0) for value in second["remaining_capacity_by_cell"].values())


def test_regional_recovery_uses_only_members_of_the_matching_region():
    ledger = CreditLedger(initial_cash_per_cell=100.0, minimum_post_contribution_cash=10.0)
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 10.0, "EAST": 0.0},
        target_federation=0.0,
        allocation_rule="equal",
        contribution_fraction_per_period=0.50,
        recovery_period_id="day-window-0",
    )
    assert sum(plan["regional_contributions_by_cell"][cell.cell_id] for cell in CELLS if cell.region == "WEST") == pytest.approx(10.0)
    assert sum(plan["regional_contributions_by_cell"][cell.cell_id] for cell in CELLS if cell.region == "EAST") == pytest.approx(0.0)
    assert sum(plan["federation_contributions_by_cell"].values()) == pytest.approx(0.0)


def test_production_capacity_weighted_recovery_respects_member_caps():
    ledger = CreditLedger(initial_cash_per_cell=100.0, minimum_post_contribution_cash=10.0)
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 10.0, "EAST": 0.0},
        target_federation=0.0,
        allocation_rule="production_capacity",
        contribution_fraction_per_period=0.50,
        recovery_period_id="day-window-0",
    )
    west = plan["regional_contributions_by_cell"]
    assert west["WEST-AG1"] > west["WEST-MF2"]
    assert all(value <= 50.0 + 1e-9 for value in west.values())


def test_stale_recovery_plan_is_rejected_before_any_transfer():
    ledger = CreditLedger(initial_cash_per_cell=100.0, minimum_post_contribution_cash=10.0)
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 5.0, "EAST": 5.0},
        target_federation=0.0,
        recovery_period_id="day-window-0",
    )
    ledger.accounts["WEST-PR1"].cash -= 1.0
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="ledger state changed"):
        execute_reserve_recovery(ledger, plan, "STALE-RECOVERY", day=0)
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after["federation_pool_reserve_balance"] == before["federation_pool_reserve_balance"]


def test_unified_reserve_replenishment_is_atomic_when_one_member_breaches_floor():
    ledger = CreditLedger(initial_cash_per_cell=20.0, minimum_post_contribution_cash=10.0, reserve_recovery_contribution_fraction=1.0)
    ledger.process_day(0)
    regional = _zero_map()
    federation = _zero_map()
    regional["WEST-PR1"] = 1.0
    federation["EAST-PR1"] = 11.0
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="cash floor"):
        ledger.replenish_reserves(
            regional,
            federation,
            day=0,
            replenishment_id="ATOMIC-MULTI-LEVEL",
            recovery_period_id="day-window-0",
            contribution_limit_by_cell={cell.cell_id: 20.0 for cell in CELLS},
        )
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after["federation_pool_reserve_balance"] == before["federation_pool_reserve_balance"]
    assert after["cash_conservation_error"] == pytest.approx(0.0)


def test_recovery_rejects_invalid_targets_and_unknown_allocation_rule():
    ledger = CreditLedger(initial_cash_per_cell=100.0)
    with pytest.raises(ValueError):
        plan_reserve_recovery(ledger, {"WEST": 1.0}, 0.0)
    with pytest.raises(ValueError):
        plan_reserve_recovery(ledger, {"WEST": 1.0, "EAST": 1.0}, 0.0, allocation_rule="magic")
    with pytest.raises(ValueError):
        plan_reserve_recovery(ledger, {"WEST": 1.0, "EAST": 1.0}, 0.0, contribution_fraction_per_period=1.5)


def test_modified_recovery_plan_is_rejected_before_settlement():
    ledger = CreditLedger(initial_cash_per_cell=100.0, minimum_post_contribution_cash=10.0)
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 5.0, "EAST": 5.0},
        target_federation=0.0,
        recovery_period_id="day-window-0",
    )
    plan["regional_contributions_by_cell"]["WEST-PR1"] += 1.0
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="plan was modified"):
        execute_reserve_recovery(ledger, plan, "TAMPERED-PLAN", day=0)
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]
    assert after["cash_conservation_error"] == pytest.approx(0.0)


def test_recovery_period_is_derived_from_ledger_day_not_caller_label():
    ledger = CreditLedger(initial_cash_per_cell=100.0)
    ledger.process_day(0)
    with pytest.raises(ValueError, match="ledger-defined day-window-0"):
        plan_reserve_recovery(
            ledger,
            target_regional_by_region={"WEST": 5.0, "EAST": 5.0},
            target_federation=0.0,
            recovery_period_id="caller-chosen-reset",
        )


def test_ledger_rejects_multi_level_replenishment_without_canonical_period_and_cap():
    ledger = CreditLedger(initial_cash_per_cell=100.0)
    ledger.process_day(0)
    zeros = _zero_map()
    regional = dict(zeros)
    regional["WEST-PR1"] = 1.0
    with pytest.raises(ValueError, match="ledger-defined"):
        ledger.replenish_reserves(
            regional,
            zeros,
            day=0,
            replenishment_id="BYPASS-PERIOD",
            recovery_period_id="arbitrary-period",
            contribution_limit_by_cell={cell.cell_id: 10.0 for cell in CELLS},
        )
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="contribution_limit_by_cell is required"):
        ledger.replenish_reserves(
            regional,
            zeros,
            day=0,
            replenishment_id="MISSING-CAP",
            recovery_period_id="day-window-0",
        )
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]


def test_legacy_federation_api_cannot_bypass_period_cap_with_new_ids():
    ledger = CreditLedger(initial_cash_per_cell=100.0, minimum_post_contribution_cash=10.0)
    ledger.process_day(0)
    first = _zero_map()
    first["WEST-PR1"] = 10.0
    ledger.replenish_federation_reserve(first, day=0, replenishment_id="LEGACY-TOPUP-1")
    second = _zero_map()
    second["WEST-PR1"] = 0.5
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="cumulative period limit"):
        ledger.replenish_federation_reserve(second, day=0, replenishment_id="LEGACY-TOPUP-2")
    after = ledger.snapshot()
    assert after["cash_by_cell"] == before["cash_by_cell"]
    assert after["federation_pool_reserve_balance"] == before["federation_pool_reserve_balance"]
    assert after["cash_conservation_error"] == pytest.approx(0.0)


def test_ledger_rejects_caller_supplied_period_cap_above_its_own_policy():
    ledger = CreditLedger(initial_cash_per_cell=100.0, reserve_recovery_contribution_fraction=0.10)
    ledger.process_day(0)
    regional = _zero_map()
    federation = _zero_map()
    regional["WEST-PR1"] = 1.0
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="exceeds ledger policy cap"):
        ledger.replenish_reserves(
            regional,
            federation,
            day=0,
            replenishment_id="INFLATED-CAP",
            recovery_period_id="day-window-0",
            contribution_limit_by_cell={cell.cell_id: 100.0 for cell in CELLS},
        )
    assert ledger.snapshot()["cash_by_cell"] == before["cash_by_cell"]
    assert ledger.snapshot()["regional_pool_reserve_by_region"] == before["regional_pool_reserve_by_region"]


def test_planner_cannot_raise_ledger_owned_period_cap():
    ledger = CreditLedger(initial_cash_per_cell=100.0, reserve_recovery_contribution_fraction=0.10)
    with pytest.raises(ValueError, match="cannot exceed the ledger policy cap"):
        plan_reserve_recovery(
            ledger,
            target_regional_by_region={"WEST": 5.0, "EAST": 5.0},
            target_federation=0.0,
            contribution_fraction_per_period=0.50,
        )
