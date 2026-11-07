"""FIFO inventory subledger with typed physical quantities and functional-currency cost."""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Money, Quantity, _aware, _calendar_date
from .journal import AccountType, Journal, JournalEntry, JournalLine, NormalBalance, PostingSide


class InventoryMovementType(str, Enum):
    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    WRITEOFF = "WRITEOFF"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


@dataclass
class _InventoryLot:
    lot_id: str
    item_id: str
    location_id: str
    remaining_quantity: Quantity
    remaining_cost: Money
    received_date: date
    source_ref: str


@dataclass(frozen=True)
class InventoryLotAllocation:
    lot_id: str
    quantity: Quantity
    cost: Money
    source_ref: str
    destination_lot_id: str | None = None

    def __post_init__(self) -> None:
        if not self.lot_id or not self.source_ref:
            raise ValueError("Inventory lot allocation requires lot and source identity")
        if self.quantity.amount <= 0 or self.cost.amount < 0:
            raise ValueError("Inventory lot allocation quantity/cost is invalid")


@dataclass(frozen=True)
class InventoryMovement:
    movement_id: str
    movement_type: InventoryMovementType
    item_id: str
    location_id: str
    quantity: Quantity
    cost: Money
    movement_date: date
    source_ref: str
    destination_location_id: str | None = None
    lot_id: str | None = None
    lot_allocations: tuple[InventoryLotAllocation, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.movement_id, self.item_id, self.location_id, self.source_ref)):
            raise ValueError("Inventory movement identity and source are required")
        if not isinstance(self.movement_type, InventoryMovementType):
            object.__setattr__(self, "movement_type", InventoryMovementType(self.movement_type))
        _calendar_date(self.movement_date, "inventory movement date")
        if self.quantity.amount <= 0:
            raise ValueError("Inventory movement quantity must be positive")
        if self.cost.amount < 0:
            raise ValueError("Inventory movement cost must be non-negative")
        if not isinstance(self.lot_allocations, tuple):
            object.__setattr__(self, "lot_allocations", tuple(self.lot_allocations))
        if self.movement_type == InventoryMovementType.RECEIPT and not self.lot_id:
            raise ValueError("Inventory receipt movement requires a lot_id")
        if self.movement_type in {InventoryMovementType.TRANSFER_IN, InventoryMovementType.TRANSFER_OUT}:
            if not self.destination_location_id:
                raise ValueError("Inventory transfer movement requires the opposite location")
        elif self.destination_location_id is not None:
            raise ValueError("Only transfer movements may specify a destination location")
        if self.movement_type != InventoryMovementType.RECEIPT and not self.lot_allocations:
            raise ValueError("Inventory consumption/transfer movement requires lot allocations")
        if self.movement_type in {InventoryMovementType.TRANSFER_IN, InventoryMovementType.TRANSFER_OUT}:
            if any(row.destination_lot_id is None for row in self.lot_allocations):
                raise ValueError("Inventory transfer allocations require destination lot IDs")
        elif any(row.destination_lot_id is not None for row in self.lot_allocations):
            raise ValueError("Only transfer movements may include destination lot IDs")
        if self.lot_allocations:
            allocated_quantity = sum((row.quantity.amount for row in self.lot_allocations), Decimal("0"))
            allocated_cost = sum((row.cost.amount for row in self.lot_allocations), Decimal("0"))
            if allocated_quantity != self.quantity.amount or allocated_cost != self.cost.amount:
                raise ValueError("Inventory lot allocations must reconcile to movement quantity and cost")
            if any(row.quantity.unit != self.quantity.unit or row.cost.currency != self.cost.currency
                   for row in self.lot_allocations):
                raise ValueError("Inventory lot allocation unit/currency mismatch")


