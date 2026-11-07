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
    BenefitAttribution, BenefitAttributionRegistry, BenefitEvent, FlowBoundary, FlowEvidenceStatus,
    PhysicalFlow, summarize_physical_flows, IntercompanyRecord, IntercompanyRecordType,
    reconcile_intercompany, post_intercompany_eliminations, BankAllocation, BankStatement, BankStatementLine,
    reconcile_bank_account, TranslationPolicy, TrialBalanceAccount, translate_trial_balance,
    TradeAccountMap, TradeDocument, TradeSettlement, TradeSide, TradeSubledger,
    InventoryLedger, InventoryMovementType,
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


def test_trial_balance_translation_uses_closing_average_and_historical_rates():
    now = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    policy = TranslationPolicy(
        closing_rate=FXRate("close-eur-usd", "EUR", "USD", "1.1", now, "fx:close"),
        average_rate=FXRate("avg-eur-usd", "EUR", "USD", "1.05", now, "fx:average"),
        historical_equity_rates={
            "capital": FXRate("hist-capital", "EUR", "USD", "1.0", now, "fx:historical")
        },
        reporting_date=date(2026, 11, 6),
        translation_adjustment_account_id="cta",
    )
    rows = [
        TrialBalanceAccount("cash", AccountType.ASSET, Money("100", "EUR"), Money("0", "EUR")),
        TrialBalanceAccount("payable", AccountType.LIABILITY, Money("0", "EUR"), Money("40", "EUR")),
        TrialBalanceAccount("capital", AccountType.EQUITY, Money("0", "EUR"), Money("50", "EUR")),
        TrialBalanceAccount("revenue", AccountType.REVENUE, Money("0", "EUR"), Money("30", "EUR")),
        TrialBalanceAccount("opex", AccountType.EXPENSE, Money("20", "EUR"), Money("0", "EUR")),
    ]
    result = translate_trial_balance(rows, policy, "USD")
    assert result["balanced"]
    assert result["total_debits"] == result["total_credits"] == "131.00"
    assert result["translation_adjustment"]["credit"] == "5.50"
    assert result["translation_is_not_operating_profit"]


def test_trial_balance_translation_rejects_missing_historical_rate_and_future_rate():
    now = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    base = TranslationPolicy(
        closing_rate=FXRate("close", "EUR", "USD", "1.1", now, "fx:close"),
        average_rate=FXRate("avg", "EUR", "USD", "1.05", now, "fx:avg"),
        historical_equity_rates={},
        reporting_date=date(2026, 11, 6),
        translation_adjustment_account_id="cta",
    )
    equity = [TrialBalanceAccount("capital", AccountType.EQUITY, Money("0", "EUR"), Money("10", "EUR"))]
    with pytest.raises(ValueError, match="Missing historical FX"):
        translate_trial_balance(equity, base, "USD")

    future_policy = TranslationPolicy(
        closing_rate=FXRate("future", "EUR", "USD", "1.1",
            datetime(2026, 11, 7, 10, tzinfo=timezone.utc), "fx:future"),
        average_rate=FXRate("avg", "EUR", "USD", "1.05", now, "fx:avg"),
        historical_equity_rates={"capital": FXRate("hist", "EUR", "USD", "1.0", now, "fx:hist")},
        reporting_date=date(2026, 11, 6),
        translation_adjustment_account_id="cta",
    )
    with pytest.raises(ValueError, match="post-date"):
        translate_trial_balance(equity, future_policy, "USD")


