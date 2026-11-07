from datetime import date, datetime, timezone
import json
from pathlib import Path
from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator

from synergy_sues.contracts import Money, Quantity
from synergy_sues.inventory import InventoryLedger
from synergy_sues.journal import Account, AccountType, Journal, JournalEntry, JournalLine, NormalBalance, PostingSide
from synergy_sues.production import (
    BOMComponent, GRNIMatcher, GoodsReceipt, ProductionOrder,
    ProductionCompletionEvidence, ProductionCostEvent, ProductionCostType, PurchaseOrderLine, SupplierInvoiceLine, execute_production_order,
    post_grni_invoice, post_grni_receipt,
)


NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


def add_account(journal, account_id, code, account_type, normal):
    journal.add_account(Account(account_id, code, account_id, account_type, normal))


def production_journal():
    journal = Journal("USD", entity_id="co1")
    add_account(journal, "raw", "1300", AccountType.ASSET, NormalBalance.DEBIT)
    add_account(journal, "wip", "1400", AccountType.ASSET, NormalBalance.DEBIT)
    add_account(journal, "finished", "1500", AccountType.ASSET, NormalBalance.DEBIT)
    add_account(journal, "grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT)
    add_account(journal, "ap", "2200", AccountType.LIABILITY, NormalBalance.CREDIT)
    add_account(journal, "labor_payable", "2300", AccountType.LIABILITY, NormalBalance.CREDIT)
    add_account(journal, "energy_payable", "2400", AccountType.LIABILITY, NormalBalance.CREDIT)
    return journal



def completion(order_id, amount):
    return ProductionCompletionEvidence(
        order_id, Quantity(amount, "unit"), NOW, f"evidence:completion:{order_id}"
    )


def test_grni_three_way_match_and_journal_clearance():
    journal = production_journal()
    matcher = GRNIMatcher([
        PurchaseOrderLine("po-1", "co1", "supplier-1", "steel",
            Quantity("10", "kg"), Money("5", "USD"), date(2026, 11, 1), "po:1")
    ])
    receipt = matcher.record_receipt(
        GoodsReceipt("gr-1", "po-1", Quantity("6", "kg"), date(2026, 11, 3), "warehouse:gr-1")
    )
    invoice = matcher.record_invoice(
        SupplierInvoiceLine("inv-1", "po-1", Quantity("4", "kg"),
            Money("20", "USD"), date(2026, 11, 5), "supplier-invoice:1")
    )
    post_grni_receipt(receipt, matcher, journal, "raw", "grni", "co1", NOW)
    post_grni_invoice(invoice, matcher, journal, "grni", "ap", "co1", NOW)

    report = matcher.report("po-1")
    assert report["grni_quantity"] == "2"
    assert report["grni_value_at_po_price"] == "10"
    assert report["not_received_quantity"] == "4"
    assert report["three_way_match_complete"] is False
    tb = journal.trial_balance()
    assert tb["balanced"]
    assert tb["total_debits"] == tb["total_credits"] == "50"


def test_grni_rejects_over_receipt_unreceived_invoice_and_price_variance():
    matcher = GRNIMatcher([
        PurchaseOrderLine("po", "co1", "supplier", "part",
            Quantity("5", "unit"), Money("2", "USD"), date(2026, 11, 1), "po:part")
    ])
    with pytest.raises(ValueError, match="exceed ordered"):
        matcher.record_receipt(GoodsReceipt("r1", "po", Quantity("6", "unit"),
            date(2026, 11, 2), "evidence:r1"))
    matcher.record_receipt(GoodsReceipt("r2", "po", Quantity("3", "unit"),
        date(2026, 11, 2), "evidence:r2"))
    with pytest.raises(ValueError, match="exceeds physically received"):
        matcher.record_invoice(SupplierInvoiceLine("i1", "po", Quantity("4", "unit"),
            Money("8", "USD"), date(2026, 11, 3), "invoice:i1"))
    with pytest.raises(ValueError, match="does not match PO price"):
        matcher.record_invoice(SupplierInvoiceLine("i2", "po", Quantity("2", "unit"),
            Money("5", "USD"), date(2026, 11, 3), "invoice:i2"))
    assert matcher.report("po")["grni_quantity"] == "3"


def test_bom_execution_reconciles_material_wip_and_finished_goods():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    receipt = inventory.receive("raw-receipt", "steel-lot", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 1), "receipt:steel")
    inventory.post_to_journal("raw-receipt", journal, "raw", "grni", "co1", NOW)

    order = ProductionOrder(
        "batch-1", "co1", "machine-part", Quantity("2", "unit"), "factory",
        (BOMComponent("steel", Quantity("2", "kg")),),
        date(2026, 11, 6), "production-order:batch-1",
    )
    result = execute_production_order(order, inventory, journal,
        "raw", "wip", "finished", NOW, completion=completion("batch-1", "2"))

    assert result.direct_material_cost == Money("40", "USD")
    assert result.output_movement.quantity == Quantity("2", "unit")
    assert result.output_movement.cost == Money("40", "USD")
    pools = {(x["item_id"], x["location_id"]): x for x in inventory.summary()["pools"]}
    assert pools[("steel", "factory")]["quantity"] == "6"
    assert pools[("steel", "factory")]["inventory_cost"] == "60"
    assert pools[("machine-part", "factory")]["quantity"] == "2"
    assert pools[("machine-part", "factory")]["inventory_cost"] == "40"
    assert journal.trial_balance()["balanced"]
    assert journal.trial_balance()["total_debits"] == journal.trial_balance()["total_credits"] == "180"
    with pytest.raises(ValueError, match="already executed"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW, completion=completion("batch-1", "2"))


