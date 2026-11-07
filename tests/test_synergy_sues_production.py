from datetime import date, datetime, timezone
import json
from pathlib import Path
from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator

from synergy_sues.contracts import Money, Quantity
from synergy_sues.inventory import InventoryLedger
from synergy_sues.journal import Account, AccountType, Journal, NormalBalance
from synergy_sues.production import (
    BOMComponent, GRNIMatcher, GoodsReceipt, ProductionOrder,
    ProductionCostEvent, ProductionCostType, ProductionCompletionEvidence, ProductionInputConsumption,
    PurchaseOrderLine, SupplierInvoiceLine, execute_production_order,
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

def completion_for(order, output_quantity=None, input_quantities=None, evidence_ref="quality:accepted-output"):
    output = output_quantity or order.output_quantity
    measured = input_quantities or {
        component.item_id: Quantity(
            component.quantity_per_output_unit.amount * order.output_quantity.amount,
            component.quantity_per_output_unit.unit,
        )
        for component in order.components
    }
    return ProductionCompletionEvidence(
        order.order_id, output, NOW, evidence_ref,
        tuple(ProductionInputConsumption(item, quantity, f"scale:{item}")
              for item, quantity in measured.items()),
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
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("gr-1", "gr-1-lot", "steel", "warehouse",
        Quantity("6", "kg"), Money("30", "USD"), date(2026, 11, 3), "warehouse:gr-1")
    post_grni_receipt(receipt, matcher, inventory, journal, "raw", "grni", "co1", NOW)
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
        "raw", "wip", "finished", NOW, completion=completion_for(order))

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
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion_for(order))


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
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion_for(order))
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
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion_for(order))
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
        completion=completion_for(order),
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
            completion=completion_for(order))
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
        {"order_id": "batch", "direct_material_cost": {"amount": "10", "currency": "USD"},
         "conversion_cost": {"amount": "5", "currency": "USD"}, "capitalized_cost": {"amount": "15", "currency": "USD"},
         "output_quantity": {"amount": "1", "unit": "unit"}, "journal_entry_ids": ["entry:1"],
         "completion_evidence_ref": "quality:accepted", "completed_at": "2026-11-06T10:00:00Z"},
        {"order_id": "batch", "output_quantity": {"amount": "1", "unit": "unit"},
         "completed_at": "2026-11-06T10:00:00Z", "evidence_ref": "quality:accepted",
         "input_consumption": [{"item_id": "steel", "quantity": {"amount": "2", "unit": "kg"},
                                "evidence_ref": "scale:steel"}]},
    ]
    for sample in samples:
        validator.validate(sample)


def test_grni_rejects_invoice_before_supporting_physical_receipt():
    matcher = GRNIMatcher([
        PurchaseOrderLine("po-temporal", "co1", "supplier", "steel",
            Quantity("10", "kg"), Money("5", "USD"), date(2026, 11, 1), "po:temporal")
    ])
    matcher.record_receipt(GoodsReceipt(
        "receipt-later", "po-temporal", Quantity("5", "kg"),
        date(2026, 11, 10), "warehouse:receipt-later",
    ))
    with pytest.raises(ValueError, match="precedes the physical receipt"):
        matcher.record_invoice(SupplierInvoiceLine(
            "invoice-earlier", "po-temporal", Quantity("5", "kg"),
            Money("25", "USD"), date(2026, 11, 5), "invoice:earlier",
        ))
    assert matcher.invoices == ()


