from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from synergy_sues.contracts import Money, Quantity
from synergy_sues.inventory import InventoryLedger
from synergy_sues.journal import Account, AccountType, Journal, NormalBalance
from synergy_sues.production import (
    BOMComponent, GRNIMatcher, GoodsReceipt, ProductionOrder,
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
    return journal


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
    inventory = InventoryLedger("USD")
    receipt = inventory.receive("raw-receipt", "steel-lot", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 1), "receipt:steel")
    inventory.post_to_journal("raw-receipt", journal, "raw", "grni", "co1", NOW)

    order = ProductionOrder(
        "batch-1", "co1", "machine-part", Quantity("2", "unit"), "factory",
        (BOMComponent("steel", Quantity("2", "kg")),),
        date(2026, 11, 6), "production-order:batch-1",
    )
    result = execute_production_order(order, inventory, journal,
        "raw", "wip", "finished", NOW)

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
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW)


def test_production_preflight_prevents_partial_material_consumption():
    journal = production_journal()
    inventory = InventoryLedger("USD")
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
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW)
    assert inventory.summary() == before
    assert journal.entries == ()



def test_zero_cost_bom_is_rejected_before_inventory_mutation():
    journal = production_journal()
    inventory = InventoryLedger("USD")
    inventory.receive("free-input", "free-lot", "sample", "factory",
        Quantity("2", "kg"), Money("0", "USD"), date(2026, 11, 1), "receipt:free")
    before = inventory.summary()
    order = ProductionOrder(
        "batch-free", "co1", "sample-product", Quantity("1", "unit"), "factory",
        (BOMComponent("sample", Quantity("1", "kg")),),
        date(2026, 11, 6), "production-order:free",
    )
    with pytest.raises(ValueError, match="Zero-cost production batch"):
        execute_production_order(order, inventory, journal, "raw", "wip", "finished", NOW)
    assert inventory.summary() == before
    assert journal.entries == ()