def test_trade_subledger_posts_invoices_and_settlements_to_balanced_gl():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ap", "2000", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("purchases", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    docs = [
        TradeDocument("inv-ar", TradeSide.RECEIVABLE, "co1", "customer1",
            date(2026, 11, 1), date(2026, 11, 30), Money("100", "USD"), "invoice:ar"),
        TradeDocument("inv-ap", TradeSide.PAYABLE, "co1", "supplier1",
            date(2026, 11, 2), date(2026, 11, 20), Money("80", "USD"), "invoice:ap"),
    ]
    settlements = [
        TradeSettlement("settle-ar", "inv-ar", date(2026, 11, 6), Money("30", "USD"), "cash", "bank:ar"),
        TradeSettlement("settle-ap", "inv-ap", date(2026, 11, 6), Money("20", "USD"), "cash", "bank:ap"),
    ]
    subledger = TradeSubledger(docs, settlements)
    projection = subledger.project(date(2026, 11, 6))
    assert projection["totals_by_side_currency"] == {
        "PAYABLE::USD": "60", "RECEIVABLE::USD": "70"
    }
    result = subledger.post_to_journal(
        journal,
        TradeAccountMap("ar", "revenue", "ap", "purchases"),
        datetime(2026, 11, 6, 12, tzinfo=timezone.utc),
    )
    assert result["trade_subledger_delta_matches_journal_control_accounts"]
    assert result["expected_ar_control_delta"] == result["actual_ar_control_delta"] == "70"
    assert result["expected_ap_credit_control_delta"] == result["actual_ap_credit_control_delta"] == "60"
    assert journal.trial_balance()["balanced"]


def test_trade_subledger_rejects_over_settlement_and_wrong_cash_account():
    docs = [TradeDocument("inv", TradeSide.RECEIVABLE, "co1", "customer",
        date(2026, 11, 1), date(2026, 11, 30), Money("10", "USD"), "invoice:1")]
    settlements = [TradeSettlement("s1", "inv", date(2026, 11, 2), Money("11", "USD"), "cash", "bank:1")]
    subledger = TradeSubledger(docs, settlements)
    with pytest.raises(ValueError, match="exceeds open balance"):
        subledger.project(date(2026, 11, 3))


