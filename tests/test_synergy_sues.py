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
    BenefitAttribution, BenefitAttributionRegistry, BenefitEvent, FlowBoundary,
    PhysicalFlow, summarize_physical_flows, IntercompanyRecord, IntercompanyRecordType,
    reconcile_intercompany, post_intercompany_eliminations, BankAllocation, BankStatement, BankStatementLine,
    reconcile_bank_account,
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
    journal.add_fx_rate(FXRate("EURUSD:2026-11-06", "EUR", "USD", "1.1", now, "market-feed:fx"))
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
    with pytest.raises(ValueError, match="Same-currency"):
        JournalLine("a", "cash", "DEBIT", Money("10", "USD"), Money("11", "USD"), "co1", "x",
                    fx_rate_ref="bad")


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


def test_sues_contracts_json_schema_accepts_all_five_contract_shapes():
    import json
    import jsonschema

    schema_path = ROOT / "interfaces" / "synergy_sues_economic_contracts.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    checker = jsonschema.FormatChecker()
    examples = [
        {"amount": "125.50", "currency": "KZT"},
        {"amount": "2.75", "unit": "MWh"},
        {"period_id": "2026-Q4", "start": "2026-10-01", "end": "2026-12-31"},
        {"rate_id": "fx1", "base_currency": "USD", "quote_currency": "KZT",
         "rate": "500.25", "observed_at": "2026-11-06T08:00:00Z", "source_ref": "feed:1"},
        {"evidence_id": "e1", "source_ref": "meter:1", "status": "VERIFIED",
         "captured_at": "2026-11-06T08:00:00Z", "effective_from": "2026-11-01"},
    ]
    for example in examples:
        jsonschema.validate(example, schema, format_checker=checker)


def test_physical_flow_summary_never_mixes_units_resources_or_periods():
    flows = [
        PhysicalFlow("f1", "supplier", "factory", "steel", Quantity("10", "tonne"), "2026-Q4", FlowBoundary.INTERNAL),
        PhysicalFlow("f2", "grid", "factory", "electricity", Quantity("5", "MWh"), "2026-Q4", FlowBoundary.IMPORT),
        PhysicalFlow("f3", "factory", "customer", "steel", Quantity("4", "tonne"), "2027-Q1", FlowBoundary.EXPORT),
    ]
    result = summarize_physical_flows(flows)
    assert len(result["flows"]) == 3
    assert {row["unit"] for row in result["flows"]} == {"tonne", "MWh"}
    assert result["internal_transfers_are_not_new_output"]


def test_physical_flow_rejects_duplicate_ids_and_negative_quantity():
    flow = PhysicalFlow("f1", "a", "b", "water", Quantity("1", "m3"), "2026-Q4")
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_physical_flows([flow, flow])
    with pytest.raises(ValueError, match="non-negative"):
        PhysicalFlow("f2", "a", "b", "water", Quantity("-1", "m3"), "2026-Q4")


def test_benefit_registry_caps_attribution_across_projects():
    registry = BenefitAttributionRegistry()
    event = BenefitEvent("be1", "meter-reading-1", "enterprise-1", "2026-Q4",
        "ENERGY_SAVING", Money("100", "USD"), "baseline-vs-control-1",
        ("meter:evidence-1",), EvidenceStatus.VERIFIED)
    registry.add_event(event)
    registry.add_claim(BenefitAttribution("claim-a", "be1", "project-a", "0.4"))
    registry.add_claim(BenefitAttribution("claim-b", "be1", "project-b", "0.6"))
    summary = registry.summary()
    assert {x["amount"] for x in summary["attributed_amount_by_project_currency"]} == {"40.0", "60.0"}
    assert summary["events"][0]["attributed_weight"] == "1.0"
    with pytest.raises(ValueError, match="exceed 1.0"):
        registry.add_claim(BenefitAttribution("claim-c", "be1", "project-c", "0.01"))


def test_benefit_registry_rejects_duplicate_measurement_and_preserves_scenario_status():
    registry = BenefitAttributionRegistry()
    event = BenefitEvent("be1", "measurement-1", "enterprise-1", "2026-Q4",
        "OUTPUT_GAIN", Money("20", "KZT"), "counterfactual-1",
        ("scenario:fixture-1",), EvidenceStatus.SCENARIO)
    registry.add_event(event)
    with pytest.raises(ValueError, match="Measurement already registered"):
        registry.add_event(BenefitEvent("be2", "measurement-1", "enterprise-1", "2026-Q4",
            "OUTPUT_GAIN", Money("20", "KZT"), "counterfactual-2",
            ("scenario:fixture-2",), EvidenceStatus.SCENARIO))
    registry.add_claim(BenefitAttribution("claim-1", "be1", "project-a", "1"))
    assert registry.summary()["events"][0]["scenario_is_not_observed_cash"]


