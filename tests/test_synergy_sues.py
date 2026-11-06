import sys
from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_sues import (
    Account, AccountType, EconomicPeriod, EvidenceRecord, EvidenceStatus,
    FXRate, Journal, JournalEntry, JournalLine, Money, NormalBalance, Quantity,
)


def test_money_rejects_implicit_currency_arithmetic():
    with pytest.raises(ValueError, match="identical currencies"):
        _ = Money("10", "USD") + Money("10", "KZT")


def test_money_uses_decimal_and_allows_explicit_scaling():
    result = Money("0.1", "USD") + Money("0.2", "USD")
    assert result.amount == Decimal("0.3")
    assert result.scale("2").amount == Decimal("0.6")


def test_quantity_rejects_unit_mismatch():
    with pytest.raises(ValueError, match="identical units"):
        _ = Quantity("1", "tonne") + Quantity("1", "MWh")


def test_period_and_fx_rate_are_explicit_and_dated():
    period = EconomicPeriod("2026-Q4", date(2026, 10, 1), date(2026, 12, 31))
    assert period.contains(date(2026, 11, 6))
    fx = FXRate("fx1", "USD", "KZT", "500", datetime(2026, 11, 6, tzinfo=timezone.utc), "market-feed:1")
    assert fx.convert(Money("2", "USD")) == Money("1000", "KZT")


def test_evidence_requires_timezone_and_valid_hash():
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceRecord("e1", "meter:1", EvidenceStatus.VERIFIED, datetime(2026, 1, 1),
                       date(2026, 1, 1))
    with pytest.raises(ValueError, match="SHA-256"):
        EvidenceRecord("e2", "meter:2", EvidenceStatus.OBSERVED,
                       datetime(2026, 1, 1, tzinfo=timezone.utc), date(2026, 1, 1),
                       content_sha256="not-a-hash")


def account(account_id, code, account_type, normal):
    return Account(account_id, code, code, account_type, normal)


def entry(entry_id="je1", key="idem1", amount="100"):
    now = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)
    return JournalEntry(
        entry_id, date(2026, 11, 6), now, "USD",
        (
            JournalLine("l1", "cash", "DEBIT", Money(amount, "USD"), Money(amount, "USD"), "co1", "bank:tx1"),
            JournalLine("l2", "revenue", "CREDIT", Money(amount, "USD"), Money(amount, "USD"), "co1", "invoice:1"),
        ),
        "event:1", key, "Recognize external sale",
    )


def new_journal():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("fx", "7990", AccountType.EXPENSE, NormalBalance.DEBIT))
    return journal


def test_journal_posts_balanced_entry_and_builds_trial_balance():
    journal = new_journal()
    journal.post(entry())
    trial = journal.trial_balance()
    assert trial["balanced"]
    assert trial["total_debits"] == "100"
    assert trial["total_credits"] == "100"


def test_journal_rejects_unbalanced_entry_and_unknown_account():
    journal = new_journal()
    bad = entry(amount="100")
    bad = JournalEntry(bad.entry_id, bad.effective_date, bad.recorded_at, bad.functional_currency,
        (bad.lines[0], JournalLine("l2", "revenue", "CREDIT", Money("99", "USD"),
         Money("99", "USD"), "co1", "invoice:1")), bad.source_event_id, bad.idempotency_key,
        bad.description)
    with pytest.raises(ValueError, match="Unbalanced"):
        journal.post(bad)
    missing = JournalEntry("je2", date(2026, 11, 6), bad.recorded_at, "USD",
        (JournalLine("x1", "missing", "DEBIT", Money("1", "USD"), Money("1", "USD"), "co1", "x"),
         JournalLine("x2", "cash", "CREDIT", Money("1", "USD"), Money("1", "USD"), "co1", "x")),
        "event:2", "idem2", "Missing account")
    with pytest.raises(ValueError, match="Unknown account"):
        journal.post(missing)


def test_foreign_currency_posting_requires_fx_reference_and_balances_functional_currency():
    journal = new_journal()
    now = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)
    lines = (
        JournalLine("fx1", "cash", "DEBIT", Money("2", "EUR"), Money("2.2", "USD"),
                    "co1", "bank:fx", fx_rate_ref="EURUSD:2026-11-06"),
        JournalLine("fx2", "revenue", "CREDIT", Money("2.2", "USD"), Money("2.2", "USD"),
                    "co1", "sale:fx"),
    )
    je = JournalEntry("je-fx", date(2026, 11, 6), now, "USD", lines, "event-fx", "idem-fx", "FX sale")
    journal.post(je)
    assert journal.trial_balance()["balanced"]


def test_same_currency_functional_value_cannot_be_changed_without_fx():
    journal = new_journal()
    bad = JournalEntry("je-bad", date(2026, 11, 6), datetime(2026, 11, 6, tzinfo=timezone.utc), "USD",
        (JournalLine("a", "cash", "DEBIT", Money("10", "USD"), Money("11", "USD"), "co1", "x",
                     fx_rate_ref="bad"),
         JournalLine("b", "revenue", "CREDIT", Money("11", "USD"), Money("11", "USD"), "co1", "y")),
        "event-bad", "idem-bad", "Invalid same-currency valuation")
    with pytest.raises(ValueError, match="Same-currency"):
        journal.post(bad)


def test_journal_enforces_idempotency_and_single_reversal():
    journal = new_journal()
    original = journal.post(entry())
    with pytest.raises(ValueError, match="idempotency"):
        journal.post(entry("je-duplicate", "idem1"))
    reversed_entry = journal.reverse(original.entry_id, "je-reversal", date(2026, 11, 7),
        datetime(2026, 11, 7, 8, tzinfo=timezone.utc), "event-reversal", "idem-reversal", "Reverse sale")
    assert reversed_entry.reversal_of == original.entry_id
    assert journal.trial_balance()["total_debits"] == "200"
    assert journal.trial_balance()["total_credits"] == "200"
    with pytest.raises(ValueError, match="already been reversed"):
        journal.reverse(original.entry_id, "je-reversal-2", date(2026, 11, 8),
            datetime(2026, 11, 8, 8, tzinfo=timezone.utc), "event-reversal-2", "idem-reversal-2", "Second reversal")


def test_journal_rejects_a_forged_reversal_that_does_not_mirror_original():
    journal = new_journal()
    original = journal.post(entry())
    now = datetime(2026, 11, 7, 8, tzinfo=timezone.utc)
    forged = JournalEntry(
        "je-forged-reversal", date(2026, 11, 7), now, "USD",
        (
            JournalLine("fr1", "cash", "CREDIT", Money("50", "USD"), Money("50", "USD"), "co1", "bank:tx1"),
            JournalLine("fr2", "revenue", "DEBIT", Money("50", "USD"), Money("50", "USD"), "co1", "invoice:1"),
        ),
        "event-forged", "idem-forged", "Forged partial reversal", reversal_of=original.entry_id,
    )
    with pytest.raises(ValueError, match="exactly mirror"):
        journal.post(forged)
    assert len(journal.entries) == 1
