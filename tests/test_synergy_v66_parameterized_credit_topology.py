from __future__ import annotations

import pytest

from synergy_v66.credit import CreditLedger
from synergy_v66.network_topology import CELLS, CellSpec
from synergy_v66.reserve_recovery import execute_reserve_recovery, plan_reserve_recovery


def _stress_cells():
    return (
        CellSpec("WEST-B01", "WEST", "trade", "borrower", 8.0),
        CellSpec("WEST-S01", "WEST", "trade", "seller", 12.0),
        CellSpec("WEST-R01", "WEST", "services", "reserve_member", 6.0),
        CellSpec("EAST-B01", "EAST", "trade", "borrower", 8.0),
        CellSpec("EAST-S01", "EAST", "trade", "seller", 12.0),
        CellSpec("EAST-R01", "EAST", "services", "reserve_member", 6.0),
    )


def _maps(cells):
    regional = {cell.cell_id: 0.0 for cell in cells}
    federation = {cell.cell_id: 0.0 for cell in cells}
    regional["WEST-R01"] = 2.0
    regional["EAST-R01"] = 2.0
    federation["WEST-S01"] = 2.0
    federation["EAST-S01"] = 2.0
    return regional, federation


def test_default_credit_topology_remains_the_canonical_physical_topology():
    ledger = CreditLedger()
    assert set(ledger.accounts) == {cell.cell_id for cell in CELLS}
    assert ledger.regions == ("WEST", "EAST")
    assert len(ledger.cells) == 20


def test_credit_ledger_accepts_an_independent_parameterized_stress_topology():
    cells = _stress_cells()
    regional, federation = _maps(cells)
    cash = {cell.cell_id: 100.0 for cell in cells}
    ledger = CreditLedger(
        cells=cells,
        regions=("WEST", "EAST"),
        initial_cash_by_cell=cash,
        regional_pool_reserve_per_region=2.0,
        regional_reserve_contributions_by_cell=regional,
        federation_pool_reserve_total=4.0,
        federation_reserve_contributions_by_cell=federation,
        minimum_post_contribution_cash=20.0,
    )
    assert set(ledger.accounts) == set(cash)
    assert ledger.cell_by_id["WEST-B01"].region == "WEST"
    assert ledger.snapshot()["cash_conservation_error"] == pytest.approx(0.0)


def test_custom_topology_requires_exact_opening_cash_and_reserve_membership_maps():
    cells = _stress_cells()
    regional, federation = _maps(cells)
    cash = {cell.cell_id: 100.0 for cell in cells}
    with pytest.raises(ValueError, match="every known cell"):
        CreditLedger(cells=cells, initial_cash_by_cell={**cash, "EXTRA": 1.0})
    with pytest.raises(ValueError, match="every known cell"):
        CreditLedger(
            cells=cells,
            initial_cash_by_cell=cash,
            regional_pool_reserve_per_region=2.0,
            regional_reserve_contributions_by_cell={key: value for key, value in regional.items() if key != "WEST-B01"},
        )
    with pytest.raises(ValueError, match="unique"):
        CreditLedger(cells=(cells[0], cells[0]))


def test_recovery_planner_uses_the_ledger_topology_not_global_physical_cells():
    cells = _stress_cells()
    regional, federation = _maps(cells)
    cash = {cell.cell_id: 100.0 for cell in cells}
    ledger = CreditLedger(
        cells=cells,
        initial_cash_by_cell=cash,
        regional_pool_reserve_per_region=2.0,
        regional_reserve_contributions_by_cell=regional,
        federation_pool_reserve_total=4.0,
        federation_reserve_contributions_by_cell=federation,
        minimum_post_contribution_cash=20.0,
        reserve_recovery_contribution_fraction=0.10,
    )
    ledger.process_day(0)
    plan = plan_reserve_recovery(
        ledger,
        target_regional_by_region={"WEST": 5.0, "EAST": 5.0},
        target_federation=8.0,
        allocation_rule="adaptive_liquidity",
    )
    assert set(plan["regional_contributions_by_cell"]) == set(cash)
    assert set(plan["federation_contributions_by_cell"]) == set(cash)
    assert plan["requested_total"] == pytest.approx(10.0)
    assert plan["funded_total"] == pytest.approx(10.0)
    settlement = execute_reserve_recovery(
        ledger, plan, replenishment_id="STRESS-TOPOLOGY-RECOVERY-1", day=0
    )
    assert settlement["total_amount"] == pytest.approx(10.0)
    snapshot = ledger.snapshot()
    assert snapshot["regional_pool_reserve_by_region"] == pytest.approx({"WEST": 5.0, "EAST": 5.0})
    assert snapshot["federation_pool_reserve_balance"] == pytest.approx(8.0)
    assert snapshot["cash_conservation_error"] == pytest.approx(0.0)


def test_stress_topology_does_not_mutate_the_canonical_physical_topology():
    before = tuple((cell.cell_id, cell.region, cell.capacity) for cell in CELLS)
    custom = _stress_cells()
    CreditLedger(cells=custom)
    after = tuple((cell.cell_id, cell.region, cell.capacity) for cell in CELLS)
    assert after == before

def test_stress_topology_rejects_invalid_capacity_and_region_metadata():
    with pytest.raises(ValueError, match="capacities"):
        CreditLedger(cells=(CellSpec("BAD-1", "WEST", "trade", "borrower", -1.0),))
    with pytest.raises(ValueError, match="regions"):
        CreditLedger(cells=(CellSpec("BAD-2", "", "trade", "borrower", 1.0),))
