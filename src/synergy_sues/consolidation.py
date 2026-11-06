"""Intercompany matching and elimination controls for federated consolidation."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Money


class IntercompanyRecordType(str, Enum):
    SELLER_REVENUE = "SELLER_REVENUE"
    BUYER_EXPENSE = "BUYER_EXPENSE"
    SELLER_RECEIVABLE = "SELLER_RECEIVABLE"
    BUYER_PAYABLE = "BUYER_PAYABLE"
    SELLER_CASH_IN = "SELLER_CASH_IN"
    BUYER_CASH_OUT = "BUYER_CASH_OUT"


@dataclass(frozen=True)
class IntercompanyRecord:
    record_id: str
    transaction_id: str
    entity_id: str
    counterparty_id: str
    record_type: IntercompanyRecordType
    amount: Money
    period_id: str
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.record_id, self.transaction_id, self.entity_id,
                    self.counterparty_id, self.period_id, self.source_ref)):
            raise ValueError("Intercompany record identity and provenance are required")
        if self.entity_id == self.counterparty_id:
            raise ValueError("Intercompany entity and counterparty must differ")
        if not isinstance(self.record_type, IntercompanyRecordType):
            object.__setattr__(self, "record_type", IntercompanyRecordType(self.record_type))
        if self.amount.amount <= 0:
            raise ValueError("Intercompany amount must be positive")


_SELLER_TYPES = {
    IntercompanyRecordType.SELLER_REVENUE,
    IntercompanyRecordType.SELLER_RECEIVABLE,
    IntercompanyRecordType.SELLER_CASH_IN,
}
_BUYER_TYPES = {
    IntercompanyRecordType.BUYER_EXPENSE,
    IntercompanyRecordType.BUYER_PAYABLE,
    IntercompanyRecordType.BUYER_CASH_OUT,
}
_MATCHES = (
    (IntercompanyRecordType.SELLER_REVENUE, IntercompanyRecordType.BUYER_EXPENSE, "P_AND_L"),
    (IntercompanyRecordType.SELLER_RECEIVABLE, IntercompanyRecordType.BUYER_PAYABLE, "BALANCE_SHEET"),
    (IntercompanyRecordType.SELLER_CASH_IN, IntercompanyRecordType.BUYER_CASH_OUT, "CASH_TRANSFER"),
)


def reconcile_intercompany(records: Iterable[IntercompanyRecord]) -> dict:
    """Match reciprocal records; eliminate only the amount supported on both sides.

    Any missing or unequal reciprocal amount remains an explicit exception.
    Different currencies are never netted or translated implicitly.
    """
    rows = list(records)
    ids = [row.record_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate intercompany record_id")

    grouped: dict[str, list[IntercompanyRecord]] = {}
    for row in rows:
        grouped.setdefault(row.transaction_id, []).append(row)

    transaction_results = []
    total_eliminations: dict[str, dict[str, Decimal]] = {}
    exceptions = []

    for transaction_id, tx_rows in sorted(grouped.items()):
        sellers = (
            {row.entity_id for row in tx_rows if row.record_type in _SELLER_TYPES}
            | {row.counterparty_id for row in tx_rows if row.record_type in _BUYER_TYPES}
        )
        buyers = (
            {row.counterparty_id for row in tx_rows if row.record_type in _SELLER_TYPES}
            | {row.entity_id for row in tx_rows if row.record_type in _BUYER_TYPES}
        )
        if len(sellers) != 1 or len(buyers) != 1:
            raise ValueError(f"Transaction {transaction_id} must identify one reciprocal seller/buyer pair")
        seller, buyer = next(iter(sellers)), next(iter(buyers))
        if seller == buyer:
            raise ValueError(f"Transaction {transaction_id} has identical seller and buyer")

        currencies = {row.amount.currency for row in tx_rows}
        if len(currencies) != 1:
            raise ValueError(f"Transaction {transaction_id} mixes currencies without an explicit FX bridge")
        currency = next(iter(currencies))

        for row in tx_rows:
            expected_counterparty = buyer if row.record_type in _SELLER_TYPES else seller
            if row.counterparty_id != expected_counterparty:
                raise ValueError(f"Counterparty mismatch in transaction {transaction_id}: {row.record_id}")

        period_results = []
        transaction_eliminations = {
            "P_AND_L": Decimal("0"),
            "BALANCE_SHEET": Decimal("0"),
            "CASH_TRANSFER": Decimal("0"),
        }
        discrepancies = []
        for period_id in sorted({row.period_id for row in tx_rows}):
            period_rows = [row for row in tx_rows if row.period_id == period_id]
            amounts = {
                record_type: sum(
                    (row.amount.amount for row in period_rows if row.record_type == record_type),
                    Decimal("0"),
                )
                for record_type in IntercompanyRecordType
            }
            period_eliminations = {}
            period_discrepancies = []
            for seller_type, buyer_type, category in _MATCHES:
                seller_amount = amounts[seller_type]
                buyer_amount = amounts[buyer_type]
                matched = min(seller_amount, buyer_amount)
                seller_unmatched = seller_amount - matched
                buyer_unmatched = buyer_amount - matched
                period_eliminations[category] = matched
                transaction_eliminations[category] += matched
                if seller_unmatched or buyer_unmatched:
                    discrepancy = {
                        "period_id": period_id,
                        "category": category,
                        "seller_record_type": seller_type.value,
                        "buyer_record_type": buyer_type.value,
                        "seller_amount": str(seller_amount),
                        "buyer_amount": str(buyer_amount),
                        "eliminated_amount": str(matched),
                        "seller_unmatched": str(seller_unmatched),
                        "buyer_unmatched": str(buyer_unmatched),
                    }
                    period_discrepancies.append(discrepancy)
                    discrepancies.append(discrepancy)
                    exceptions.append({"transaction_id": transaction_id, **discrepancy})
            currency_totals = total_eliminations.setdefault(currency, {})
            for category, amount in period_eliminations.items():
                currency_totals[category] = currency_totals.get(category, Decimal("0")) + amount
            period_results.append({
                "period_id": period_id,
                "eliminations": {category: str(amount) for category, amount in period_eliminations.items()},
                "discrepancies": period_discrepancies,
            })

        transaction_results.append({
            "transaction_id": transaction_id,
            "seller_id": seller,
            "buyer_id": buyer,
            "currency": currency,
            "eliminations": {category: str(amount) for category, amount in transaction_eliminations.items()},
            "periods": period_results,
            "discrepancies": discrepancies,
            "fully_matched": not discrepancies,
        })

    return {
        "transactions": transaction_results,
        "elimination_totals_by_currency": {
            currency: {category: str(amount) for category, amount in totals.items()}
            for currency, totals in total_eliminations.items()
        },
        "exceptions": exceptions,
        "complete": not exceptions,
        "unmatched_amounts_are_not_silently_eliminated": True,
        "cross_currency_netting_performed": False,
    }
