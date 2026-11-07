"""Typed AR/AP trade subledger and journal posting bridge for SUES."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Money, _aware, _calendar_date
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
        _calendar_date(self.issue_date, "trade document issue_date")
        _calendar_date(self.due_date, "trade document due_date")
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
        _calendar_date(self.settlement_date, "trade settlement date")
        if self.amount.amount <= 0:
            raise ValueError("Trade settlement amount must be positive")


@dataclass(frozen=True)
class TradeAccountMap:
    receivable_account_id: str
    revenue_account_id: str
    payable_account_id: str
    purchase_account_id: str
    realized_fx_gain_account_id: str | None = None
    realized_fx_loss_account_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.receivable_account_id, self.revenue_account_id,
                    self.payable_account_id, self.purchase_account_id)):
            raise ValueError("All AR/AP and revenue/purchase accounts are required")
        optional_accounts = [
            x for x in (self.realized_fx_gain_account_id, self.realized_fx_loss_account_id) if x
        ]
        if len(optional_accounts) != len(set(optional_accounts)):
            raise ValueError("Realized FX gain/loss accounts must be distinct")


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
        _calendar_date(as_of, "trade subledger as_of")
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
        cutoff = as_of if as_of is not None else date.max
        _calendar_date(cutoff, "trade journal cutoff")
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
        if accounts.realized_fx_gain_account_id:
            require_account(accounts.realized_fx_gain_account_id, AccountType.REVENUE, NormalBalance.CREDIT)
        if accounts.realized_fx_loss_account_id:
            require_account(accounts.realized_fx_loss_account_id, AccountType.EXPENSE, NormalBalance.DEBIT)
        configured_accounts = [
            accounts.receivable_account_id, accounts.revenue_account_id,
            accounts.payable_account_id, accounts.purchase_account_id,
            *[x for x in (accounts.realized_fx_gain_account_id, accounts.realized_fx_loss_account_id) if x],
        ]
        if len(configured_accounts) != len(set(configured_accounts)):
            raise ValueError("Trade control, P&L and realized FX accounts must be distinct")
        purchase = account_map.get(accounts.purchase_account_id)
        if purchase is None or purchase.normal_balance != NormalBalance.DEBIT or purchase.account_type not in {AccountType.ASSET, AccountType.EXPENSE}:
            raise ValueError("Purchase account must be a debit-normal asset or expense")
        pending_entries = []
        expected_ar_delta = Decimal("0")
        expected_ap_delta = Decimal("0")
        document_functional_amounts: dict[str, Money] = {}

        def functional(amount: Money, source_ref: str):
            rate_ref = fx_refs.get(source_ref)
            return journal.functional_value(amount, rate_ref), rate_ref

        for document in sorted(self.documents, key=lambda row: (row.issue_date, row.document_id)):
            if document.issue_date > cutoff:
                continue
            if document.issue_date > recorded_at.date():
                raise ValueError(f"Trade document is future-effective at posting time: {document.document_id}")
            if document.side == TradeSide.RECEIVABLE:
                debit_account, credit_account = accounts.receivable_account_id, accounts.revenue_account_id
                debit_side, credit_side = PostingSide.DEBIT, PostingSide.CREDIT
            else:
                debit_account, credit_account = accounts.purchase_account_id, accounts.payable_account_id
                debit_side, credit_side = PostingSide.DEBIT, PostingSide.CREDIT
            functional_amount, fx_ref = functional(document.original_amount, document.source_ref)
            document_functional_amounts[document.document_id] = functional_amount
            if document.side == TradeSide.RECEIVABLE:
                expected_ar_delta += functional_amount.amount
            else:
                expected_ap_delta += functional_amount.amount
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
            pending_entries.append(entry)

        # Allocate the invoice's original functional carrying value to each
        # settlement. The final settlement absorbs any Decimal division remainder.
        remaining_original = {
            row.document_id: row.original_amount.amount for row in self.documents
        }
        remaining_carrying = {
            key: value.amount for key, value in document_functional_amounts.items()
        }
        settlement_carrying: dict[str, Decimal] = {}
        for settlement in sorted(self.settlements, key=lambda row: (row.settlement_date, row.settlement_id)):
            if settlement.settlement_date > cutoff:
                continue
            if settlement.settlement_date > recorded_at.date():
                raise ValueError(f"Trade settlement is future-effective at posting time: {settlement.settlement_id}")
            document = self._documents[settlement.document_id]
            original_left = remaining_original[document.document_id]
            carrying_left = remaining_carrying[document.document_id]
            if settlement.amount.amount == original_left:
                carrying_amount = carrying_left
            else:
                carrying_amount = (
                    document_functional_amounts[document.document_id].amount
                    * settlement.amount.amount / document.original_amount.amount
                )
            settlement_carrying[settlement.settlement_id] = carrying_amount
            remaining_original[document.document_id] = original_left - settlement.amount.amount
            remaining_carrying[document.document_id] = carrying_left - carrying_amount

        for settlement in sorted(self.settlements, key=lambda row: (row.settlement_date, row.settlement_id)):
            if settlement.settlement_date > cutoff:
                continue
            document = self._documents[settlement.document_id]
            require_account(settlement.cash_account_id, AccountType.ASSET, NormalBalance.DEBIT)
            if settlement.cash_account_id in {
                accounts.receivable_account_id, accounts.revenue_account_id,
                accounts.payable_account_id, accounts.purchase_account_id,
            }:
                raise ValueError("Settlement cash account must be distinct from trade control accounts")
            cash_functional, cash_fx_ref = functional(settlement.amount, settlement.source_ref)
            carrying_amount = Money(settlement_carrying[settlement.settlement_id], journal.functional_currency)
            document_fx_ref = fx_refs.get(document.source_ref)
            fx_difference = cash_functional.amount - carrying_amount.amount
            if document.side == TradeSide.RECEIVABLE:
                expected_ar_delta -= carrying_amount.amount
            else:
                expected_ap_delta -= carrying_amount.amount
            entry_id = f"trade-settlement:{settlement.settlement_id}"
            if document.side == TradeSide.RECEIVABLE:
                lines = [
                    JournalLine(f"{entry_id}:dr", settlement.cash_account_id, PostingSide.DEBIT,
                        settlement.amount, cash_functional, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, cash_fx_ref),
                    JournalLine(f"{entry_id}:cr", accounts.receivable_account_id, PostingSide.CREDIT,
                        settlement.amount, carrying_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, document_fx_ref),
                ]
                if fx_difference > 0:
                    if not accounts.realized_fx_gain_account_id:
                        raise ValueError("Realized FX gain account is required for this settlement")
                    lines.append(JournalLine(f"{entry_id}:fx-gain", accounts.realized_fx_gain_account_id,
                        PostingSide.CREDIT, Money(fx_difference, journal.functional_currency),
                        Money(fx_difference, journal.functional_currency), document.enterprise_id,
                        settlement.source_ref, document.counterparty_id))
                elif fx_difference < 0:
                    if not accounts.realized_fx_loss_account_id:
                        raise ValueError("Realized FX loss account is required for this settlement")
                    loss = Money(-fx_difference, journal.functional_currency)
                    lines.append(JournalLine(f"{entry_id}:fx-loss", accounts.realized_fx_loss_account_id,
                        PostingSide.DEBIT, loss, loss, document.enterprise_id,
                        settlement.source_ref, document.counterparty_id))
            else:
                lines = [
                    JournalLine(f"{entry_id}:dr", accounts.payable_account_id, PostingSide.DEBIT,
                        settlement.amount, carrying_amount, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, document_fx_ref),
                    JournalLine(f"{entry_id}:cr", settlement.cash_account_id, PostingSide.CREDIT,
                        settlement.amount, cash_functional, document.enterprise_id, settlement.source_ref,
                        document.counterparty_id, cash_fx_ref),
                ]
                if fx_difference > 0:
                    if not accounts.realized_fx_loss_account_id:
                        raise ValueError("Realized FX loss account is required for this settlement")
                    loss = Money(fx_difference, journal.functional_currency)
                    lines.append(JournalLine(f"{entry_id}:fx-loss", accounts.realized_fx_loss_account_id,
                        PostingSide.DEBIT, loss, loss, document.enterprise_id,
                        settlement.source_ref, document.counterparty_id))
                elif fx_difference < 0:
                    if not accounts.realized_fx_gain_account_id:
                        raise ValueError("Realized FX gain account is required for this settlement")
                    gain = Money(-fx_difference, journal.functional_currency)
                    lines.append(JournalLine(f"{entry_id}:fx-gain", accounts.realized_fx_gain_account_id,
                        PostingSide.CREDIT, gain, gain, document.enterprise_id,
                        settlement.source_ref, document.counterparty_id))
            pending_entries.append(JournalEntry(
                entry_id, settlement.settlement_date, recorded_at, journal.functional_currency,
                tuple(lines), f"trade-settlement:{settlement.settlement_id}",
                f"trade-settlement:{settlement.settlement_id}",
                f"Post settlement {settlement.settlement_id}",
            ))

        # Atomic batch: a bad later settlement cannot leave earlier invoices posted.
        journal.post_many(pending_entries)
        posted = [entry.entry_id for entry in pending_entries]
        posted_entries = {entry.entry_id: entry for entry in pending_entries}
        actual_ar_delta = Decimal("0")
        actual_ap_delta = Decimal("0")
        for entry in posted_entries.values():
            for line in entry.lines:
                signed_debit = line.functional_amount.amount if line.side == PostingSide.DEBIT else -line.functional_amount.amount
                if line.account_id == accounts.receivable_account_id:
                    actual_ar_delta += signed_debit
                if line.account_id == accounts.payable_account_id:
                    actual_ap_delta -= signed_debit
        ar_matches = actual_ar_delta == expected_ar_delta
        ap_matches = actual_ap_delta == expected_ap_delta
        return {
            "posted_entry_ids": posted,
            "posted_entry_count": len(posted),
            "as_of": cutoff.isoformat(),
            "expected_ar_control_delta": str(expected_ar_delta),
            "actual_ar_control_delta": str(actual_ar_delta),
            "expected_ap_credit_control_delta": str(expected_ap_delta),
            "actual_ap_credit_control_delta": str(actual_ap_delta),
            "trade_subledger_delta_matches_journal_control_accounts": ar_matches and ap_matches,
            "adjustments_and_disputes_require_separate_explicit_workflows": True,
        }
