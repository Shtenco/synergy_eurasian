"""Intercompany matching and elimination controls for federated consolidation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from enum import Enum
from typing import Iterable

from .contracts import Money, _aware
from .journal import Journal, JournalEntry, JournalLine, PostingSide


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
    account_id: str = ""

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
            raise ValueError(f"Counterparty mismatch or ambiguous seller/buyer pair in transaction {transaction_id}")
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



def post_intercompany_eliminations(
    journal: Journal,
    records: Iterable[IntercompanyRecord],
    effective_dates_by_period: dict[str, date],
    recorded_at: datetime,
    source_event_id_prefix: str,
    idempotency_prefix: str,
) -> dict:
    """Post balanced consolidation entries for matched P&L and AR/AP amounts.

    Cash transfer eliminations are reported for consolidated cash-flow reporting;
    they do not create a journal entry because cash remains in member bank accounts.
    V1 requires transaction currency to equal the consolidation journal's
    functional currency. Translation and CTA belong to the next consolidation layer.
    """
    _aware(recorded_at, "recorded_at")
    rows = list(records)
    result = reconcile_intercompany(rows)
    by_transaction_period: dict[tuple[str, str], list[IntercompanyRecord]] = {}
    for row in rows:
        by_transaction_period.setdefault((row.transaction_id, row.period_id), []).append(row)

    posted = []
    cash_eliminations: dict[str, Decimal] = {}
    for tx in result["transactions"]:
        for period in tx["periods"]:
            period_id = period["period_id"]
            period_rows = by_transaction_period[(tx["transaction_id"], period_id)]
            currency = tx["currency"]
            if currency != journal.functional_currency:
                raise ValueError("Intercompany elimination currency must match journal functional currency")
            for category, debit_type, credit_type in (
                ("P_AND_L", IntercompanyRecordType.SELLER_REVENUE, IntercompanyRecordType.BUYER_EXPENSE),
                ("BALANCE_SHEET", IntercompanyRecordType.BUYER_PAYABLE, IntercompanyRecordType.SELLER_RECEIVABLE),
            ):
                amount = Decimal(period["eliminations"][category])
                if amount == 0:
                    continue
                debit_rows = [row for row in period_rows if row.record_type == debit_type]
                credit_rows = [row for row in period_rows if row.record_type == credit_type]
                debit_accounts = {row.account_id for row in debit_rows}
                credit_accounts = {row.account_id for row in credit_rows}
                if len(debit_accounts) != 1 or "" in debit_accounts:
                    raise ValueError(f"One explicit debit account_id is required for {category}")
                if len(credit_accounts) != 1 or "" in credit_accounts:
                    raise ValueError(f"One explicit credit account_id is required for {category}")
                identity = f"{tx['transaction_id']}|{period_id}|{category}"
                suffix = sha256(identity.encode("utf-8")).hexdigest()[:20]
                entry_id = f"elim-{suffix}"
                source_ref = f"intercompany:{tx['transaction_id']}:{period_id}:{category}"
                money = Money(amount, currency)
                entry = JournalEntry(
                    entry_id=entry_id,
                    effective_date=effective_dates_by_period[period_id],
                    recorded_at=recorded_at,
                    functional_currency=journal.functional_currency,
                    lines=(
                        JournalLine(
                            line_id=f"{entry_id}:debit",
                            account_id=next(iter(debit_accounts)),
                            side=PostingSide.DEBIT,
                            amount=money,
                            functional_amount=money,
                            entity_id="CONSOLIDATED",
                            source_ref=source_ref,
                            counterparty_id=tx["buyer_id"],
                        ),
                        JournalLine(
                            line_id=f"{entry_id}:credit",
                            account_id=next(iter(credit_accounts)),
                            side=PostingSide.CREDIT,
                            amount=money,
                            functional_amount=money,
                            entity_id="CONSOLIDATED",
                            source_ref=source_ref,
                            counterparty_id=tx["seller_id"],
                        ),
                    ),
                    source_event_id=f"{source_event_id_prefix}:{suffix}",
                    idempotency_key=f"{idempotency_prefix}:{suffix}",
                    description=f"Intercompany {category} elimination for {tx['transaction_id']}",
                )
                journal.post(entry)
                posted.append(entry_id)

            cash_amount = Decimal(period["eliminations"]["CASH_TRANSFER"])
            if cash_amount:
                cash_eliminations[currency] = cash_eliminations.get(currency, Decimal("0")) + cash_amount

    return {
        "posted_elimination_entry_ids": posted,
        "posted_entry_count": len(posted),
        "cash_flow_eliminations_by_currency": {k: str(v) for k, v in cash_eliminations.items()},
        "cash_transfers_posted_to_general_ledger": False,
        "currency_translation_supported": False,
        "source_reconciliation_complete": result["complete"],
    }
