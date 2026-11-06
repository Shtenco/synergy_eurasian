"""Functional-to-reporting-currency trial-balance translation for SUES."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from .contracts import FXRate, Money
from .journal import AccountType


@dataclass(frozen=True)
class TrialBalanceAccount:
    account_id: str
    account_type: AccountType
    debit_balance: Money
    credit_balance: Money

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("Trial balance account_id is required")
        if not isinstance(self.account_type, AccountType):
            object.__setattr__(self, "account_type", AccountType(self.account_type))
        if self.debit_balance.currency != self.credit_balance.currency:
            raise ValueError("Trial balance debit and credit currencies must match")
        if self.debit_balance.amount < 0 or self.credit_balance.amount < 0:
            raise ValueError("Trial balance debit and credit balances must be non-negative")
        if self.debit_balance.amount > 0 and self.credit_balance.amount > 0:
            raise ValueError("One trial balance account cannot have both debit and credit closing balances")


@dataclass(frozen=True)
class TranslationPolicy:
    closing_rate: FXRate
    average_rate: FXRate
    historical_equity_rates: dict[str, FXRate]
    reporting_date: date
    translation_adjustment_account_id: str

    def __post_init__(self) -> None:
        if not self.translation_adjustment_account_id:
            raise ValueError("Translation adjustment account ID is required")
        if not isinstance(self.reporting_date, date):
            raise ValueError("reporting_date must be a date")


def translate_trial_balance(
    accounts: Iterable[TrialBalanceAccount],
    policy: TranslationPolicy,
    reporting_currency: str,
) -> dict:
    """Translate a subsidiary trial balance and expose CTA as a separate equity line.

    Assets/liabilities use the closing rate, income/expenses use the average rate,
    and equity uses account-specific historical rates. No rate is inferred.
    """
    rows = list(accounts)
    ids = [row.account_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate trial balance account_id")
    if policy.translation_adjustment_account_id in set(ids):
        raise ValueError("Translation adjustment account ID already exists in source trial balance")

    rates = [policy.closing_rate, policy.average_rate, *policy.historical_equity_rates.values()]
    if not rates:
        raise ValueError("At least one FX translation rate is required")
    base_currency = rates[0].base_currency
    if rates[0].quote_currency != reporting_currency:
        raise ValueError("FX quote currency must equal reporting currency")
    for rate in rates:
        if rate.base_currency != base_currency or rate.quote_currency != reporting_currency:
            raise ValueError("All translation rates must share functional and reporting currencies")
        if rate.observed_at.date() > policy.reporting_date:
            raise ValueError("FX translation rate cannot post-date reporting date")

    translated = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    for row in rows:
        if row.debit_balance.currency != base_currency:
            raise ValueError(f"Account {row.account_id} currency differs from translation base")
        if row.account_type in {AccountType.ASSET, AccountType.LIABILITY}:
            rate = policy.closing_rate
            rate_type = "CLOSING"
        elif row.account_type in {AccountType.REVENUE, AccountType.EXPENSE}:
            rate = policy.average_rate
            rate_type = "AVERAGE"
        else:
            rate = policy.historical_equity_rates.get(row.account_id)
            if rate is None:
                raise ValueError(f"Missing historical FX rate for equity account {row.account_id}")
            rate_type = "HISTORICAL"

        net_functional = row.debit_balance.amount - row.credit_balance.amount
        translated_net = net_functional * rate.rate
        if translated_net > 0:
            debit, credit = translated_net, Decimal("0")
        elif translated_net < 0:
            debit, credit = Decimal("0"), -translated_net
        else:
            debit = credit = Decimal("0")
        total_debits += debit
        total_credits += credit
        translated.append({
            "account_id": row.account_id,
            "account_type": row.account_type.value,
            "rate_type": rate_type,
            "fx_rate_id": rate.rate_id,
            "debit": str(debit),
            "credit": str(credit),
            "currency": reporting_currency,
        })

    difference = total_debits - total_credits
    if difference > 0:
        cta_debit, cta_credit = Decimal("0"), difference
    elif difference < 0:
        cta_debit, cta_credit = -difference, Decimal("0")
    else:
        cta_debit = cta_credit = Decimal("0")
    if difference:
        translated.append({
            "account_id": policy.translation_adjustment_account_id,
            "account_type": AccountType.EQUITY.value,
            "rate_type": "CURRENCY_TRANSLATION_ADJUSTMENT",
            "fx_rate_id": None,
            "debit": str(cta_debit),
            "credit": str(cta_credit),
            "currency": reporting_currency,
        })
    total_debits += cta_debit
    total_credits += cta_credit

    return {
        "functional_currency": base_currency,
        "reporting_currency": reporting_currency,
        "reporting_date": policy.reporting_date.isoformat(),
        "accounts": translated,
        "translation_adjustment": {
            "account_id": policy.translation_adjustment_account_id,
            "debit": str(cta_debit),
            "credit": str(cta_credit),
            "currency": reporting_currency,
        },
        "total_debits": str(total_debits),
        "total_credits": str(total_credits),
        "balanced": total_debits == total_credits,
        "translation_policy": {
            "assets_liabilities": "CLOSING_RATE",
            "income_expenses": "AVERAGE_RATE",
            "equity": "HISTORICAL_RATE_BY_ACCOUNT",
        },
        "translation_is_not_operating_profit": True,
    }
