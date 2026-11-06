"""GRNI three-way matching and auditable BOM-to-WIP-to-finished-goods execution.

Reference implementation only: callers must supply evidence and validated GL accounts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Money, Quantity, _aware
from .inventory import InventoryLedger, InventoryMovement
from .journal import (
    AccountType, Journal, JournalEntry, JournalLine, NormalBalance, PostingSide,
)


@dataclass(frozen=True)
class PurchaseOrderLine:
    po_line_id: str
    entity_id: str
    supplier_id: str
    item_id: str
    ordered_quantity: Quantity
    unit_price: Money
    order_date: date
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.po_line_id, self.entity_id, self.supplier_id, self.item_id, self.source_ref)):
            raise ValueError("PO line identity, entity, supplier, item and source are required")
        if self.ordered_quantity.amount <= 0 or self.unit_price.amount < 0:
            raise ValueError("PO quantity must be positive and unit price non-negative")
        if not isinstance(self.order_date, date):
            raise ValueError("PO order_date must be a date")


@dataclass(frozen=True)
class GoodsReceipt:
    receipt_id: str
    po_line_id: str
    received_quantity: Quantity
    received_date: date
    evidence_ref: str

    def __post_init__(self) -> None:
        if not all((self.receipt_id, self.po_line_id, self.evidence_ref)):
            raise ValueError("Goods receipt identity and evidence are required")
        if self.received_quantity.amount <= 0 or not isinstance(self.received_date, date):
            raise ValueError("Goods receipt requires positive quantity and valid date")


@dataclass(frozen=True)
class SupplierInvoiceLine:
    invoice_line_id: str
    po_line_id: str
    invoiced_quantity: Quantity
    amount: Money
    invoice_date: date
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.invoice_line_id, self.po_line_id, self.source_ref)):
            raise ValueError("Invoice line identity and source are required")
        if self.invoiced_quantity.amount <= 0 or self.amount.amount <= 0:
            raise ValueError("Invoice quantity and amount must be positive")
        if not isinstance(self.invoice_date, date):
            raise ValueError("Invoice date must be a date")


class GRNIMatcher:
    """Matches PO quantity, physically received quantity and supplier invoicing."""

    def __init__(self, purchase_orders: Iterable[PurchaseOrderLine] = ()) -> None:
        self._orders: dict[str, PurchaseOrderLine] = {}
        self._receipts: dict[str, GoodsReceipt] = {}
        self._invoices: dict[str, SupplierInvoiceLine] = {}
        for row in purchase_orders:
            self.add_purchase_order(row)

    @property
    def receipts(self) -> tuple[GoodsReceipt, ...]:
        return tuple(self._receipts.values())

    @property
    def invoices(self) -> tuple[SupplierInvoiceLine, ...]:
        return tuple(self._invoices.values())

    def add_purchase_order(self, row: PurchaseOrderLine) -> None:
        if row.po_line_id in self._orders:
            raise ValueError(f"Duplicate PO line: {row.po_line_id}")
        self._orders[row.po_line_id] = row

    def record_receipt(self, row: GoodsReceipt) -> GoodsReceipt:
        po = self._orders.get(row.po_line_id)
        if po is None:
            raise ValueError(f"Unknown PO line: {row.po_line_id}")
        if row.receipt_id in self._receipts:
            raise ValueError(f"Duplicate goods receipt: {row.receipt_id}")
        if row.received_quantity.unit != po.ordered_quantity.unit:
            raise ValueError("Goods receipt unit differs from PO unit")
        if row.received_date < po.order_date:
            raise ValueError("Goods receipt cannot predate purchase order")
        received = sum((x.received_quantity.amount for x in self._receipts.values()
                        if x.po_line_id == row.po_line_id), Decimal("0"))
        if received + row.received_quantity.amount > po.ordered_quantity.amount:
            raise ValueError("Cumulative goods receipts exceed ordered quantity")
        self._receipts[row.receipt_id] = row
        return row

    def record_invoice(self, row: SupplierInvoiceLine) -> SupplierInvoiceLine:
        po = self._orders.get(row.po_line_id)
        if po is None:
            raise ValueError(f"Unknown PO line: {row.po_line_id}")
        if row.invoice_line_id in self._invoices:
            raise ValueError(f"Duplicate supplier invoice line: {row.invoice_line_id}")
        if row.invoiced_quantity.unit != po.ordered_quantity.unit:
            raise ValueError("Invoice quantity unit differs from PO unit")
        if row.amount.currency != po.unit_price.currency:
            raise ValueError("Invoice currency differs from PO currency")
        if row.invoice_date < po.order_date:
            raise ValueError("Supplier invoice cannot predate purchase order")
        received = sum((x.received_quantity.amount for x in self._receipts.values()
                        if x.po_line_id == row.po_line_id), Decimal("0"))
        already_invoiced = sum((x.invoiced_quantity.amount for x in self._invoices.values()
                                if x.po_line_id == row.po_line_id), Decimal("0"))
        if already_invoiced + row.invoiced_quantity.amount > received:
            raise ValueError("Invoice quantity exceeds physically received, not-yet-invoiced quantity")
        expected = po.unit_price.amount * row.invoiced_quantity.amount
        if row.amount.amount != expected:
            raise ValueError("Invoice amount does not match PO price; route variance for approval")
        self._invoices[row.invoice_line_id] = row
        return row

    def report(self, po_line_id: str) -> dict:
        po = self._orders.get(po_line_id)
        if po is None:
            raise ValueError(f"Unknown PO line: {po_line_id}")
        received = sum((x.received_quantity.amount for x in self._receipts.values()
                        if x.po_line_id == po_line_id), Decimal("0"))
        invoiced = sum((x.invoiced_quantity.amount for x in self._invoices.values()
                        if x.po_line_id == po_line_id), Decimal("0"))
        return {
            "po_line_id": po_line_id,
            "ordered_quantity": str(po.ordered_quantity.amount),
            "received_quantity": str(received),
            "uninvoiced_received_quantity": str(received - invoiced),
            "not_received_quantity": str(po.ordered_quantity.amount - received),
            "invoiced_quantity": str(invoiced),
            "grni_quantity": str(received - invoiced),
            "po_currency": po.unit_price.currency,
            "grni_value_at_po_price": str((received - invoiced) * po.unit_price.amount),
            "fully_received": received == po.ordered_quantity.amount,
            "fully_invoiced_received_goods": invoiced == received,
            "three_way_match_complete": received == po.ordered_quantity.amount and invoiced == received,
        }


@dataclass(frozen=True)
class BOMComponent:
    item_id: str
    quantity_per_output_unit: Quantity

    def __post_init__(self) -> None:
        if not self.item_id or self.quantity_per_output_unit.amount <= 0:
            raise ValueError("BOM component requires item and positive quantity per output unit")


@dataclass(frozen=True)
class ProductionOrder:
    order_id: str
    entity_id: str
    product_id: str
    output_quantity: Quantity
    location_id: str
    components: tuple[BOMComponent, ...]
    planned_date: date
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.order_id, self.entity_id, self.product_id, self.location_id, self.source_ref)):
            raise ValueError("Production order identity, entity, product, location and source are required")
        if self.output_quantity.amount <= 0 or not self.components:
            raise ValueError("Production order requires positive output and a non-empty BOM")
        if not isinstance(self.components, tuple):
            object.__setattr__(self, "components", tuple(self.components))
        if len({x.item_id for x in self.components}) != len(self.components):
            raise ValueError("BOM item IDs must be unique; aggregate duplicate components explicitly")
        if not isinstance(self.planned_date, date):
            raise ValueError("Production planned_date must be a date")


class ProductionCostType(str, Enum):
    LABOR = "LABOR"
    ENERGY = "ENERGY"
    MACHINE = "MACHINE"
    MAINTENANCE = "MAINTENANCE"
    DEPRECIATION = "DEPRECIATION"
    SUBCONTRACT = "SUBCONTRACT"
    OTHER_OVERHEAD = "OTHER_OVERHEAD"


@dataclass(frozen=True)
class ProductionCostEvent:
    event_id: str
    order_id: str
    entity_id: str
    cost_type: ProductionCostType
    amount: Money
    effective_date: date
    source_ref: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if not all((self.event_id, self.order_id, self.entity_id, self.source_ref, self.evidence_ref)):
            raise ValueError("Production cost event identity and evidence are required")
        if not isinstance(self.cost_type, ProductionCostType):
            object.__setattr__(self, "cost_type", ProductionCostType(self.cost_type))
        if self.amount.amount <= 0 or not isinstance(self.effective_date, date):
            raise ValueError("Production cost event requires positive amount and valid date")


@dataclass(frozen=True)
class ProductionExecution:
    order_id: str
    output_movement: InventoryMovement
    input_movements: tuple[InventoryMovement, ...]
    direct_material_cost: Money
    conversion_cost: Money
    capitalized_cost: Money
    output_quantity: Quantity
    journal_entry_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.direct_material_cost.currency != self.conversion_cost.currency or self.direct_material_cost.currency != self.capitalized_cost.currency:
            raise ValueError("Production cost currencies must match")
        if self.capitalized_cost != self.direct_material_cost + self.conversion_cost:
            raise ValueError("Capitalized cost must equal direct material plus conversion cost")
        if self.output_movement.cost != self.capitalized_cost:
            raise ValueError("Finished-goods cost must reconcile to total capitalized WIP cost")
        if self.output_movement.quantity != self.output_quantity:
            raise ValueError("Finished-goods quantity differs from production output")


def _account_map(journal: Journal, account_id: str, account_type: AccountType,
                 normal_balance: NormalBalance, label: str) -> None:
    row = next((x for x in journal.accounts if x.account_id == account_id), None)
    if row is None or row.account_type != account_type or row.normal_balance != normal_balance:
        raise ValueError(f"{label} must be an existing {account_type.value}/{normal_balance.value} account")


def execute_production_order(
    order: ProductionOrder,
    inventory: InventoryLedger,
    journal: Journal,
    inventory_account_id: str,
    wip_account_id: str,
    finished_goods_account_id: str,
    recorded_at: datetime,
    conversion_costs: Iterable[ProductionCostEvent] = (),
    conversion_cost_accounts: dict[ProductionCostType | str, str] | None = None,
) -> ProductionExecution:
    """Consume a complete BOM batch and capitalize direct materials into finished goods.

    The inventory subledger records raw-material issues and finished output. The GL
    posts direct materials to WIP, then WIP to finished goods. Labor, overhead,
    depreciation, scrap variances and by-product credits are excluded from V1.
    """
    _aware(recorded_at, "recorded_at")
    if journal.functional_currency != inventory.functional_currency:
        raise ValueError("Production inventory and journal currencies must match")
    _account_map(journal, inventory_account_id, AccountType.ASSET, NormalBalance.DEBIT, "Inventory account")
    _account_map(journal, wip_account_id, AccountType.ASSET, NormalBalance.DEBIT, "WIP account")
    _account_map(journal, finished_goods_account_id, AccountType.ASSET, NormalBalance.DEBIT, "Finished-goods account")
    if len({inventory_account_id, wip_account_id, finished_goods_account_id}) != 3:
        raise ValueError("Raw inventory, WIP and finished-goods accounts must be distinct")
    if journal.entity_id is not None and journal.entity_id != order.entity_id:
        raise ValueError("Production order entity differs from journal owner")
    prefix = f"production:{order.order_id}:"
    if any(row.movement_id.startswith(prefix) for row in inventory.movements):
        raise ValueError(f"Production order already executed: {order.order_id}")
    cost_events = tuple(conversion_costs)
    if len({row.event_id for row in cost_events}) != len(cost_events):
        raise ValueError("Production cost event IDs must be unique")
    account_map: dict[ProductionCostType, str] = {}
    for key, account_id in (conversion_cost_accounts or {}).items():
        kind = key if isinstance(key, ProductionCostType) else ProductionCostType(key)
        account_map[kind] = account_id
    for event in cost_events:
        if event.order_id != order.order_id or event.entity_id != order.entity_id:
            raise ValueError("Production cost event order/entity mismatch")
        if event.effective_date > order.planned_date:
            raise ValueError("Production cost event cannot post after batch completion date")
        if event.amount.currency != journal.functional_currency:
            raise ValueError("Production cost event currency must equal functional currency")
        account_id = account_map.get(event.cost_type)
        if not account_id:
            raise ValueError(f"Missing credit account mapping for production cost type {event.cost_type.value}")
        account = next((row for row in journal.accounts if row.account_id == account_id), None)
        if account is None or account.normal_balance != NormalBalance.CREDIT:
            raise ValueError("Production cost offset must be an existing credit-normal account")
        if account_id in {inventory_account_id, wip_account_id, finished_goods_account_id}:
            raise ValueError("Production cost offset cannot be a raw inventory, WIP or finished-goods account")

    expected_entries = {f"inventory:{prefix}issue:{row.item_id}" for row in order.components}
    expected_entries.update(f"{prefix}cost:{row.event_id}" for row in cost_events)
    expected_entries.add(f"{prefix}capitalize")
    existing_entries = {row.entry_id for row in journal.entries}
    if expected_entries & existing_entries:
        raise ValueError(f"Production order already journalized: {order.order_id}")
    expected_idempotency = {f"production-consumption:production:{order.order_id}:issue:{row.item_id}" for row in order.components}
    expected_idempotency.update(f"production-cost:{row.event_id}" for row in cost_events)
    expected_idempotency.add(f"production-completion:{order.order_id}")
    if expected_idempotency & {row.idempotency_key for row in journal.entries}:
        raise ValueError(f"Production order idempotency key already used: {order.order_id}")

    required: list[tuple[BOMComponent, Quantity]] = []
    previewed_cost = Decimal("0")
    for component in order.components:
        quantity = Quantity(
            component.quantity_per_output_unit.amount * order.output_quantity.amount,
            component.quantity_per_output_unit.unit,
        )
        available = inventory.available(component.item_id, order.location_id, quantity.unit)
        if available.amount < quantity.amount:
            raise ValueError(
                f"Insufficient component {component.item_id}: required {quantity.amount}, available {available.amount}"
            )
        previewed_cost += inventory.preview_issue_cost(component.item_id, order.location_id, quantity).amount
        required.append((component, quantity))
    # Validate output pool units and zero-cost policy before consuming any input.
    inventory.available(order.product_id, order.location_id, order.output_quantity.unit)
    if previewed_cost <= 0:
        raise ValueError("Zero-cost production batch cannot be capitalized in the monetary journal")

    input_movements = tuple(
        inventory.issue(
            f"production:{order.order_id}:issue:{component.item_id}",
            component.item_id, order.location_id, quantity, order.planned_date,
            f"production-order:{order.order_id}:component:{component.item_id}",
        )
        for component, quantity in required
    )
    direct_material_cost = Money(
        sum((movement.cost.amount for movement in input_movements), Decimal("0")),
        inventory.functional_currency,
    )
    if direct_material_cost.amount != previewed_cost:
        raise ValueError("FIFO issue cost changed between preflight and consumption")
    conversion_cost = Money(
        sum((event.amount.amount for event in cost_events), Decimal("0")),
        inventory.functional_currency,
    )
    capitalized_cost = direct_material_cost + conversion_cost

    output_movement = inventory.receive(
        f"production:{order.order_id}:output",
        f"production:{order.order_id}:lot",
        order.product_id,
        order.location_id,
        order.output_quantity,
        capitalized_cost,
        order.planned_date,
        f"production-order:{order.order_id}:completed-output",
    )

    entries: list[JournalEntry] = []
    for movement in input_movements:
        # InventoryLedger uses movement IDs as deterministic journal identities.
        entry_id = f"inventory:{movement.movement_id}"
        money = movement.cost
        entries.append(JournalEntry(
            entry_id, movement.movement_date, recorded_at, journal.functional_currency,
            (
                JournalLine(f"{entry_id}:dr", wip_account_id, PostingSide.DEBIT,
                    money, money, order.entity_id, movement.source_ref),
                JournalLine(f"{entry_id}:cr", inventory_account_id, PostingSide.CREDIT,
                    money, money, order.entity_id, movement.source_ref),
            ),
            f"production-consumption:{movement.movement_id}",
            f"production-consumption:{movement.movement_id}",
            f"Consume BOM component {movement.item_id} for {order.order_id}",
        ))
    for event in cost_events:
        entry_id = f"production:{order.order_id}:cost:{event.event_id}"
        amount = event.amount
        entries.append(JournalEntry(
            entry_id, event.effective_date, recorded_at, journal.functional_currency,
            (
                JournalLine(f"{entry_id}:dr", wip_account_id, PostingSide.DEBIT,
                    amount, amount, order.entity_id, event.source_ref, evidence_ids=(event.evidence_ref,)),
                JournalLine(f"{entry_id}:cr", account_map[event.cost_type], PostingSide.CREDIT,
                    amount, amount, order.entity_id, event.source_ref, evidence_ids=(event.evidence_ref,)),
            ),
            f"production-cost:{event.event_id}", f"production-cost:{event.event_id}",
            f"Capitalize {event.cost_type.value.lower()} cost for {order.order_id}",
        ))
    completion_id = f"production:{order.order_id}:capitalize"
    entries.append(JournalEntry(
        completion_id, order.planned_date, recorded_at, journal.functional_currency,
        (
            JournalLine(f"{completion_id}:dr", finished_goods_account_id, PostingSide.DEBIT,
                capitalized_cost, capitalized_cost, order.entity_id, output_movement.source_ref),
            JournalLine(f"{completion_id}:cr", wip_account_id, PostingSide.CREDIT,
                capitalized_cost, capitalized_cost, order.entity_id, output_movement.source_ref),
        ),
        f"production-completion:{order.order_id}",
        f"production-completion:{order.order_id}",
        f"Capitalize finished output for {order.order_id}",
    ))
    journal.post_many(entries)
    return ProductionExecution(
        order.order_id, output_movement, input_movements, direct_material_cost,
        conversion_cost, capitalized_cost, order.output_quantity, tuple(x.entry_id for x in entries),
    )



def post_grni_receipt(
    receipt: GoodsReceipt,
    matcher: GRNIMatcher,
    journal: Journal,
    inventory_account_id: str,
    grni_account_id: str,
    entity_id: str,
    recorded_at: datetime,
) -> JournalEntry:
    """Accrue received-but-not-invoiced goods: Dr inventory / Cr GRNI."""
    _aware(recorded_at, "recorded_at")
    po = matcher._orders.get(receipt.po_line_id)
    if po is None or matcher._receipts.get(receipt.receipt_id) != receipt:
        raise ValueError("Receipt must first be accepted by this GRNI matcher")
    if po.entity_id != entity_id or journal.entity_id not in (None, entity_id):
        raise ValueError("GRNI receipt entity mismatch")
    if po.unit_price.currency != journal.functional_currency:
        raise ValueError("GRNI reference posting requires PO currency equal to journal functional currency")
    _account_map(journal, inventory_account_id, AccountType.ASSET, NormalBalance.DEBIT, "Inventory account")
    _account_map(journal, grni_account_id, AccountType.LIABILITY, NormalBalance.CREDIT, "GRNI account")
    amount = Money(receipt.received_quantity.amount * po.unit_price.amount, journal.functional_currency)
    if amount.amount <= 0:
        raise ValueError("Zero-value GRNI receipt cannot be posted")
    entry_id = f"grni:receipt:{receipt.receipt_id}"
    return journal.post(JournalEntry(
        entry_id, receipt.received_date, recorded_at, journal.functional_currency,
        (
            JournalLine(f"{entry_id}:dr", inventory_account_id, PostingSide.DEBIT,
                amount, amount, entity_id, receipt.evidence_ref),
            JournalLine(f"{entry_id}:cr", grni_account_id, PostingSide.CREDIT,
                amount, amount, entity_id, receipt.evidence_ref),
        ),
        f"grni-receipt:{receipt.receipt_id}", f"grni-receipt:{receipt.receipt_id}",
        f"Accrue received goods {receipt.receipt_id}",
    ))


def post_grni_invoice(
    invoice: SupplierInvoiceLine,
    matcher: GRNIMatcher,
    journal: Journal,
    grni_account_id: str,
    accounts_payable_account_id: str,
    entity_id: str,
    recorded_at: datetime,
) -> JournalEntry:
    """Clear matched GRNI into supplier AP: Dr GRNI / Cr accounts payable."""
    _aware(recorded_at, "recorded_at")
    po = matcher._orders.get(invoice.po_line_id)
    if po is None or matcher._invoices.get(invoice.invoice_line_id) != invoice:
        raise ValueError("Invoice must first be accepted by this GRNI matcher")
    if po.entity_id != entity_id or journal.entity_id not in (None, entity_id):
        raise ValueError("GRNI invoice entity mismatch")
    if invoice.amount.currency != journal.functional_currency:
        raise ValueError("GRNI reference posting requires invoice currency equal to journal functional currency")
    _account_map(journal, grni_account_id, AccountType.LIABILITY, NormalBalance.CREDIT, "GRNI account")
    _account_map(journal, accounts_payable_account_id, AccountType.LIABILITY, NormalBalance.CREDIT, "AP account")
    posted_receipts = sum((
        matcher._orders[receipt.po_line_id].unit_price.amount * receipt.received_quantity.amount
        for receipt in matcher.receipts
        if receipt.po_line_id == invoice.po_line_id
        and f"grni:receipt:{receipt.receipt_id}" in {x.entry_id for x in journal.entries}
    ), Decimal("0"))
    posted_invoices = sum((
        row.amount.amount for row in matcher.invoices
        if row.po_line_id == invoice.po_line_id
        and f"grni:invoice:{row.invoice_line_id}" in {x.entry_id for x in journal.entries}
    ), Decimal("0"))
    if invoice.amount.amount > posted_receipts - posted_invoices:
        raise ValueError("Invoice cannot clear more GRNI than has been accrued from posted receipts")
    entry_id = f"grni:invoice:{invoice.invoice_line_id}"
    return journal.post(JournalEntry(
        entry_id, invoice.invoice_date, recorded_at, journal.functional_currency,
        (
            JournalLine(f"{entry_id}:dr", grni_account_id, PostingSide.DEBIT,
                invoice.amount, invoice.amount, entity_id, invoice.source_ref),
            JournalLine(f"{entry_id}:cr", accounts_payable_account_id, PostingSide.CREDIT,
                invoice.amount, invoice.amount, entity_id, invoice.source_ref),
        ),
        f"grni-invoice:{invoice.invoice_line_id}", f"grni-invoice:{invoice.invoice_line_id}",
        f"Reclassify matched GRNI to AP {invoice.invoice_line_id}",
    ))