def test_production_preflight_prevents_partial_material_consumption():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("r1", "lot-1", "steel", "factory",
        Quantity("3", "kg"), Money("30", "USD"), date(2026, 11, 1), "receipt:steel")
    before = inventory.summary()
    order = ProductionOrder(
        "batch-short", "co1", "assembly", Quantity("2", "unit"), "factory",
        (
            BOMComponent("steel", Quantity("1", "kg")),
            BOMComponent("copper", Quantity("1", "kg")),
        ),
        date(2026, 11, 6), "production-order:short",
    )
    with pytest.raises(ValueError, match="Insufficient component copper"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW, completion=completion("batch-short", "2"))
    assert inventory.summary() == before
    assert journal.entries == ()



def test_zero_cost_bom_is_rejected_before_inventory_mutation():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("free-input", "free-lot", "sample", "factory",
        Quantity("2", "kg"), Money("0", "USD"), date(2026, 11, 1), "receipt:free")
    before = inventory.summary()
    order = ProductionOrder(
        "batch-free", "co1", "sample-product", Quantity("1", "unit"), "factory",
        (BOMComponent("sample", Quantity("1", "kg")),),
        date(2026, 11, 6), "production-order:free",
    )
    with pytest.raises(ValueError, match="Zero-cost production batch"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW, completion=completion("batch-free", "1"))
    assert inventory.summary() == before
    assert journal.entries == ()



def test_evidence_backed_labor_and_energy_costs_are_capitalized_into_finished_goods():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("raw-receipt-costed", "steel-lot-costed", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 1), "receipt:steel-costed")
    inventory.post_to_journal("raw-receipt-costed", journal, "raw", "grni", "co1", NOW)
    order = ProductionOrder(
        "batch-costed", "co1", "machine-part", Quantity("2", "unit"), "factory",
        (BOMComponent("steel", Quantity("2", "kg")),),
        date(2026, 11, 6), "production-order:batch-costed",
    )
    costs = (
        ProductionCostEvent("labor-1", "batch-costed", "co1", ProductionCostType.LABOR,
            Money("20", "USD"), date(2026, 11, 6), "payroll:batch-costed", "evidence:time-sheet"),
        ProductionCostEvent("energy-1", "batch-costed", "co1", ProductionCostType.ENERGY,
            Money("10", "USD"), date(2026, 11, 6), "utility:batch-costed", "evidence:meter"),
    )
    result = execute_production_order(
        order, inventory, journal, "raw", "wip", "finished", NOW,
        costs, {ProductionCostType.LABOR: "labor_payable", ProductionCostType.ENERGY: "energy_payable"},
        completion=completion("batch-costed", "2"),
    )
    assert result.direct_material_cost == Money("40", "USD")
    assert result.conversion_cost == Money("30", "USD")
    assert result.capitalized_cost == Money("70", "USD")
    assert result.output_movement.cost == Money("70", "USD")
    assert journal.trial_balance()["balanced"]
    assert journal.trial_balance()["total_debits"] == journal.trial_balance()["total_credits"] == "240"


