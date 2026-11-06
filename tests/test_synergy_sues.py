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
    PhysicalFlow, summarize_physical_flows,
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