def test_journal_rejects_missing_wrong_direction_or_wrong_value_fx_rate():
    journal = new_journal()
    now = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)
    foreign_line = JournalLine("fx-debit", "cash", "DEBIT", Money("2", "EUR"),
        Money("2.2", "USD"), "co1", "bank:fx", fx_rate_ref="EURUSD")
    balancing_line = JournalLine("fx-credit", "revenue", "CREDIT", Money("2.2", "USD"),
        Money("2.2", "USD"), "co1", "sale:fx")
    missing = JournalEntry("fx-missing", date(2026, 11, 6), now, "USD",
        (foreign_line, balancing_line), "event-missing", "idem-missing", "Missing FX")
    with pytest.raises(ValueError, match="Unknown FX rate"):
        journal.post(missing)

    journal.add_fx_rate(FXRate("EURUSD", "EUR", "USD", "1.1", now, "feed:1"))
    wrong_direction = Journal("USD")
    wrong_direction.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    wrong_direction.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    wrong_direction.add_fx_rate(FXRate("USDEUR", "USD", "EUR", "0.9", now, "feed:2"))
    wrong_direction_line = JournalLine("fx-debit-wrong-direction", "cash", "DEBIT",
        Money("2", "EUR"), Money("2.2", "USD"), "co1", "bank:fx", fx_rate_ref="USDEUR")
    wrong = JournalEntry("fx-wrong-direction", date(2026, 11, 6), now, "USD",
        (wrong_direction_line, balancing_line), "event-direction", "idem-direction", "Wrong direction")
    with pytest.raises(ValueError, match="direction"):
        wrong_direction.post(wrong)

    bad_value = JournalEntry("fx-bad-value", date(2026, 11, 6), now, "USD",
        (JournalLine("fx-debit-2", "cash", "DEBIT", Money("2", "EUR"),
                     Money("2.3", "USD"), "co1", "bank:fx", fx_rate_ref="EURUSD"),
         balancing_line),
        "event-value", "idem-value", "Wrong FX valuation")
    with pytest.raises(ValueError, match="does not match"):
        journal.post(bad_value)


def test_intercompany_reconciliation_eliminates_only_reciprocal_amounts():
    rows = [
        IntercompanyRecord("r1", "tx1", "seller", "buyer", "SELLER_REVENUE", Money("100", "USD"), "2026-Q4", "erp:sale"),
        IntercompanyRecord("e1", "tx1", "buyer", "seller", "BUYER_EXPENSE", Money("100", "USD"), "2026-Q4", "erp:purchase"),
        IntercompanyRecord("ar1", "tx1", "seller", "buyer", "SELLER_RECEIVABLE", Money("60", "USD"), "2026-Q4", "erp:ar"),
        IntercompanyRecord("ap1", "tx1", "buyer", "seller", "BUYER_PAYABLE", Money("55", "USD"), "2026-Q4", "erp:ap"),
        IntercompanyRecord("ci1", "tx1", "seller", "buyer", "SELLER_CASH_IN", Money("40", "USD"), "2026-Q4", "bank:in"),
        IntercompanyRecord("co1", "tx1", "buyer", "seller", "BUYER_CASH_OUT", Money("40", "USD"), "2026-Q4", "bank:out"),
    ]
    result = reconcile_intercompany(rows)
    tx = result["transactions"][0]
    assert tx["eliminations"]["P_AND_L"] == "100"
    assert tx["eliminations"]["BALANCE_SHEET"] == "55"
    assert tx["eliminations"]["CASH_TRANSFER"] == "40"
    assert not result["complete"]
    assert result["exceptions"][0]["seller_unmatched"] == "5"


def test_intercompany_reconciliation_rejects_mixed_currency_and_wrong_counterparty():
    mixed = [
        IntercompanyRecord("r1", "tx1", "seller", "buyer", "SELLER_REVENUE", Money("10", "USD"), "2026-Q4", "sale"),
        IntercompanyRecord("e1", "tx1", "buyer", "seller", "BUYER_EXPENSE", Money("10", "KZT"), "2026-Q4", "purchase"),
    ]
    with pytest.raises(ValueError, match="mixes currencies"):
        reconcile_intercompany(mixed)

    wrong = [
        IntercompanyRecord("r2", "tx2", "seller", "other", "SELLER_REVENUE", Money("10", "USD"), "2026-Q4", "sale"),
        IntercompanyRecord("e2", "tx2", "buyer", "seller", "BUYER_EXPENSE", Money("10", "USD"), "2026-Q4", "purchase"),
    ]
    with pytest.raises(ValueError, match="Counterparty mismatch"):
        reconcile_intercompany(wrong)