def test_production_cost_events_require_mapping_before_inventory_is_consumed():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("raw-receipt-unmapped", "steel-lot-unmapped", "steel", "factory",
        Quantity("2", "kg"), Money("20", "USD"), date(2026, 11, 1), "receipt:steel-unmapped")
    before = inventory.summary()
    order = ProductionOrder(
        "batch-unmapped", "co1", "machine-part", Quantity("1", "unit"), "factory",
        (BOMComponent("steel", Quantity("1", "kg")),),
        date(2026, 11, 6), "production-order:batch-unmapped",
    )
    event = ProductionCostEvent("labor-unmapped", "batch-unmapped", "co1", ProductionCostType.LABOR,
        Money("5", "USD"), date(2026, 11, 6), "payroll:unmapped", "evidence:unmapped")
    with pytest.raises(ValueError, match="Missing credit account mapping"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW, (event,), {},
        completion=completion("batch-unmapped", "1"))
    assert inventory.summary() == before
    assert journal.entries == ()



def test_production_json_schema_validates_all_procurement_and_production_contracts():
    schema_path = Path(__file__).resolve().parents[1] / "interfaces" / "synergy_sues_production.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    samples = [
        {"po_line_id": "po", "entity_id": "co1", "supplier_id": "s1", "item_id": "steel",
         "ordered_quantity": {"amount": "10", "unit": "kg"},
         "unit_price": {"amount": "5", "currency": "USD"}, "order_date": "2026-11-01", "source_ref": "po:1"},
        {"receipt_id": "r1", "po_line_id": "po", "received_quantity": {"amount": "2", "unit": "kg"},
         "received_date": "2026-11-02", "evidence_ref": "warehouse:r1"},
        {"invoice_line_id": "i1", "po_line_id": "po", "invoiced_quantity": {"amount": "2", "unit": "kg"},
         "amount": {"amount": "10", "currency": "USD"}, "invoice_date": "2026-11-03", "source_ref": "invoice:1"},
        {"item_id": "steel", "quantity_per_output_unit": {"amount": "2", "unit": "kg"}},
        {"order_id": "batch", "entity_id": "co1", "product_id": "part",
         "output_quantity": {"amount": "1", "unit": "unit"}, "location_id": "factory",
         "components": [{"item_id": "steel", "quantity_per_output_unit": {"amount": "2", "unit": "kg"}}],
         "planned_date": "2026-11-06", "source_ref": "production:batch"},
        {"event_id": "labor-1", "order_id": "batch", "entity_id": "co1", "cost_type": "LABOR",
         "amount": {"amount": "5", "currency": "USD"}, "effective_date": "2026-11-06",
         "source_ref": "payroll:1", "evidence_ref": "timesheet:1"},
        {"order_id": "batch", "output_quantity": {"amount": "1", "unit": "unit"},
         "completed_at": "2026-11-06T12:00:00Z", "evidence_ref": "production:completion:1"},
        {"order_id": "batch", "direct_material_cost": {"amount": "10", "currency": "USD"},
         "conversion_cost": {"amount": "5", "currency": "USD"}, "capitalized_cost": {"amount": "15", "currency": "USD"},
         "output_quantity": {"amount": "1", "unit": "unit"}, "completion_evidence_ref": "production:completion:1",
         "completed_at": "2026-11-06T12:00:00Z", "journal_entry_ids": ["entry:1"]},
    ]
    for sample in samples:
        validator.validate(sample)


