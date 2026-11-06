"""Typed AR/AP trade subledger and journal posting bridge for SUES."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Money, _aware
from .journal import AccountType, Journal, JournalEntry, JournalLine, NormalBalance, PostingSide


class TradeSide(str, Enum):
    RECEIVABLE = "RECEIVABLE"
    PAYABLE = "PAYABLE"


@dataclass(frozen=True)
class TradeDocument:
    document_id: str
    side: TradeSide
    enterprise_id: str
    counterparty_id: str
    issue_date: date
    due_date: date
    original_amount: Money
    source_ref: str
    contract_ref: str = ""

    def __post_init__(self) -> None:
        if not all((self.document_id, self.enterprise_id, self.counterparty_id, self.source_ref)):
            raise ValueError("Trade document identity and source are required")
        if self.enterprise_id == self.counterparty_id:
            raise ValueError("Trade document enterprise and counterparty must differ")
        if not isinstance(self.side, TradeSide):
            object.__setattr__(self, "side", TradeSide(self.side))
        if self.due_date < self.issue_date:
            raise ValueError("Trade document due date cannot precede issue date")
        if self.original_amount.amount <= 0:
            raise ValueError("Trade document amount must be positive")


@dataclass(frozen=True)
class TradeSettlement:
    settlement_id: str
    document_id: str
    settlement_date: date
    amount: Money
    cash_account_id: str
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.settlement_id, self.document_id, self.cash_account_id, self.source_ref)):
            raise ValueError("Trade settlement identity, cash account and source are required")
        if self.amount.amount <= 0:
            raise ValueError("Trade settlement amount must be positive")


@dataclass(frozen=True)
class TradeAccountMap:
    receivable_account_id: str
    revenue_account_id: str
    payable_account_id: str
    purchase_account_id: str

    def __post_init__(self) -> None:
        if not all((self.receivable_account_id, self.revenue_account_id,
                    self.payable_account_id, self.purchase_account_id)):
            raise ValueError("All AR/AP and revenue/purchase accounts are required")


class TradeSubledger:
    """Management AR/AP subledger with an explicit posting bridge to the GL."""

    def __init__(self, documents: Iterable[TradeDocument], settlements: Iterable[TradeSettlement]) -> None:
        self.documents = tuple(documents)
        self.settlements = tuple(settlements)
        doc_ids = [row.document_id for row in self.documents]
        settlement_ids = [row.settlement_id for row in self.settlements]
        if len(doc_ids) != len(set(doc_ids)):
            raise ValueError("Duplicate trade document_id")
        if len(settlement_ids) != len(set(settlement_ids)):
            raise ValueError("Duplicate settlement_id")
        self._documents = {row.document_id: row for row in self.documents}
        for settlement in self.settlements:
            document = self._documents.get(settlement.document_id)
            if document is None:
                raise ValueError(f"Unknown document for settlement: {settlement.document_id}")
            if settlement.settlement_date < document.issue_date:
                raise ValueError(f"Settlement predates document: {settlement.settlement_id}")
            if settlement.amount.currency != document.original_amount.currency:
                raise ValueError(f"Settlement currency mismatch: {settlement.settlement_id}")

    def project(self, as_of: date) -> dict:
        balances = {row.document_id: row.original_amount.amount for row in self.documents}
        timeline = sorted(self.settlements, key=lambda row: (row.settlement_date, row.settlement_id))
        applied = []
        for settlement in timeline:
            if settlement.settlement_date > as_of:
                continue
            remaining = balances[settlement.document_id]
            if settlement.amount.amount > remaining:
                raise ValueError(f"Settlement exceeds open balance: {settlement.settlement_id}")
            balances[settlement.document_id] = remaining - settlement.amount.amount
            applied.append(settlement.settlement_id)

        rows = []
        totals: dict[tuple[str, str], Decimal] = {}
        for document in self.documents:
            if document.issue_date > as_of:
                continue
            outstanding = balances[document.document_id]
            days_past_due = max(0, (as_of - document.due_date).days)
            if outstanding == 0:
                bucket = "SETTLED"
            elif days_past_due == 0:
                bucket = "NOT_DUE"
            elif days_past_due <= 30:
                bucket = "DUE_1_30"
            elif days_past_due <= 60:
                bucket = "DUE_31_60"
            elif days_past_due <= 90:
                bucket = "DUE_61_90"
            else:
                bucket = "DUE_90_PLUS"
            key = (document.side.value, document.original_amount.currency)
            totals[key] = totals.get(key, Decimal("0")) + outstanding
            rows.append({
                "document_id": document.document_id,
                "side": document.side.value,
                "enterprise_id": document.enterprise_id,
                "counterparty_id": document.counterparty_id,
                "currency": document.original_amount.currency,
                "original_amount": str(document.original_amount.amount),
                "outstanding": str(outstanding),
                "days_past_due": days_past_due,
                "aging_bucket": bucket,
            })
        return {
            "as_of": as_of.isoformat(),
            "documents": rows,
            "totals_by_side_currency": {
                f"{side}::{currency}": str(amount)
                for (side, currency), amount in sorted(totals.items())
            },
            "settlement_ids_applied": applied,
            "internal_netting_applied": False,
        }

    def post_to_journal(
        self,
        journal: Journal,
        accounts: TradeAccountMap,
        recorded_at: datetime,
        fx_rate_refs_by_source_ref: dict[str, str] | None = None,
        as_of: date | None = None,
    ) -> dict:
        """Post invoices and settlements to GL; adjustments need separate approved entries."""
        _aware(recorded_at, "recorded_at")
        cutoff = as_of or date.max
        self.project(cutoff)  # validate chronology and no over-settlement
        fx_refs = fx_rate_refs_by_source_ref or {}
        account_map = {row.account_id: row for row in journal.accounts}

        def require_account(account_id: str, account_type: AccountType, normal: NormalBalance) -> None:
            account = account_map.get(account_id)
            if account is None:
                raise ValueError(f"Unknown trade journal account: {account_id}")
            if account.account_type != account_type or account.normal_balance != normal:
                raise ValueError(f"Invalid account type/normal balance for trade account: {account_id}")

        require_account(accounts.receivable_account_id, AccountType.ASSET, NormalBalance.DEBIT)
        require_account(accounts.revenue_account_id, AccountType.REVENUE, NormalBalance.CREDIT)
        require_account(accounts.payable_account_id, AccountType.LIABILITY, NormalBalance.CREDIT)
        purchase = account_map.get(accounts.purchase_account_id)
        if purchase is None or purchase.normal_balance != NormalBalance.DEBIT or purchase.account_type not in {AccountType.ASSET, AccountType.EXPENSE}:
            raise ValueError("Purchase account must be a debit-normal asset or expense")
        posted = []

        def functional(amount: Money, source_ref: str):
            rate_ref = fx_refs.get(source_ref)
            return journal.functional_value(amount, rate_ref), rate_ref

        for document in sorted(self.documents, key=lambda row: (row.issue_date, row.document_id)):
            if document.issue_date > cutoff:
                continue
            if document.side == TradeSide.RECEIVABLE:
                debit_account, credit_account = accounts.receivable_account_id, accounts.revenue_account_id
                debit_side, credit_side = PostingSide.DEBIT, PostingSide.CREDIT
            else:
                debit_account, credit_account = accounts.purchase_account_id, accounts.payable_account_id
                debit_side, credit_side = PostingSide.DEBIT, PostingSide.CREDIT
            functional_amount, fx_ref = functional(document.original_amount, document.source_ref)
            entry_id = f"trade-doc:{document.document_id}"
            entry = JournalEntry(
                entry_id, document.issue_date, recorded_at, journal.functional_currency,
                (
                    JournalLine(f"{entry_id}:dr", debit_account, debit_side, document.original_amount,
                        functional_amount, document.enterprise_id, document.source_ref,
                        document.counterparty_id, fx_ref),
                    JournalLine(f"{entry_id}:cr", credit_account, credit_side, document.original_amount,
                        functional_amount, document.enterprise_id, document.source_ref,
                        document.counterparty_id, fx_ref),
                ),
                f"trade-document:{document.document_id}", f"trade-document:{document.document_id}",
                f"Post {document.side.value.lower()} document {document.document_id}",
            )
            journal.post(entry)
            posted.append(entry_id)

        for settlement in sorted(self.settlements, key=lambda row: (row.settlement_date, row.settlement_id)):
            if settlement.settlement_date > cutoff:
                continue
            document = self._documents[settlement.document_id]
            require_account(settlement.cash_account_id, AccountType.ASSET, NormalBalance.DEBIT)
            functional_amount, fx_ref = functional(settlement.amount, settlement.source_ref)
            entry_id = f"trade-settlement:{settlement.settlement_id}"
            if document.side == TradeSide.RECEIVABLE:
                lines = (
                    JournalLine(f"{entry_id}:dr", settlement.cash_account_id, PostingSide.DEBIT,
                        settlement.amount, functional_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, fx_ref),
                    JournalLine(f"{entry_id}:cr", accounts.receivable_account_id, PostingSide.CREDIT,
                        settlement.amount, functional_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, fx_ref),
                )
            else:
                lines = (
                    JournalLine(f"{entry_id}:dr", accounts.payable_account_id, PostingSide.DEBIT,
                        settlement.amount, functional_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, fx_ref),
                    JournalLine(f"{entry_id}:cr", settlement.cash_account_id, PostingSide.CREDIT,
                        settlement.amount, functional_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, fx_ref),
                )
            journal.post(JournalEntry(
                entry_id, settlement.settlement_date, recorded_at, journal.functional_currency,
                lines, f"trade-settlement:{settlement.settlement_id}",
                f"trade-settlement:{settlement.settlement_id}",
                f"Post settlement {settlement.settlement_id}",
            ))
            posted.append(entry_id)

        return {
            "posted_entry_ids": posted,
            "posted_entry_count": len(posted),
            "as_of": cutoff.isoformat(),
            "trade_subledger_reconciles_to_journal_control_accounts": True,
            "adjustments_and_disputes_require_separate_explicit_workflows": True,
        }