def test_intercompany_reconciliation_rejects_duplicate_record_ids():
    row = IntercompanyRecord("r1", "tx1", "seller", "buyer", "SELLER_REVENUE", Money("10", "USD"), "2026-Q4", "sale")
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile_intercompany([row, row])


def test_intercompany_reconciliation_does_not_net_across_periods():
    rows = [
        IntercompanyRecord("r1", "tx-period", "seller", "buyer", "SELLER_REVENUE", Money("100", "USD"), "2026-Q4", "sale"),
        IntercompanyRecord("e1", "tx-period", "buyer", "seller", "BUYER_EXPENSE", Money("100", "USD"), "2027-Q1", "purchase"),
    ]
    result = reconcile_intercompany(rows)
    assert not result["complete"]
    assert len(result["exceptions"]) == 2
    assert result["transactions"][0]["eliminations"]["P_AND_L"] == "0"


def test_intercompany_reconciliation_reports_missing_reciprocal_side():
    rows = [
        IntercompanyRecord("r1", "tx-missing", "seller", "buyer", "SELLER_REVENUE",
                           Money("25", "USD"), "2026-Q4", "erp:sale"),
    ]
    result = reconcile_intercompany(rows)
    assert not result["complete"]
    assert result["transactions"][0]["eliminations"]["P_AND_L"] == "0"
    assert result["exceptions"][0]["seller_unmatched"] == "25"
    assert result["exceptions"][0]["buyer_unmatched"] == "0"


def test_bank_reconciliation_matches_statement_lines_to_cash_journal():
    journal = new_journal()
    journal.add_account(account("opex", "6000", AccountType.EXPENSE, NormalBalance.DEBIT))
    now = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
    sale = JournalEntry("bank-sale", date(2026, 11, 6), now, "USD",
        (JournalLine("cash-in", "cash", "DEBIT", Money("50", "USD"), Money("50", "USD"), "co1", "bank:in"),
         JournalLine("rev", "revenue", "CREDIT", Money("50", "USD"), Money("50", "USD"), "co1", "sale:1")),
        "evt-sale", "idem-sale", "External receipt")
    expense = JournalEntry("bank-opex", date(2026, 11, 6), now, "USD",
        (JournalLine("expense", "opex", "DEBIT", Money("20", "USD"), Money("20", "USD"), "co1", "bill:1"),
         JournalLine("cash-out", "cash", "CREDIT", Money("20", "USD"), Money("20", "USD"), "co1", "bank:out")),
        "evt-opex", "idem-opex", "Operating payment")
    journal.post(sale)
    journal.post(expense)
    period = EconomicPeriod("2026-11", date(2026, 11, 1), date(2026, 11, 30))
    statement = BankStatement("stmt1", "cash", "USD", period, Money("100", "USD"),
        Money("130", "USD"), Money("100", "USD"),
        (BankStatementLine("b1", date(2026, 11, 6), Money("50", "USD"), "bank:1", "statement:1"),
         BankStatementLine("b2", date(2026, 11, 6), Money("-20", "USD"), "bank:2", "statement:2")))
    allocations = [
        BankAllocation("a1", "b1", "bank-sale", "cash-in", Money("50", "USD"), "allocation:1"),
        BankAllocation("a2", "b2", "bank-opex", "cash-out", Money("20", "USD"), "allocation:2"),
    ]
    result = reconcile_bank_account(journal, statement, allocations)
    assert result["fully_reconciled"]
    assert result["bank_closing_balance"] == result["ledger_closing_balance"] == "130"


def test_bank_reconciliation_preserves_unmatched_cash_and_closing_difference():
    journal = new_journal()
    now = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
    sale = JournalEntry("bank-sale", date(2026, 11, 6), now, "USD",
        (JournalLine("cash-in", "cash", "DEBIT", Money("45", "USD"), Money("45", "USD"), "co1", "bank:in"),
         JournalLine("rev", "revenue", "CREDIT", Money("45", "USD"), Money("45", "USD"), "co1", "sale:1")),
        "evt-sale", "idem-sale", "External receipt")
    journal.post(sale)
    period = EconomicPeriod("2026-11", date(2026, 11, 1), date(2026, 11, 30))
    statement = BankStatement("stmt2", "cash", "USD", period, Money("100", "USD"),
        Money("150", "USD"), Money("100", "USD"),
        (BankStatementLine("b1", date(2026, 11, 6), Money("50", "USD"), "bank:1", "statement:1"),))
    result = reconcile_bank_account(journal, statement, [
        BankAllocation("a1", "b1", "bank-sale", "cash-in", Money("45", "USD"), "allocation:1")
    ])
    assert not result["fully_reconciled"]
    assert result["bank_minus_ledger_closing_difference"] == "5"
    assert result["unmatched_statement_lines"][0]["signed_unmatched_amount"] == "5"