class InventoryLedger:
    """FIFO inventory quantity/value subledger; costs are stored in entity functional currency."""

    def __init__(self, functional_currency: str, entity_id: str | None = None) -> None:
        self.functional_currency = Money("0", functional_currency).currency
        if entity_id is not None and (not isinstance(entity_id, str) or not entity_id.strip()):
            raise ValueError("inventory ledger entity_id must be a non-empty string")
        self.entity_id = entity_id
        self._lots: dict[tuple[str, str], list[_InventoryLot]] = {}
        self._pool_units: dict[tuple[str, str], str] = {}
        self._lot_ids: set[str] = set()
        self._movements: dict[str, InventoryMovement] = {}
        self._journal_posted_movements: set[str] = set()

    @property
    def movements(self) -> tuple[InventoryMovement, ...]:
        return tuple(self._movements.values())

    def _snapshot(self):
        """Capture the complete in-memory subledger state for a compound operation."""
        return deepcopy((
            self._lots, self._pool_units, self._lot_ids, self._movements,
            self._journal_posted_movements,
        ))

    def _restore(self, snapshot) -> None:
        (
            self._lots, self._pool_units, self._lot_ids, self._movements,
            self._journal_posted_movements,
        ) = deepcopy(snapshot)

    def _mark_journal_posted(self, movement_ids: Iterable[str], entity_id: str) -> None:
        if self.entity_id is None or self.entity_id != entity_id:
            raise ValueError("Inventory ledger entity ownership mismatch")
        ids = tuple(movement_ids)
        if any(movement_id not in self._movements for movement_id in ids):
            raise ValueError("Cannot journalize an unknown inventory movement")
        if any(movement_id in self._journal_posted_movements for movement_id in ids):
            raise ValueError("Inventory movement has already been journalized")
        self._journal_posted_movements.update(ids)

    def _check_pool(self, item_id: str, location_id: str, unit: str) -> tuple[str, str]:
        key = (item_id, location_id)
        old_unit = self._pool_units.get(key)
        if old_unit is not None and old_unit != unit:
            raise ValueError("Inventory item/location pool cannot mix units")
        self._pool_units[key] = unit
        return key

    def _add_movement(self, movement: InventoryMovement) -> InventoryMovement:
        if movement.movement_id in self._movements:
            raise ValueError(f"Duplicate inventory movement_id: {movement.movement_id}")
        if movement.cost.currency != self.functional_currency:
            raise ValueError("Inventory cost must be in entity functional currency")
        self._movements[movement.movement_id] = movement
        return movement

    def receive(
        self,
        receipt_id: str,
        lot_id: str,
        item_id: str,
        location_id: str,
        quantity: Quantity,
        functional_cost: Money,
        received_date: date,
        source_ref: str,
    ) -> InventoryMovement:
        if not all((receipt_id, lot_id, item_id, location_id, source_ref)):
            raise ValueError("Inventory receipt identity and source are required")
        if receipt_id in self._movements:
            raise ValueError(f"Duplicate inventory movement_id: {receipt_id}")
        if lot_id in self._lot_ids:
            raise ValueError(f"Duplicate inventory lot_id: {lot_id}")
        if quantity.amount <= 0:
            raise ValueError("Inventory receipt quantity must be positive")
        if functional_cost.currency != self.functional_currency or functional_cost.amount < 0:
            raise ValueError("Inventory receipt cost must be non-negative and in functional currency")
        _calendar_date(received_date, "received_date")
        movement = InventoryMovement(
            receipt_id, InventoryMovementType.RECEIPT, item_id, location_id,
            quantity, functional_cost, received_date, source_ref, lot_id=lot_id,
        )
        key = self._check_pool(item_id, location_id, quantity.unit)
        lot = _InventoryLot(lot_id, item_id, location_id, quantity, functional_cost, received_date, source_ref)
        self._lots.setdefault(key, []).append(lot)
        self._lots[key].sort(key=lambda x: (x.received_date, x.lot_id))
        self._lot_ids.add(lot_id)
        return self._add_movement(movement)

    def available(self, item_id: str, location_id: str, unit: str) -> Quantity:
        key = self._check_pool(item_id, location_id, unit)
        amount = sum((lot.remaining_quantity.amount for lot in self._lots.get(key, [])), Decimal("0"))
        return Quantity(amount, unit)

    def preview_issue_cost(
        self, item_id: str, location_id: str, quantity: Quantity,
        as_of_date: date | None = None,
    ) -> Money:
        """Return FIFO issue cost using only lots received on/before the issue date."""
        if as_of_date is not None:
            _calendar_date(as_of_date, "inventory valuation date")
        key = self._check_pool(item_id, location_id, quantity.unit)
        lots = [
            lot for lot in self._lots.get(key, [])
            if as_of_date is None or lot.received_date <= as_of_date
        ]
        available = sum((lot.remaining_quantity.amount for lot in lots), Decimal("0"))
        if quantity.amount <= 0 or available < quantity.amount:
            raise ValueError(f"Insufficient inventory: requested {quantity.amount}, available {available}")
        remaining = quantity.amount
        total_cost = Decimal("0")
        for lot in lots:
            if remaining <= 0:
                break
            lot_qty = lot.remaining_quantity.amount
            if lot_qty <= 0:
                continue
            take = min(remaining, lot_qty)
            take_cost = lot.remaining_cost.amount if take == lot_qty else lot.remaining_cost.amount * take / lot_qty
            total_cost += take_cost
            remaining -= take
        return Money(total_cost, self.functional_currency)

    def _consume_fifo(
        self, item_id: str, location_id: str, quantity: Quantity,
        as_of_date: date | None = None,
    ) -> list[tuple[Quantity, Money, _InventoryLot]]:
        if as_of_date is not None:
            _calendar_date(as_of_date, "inventory consumption date")
        key = self._check_pool(item_id, location_id, quantity.unit)
        lots = [
            lot for lot in self._lots.get(key, [])
            if as_of_date is None or lot.received_date <= as_of_date
        ]
        available = sum((lot.remaining_quantity.amount for lot in lots), Decimal("0"))
        if available < quantity.amount:
            raise ValueError(f"Insufficient inventory: requested {quantity.amount}, available {available}")
        remaining = quantity.amount
        consumed = []
        for lot in lots:
            if remaining <= 0:
                break
            lot_qty = lot.remaining_quantity.amount
            if lot_qty <= 0:
                continue
            take = min(remaining, lot_qty)
            if take == lot_qty:
                take_cost = lot.remaining_cost.amount
            else:
                take_cost = lot.remaining_cost.amount * take / lot_qty
            take_quantity = Quantity(take, quantity.unit)
            take_money = Money(take_cost, self.functional_currency)
            lot.remaining_quantity = Quantity(lot_qty - take, quantity.unit)
            lot.remaining_cost = Money(lot.remaining_cost.amount - take_cost, self.functional_currency)
            consumed.append((take_quantity, take_money, lot))
            remaining -= take
        return consumed

    def issue(
        self,
        issue_id: str,
        item_id: str,
        location_id: str,
        quantity: Quantity,
        issue_date: date,
        source_ref: str,
    ) -> InventoryMovement:
        if not all((issue_id, item_id, location_id, source_ref)):
            raise ValueError("Inventory issue identity and source are required")
        _calendar_date(issue_date, "inventory issue date")
        if quantity.amount <= 0:
            raise ValueError("Inventory issue quantity must be positive")
        if issue_id in self._movements:
            raise ValueError(f"Duplicate inventory movement_id: {issue_id}")
        consumed = self._consume_fifo(item_id, location_id, quantity, issue_date)
        total_cost = sum((money.amount for _, money, _ in consumed), Decimal("0"))
        lot_allocations = tuple(
            InventoryLotAllocation(lot.lot_id, taken_quantity, taken_cost, lot.source_ref)
            for taken_quantity, taken_cost, lot in consumed
        )
        return self._add_movement(InventoryMovement(
            issue_id, InventoryMovementType.ISSUE, item_id, location_id,
            quantity, Money(total_cost, self.functional_currency), issue_date, source_ref,
            lot_allocations=lot_allocations,
        ))

    def writeoff(
        self,
        writeoff_id: str,
        item_id: str,
        location_id: str,
        quantity: Quantity,
        writeoff_date: date,
        source_ref: str,
    ) -> InventoryMovement:
        if not all((writeoff_id, item_id, location_id, source_ref)):
            raise ValueError("Inventory writeoff identity and source are required")
        _calendar_date(writeoff_date, "inventory writeoff date")
        if quantity.amount <= 0:
            raise ValueError("Inventory writeoff quantity must be positive")
        if writeoff_id in self._movements:
            raise ValueError(f"Duplicate inventory movement_id: {writeoff_id}")
        consumed = self._consume_fifo(item_id, location_id, quantity, writeoff_date)
        total_cost = sum((money.amount for _, money, _ in consumed), Decimal("0"))
        lot_allocations = tuple(
            InventoryLotAllocation(lot.lot_id, taken_quantity, taken_cost, lot.source_ref)
            for taken_quantity, taken_cost, lot in consumed
        )
        return self._add_movement(InventoryMovement(
            writeoff_id, InventoryMovementType.WRITEOFF, item_id, location_id,
            quantity, Money(total_cost, self.functional_currency), writeoff_date, source_ref,
            lot_allocations=lot_allocations,
        ))

    def transfer(
        self,
        transfer_id: str,
        item_id: str,
        source_location_id: str,
        destination_location_id: str,
        quantity: Quantity,
        transfer_date: date,
        source_ref: str,
    ) -> tuple[InventoryMovement, InventoryMovement]:
        if not all((transfer_id, item_id, source_location_id, destination_location_id, source_ref)):
            raise ValueError("Inventory transfer identity and endpoints are required")
        if source_location_id == destination_location_id:
            raise ValueError("Inventory transfer locations must differ")
        _calendar_date(transfer_date, "inventory transfer date")
        if quantity.amount <= 0:
            raise ValueError("Inventory transfer quantity must be positive")
        out_id, in_id = f"{transfer_id}:OUT", f"{transfer_id}:IN"
        if out_id in self._movements or in_id in self._movements:
            raise ValueError(f"Duplicate inventory transfer_id: {transfer_id}")
        # Preflight all source lots and destination lot IDs before mutating stock.
        destination_key = self._check_pool(item_id, destination_location_id, quantity.unit)
        source_key = self._check_pool(item_id, source_location_id, quantity.unit)
        source_lots = [
            lot for lot in self._lots.get(source_key, [])
            if lot.received_date <= transfer_date
        ]
        available = sum((lot.remaining_quantity.amount for lot in source_lots), Decimal("0"))
        if available < quantity.amount:
            raise ValueError(f"Insufficient inventory: requested {quantity.amount}, available {available}")
        remaining_to_transfer = quantity.amount
        lots_needed = 0
        for lot in source_lots:
            if remaining_to_transfer <= 0:
                break
            if lot.remaining_quantity.amount <= 0:
                continue
            lots_needed += 1
            remaining_to_transfer -= min(remaining_to_transfer, lot.remaining_quantity.amount)
        candidate_lot_ids = [f"{transfer_id}:LOT:{index}" for index in range(1, lots_needed + 1)]
        if any(lot_id in self._lot_ids for lot_id in candidate_lot_ids):
            raise ValueError(f"Duplicate destination lot ID for transfer: {transfer_id}")
        source_consumed = self._consume_fifo(item_id, source_location_id, quantity, transfer_date)
        total_cost = sum((money.amount for _, money, _ in source_consumed), Decimal("0"))
        transfer_allocations = []
        for index, (taken_quantity, taken_cost, source_lot) in enumerate(source_consumed, start=1):
            new_lot_id = f"{transfer_id}:LOT:{index}"
            if new_lot_id in self._lot_ids:
                raise ValueError(f"Duplicate inventory lot_id: {new_lot_id}")
            new_lot = _InventoryLot(
                new_lot_id, item_id, destination_location_id, taken_quantity,
                taken_cost, transfer_date, f"transfer:{transfer_id}:{source_lot.lot_id}",
            )
            self._lots.setdefault(destination_key, []).append(new_lot)
            self._lot_ids.add(new_lot_id)
            transfer_allocations.append(InventoryLotAllocation(
                source_lot.lot_id, taken_quantity, taken_cost, source_lot.source_ref, new_lot_id,
            ))
        self._lots[destination_key].sort(key=lambda x: (x.received_date, x.lot_id))
        out_move = self._add_movement(InventoryMovement(
            out_id, InventoryMovementType.TRANSFER_OUT, item_id, source_location_id,
            quantity, Money(total_cost, self.functional_currency), transfer_date, source_ref,
            destination_location_id=destination_location_id,
            lot_allocations=tuple(transfer_allocations),
        ))
        in_move = self._add_movement(InventoryMovement(
            in_id, InventoryMovementType.TRANSFER_IN, item_id, destination_location_id,
            quantity, Money(total_cost, self.functional_currency), transfer_date, source_ref,
            destination_location_id=source_location_id,
            lot_allocations=tuple(transfer_allocations),
        ))
        return out_move, in_move

    def summary(self) -> dict:
        rows = []
        for (item_id, location_id), lots in sorted(self._lots.items()):
            quantity = sum((lot.remaining_quantity.amount for lot in lots), Decimal("0"))
            cost = sum((lot.remaining_cost.amount for lot in lots), Decimal("0"))
            unit = self._pool_units[(item_id, location_id)]
            rows.append({
                "item_id": item_id,
                "location_id": location_id,
                "quantity": str(quantity),
                "unit": unit,
                "inventory_cost": str(cost),
                "currency": self.functional_currency,
                "lot_count": sum(lot.remaining_quantity.amount > 0 for lot in lots),
            })
        return {"functional_currency": self.functional_currency, "pools": rows}

    def post_to_journal(
        self,
        movement_id: str,
        journal: Journal,
        inventory_account_id: str,
        offset_account_id: str,
        entity_id: str,
        recorded_at: datetime,
    ) -> JournalEntry | None:
        movement = self._movements.get(movement_id)
        if movement is None:
            raise ValueError(f"Unknown inventory movement: {movement_id}")
        if movement.movement_type in {InventoryMovementType.TRANSFER_IN, InventoryMovementType.TRANSFER_OUT}:
            return None
        if self.entity_id is None:
            raise ValueError("Inventory ledger must be bound to an entity before GL posting")
        if entity_id != self.entity_id or journal.entity_id not in (None, self.entity_id):
            raise ValueError("Inventory ledger, journal and posting entity ownership mismatch")
        if movement_id in self._journal_posted_movements:
            raise ValueError(f"Inventory movement already journalized: {movement_id}")
        _aware(recorded_at, "recorded_at")
        if journal.functional_currency != self.functional_currency:
            raise ValueError("Inventory and journal functional currencies must match")
        accounts = {row.account_id: row for row in journal.accounts}
        inventory_account = accounts.get(inventory_account_id)
        if inventory_account is None or inventory_account.account_type != AccountType.ASSET or inventory_account.normal_balance != NormalBalance.DEBIT:
            raise ValueError("Inventory account must be a debit-normal asset account")
        if offset_account_id not in accounts or offset_account_id == inventory_account_id:
            raise ValueError("Inventory offset account must exist and differ from inventory account")
        if movement.cost.amount <= 0:
            raise ValueError("Zero-cost inventory movement cannot create a monetary journal entry")
        money = movement.cost
        entry_id = f"inventory:{movement.movement_id}"
        if movement.movement_type == InventoryMovementType.RECEIPT:
            lines = (
                JournalLine(f"{entry_id}:dr", inventory_account_id, PostingSide.DEBIT,
                    money, money, entity_id, movement.source_ref),
                JournalLine(f"{entry_id}:cr", offset_account_id, PostingSide.CREDIT,
                    money, money, entity_id, movement.source_ref),
            )
        else:
            lines = (
                JournalLine(f"{entry_id}:dr", offset_account_id, PostingSide.DEBIT,
                    money, money, entity_id, movement.source_ref),
                JournalLine(f"{entry_id}:cr", inventory_account_id, PostingSide.CREDIT,
                    money, money, entity_id, movement.source_ref),
            )
        posted = journal.post(JournalEntry(
            entry_id, movement.movement_date, recorded_at, journal.functional_currency,
            lines, f"inventory-movement:{movement.movement_id}",
            f"inventory-movement:{movement.movement_id}",
            f"Post inventory {movement.movement_type.value.lower()} {movement.movement_id}",
        ))
        self._journal_posted_movements.add(movement_id)
        return posted
