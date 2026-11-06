"""Immutable double-entry journal primitives for SUES.

All posted entries balance in the entity's functional currency. Transaction
currency is retained on every line; foreign-currency lines require an explicit
FX rate reference and functional-currency valuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import FXRate, Money, _aware


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class NormalBalance(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class PostingSide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True)
class Account:
    account_id: str
    code: str
    name: str
    account_type: AccountType
    normal_balance: NormalBalance

    def __post_init__(self) -> None:
        if not all((self.account_id, self.code, self.name)):
            raise ValueError("Account ID, code and name are required")
        if not isinstance(self.account_type, AccountType):
            object.__setattr__(self, "account_type", AccountType(self.account_type))
        if not isinstance(self.normal_balance, NormalBalance):
            object.__setattr__(self, "normal_balance", NormalBalance(self.normal_balance))


@dataclass(frozen=True)
class JournalLine:
    line_id: str
    account_id: str
    side: PostingSide
    amount: Money
    functional_amount: Money
    entity_id: str
    source_ref: str
    counterparty_id: str | None = None
    fx_rate_ref: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.line_id, self.account_id, self.entity_id, self.source_ref)):
            raise ValueError("Journal line identity, entity and source are required")
        if not isinstance(self.side, PostingSide):
            object.__setattr__(self, "side", PostingSide(self.side))
        if self.amount.amount <= 0 or self.functional_amount.amount <= 0:
            raise ValueError("Journal line amounts must be positive")
        if self.amount.currency == self.functional_amount.currency:
            if self.amount.amount != self.functional_amount.amount:
                raise ValueError("Same-currency transaction and functional amounts must match")
            if self.fx_rate_ref is not None:
                raise ValueError("FX rate reference is not allowed for same-currency line")
        elif not self.fx_rate_ref:
            raise ValueError("Foreign-currency line requires fx_rate_ref")


@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    effective_date: date
    recorded_at: datetime
    functional_currency: str
    lines: tuple[JournalLine, ...]
    source_event_id: str
    idempotency_key: str
    description: str
    reversal_of: str | None = None

    def __post_init__(self) -> None:
        if not all((self.entry_id, self.source_event_id, self.idempotency_key, self.description)):
            raise ValueError("Journal entry identity, source, idempotency key and description are required")
        if not isinstance(self.effective_date, date):
            raise ValueError("effective_date must be a date")
        _aware(self.recorded_at, "recorded_at")
        if not isinstance(self.lines, tuple):
            object.__setattr__(self, "lines", tuple(self.lines))
        if len(self.lines) < 2:
            raise ValueError("A journal entry requires at least two lines")


class Journal:
    """In-memory reference journal; durable storage is a separate infrastructure task."""

    def __init__(self, functional_currency: str) -> None:
        # Reuse Money's canonical currency validation.
        self.functional_currency = Money(Decimal("0"), functional_currency).currency
        self._accounts: dict[str, Account] = {}
        self._entries: dict[str, JournalEntry] = {}
        self._idempotency_keys: set[str] = set()
        self._reversed: set[str] = set()
        self._fx_rates: dict[str, FXRate] = {}

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(self._accounts.values())

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return tuple(self._entries.values())

    def functional_value(self, amount: Money, fx_rate_ref: str | None = None) -> Money:
        """Value transaction currency in the journal functional currency."""
        if amount.currency == self.functional_currency:
            if fx_rate_ref is not None:
                raise ValueError("FX rate reference is not allowed for functional-currency amount")
            return amount
        rate = self._fx_rates.get(fx_rate_ref or "")
        if rate is None:
            raise ValueError(f"Unknown FX rate reference: {fx_rate_ref}")
        if rate.base_currency != amount.currency or rate.quote_currency != self.functional_currency:
            raise ValueError("FX rate direction must convert transaction currency to functional currency")
        return rate.convert(amount)

    def add_fx_rate(self, rate: FXRate) -> None:
        if rate.rate_id in self._fx_rates:
            raise ValueError(f"Duplicate FX rate_id: {rate.rate_id}")
        self._fx_rates[rate.rate_id] = rate

    def add_account(self, account: Account) -> None:
        if account.account_id in self._accounts:
            raise ValueError(f"Duplicate account_id: {account.account_id}")
        if any(x.code == account.code for x in self._accounts.values()):
            raise ValueError(f"Duplicate account code: {account.code}")
        self._accounts[account.account_id] = account

    def post(self, entry: JournalEntry) -> JournalEntry:
        if entry.entry_id in self._entries:
            raise ValueError(f"Duplicate journal entry: {entry.entry_id}")
        if entry.idempotency_key in self._idempotency_keys:
            raise ValueError(f"Duplicate idempotency key: {entry.idempotency_key}")
        if entry.functional_currency != self.functional_currency:
            raise ValueError("Journal entry functional currency mismatch")
        line_ids = [line.line_id for line in entry.lines]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("Duplicate journal line_id")
        debit = Decimal("0")
        credit = Decimal("0")
        for line in entry.lines:
            if line.account_id not in self._accounts:
                raise ValueError(f"Unknown account_id: {line.account_id}")
            if line.functional_amount.currency != self.functional_currency:
                raise ValueError("Journal line functional currency mismatch")
            if line.amount.currency != self.functional_currency:
                rate = self._fx_rates.get(line.fx_rate_ref or "")
                if rate is None:
                    raise ValueError(f"Unknown FX rate reference: {line.fx_rate_ref}")
                if rate.base_currency != line.amount.currency or rate.quote_currency != self.functional_currency:
                    raise ValueError("FX rate direction must convert transaction currency to functional currency")
                if rate.observed_at.date() > entry.effective_date:
                    raise ValueError("FX rate observation cannot post-date the journal effective date")
                expected_functional = rate.convert(line.amount)
                if expected_functional.amount != line.functional_amount.amount:
                    raise ValueError("Functional amount does not match the referenced FX rate")
            if line.side == PostingSide.DEBIT:
                debit += line.functional_amount.amount
            else:
                credit += line.functional_amount.amount
        if debit != credit:
            raise ValueError(f"Unbalanced journal entry: debit={debit}, credit={credit}")
        if entry.reversal_of is not None:
            if entry.reversal_of not in self._entries:
                raise ValueError("Reversal references unknown journal entry")
            if entry.reversal_of in self._reversed:
                raise ValueError("Journal entry has already been reversed")
            original = self._entries[entry.reversal_of]
            def reversal_signature(line: JournalLine):
                return (
                    line.account_id,
                    PostingSide.CREDIT if line.side == PostingSide.DEBIT else PostingSide.DEBIT,
                    line.amount,
                    line.functional_amount,
                    line.entity_id,
                    line.source_ref,
                    line.counterparty_id,
                    line.fx_rate_ref,
                    line.evidence_ids,
                )
            expected = sorted((reversal_signature(line) for line in original.lines), key=repr)
            actual = sorted((
                (line.account_id, line.side, line.amount, line.functional_amount,
                 line.entity_id, line.source_ref, line.counterparty_id,
                 line.fx_rate_ref, line.evidence_ids)
                for line in entry.lines
            ), key=repr)
            if actual != expected:
                raise ValueError("Reversal lines must exactly mirror the original entry")
        self._entries[entry.entry_id] = entry
        self._idempotency_keys.add(entry.idempotency_key)
        if entry.reversal_of is not None:
            self._reversed.add(entry.reversal_of)
        return entry

    def reverse(
        self,
        entry_id: str,
        reversal_entry_id: str,
        effective_date: date,
        recorded_at: datetime,
        source_event_id: str,
        idempotency_key: str,
        description: str,
    ) -> JournalEntry:
        original = self._entries.get(entry_id)
        if original is None:
            raise ValueError(f"Unknown journal entry: {entry_id}")
        if entry_id in self._reversed:
            raise ValueError(f"Journal entry has already been reversed: {entry_id}")
        reversed_lines = tuple(
            JournalLine(
                line_id=f"{reversal_entry_id}:{line.line_id}",
                account_id=line.account_id,
                side=PostingSide.CREDIT if line.side == PostingSide.DEBIT else PostingSide.DEBIT,
                amount=line.amount,
                functional_amount=line.functional_amount,
                entity_id=line.entity_id,
                source_ref=line.source_ref,
                counterparty_id=line.counterparty_id,
                fx_rate_ref=line.fx_rate_ref,
                evidence_ids=line.evidence_ids,
            )
            for line in original.lines
        )
        reversal = JournalEntry(
            entry_id=reversal_entry_id,
            effective_date=effective_date,
            recorded_at=recorded_at,
            functional_currency=self.functional_currency,
            lines=reversed_lines,
            source_event_id=source_event_id,
            idempotency_key=idempotency_key,
            description=description,
            reversal_of=entry_id,
        )
        return self.post(reversal)

    def trial_balance(self) -> dict:
        totals: dict[str, dict[str, Decimal]] = {
            account_id: {"debit": Decimal("0"), "credit": Decimal("0")}
            for account_id in self._accounts
        }
        for entry in self._entries.values():
            for line in entry.lines:
                key = "debit" if line.side == PostingSide.DEBIT else "credit"
                totals[line.account_id][key] += line.functional_amount.amount
        debit_total = sum((x["debit"] for x in totals.values()), Decimal("0"))
        credit_total = sum((x["credit"] for x in totals.values()), Decimal("0"))
        return {
            "functional_currency": self.functional_currency,
            "accounts": {
                account_id: {
                    "debit": str(values["debit"]),
                    "credit": str(values["credit"]),
                    "net_debit": str(values["debit"] - values["credit"]),
                }
                for account_id, values in totals.items()
            },
            "total_debits": str(debit_total),
            "total_credits": str(credit_total),
            "balanced": debit_total == credit_total,
            "entry_count": len(self._entries),
        }