def test_grni_invoice_cannot_predate_the_receipt_supporting_it():
    matcher = GRNIMatcher([
        PurchaseOrderLine("po-date", "co1", "supplier", "steel",
            Quantity("5", "kg"), Money("2", "USD"), date(2026, 11, 1), "po:date")
    ])
    matcher.record_receipt(GoodsReceipt(
        "receipt-date", "po-date", Quantity("3", "kg"),
        date(2026, 11, 5), "warehouse:receipt-date",
    ))
    with pytest.raises(ValueError, match="precedes the physical receipt"):
        matcher.record_invoice(SupplierInvoiceLine(
            "invoice-date", "po-date", Quantity("2", "kg"),
            Money("4", "USD"), date(2026, 11, 4), "supplier:invoice-date",
        ))
    assert matcher.report("po-date")["invoiced_quantity"] == "0"


def test_production_books_measured_output_not_planned_quantity():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("measured-input", "measured-lot", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 1), "receipt:measured")
    order = ProductionOrder(
        "batch-measured", "co1", "part", Quantity("4", "unit"), "factory",
        (BOMComponent("steel", Quantity("2", "kg")),),
        date(2026, 11, 6), "production:measured",
    )
    result = execute_production_order(
        order, inventory, journal, "raw", "wip", "finished", NOW,
        completion=completion("batch-measured", "1"),
    )
    assert result.output_quantity == Quantity("1", "unit")
    assert result.output_movement.quantity == Quantity("1", "unit")
    assert result.completion_evidence_ref == "evidence:completion:batch-measured"
    pools = {row["item_id"]: row for row in inventory.summary()["pools"]}
    assert pools["steel"]["quantity"] == "8"
    assert pools["part"]["quantity"] == "1"


def test_production_execution_requires_completion_evidence_and_rejects_overproduction():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("input", "input-lot", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 1), "receipt:input")
    order = ProductionOrder(
        "batch-no-evidence", "co1", "part", Quantity("2", "unit"), "factory",
        (BOMComponent("steel", Quantity("1", "kg")),),
        date(2026, 11, 6), "production:no-evidence",
    )
    with pytest.raises(ValueError, match="completion evidence is required"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW)
    with pytest.raises(ValueError, match="exceeds the authorized order"):
        execute_production_order(
            order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion("batch-no-evidence", "3"),
        )
    assert inventory.summary()["pools"][0]["quantity"] == "10"
    assert journal.entries == ()


def test_production_rolls_back_inventory_when_atomic_journal_batch_rejects():
    journal = production_journal()
    collision_event_id = "production-consumption:production:batch-atomic:issue:steel"
    journal.post(JournalEntry(
        "unrelated-seed", date(2026, 11, 6), NOW, "USD",
        (
            JournalLine("seed-dr", "raw", PostingSide.DEBIT, Money("1", "USD"), Money("1", "USD"), "co1", "seed:raw"),
            JournalLine("seed-cr", "grni", PostingSide.CREDIT, Money("1", "USD"), Money("1", "USD"), "co1", "seed:grni"),
        ),
        collision_event_id, "unrelated-seed-idem", "Seed conflicting source event",
    ))
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("atomic-input", "atomic-lot", "steel", "factory",
        Quantity("5", "kg"), Money("50", "USD"), date(2026, 11, 1), "receipt:atomic")
    before_summary = inventory.summary()
    before_movements = inventory.movements
    order = ProductionOrder(
        "batch-atomic", "co1", "part", Quantity("2", "unit"), "factory",
        (BOMComponent("steel", Quantity("1", "kg")),),
        date(2026, 11, 6), "production:atomic",
    )
    with pytest.raises(ValueError, match="Duplicate source_event_id"):
        execute_production_order(
            order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion("batch-atomic", "2"),
        )
    assert inventory.summary() == before_summary
    assert inventory.movements == before_movements
    assert len(journal.entries) == 1
