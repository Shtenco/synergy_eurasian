"""Explicit bank-statement to double-entry journal reconciliation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timezone
from decimal import Decimal
from typing import Iterable

from .contracts import EconomicPeriod, Money, _calendar_date
from .journal import AccountType, Journal, NormalBalance, PostingSide


@dataclass(frozen=True)
class BankStatementLine:
    line_id: str
    booked_date: date
    signed_amount: Money
    bank_reference: str
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.line_id, self.bank_reference, self.source_ref)):
            raise ValueError("Bank statement line identity and provenance are required")
        _calendar_date(self.booked_date, "bank booked_date")
        if self.signed_amount.amount == 0:
            raise ValueError("Bank statement movement cannot be zero")


@dataclass(frozen=True)
class BankStatement:
    statement_id: str
    account_id: str
    currency: str
    period: EconomicPeriod
    opening_bank_balance: Money
    closing_bank_balance: Money
    opening_ledger_balance: Money
    lines: tuple[BankStatementLine, ...]

    def __post_init__(self) -> None:
        if not all((self.statement_id, self.account_id, self.currency)):
            raise ValueError("Bank statement identity and currency are required")
        for name in ("opening_bank_balance", "closing_bank_balance", "opening_ledger_balance"):
            value = getattr(self, name)
            if value.currency != self.currency:
                raise ValueError(f"{name} currency mismatch")
        if not isinstance(self.lines, tuple):
            object.__setattr__(self, "lines", tuple(self.lines))
        ids = [line.line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate bank statement line_id")
        for line in self.lines:
            if line.signed_amount.currency != self.currency:
                raise ValueError("Bank statement line currency mismatch")
            if not self.period.contains(line.booked_date):
                raise ValueError(f"Bank line outside statement period: {line.line_id}")
        calculated = self.opening_bank_balance.amount + sum(
            (line.signed_amount.amount for line in self.lines), Decimal("0")
        )
        if calculated != self.closing_bank_balance.amount:
            raise ValueError("Bank statement opening + movements does not equal closing balance")


@dataclass(frozen=True)
class BankAllocation:
    allocation_id: str
    statement_line_id: str
    journal_entry_id: str
    journal_line_id: str
    allocated_amount: Money
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.allocation_id, self.statement_line_id, self.journal_entry_id,
                    self.journal_line_id, self.source_ref)):
            raise ValueError("Bank allocation identity and provenance are required")
        if self.allocated_amount.amount <= 0:
            raise ValueError("Bank allocation amount must be positive")


def reconcile_bank_account(
    journal: Journal,
    statement: BankStatement,
    allocations: Iterable[BankAllocation],
) -> dict:
    """Reconcile explicit bank-line allocations to posted cash journal lines.

    The function never guesses matches. Unallocated statement or journal amounts
    remain visible as exceptions. The bank statement's own opening/movement/
    closing identity is checked when the statement object is created.
    """
    account_map = {account.account_id: account for account in journal.accounts}
    account = account_map.get(statement.account_id)
    if account is None:
        raise ValueError(f"Unknown journal cash account: {statement.account_id}")
    if account.account_type != AccountType.ASSET or account.normal_balance != NormalBalance.DEBIT:
        raise ValueError("Bank reconciliation requires a debit-normal asset cash account")

    journal_movements = {}
    late_recorded_journal_lines = []
    for entry in journal.entries:
        if not statement.period.contains(entry.effective_date):
            continue
        # Preserve the historical knowledge cut-off: a backdated entry recorded
        # after the statement period closed must not rewrite that period's
        # reconciliation. It remains a visible late-recording exception.
        recorded_date_utc = entry.recorded_at.astimezone(timezone.utc).date()
        if recorded_date_utc > statement.period.end:
            for line in entry.lines:
                if line.account_id == statement.account_id:
                    late_recorded_journal_lines.append({
                        "journal_line_ref": f"{entry.entry_id}:{line.line_id}",
                        "effective_date": entry.effective_date.isoformat(),
                        "recorded_at": entry.recorded_at.isoformat(),
                        "recorded_after_period_end": statement.period.end.isoformat(),
                    })
            continue
        for line in entry.lines:
            if line.account_id != statement.account_id:
                continue
            if line.amount.currency != statement.currency:
                raise ValueError(f"Cash journal line currency mismatch: {entry.entry_id}:{line.line_id}")
            signed = line.amount.amount if line.side == PostingSide.DEBIT else -line.amount.amount
            ref = (entry.entry_id, line.line_id)
            if ref in journal_movements:
                raise ValueError(f"Duplicate journal cash line reference: {ref}")
            journal_movements[ref] = signed

    bank_lines = {line.line_id: line for line in statement.lines}
    allocation_rows = list(allocations)
    allocation_ids = [row.allocation_id for row in allocation_rows]
    if len(allocation_ids) != len(set(allocation_ids)):
        raise ValueError("Duplicate bank allocation_id")

    bank_allocated: dict[str, Decimal] = {}
    journal_allocated: dict[tuple[str, str], Decimal] = {}
    allocation_results = []
    for row in allocation_rows:
        if row.statement_line_id not in bank_lines:
            raise ValueError(f"Unknown bank statement line: {row.statement_line_id}")
        journal_ref = (row.journal_entry_id, row.journal_line_id)
        if journal_ref not in journal_movements:
            raise ValueError(f"Unknown cash journal line: {journal_ref}")
        bank_line = bank_lines[row.statement_line_id]
        bank_signed = bank_line.signed_amount.amount
        journal_signed = journal_movements[journal_ref]
        if row.allocated_amount.currency != statement.currency:
            raise ValueError("Bank allocation currency mismatch")
        if (bank_signed > 0) != (journal_signed > 0):
            raise ValueError("Bank movement direction does not match journal cash posting")
        bank_allocated[row.statement_line_id] = bank_allocated.get(row.statement_line_id, Decimal("0")) + row.allocated_amount.amount
        journal_allocated[journal_ref] = journal_allocated.get(journal_ref, Decimal("0")) + row.allocated_amount.amount
        allocation_results.append({
            "allocation_id": row.allocation_id,
            "statement_line_id": row.statement_line_id,
            "journal_line_ref": f"{row.journal_entry_id}:{row.journal_line_id}",
            "amount": str(row.allocated_amount.amount),
        })

    for line_id, amount in bank_allocated.items():
        if amount > abs(bank_lines[line_id].signed_amount.amount):
            raise ValueError(f"Allocations exceed bank statement line: {line_id}")
    for ref, amount in journal_allocated.items():
        if amount > abs(journal_movements[ref]):
            raise ValueError(f"Allocations exceed journal cash line: {ref}")

    bank_exceptions = []
    for line_id, line in bank_lines.items():
        unmatched = abs(line.signed_amount.amount) - bank_allocated.get(line_id, Decimal("0"))
        if unmatched:
            bank_exceptions.append({
                "statement_line_id": line_id,
                "signed_unmatched_amount": str(unmatched if line.signed_amount.amount > 0 else -unmatched),
            })

    journal_exceptions = []
    for ref, signed in journal_movements.items():
        unmatched = abs(signed) - journal_allocated.get(ref, Decimal("0"))
        if unmatched:
            journal_exceptions.append({
                "journal_line_ref": f"{ref[0]}:{ref[1]}",
                "signed_unmatched_amount": str(unmatched if signed > 0 else -unmatched),
            })

    statement_net = sum((line.signed_amount.amount for line in statement.lines), Decimal("0"))
    ledger_net = sum(journal_movements.values(), Decimal("0"))
    bank_close = statement.opening_bank_balance.amount + statement_net
    ledger_close = statement.opening_ledger_balance.amount + ledger_net
    closing_difference = bank_close - ledger_close

    return {
        "statement_id": statement.statement_id,
        "account_id": statement.account_id,
        "currency": statement.currency,
        "period_id": statement.period.period_id,
        "bank_opening_balance": str(statement.opening_bank_balance.amount),
        "bank_closing_balance": str(bank_close),
        "ledger_opening_balance": str(statement.opening_ledger_balance.amount),
        "ledger_closing_balance": str(ledger_close),
        "bank_minus_ledger_closing_difference": str(closing_difference),
        "statement_line_count": len(statement.lines),
        "journal_cash_line_count": len(journal_movements),
        "allocations": allocation_results,
        "unmatched_statement_lines": bank_exceptions,
        "unmatched_journal_lines": journal_exceptions,
        "late_recorded_journal_lines": late_recorded_journal_lines,
        "fully_reconciled": (
            closing_difference == 0 and not bank_exceptions and not journal_exceptions
            and not late_recorded_journal_lines
        ),
        "automatic_matching_performed": False,
    }