def test_bank_statement_rejects_invalid_opening_movement_closing_identity():
    period = EconomicPeriod("2026-11", date(2026, 11, 1), date(2026, 11, 30))
    with pytest.raises(ValueError, match="does not equal closing"):
        BankStatement("bad", "cash", "USD", period, Money("100", "USD"),
            Money("140", "USD"), Money("100", "USD"),
            (BankStatementLine("b1", date(2026, 11, 6), Money("50", "USD"), "bank:1", "statement:1"),))


def test_intercompany_eliminations_post_balanced_journal_entries():
    journal = Journal("USD")
    journal.add_account(account("seller-revenue", "4100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("buyer-expense", "5100", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_account(account("seller-ar", "1200", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("buyer-ap", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    rows = [
        IntercompanyRecord("r1", "tx-elim", "seller", "buyer", "SELLER_REVENUE",
            Money("100", "USD"), "2026-Q4", "erp:sale", "seller-revenue"),
        IntercompanyRecord("e1", "tx-elim", "buyer", "seller", "BUYER_EXPENSE",
            Money("100", "USD"), "2026-Q4", "erp:purchase", "buyer-expense"),
        IntercompanyRecord("ar1", "tx-elim", "seller", "buyer", "SELLER_RECEIVABLE",
            Money("60", "USD"), "2026-Q4", "erp:ar", "seller-ar"),
        IntercompanyRecord("ap1", "tx-elim", "buyer", "seller", "BUYER_PAYABLE",
            Money("55", "USD"), "2026-Q4", "erp:ap", "buyer-ap"),
        IntercompanyRecord("ci1", "tx-elim", "seller", "buyer", "SELLER_CASH_IN",
            Money("30", "USD"), "2026-Q4", "bank:in"),
        IntercompanyRecord("co1", "tx-elim", "buyer", "seller", "BUYER_CASH_OUT",
            Money("30", "USD"), "2026-Q4", "bank:out"),
    ]
    result = post_intercompany_eliminations(
        journal, rows, {"2026-Q4": date(2026, 12, 31)},
        datetime(2026, 12, 31, 23, tzinfo=timezone.utc), "consol-event", "consol-idem",
    )
    assert result["posted_entry_count"] == 2
    assert result["cash_flow_eliminations_by_currency"] == {"USD": "30"}
    trial = journal.trial_balance()
    assert trial["balanced"]
    assert trial["total_debits"] == trial["total_credits"] == "155"


def test_intercompany_elimination_refuses_unmapped_period_and_wrong_accounts():
    journal = Journal("USD")
    journal.add_account(account("seller-revenue", "4100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("buyer-expense", "5100", AccountType.EXPENSE, NormalBalance.DEBIT))
    rows = [
        IntercompanyRecord("r1", "tx-elim", "seller", "buyer", "SELLER_REVENUE",
            Money("10", "USD"), "2026-Q4", "erp:sale", "seller-revenue"),
        IntercompanyRecord("e1", "tx-elim", "buyer", "seller", "BUYER_EXPENSE",
            Money("10", "USD"), "2026-Q4", "erp:purchase", "buyer-expense"),
    ]
    with pytest.raises(ValueError, match="Missing effective date"):
        post_intercompany_eliminations(journal, rows, {}, datetime(2026, 12, 31, tzinfo=timezone.utc),
            "event", "idem")

    wrong_accounts = Journal("USD")
    wrong_accounts.add_account(account("seller-revenue", "4100", AccountType.REVENUE, NormalBalance.CREDIT))
    wrong_accounts.add_account(account("buyer-expense", "5100", AccountType.REVENUE, NormalBalance.CREDIT))
    with pytest.raises(ValueError, match="revenue debit and expense credit"):
        post_intercompany_eliminations(wrong_accounts, rows, {"2026-Q4": date(2026, 12, 31)},
            datetime(2026, 12, 31, tzinfo=timezone.utc), "event-wrong", "idem-wrong")
