"""Typed money, physical quantity, time, FX and evidence contracts for SUES.

The contracts intentionally reject implicit currency/unit conversion. Conversion
must be explicit and traceable to a dated FXRate and its source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import re


_CURRENCY_RE = re.compile(r"^[A-Z][A-Z0-9]{2,11}$")
_UNIT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_./*-]{0,31}$")


def _decimal(value: Decimal | int | float | str, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal number")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal number") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _currency(value: str) -> str:
    if not isinstance(value, str) or not _CURRENCY_RE.fullmatch(value):
        raise ValueError("currency must be an uppercase 3–12 character currency/asset code")
    return value


def _aware(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")


def _calendar_date(value: date, field: str) -> None:
    """Reject datetime values where a calendar date is required."""
    if isinstance(value, datetime) or not isinstance(value, date):
        raise ValueError(f"{field} must be a calendar date, not a datetime")


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "amount"))
        object.__setattr__(self, "currency", _currency(self.currency))

    def _same_currency(self, other: Money) -> None:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise ValueError("Money arithmetic requires identical currencies")

    def __add__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def scale(self, factor: Decimal | int | float | str) -> Money:
        return Money(self.amount * _decimal(factor, "factor"), self.currency)


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "amount"))
        if not isinstance(self.unit, str) or not _UNIT_RE.fullmatch(self.unit):
            raise ValueError("unit must be a non-empty canonical unit identifier")

    def _same_unit(self, other: Quantity) -> None:
        if not isinstance(other, Quantity) or self.unit != other.unit:
            raise ValueError("Quantity arithmetic requires identical units")

    def __add__(self, other: Quantity) -> Quantity:
        self._same_unit(other)
        return Quantity(self.amount + other.amount, self.unit)

    def __sub__(self, other: Quantity) -> Quantity:
        self._same_unit(other)
        return Quantity(self.amount - other.amount, self.unit)

    def scale(self, factor: Decimal | int | float | str) -> Quantity:
        return Quantity(self.amount * _decimal(factor, "factor"), self.unit)


@dataclass(frozen=True)
class EconomicPeriod:
    period_id: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if not self.period_id:
            raise ValueError("period_id is required")
        _calendar_date(self.start, "period start")
        _calendar_date(self.end, "period end")
        if self.end < self.start:
            raise ValueError("period end cannot precede period start")

    def contains(self, value: date) -> bool:
        _calendar_date(value, "period value")
        return self.start <= value <= self.end


@dataclass(frozen=True)
class FXRate:
    rate_id: str
    base_currency: str
    quote_currency: str
    rate: Decimal
    observed_at: datetime
    source_ref: str

    def __post_init__(self) -> None:
        if not self.rate_id or not self.source_ref:
            raise ValueError("FX rate identity and source_ref are required")
        object.__setattr__(self, "base_currency", _currency(self.base_currency))
        object.__setattr__(self, "quote_currency", _currency(self.quote_currency))
        object.__setattr__(self, "rate", _decimal(self.rate, "rate"))
        if self.base_currency == self.quote_currency:
            raise ValueError("FX base and quote currencies must differ")
        if self.rate <= 0:
            raise ValueError("FX rate must be positive")
        _aware(self.observed_at, "observed_at")

    def convert(self, amount: Money) -> Money:
        if amount.currency != self.base_currency:
            raise ValueError("Money currency does not match FX base currency")
        return Money(amount.amount * self.rate, self.quote_currency)


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    UNDERWRITTEN = "UNDERWRITTEN"
    SCENARIO = "SCENARIO"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_ref: str
    status: EvidenceStatus
    captured_at: datetime
    effective_from: date
    effective_to: date | None = None
    content_sha256: str | None = None
    issuer_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source_ref:
            raise ValueError("evidence_id and source_ref are required")
        if not isinstance(self.status, EvidenceStatus):
            try:
                object.__setattr__(self, "status", EvidenceStatus(self.status))
            except ValueError as exc:
                raise ValueError("Unsupported evidence status") from exc
        _aware(self.captured_at, "captured_at")
        _calendar_date(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _calendar_date(self.effective_to, "effective_to")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        if self.content_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256):
            raise ValueError("content_sha256 must be a lowercase SHA-256 hex digest")