def test_grni_invoice_cannot_clear_forged_journal_entry_with_receipt_id():
    from synergy_sues.journal import JournalEntry, JournalLine, PostingSide
    journal = production_journal()
    matcher = GRNIMatcher([
        PurchaseOrderLine("po-forged", "co1", "supplier", "steel",
            Quantity("2", "kg"), Money("5", "USD"), date(2026, 11, 1), "po:forged")
    ])
    receipt = matcher.record_receipt(GoodsReceipt(
        "receipt-forged", "po-forged", Quantity("2", "kg"),
        date(2026, 11, 3), "warehouse:receipt-forged",
    ))
    invoice = matcher.record_invoice(SupplierInvoiceLine(
        "invoice-forged", "po-forged", Quantity("2", "kg"),
        Money("10", "USD"), date(2026, 11, 4), "supplier:invoice-forged",
    ))
    fake_id = f"grni:receipt:{receipt.receipt_id}"
    journal.post(JournalEntry(
        fake_id, receipt.received_date, NOW, "USD",
        (
            JournalLine(f"{fake_id}:dr", "raw", PostingSide.DEBIT,
                Money("10", "USD"), Money("10", "USD"), "co1", "fake:source"),
            JournalLine(f"{fake_id}:cr", "grni", PostingSide.CREDIT,
                Money("10", "USD"), Money("10", "USD"), "co1", "fake:source"),
        ),
        "not-the-grni-receipt-event", "not-the-grni-receipt-idem", "Forged GRNI receipt",
    ))
    with pytest.raises(ValueError, match="cannot clear more GRNI"):
        post_grni_invoice(invoice, matcher, journal, "grni", "ap", "co1", NOW)


def test_production_books_measured_partial_output_not_planned_output():
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("steel-partial", "steel-lot-partial", "steel", "factory",
        Quantity("20", "kg"), Money("200", "USD"), date(2026, 11, 1), "receipt:steel-partial")
    order = ProductionOrder(
        "batch-partial", "co1", "part", Quantity("10", "unit"), "factory",
        (BOMComponent("steel", Quantity("2", "kg")),),
        date(2026, 11, 5), "production:plan-partial",
    )
    completion = completion_for(
        order, Quantity("6", "unit"), {"steel": Quantity("12", "kg")},
        "quality:accepted-six",
    )
    result = execute_production_order(
        order, inventory, journal, "raw", "wip", "finished", NOW,
        completion=completion,
    )
    assert result.output_quantity == Quantity("6", "unit")
    assert result.output_movement.quantity == Quantity("6", "unit")
    assert result.completion_evidence_ref == "quality:accepted-six"
    pools = {(x["item_id"], x["location_id"]): x for x in inventory.summary()["pools"]}
    assert pools[("steel", "factory")]["quantity"] == "8"
    assert pools[("part", "factory")]["quantity"] == "6"


def test_production_journal_failure_rolls_back_all_inventory_mutations():
    from synergy_sues.journal import JournalEntry, JournalLine, PostingSide
    journal = production_journal()
    inventory = InventoryLedger("USD", entity_id="co1")
    inventory.receive("steel-rollback", "steel-lot-rollback", "steel", "factory",
        Quantity("5", "kg"), Money("50", "USD"), date(2026, 11, 1), "receipt:steel-rollback")
    conflicting_source = "production-consumption:production:batch-rollback:issue:steel"
    journal.post(JournalEntry(
        "preexisting-conflict", date(2026, 11, 5), NOW, "USD",
        (
            JournalLine("conflict-dr", "raw", PostingSide.DEBIT,
                Money("1", "USD"), Money("1", "USD"), "co1", "conflict:raw"),
            JournalLine("conflict-cr", "grni", PostingSide.CREDIT,
                Money("1", "USD"), Money("1", "USD"), "co1", "conflict:grni"),
        ),
        conflicting_source, "other-idempotency", "Create source-event collision",
    ))
    before = inventory.summary()
    order = ProductionOrder(
        "batch-rollback", "co1", "part", Quantity("1", "unit"), "factory",
        (BOMComponent("steel", Quantity("1", "kg")),),
        date(2026, 11, 5), "production:rollback",
    )
    with pytest.raises(ValueError, match="source_event_id"):
        execute_production_order(
            order, inventory, journal, "raw", "wip", "finished", NOW,
            completion=completion_for(order),
        )
    assert inventory.summary() == before
    assert len(journal.entries) == 1
