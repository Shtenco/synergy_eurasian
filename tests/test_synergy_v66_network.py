import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.network import CELLS, REGIONS, Lot, _consume_fifo, make_environment, run, simulate
import pytest


def test_network_has_twenty_cells_two_regions_and_three_core_sectors():
    assert len(CELLS) == 20
    assert {c.region for c in CELLS} == set(REGIONS)
    assert {c.sector for c in CELLS if c.sector != "support"} == {"primary", "processing", "manufacturing"}
    assert len({c.cell_id for c in CELLS}) == 20


def test_environment_and_replay_are_deterministic():
    assert make_environment(91, 20, "severe") == make_environment(91, 20, "severe")
    assert run(91, 20, "severe") == run(91, 20, "severe")


def test_physical_balance_and_nonnegative_outputs():
    result = simulate(make_environment(17, 35, "volatile"))
    assert abs(result["physical_balance_error"]) < 1e-7
    assert all(abs(v) < 1e-7 for v in result["physical_balance_error_by_sku"].values())
    assert result["cell_count"] == 20
    assert result["pending_shipments"] >= 0
    assert result["closing_stock"] >= -1e-9
    assert all(v >= -1e-9 for v in result["unmet_demand_by_sku"].values())
    assert all(v >= -1e-9 for v in result["sold_by_sku"].values())


def test_warehouse_and_transport_limits_are_respected():
    result = simulate(make_environment(123, 45, "severe"))
    for region in REGIONS:
        assert result["max_warehouse_load_by_region"][region] <= result["warehouse_capacity_by_region"][region] + 1e-7
        assert result["max_transport_load_by_region"][region] <= result["transport_capacity_by_region"][region] * 1.08 + 1e-7


def test_no_delivery_before_lead_time():
    result = simulate(make_environment(7, 12, "normal"))
    dispatch = {x["shipment_id"]: x for x in result["shipment_dispatch_audit"]}
    assert result["shipment_arrival_audit"]
    for arrival in result["shipment_arrival_audit"]:
        assert arrival["arrival_day"] > arrival["dispatch_day"]
        assert arrival["arrival_day"] - arrival["dispatch_day"] >= 1
        assert arrival["shipment_id"] in dispatch


def test_future_environment_cannot_change_past_ledger():
    full = make_environment(808, 18, "volatile")
    assert simulate(full[:7])["daily_ledger"] == simulate(full)["daily_ledger"][:7]


def test_invalid_inputs_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        make_environment(1, 0, "normal")
    with pytest.raises(ValueError):
        make_environment(1, 2, "unknown")
    with pytest.raises(ValueError):
        simulate([], 1.0)
    with pytest.raises(ValueError):
        simulate(make_environment(1, 2, "normal"), -1.0)


def test_fifo_consumes_earliest_expiring_lot_first():
    lots = [Lot("late", "grain", 5.0, 0, 20, "test"), Lot("early", "grain", 3.0, 0, 5, "test")]
    assert _consume_fifo(lots, "grain", 2.0, 1) == 5
    assert next(lot for lot in lots if lot.lot_id == "early").quantity == 1.0
    assert next(lot for lot in lots if lot.lot_id == "late").quantity == 5.0


def test_cash_constrained_mode_blocks_production_without_liquidity():
    environment = make_environment(2026, 20, "volatile")
    baseline = simulate(environment)
    constrained = simulate(environment, credit_config={
        "initial_cash_per_cell": 0.0,
        "bank_limit_per_cell": 0.0,
        "trade_credit_limit_per_cell": 0.0,
    })
    assert constrained["credit_constrained"] is True
    assert constrained["model_id"] == "SYNERGY_V6.6.3B_CASH_CONSTRAINED_NETWORK"
    assert sum(constrained["produced_by_sku"].values()) == pytest.approx(0.0)
    assert sum(constrained["sold_by_sku"].values()) == pytest.approx(0.0)
    assert sum(constrained["unmet_demand_by_sku"].values()) > sum(baseline["unmet_demand_by_sku"].values())
    assert abs(constrained["physical_balance_error"]) < 1e-7
    credit = constrained["credit_ledger"]
    assert credit["external_supplier_payments"] == pytest.approx(0.0)
    assert credit["cash_conservation_error"] == pytest.approx(0.0)


def test_funded_credit_mode_preserves_physical_path_and_reconciles_cash():
    environment = make_environment(2026, 20, "normal")
    baseline = simulate(environment)
    funded = simulate(environment, credit_config={
        "initial_cash_per_cell": 1_000_000.0,
        "bank_limit_per_cell": 0.0,
        "trade_credit_limit_per_cell": 1_000_000.0,
    })
    assert funded["produced_by_sku"] == pytest.approx(baseline["produced_by_sku"])
    assert funded["sold_by_sku"] == pytest.approx(baseline["sold_by_sku"])
    assert abs(funded["physical_balance_error"]) < 1e-7
    credit = funded["credit_ledger"]
    assert abs(credit["cash_conservation_error"]) < 1e-6
    assert abs(credit["internal_transfer_net"]) < 1e-9
    assert all(v >= -1e-9 for v in credit["cash_by_cell"].values())
    assert all(credit["bank_debt_by_cell"][k] <= 1e-9 for k in credit["bank_debt_by_cell"])


def test_credit_payment_terms_must_be_non_negative_integers():
    with pytest.raises(ValueError):
        simulate(make_environment(1, 2, "normal"), credit_config={"customer_terms_days": -1})
    with pytest.raises(ValueError):
        simulate(make_environment(1, 2, "normal"), credit_config={"local_terms_days": 1.5})