def test_trade_subledger_foreign_currency_posting_uses_dated_fx_for_each_event():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ap", "2000", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("purchases", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_account(account("fx-gain", "7100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("fx-loss", "8100", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_fx_rate(FXRate("eurusd-invoice", "EUR", "USD", "1.1",
        datetime(2026, 11, 1, 12, tzinfo=timezone.utc), "fx:invoice"))
    journal.add_fx_rate(FXRate("eurusd-settlement", "EUR", "USD", "1.2",
        datetime(2026, 11, 6, 12, tzinfo=timezone.utc), "fx:settlement"))
    subledger = TradeSubledger(
        [TradeDocument("inv-eur", TradeSide.RECEIVABLE, "co1", "customer",
            date(2026, 11, 1), date(2026, 11, 30), Money("100", "EUR"), "invoice:eur")],
        [TradeSettlement("settle-eur", "inv-eur", date(2026, 11, 6),
            Money("20", "EUR"), "cash", "bank:eur")],
    )
    result = subledger.post_to_journal(
        journal, TradeAccountMap("ar", "revenue", "ap", "purchases", "fx-gain", "fx-loss"),
        datetime(2026, 11, 6, 13, tzinfo=timezone.utc),
        {"invoice:eur": "eurusd-invoice", "bank:eur": "eurusd-settlement"},
    )
    assert result["expected_ar_control_delta"] == "88.0"
    assert result["actual_ar_control_delta"] == "88.0"
    assert journal.trial_balance()["accounts"]["fx-gain"]["credit"] == "2.0"
    assert journal.trial_balance()["balanced"]


def test_journal_can_enforce_single_entity_ownership():
    journal = Journal("USD", entity_id="co1")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.post(entry("entity-ok", "entity-idem"))
    cross_entity = JournalEntry(
        "entity-cross", date(2026, 11, 6), datetime(2026, 11, 6, tzinfo=timezone.utc), "USD",
        (
            JournalLine("x1", "cash", "DEBIT", Money("1", "USD"), Money("1", "USD"), "co2", "bank:x"),
            JournalLine("x2", "revenue", "CREDIT", Money("1", "USD"), Money("1", "USD"), "co2", "sale:x"),
        ),
        "event-cross", "idem-cross", "Cross-entity posting",
    )
    with pytest.raises(ValueError, match="entity_id"):
        journal.post(cross_entity)


def test_journal_post_many_is_atomic_when_later_entry_is_invalid():
    journal = new_journal()
    good = entry("batch-good", "batch-good-idem", "10")
    bad = JournalEntry(
        "batch-bad", date(2026, 11, 6), datetime(2026, 11, 6, tzinfo=timezone.utc), "USD",
        (
            JournalLine("bad-dr", "cash", "DEBIT", Money("10", "USD"), Money("10", "USD"), "co1", "bank:bad"),
            JournalLine("bad-cr", "revenue", "CREDIT", Money("9", "USD"), Money("9", "USD"), "co1", "sale:bad"),
        ),
        "event-bad", "batch-bad-idem", "Invalid batch entry",
    )
    with pytest.raises(ValueError, match="Unbalanced"):
        journal.post_many([good, bad])
    assert journal.entries == ()
    journal.post(good)
    assert len(journal.entries) == 1


def test_trade_subledger_batch_is_atomic_when_later_fx_evidence_is_invalid():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ap", "2000", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("purchases", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_account(account("fx-gain", "7100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("fx-loss", "8100", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_fx_rate(FXRate("valid-invoice-rate", "EUR", "USD", "1.1",
        datetime(2026, 11, 1, 12, tzinfo=timezone.utc), "fx:invoice"))
    journal.add_fx_rate(FXRate("future-settlement-rate", "EUR", "USD", "1.2",
        datetime(2026, 11, 7, 12, tzinfo=timezone.utc), "fx:future-settlement"))
    subledger = TradeSubledger(
        [TradeDocument("inv-atomic", TradeSide.RECEIVABLE, "co1", "customer",
            date(2026, 11, 1), date(2026, 11, 30), Money("100", "EUR"), "invoice:atomic")],
        [TradeSettlement("settle-atomic", "inv-atomic", date(2026, 11, 6),
            Money("20", "EUR"), "cash", "bank:atomic")],
    )
    with pytest.raises(ValueError, match="post-date"):
        subledger.post_to_journal(
            journal, TradeAccountMap("ar", "revenue", "ap", "purchases", "fx-gain", "fx-loss"),
            datetime(2026, 11, 7, 13, tzinfo=timezone.utc),
            {"invoice:atomic": "valid-invoice-rate", "bank:atomic": "future-settlement-rate"},
        )
    assert journal.entries == ()


def test_fifo_inventory_issues_oldest_lots_and_preserves_quantity_value():
    ledger = InventoryLedger("USD")
    ledger.receive("r1", "lot-1", "steel", "warehouse-a", Quantity("10", "tonne"),
        Money("100", "USD"), date(2026, 11, 1), "receipt:1")
    ledger.receive("r2", "lot-2", "steel", "warehouse-a", Quantity("10", "tonne"),
        Money("150", "USD"), date(2026, 11, 2), "receipt:2")
    issue = ledger.issue("issue-1", "steel", "warehouse-a", Quantity("12", "tonne"),
        date(2026, 11, 3), "production:1")
    assert issue.cost == Money("130", "USD")
    assert [(x.lot_id, x.quantity.amount, x.cost.amount) for x in issue.lot_allocations] == [
        ("lot-1", Decimal("10"), Decimal("100")),
        ("lot-2", Decimal("2"), Decimal("30")),
    ]
    pool = ledger.summary()["pools"][0]
    assert pool["quantity"] == "8"
    assert pool["inventory_cost"] == "120"


def test_fifo_inventory_transfer_preserves_cost_and_rejects_mutating_failures():
    ledger = InventoryLedger("USD")
    ledger.receive("r1", "lot-1", "copper", "warehouse-a", Quantity("10", "kg"),
        Money("100", "USD"), date(2026, 11, 1), "receipt:1")
    ledger.receive("r2", "transfer-1:LOT:1", "copper", "warehouse-b", Quantity("1", "kg"),
        Money("10", "USD"), date(2026, 11, 1), "receipt:collision")
    before = ledger.summary()
    with pytest.raises(ValueError, match="Duplicate destination lot ID"):
        ledger.transfer("transfer-1", "copper", "warehouse-a", "warehouse-b",
            Quantity("5", "kg"), date(2026, 11, 2), "transfer:1")
    assert ledger.summary() == before

    out_move, in_move = ledger.transfer("transfer-2", "copper", "warehouse-a", "warehouse-b",
        Quantity("4", "kg"), date(2026, 11, 3), "transfer:2")
    assert out_move.cost == in_move.cost == Money("40", "USD")
    assert out_move.lot_allocations == in_move.lot_allocations
    assert out_move.lot_allocations[0].lot_id == "lot-1"
    assert out_move.lot_allocations[0].destination_lot_id == "transfer-2:LOT:1"
    pools = {row["location_id"]: row for row in ledger.summary()["pools"]}
    assert pools["warehouse-a"]["quantity"] == "6"
    assert pools["warehouse-a"]["inventory_cost"] == "60"
    assert pools["warehouse-b"]["quantity"] == "5"
    assert pools["warehouse-b"]["inventory_cost"] == "50"


def test_fifo_inventory_rejects_insufficient_stock_without_mutation_and_mixed_units():
    ledger = InventoryLedger("USD")
    ledger.receive("r1", "lot-1", "grain", "silo-a", Quantity("5", "tonne"),
        Money("25", "USD"), date(2026, 11, 1), "receipt:grain")
    before = ledger.summary()
    with pytest.raises(ValueError, match="Insufficient inventory"):
        ledger.issue("issue-too-large", "grain", "silo-a", Quantity("6", "tonne"),
            date(2026, 11, 2), "production:too-large")
    assert ledger.summary() == before
    with pytest.raises(ValueError, match="cannot mix units"):
        ledger.receive("r2", "lot-2", "grain", "silo-a", Quantity("1", "MWh"),
            Money("5", "USD"), date(2026, 11, 2), "receipt:wrong-unit")


def test_fifo_inventory_movements_post_to_balanced_journal():
    ledger = InventoryLedger("USD", entity_id="co1")
    receipt = ledger.receive("r1", "lot-1", "components", "factory",
        Quantity("10", "unit"), Money("100", "USD"), date(2026, 11, 1), "receipt:components")
    issue = ledger.issue("i1", "components", "factory", Quantity("4", "unit"),
        date(2026, 11, 2), "production:components")
    transfer = ledger.transfer("t1", "components", "factory", "line-2",
        Quantity("2", "unit"), date(2026, 11, 3), "transfer:components")

    journal = Journal("USD", entity_id="co1")
    journal.add_account(account("inventory", "1300", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("wip", "1400", AccountType.ASSET, NormalBalance.DEBIT))
    assert ledger.post_to_journal(receipt.movement_id, journal, "inventory", "grni", "co1",
        datetime(2026, 11, 4, tzinfo=timezone.utc)) is not None
    assert ledger.post_to_journal(issue.movement_id, journal, "inventory", "wip", "co1",
        datetime(2026, 11, 4, tzinfo=timezone.utc)) is not None
    assert ledger.post_to_journal(transfer[0].movement_id, journal, "inventory", "wip", "co1",
        datetime(2026, 11, 4, tzinfo=timezone.utc)) is None
    assert journal.trial_balance()["balanced"]
    assert journal.trial_balance()["total_debits"] == journal.trial_balance()["total_credits"] == "140"
    assert [x.movement_type for x in ledger.movements].count(InventoryMovementType.TRANSFER_OUT) == 1


def test_calendar_date_contracts_reject_datetime_subclasses():
    timestamp = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="calendar date"):
        EconomicPeriod("bad-period", timestamp, date(2026, 11, 30))
    with pytest.raises(ValueError, match="calendar date"):
        EconomicPeriod("bad-period-value", date(2026, 11, 1), date(2026, 11, 30)).contains(timestamp)
    with pytest.raises(ValueError, match="calendar date"):
        BankStatementLine("bad-bank-line", timestamp, Money("1", "USD"), "bank:1", "statement:1")


def test_fifo_inventory_never_consumes_lots_received_after_issue_date():
    ledger = InventoryLedger("USD")
    ledger.receive("future-receipt", "future-lot", "steel", "warehouse",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 5), "receipt:future")
    with pytest.raises(ValueError, match="Insufficient inventory"):
        ledger.issue("premature-issue", "steel", "warehouse", Quantity("1", "kg"),
            date(2026, 11, 4), "production:premature")
    # The rejected historical issue must not consume the later receipt.
    assert ledger.summary()["pools"][0]["quantity"] == "10"
    issue = ledger.issue("valid-issue", "steel", "warehouse", Quantity("1", "kg"),
        date(2026, 11, 6), "production:valid")
    assert issue.cost == Money("10", "USD")
    assert ledger.summary()["pools"][0]["quantity"] == "9"


def test_money_and_quantity_reject_binary_floats():
    with pytest.raises(ValueError, match="binary floats"):
        Money(0.1, "USD")
    with pytest.raises(ValueError, match="binary floats"):
        Quantity(1.25, "kg")
    with pytest.raises(ValueError, match="binary floats"):
        Money("1", "USD").scale(0.1)


def test_journal_rejects_duplicate_source_event_even_with_new_entry_and_idempotency_ids():
    journal = new_journal()
    first = entry("source-event-first", "source-event-key-first")
    journal.post(first)
    duplicate_source = JournalEntry(
        "source-event-second", first.effective_date, first.recorded_at, first.functional_currency,
        first.lines, first.source_event_id, "source-event-key-second", "Replay same source event",
    )
    with pytest.raises(ValueError, match="Duplicate source_event_id"):
        journal.post(duplicate_source)
    assert len(journal.entries) == 1


def test_journal_line_freezes_mutable_evidence_id_input():
    evidence = ["meter:reading-1"]
    line = JournalLine(
        "evidence-line", "cash", "DEBIT", Money("1", "USD"), Money("1", "USD"),
        "co1", "bank:1", evidence_ids=evidence,
    )
    evidence.append("attacker:injected")
    assert line.evidence_ids == ("meter:reading-1",)


def test_trade_subledger_requires_realized_fx_account_for_currency_difference():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ap", "2000", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("purchases", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_fx_rate(FXRate("invoice-rate", "EUR", "USD", "1.1",
        datetime(2026, 11, 1, tzinfo=timezone.utc), "fx:invoice"))
    journal.add_fx_rate(FXRate("settlement-rate", "EUR", "USD", "1.2",
        datetime(2026, 11, 6, tzinfo=timezone.utc), "fx:settlement"))
    subledger = TradeSubledger(
        [TradeDocument("fx-invoice", TradeSide.RECEIVABLE, "co1", "customer",
            date(2026, 11, 1), date(2026, 11, 30), Money("100", "EUR"), "invoice:fx")],
        [TradeSettlement("fx-settlement", "fx-invoice", date(2026, 11, 6),
            Money("20", "EUR"), "cash", "bank:fx")],
    )
    with pytest.raises(ValueError, match="Realized FX gain account is required"):
        subledger.post_to_journal(
            journal, TradeAccountMap("ar", "revenue", "ap", "purchases"),
            datetime(2026, 11, 6, 13, tzinfo=timezone.utc),
            {"invoice:fx": "invoice-rate", "bank:fx": "settlement-rate"},
        )


def test_trade_documents_reject_datetime_in_calendar_date_fields():
    with pytest.raises(ValueError, match="calendar date"):
        TradeDocument("bad-date", TradeSide.RECEIVABLE, "co1", "customer",
            datetime(2026, 11, 1, tzinfo=timezone.utc), date(2026, 11, 30),
            Money("10", "USD"), "invoice:bad-date")


def test_trade_payable_settlement_posts_realized_fx_loss_against_invoice_carrying_value():
    journal = Journal("USD")
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("ar", "1100", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("revenue", "4000", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("ap", "2000", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("purchases", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_account(account("fx-gain", "7100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("fx-loss", "8100", AccountType.EXPENSE, NormalBalance.DEBIT))
    journal.add_fx_rate(FXRate("ap-invoice-rate", "EUR", "USD", "1.1",
        datetime(2026, 11, 1, 12, tzinfo=timezone.utc), "fx:ap-invoice"))
    journal.add_fx_rate(FXRate("ap-settlement-rate", "EUR", "USD", "1.2",
        datetime(2026, 11, 6, 12, tzinfo=timezone.utc), "fx:ap-settlement"))
    subledger = TradeSubledger(
        [TradeDocument("ap-eur", TradeSide.PAYABLE, "co1", "supplier",
            date(2026, 11, 1), date(2026, 11, 30), Money("100", "EUR"), "invoice:ap-eur")],
        [TradeSettlement("ap-settle-eur", "ap-eur", date(2026, 11, 6),
            Money("20", "EUR"), "cash", "bank:ap-eur")],
    )
    result = subledger.post_to_journal(
        journal, TradeAccountMap("ar", "revenue", "ap", "purchases", "fx-gain", "fx-loss"),
        datetime(2026, 11, 6, 13, tzinfo=timezone.utc),
        {"invoice:ap-eur": "ap-invoice-rate", "bank:ap-eur": "ap-settlement-rate"},
    )
    assert result["expected_ap_credit_control_delta"] == "88.0"
    assert result["actual_ap_credit_control_delta"] == "88.0"
    trial = journal.trial_balance()
    assert trial["accounts"]["fx-loss"]["debit"] == "2.0"
    assert trial["balanced"]


def test_intercompany_elimination_date_must_fall_inside_canonical_period():
    journal = Journal("USD")
    journal.add_account(account("seller-revenue", "4100", AccountType.REVENUE, NormalBalance.CREDIT))
    journal.add_account(account("buyer-expense", "5100", AccountType.EXPENSE, NormalBalance.DEBIT))
    rows = [
        IntercompanyRecord("period-r", "period-tx", "seller", "buyer", "SELLER_REVENUE",
            Money("10", "USD"), "2026-Q4", "erp:sale", "seller-revenue"),
        IntercompanyRecord("period-e", "period-tx", "buyer", "seller", "BUYER_EXPENSE",
            Money("10", "USD"), "2026-Q4", "erp:purchase", "buyer-expense"),
    ]
    with pytest.raises(ValueError, match="falls outside period"):
        post_intercompany_eliminations(
            journal, rows, {"2026-Q4": date(2027, 1, 15)},
            datetime(2027, 1, 15, tzinfo=timezone.utc), "period-event", "period-idem",
        )
    assert journal.entries == ()


def test_inventory_gl_posting_requires_owner_and_is_single_journal_only():
    unbound = InventoryLedger("USD")
    unbound.receive("unbound-receipt", "unbound-lot", "steel", "factory",
        Quantity("1", "kg"), Money("10", "USD"), date(2026, 11, 1), "receipt:unbound")
    journal = Journal("USD", entity_id="co1")
    journal.add_account(account("inventory", "1300", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    with pytest.raises(ValueError, match="bound to an entity"):
        unbound.post_to_journal("unbound-receipt", journal, "inventory", "grni", "co1",
            datetime(2026, 11, 2, tzinfo=timezone.utc))

    ledger = InventoryLedger("USD", entity_id="co1")
    receipt = ledger.receive("owned-receipt", "owned-lot", "steel", "factory",
        Quantity("1", "kg"), Money("10", "USD"), date(2026, 11, 1), "receipt:owned")
    ledger.post_to_journal(receipt.movement_id, journal, "inventory", "grni", "co1",
        datetime(2026, 11, 2, tzinfo=timezone.utc))
    other_journal = Journal("USD", entity_id="co1")
    other_journal.add_account(account("inventory", "1300", AccountType.ASSET, NormalBalance.DEBIT))
    other_journal.add_account(account("grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    with pytest.raises(ValueError, match="already journalized"):
        ledger.post_to_journal(receipt.movement_id, other_journal, "inventory", "grni", "co1",
            datetime(2026, 11, 2, tzinfo=timezone.utc))


def test_inventory_ledger_rejects_cross_entity_journal_posting():
    ledger = InventoryLedger("USD", entity_id="co1")
    receipt = ledger.receive("cross-entity-receipt", "cross-entity-lot", "steel", "factory",
        Quantity("1", "kg"), Money("10", "USD"), date(2026, 11, 1), "receipt:cross-entity")
    journal = Journal("USD", entity_id="co2")
    journal.add_account(account("inventory", "1300", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    with pytest.raises(ValueError, match="ownership mismatch"):
        ledger.post_to_journal(receipt.movement_id, journal, "inventory", "grni", "co2",
            datetime(2026, 11, 2, tzinfo=timezone.utc))


def test_benefit_registry_rejects_duplicate_enterprise_period_metric_counterfactual_scope():
    registry = BenefitAttributionRegistry()
    registry.add_event(BenefitEvent(
        "benefit-scope-a", "measurement-a", "enterprise-1", "2026-Q4",
        "ENERGY_SAVING", Money("100", "USD"), "baseline-vs-control",
        ["meter:site-a"], EvidenceStatus.VERIFIED,
    ))
    with pytest.raises(ValueError, match="measurement scope already registered"):
        registry.add_event(BenefitEvent(
            "benefit-scope-b", "measurement-b", "enterprise-1", "2026-Q4",
            "ENERGY_SAVING", Money("100", "USD"), "baseline-vs-control",
            ["meter:site-b"], EvidenceStatus.VERIFIED,
        ))
    # Distinct explicit scopes represent separate measured facilities.
    registry.add_event(BenefitEvent(
        "benefit-scope-c", "measurement-c", "enterprise-1", "2026-Q4",
        "ENERGY_SAVING", Money("100", "USD"), "baseline-vs-control",
        ["meter:site-b"], EvidenceStatus.VERIFIED, "facility:site-b",
    ))


def test_benefit_event_freezes_evidence_ids():
    evidence = ["meter:one"]
    event = BenefitEvent(
        "benefit-immutable", "measurement-immutable", "enterprise-1", "2026-Q4",
        "OUTPUT_GAIN", Money("10", "KZT"), "baseline-1", evidence, EvidenceStatus.OBSERVED,
    )
    evidence.append("attacker:injected")
    assert event.evidence_ids == ("meter:one",)


def test_physical_flow_summary_separates_scenario_from_observed_and_verified():
    rows = [
        PhysicalFlow("planned", "factory", "customer", "steel",
            Quantity("10", "tonne"), "2026-Q4", evidence_status=FlowEvidenceStatus.PLANNED),
        PhysicalFlow("scenario", "factory", "customer", "steel",
            Quantity("100", "tonne"), "2026-Q4", evidence_status=FlowEvidenceStatus.SCENARIO),
        PhysicalFlow("observed", "factory", "customer", "steel",
            Quantity("8", "tonne"), "2026-Q4", evidence_id="delivery:8",
            evidence_status=FlowEvidenceStatus.OBSERVED),
        PhysicalFlow("verified", "factory", "customer", "steel",
            Quantity("7", "tonne"), "2026-Q4", evidence_id="acceptance:7",
            evidence_status=FlowEvidenceStatus.VERIFIED),
    ]
    summary = summarize_physical_flows(rows)
    assert len(summary["flows"]) == 4
    assert {row["evidence_status"] for row in summary["flows"]} == {
        "PLANNED", "SCENARIO", "OBSERVED", "VERIFIED"
    }
    assert summary["scenario_and_unverified_flows_are_separated"]


def test_observed_and_verified_physical_flows_require_evidence_ids():
    with pytest.raises(ValueError, match="require evidence_id"):
        PhysicalFlow("observed-no-proof", "factory", "customer", "steel",
            Quantity("1", "tonne"), "2026-Q4", evidence_status=FlowEvidenceStatus.OBSERVED)


def test_inventory_gl_bridge_rejects_semantically_invalid_offset_accounts():
    ledger = InventoryLedger("USD", entity_id="co1")
    receipt = ledger.receive("bad-offset-receipt", "bad-offset-lot", "steel", "factory",
        Quantity("2", "kg"), Money("20", "USD"), date(2026, 11, 1), "receipt:bad-offset")
    journal = Journal("USD", entity_id="co1")
    journal.add_account(account("inventory", "1300", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("cash", "1000", AccountType.ASSET, NormalBalance.DEBIT))
    journal.add_account(account("grni", "2100", AccountType.LIABILITY, NormalBalance.CREDIT))
    journal.add_account(account("cogs", "5000", AccountType.EXPENSE, NormalBalance.DEBIT))
    with pytest.raises(ValueError, match="receipt offset"):
        ledger.post_to_journal(receipt.movement_id, journal, "inventory", "cash", "co1",
            datetime(2026, 11, 2, tzinfo=timezone.utc))
    issue = ledger.issue("bad-offset-issue", "steel", "factory",
        Quantity("1", "kg"), date(2026, 11, 2), "issue:bad-offset")
    with pytest.raises(ValueError, match="issue offset"):
        ledger.post_to_journal(issue.movement_id, journal, "inventory", "grni", "co1",
            datetime(2026, 11, 3, tzinfo=timezone.utc))



def test_calendar_date_contracts_reject_datetime_subclasses():
    from datetime import datetime, timezone
    instant = datetime(2026, 11, 6, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="calendar date"):
        EconomicPeriod("bad", instant, date(2026, 11, 30))
    with pytest.raises(ValueError, match="calendar date"):
        EconomicPeriod("bad", date(2026, 11, 1), instant)
    period = EconomicPeriod("good", date(2026, 11, 1), date(2026, 11, 30))
    with pytest.raises(ValueError, match="calendar date"):
        period.contains(instant)
    with pytest.raises(ValueError, match="calendar date"):
        EvidenceRecord("e-date", "source", EvidenceStatus.OBSERVED, instant,
            instant, None)


def test_inventory_fifo_cannot_consume_a_future_receipt():
    ledger = InventoryLedger("USD", entity_id="co1")
    ledger.receive("future", "future-lot", "steel", "factory",
        Quantity("10", "kg"), Money("100", "USD"), date(2026, 11, 7), "receipt:future")
    with pytest.raises(ValueError, match="Insufficient inventory"):
        ledger.issue("early-issue", "steel", "factory", Quantity("1", "kg"),
            date(2026, 11, 6), "production:early")
    assert ledger.summary()["pools"][0]["quantity"] == "10"
    assert ledger.movements[0].movement_id == "future"


def test_inventory_transfer_cannot_move_a_future_receipt_back_in_time():
    ledger = InventoryLedger("USD", entity_id="co1")
    ledger.receive("future-transfer-source", "future-source-lot", "copper", "warehouse-a",
        Quantity("5", "kg"), Money("50", "USD"), date(2026, 11, 7), "receipt:future-copper")
    with pytest.raises(ValueError, match="Insufficient inventory"):
        ledger.transfer("early-transfer", "copper", "warehouse-a", "warehouse-b",
            Quantity("1", "kg"), date(2026, 11, 6), "transfer:early")
    assert len(ledger.movements) == 1
    assert ledger.summary()["pools"][0]["location_id"] == "warehouse-a"



def test_money_and_quantity_reject_binary_float_inputs():
    with pytest.raises(ValueError, match="float"):
        Money(0.1, "USD")
    with pytest.raises(ValueError, match="float"):
        Quantity(0.1, "kg")
    with pytest.raises(ValueError, match="float"):
        Money("1", "USD").scale(0.1)


def test_calendar_date_contracts_reject_datetime_subclasses():
    with pytest.raises(ValueError, match="calendar date"):
        EconomicPeriod("bad", datetime(2026, 11, 1, tzinfo=timezone.utc), date(2026, 11, 30))
    period = EconomicPeriod("good", date(2026, 11, 1), date(2026, 11, 30))
    with pytest.raises(ValueError, match="calendar date"):
        period.contains(datetime(2026, 11, 6, tzinfo=timezone.utc))


def test_fifo_inventory_excludes_future_receipts_from_historical_availability_and_issue():
    ledger = InventoryLedger("USD")
    ledger.receive("future-r", "future-lot", "steel", "factory",
        Quantity("5", "kg"), Money("50", "USD"), date(2026, 11, 7), "receipt:future")
    assert ledger.available("steel", "factory", "kg", date(2026, 11, 6)) == Quantity("0", "kg")
    assert ledger.available("steel", "factory", "kg") == Quantity("5", "kg")
    before = ledger.summary()
    with pytest.raises(ValueError, match="Insufficient inventory"):
        ledger.issue("early-issue", "steel", "factory", Quantity("1", "kg"),
            date(2026, 11, 6), "production:early")
    assert ledger.summary() == before



def test_journal_reversal_cannot_be_effective_before_original_entry():
    journal = new_journal()
    original = journal.post(entry("dated-original", "dated-original-idem"))
    with pytest.raises(ValueError, match="cannot precede the original"):
        journal.reverse(
            original.entry_id, "dated-reversal",
            date(2026, 11, 5), datetime(2026, 11, 7, 8, tzinfo=timezone.utc),
            "dated-reversal-event", "dated-reversal-idem", "Backdated reversal",
        )
    assert len(journal.entries) == 1
