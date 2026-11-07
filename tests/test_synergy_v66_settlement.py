import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.network import make_environment, simulate
from synergy_v66.settlement import replay_settlement


def physical():
    return simulate(make_environment(2026, 30, "volatile"))


def test_settlement_cash_conservation_and_internal_transfer_elimination():
    result = replay_settlement(physical())
    assert abs(result["cash_conservation_error"]) < 1e-7
    assert abs(result["internal_settlement_net_system"]) < 1e-9
    assert abs(result["internal_transfer_cash_in"] - result["internal_transfer_cash_out"]) < 1e-9
    assert abs(result["internal_invoice_receivables_outstanding"] - result["internal_invoice_payables_outstanding"]) < 1e-7


def test_customer_receipts_are_delayed_and_ar_reconciles():
    result = replay_settlement(physical(), customer_terms_days=2)
    assert result["daily_ledger"][0]["external_customer_collections"] == 0.0
    assert result["external_customer_collections"] <= result["external_sales_accrued"] + 1e-9
    assert result["customer_receivables_outstanding"] >= -1e-9
    assert abs(result["external_sales_accrued"] - result["external_customer_collections"] - result["customer_receivables_outstanding"]) < 1e-7


def test_working_capital_shortfall_is_reported_not_hidden():
    result = replay_settlement(physical(), initial_cash_per_cell=0.0, customer_terms_days=5, supplier_terms_days=0)
    assert result["peak_unfunded_working_capital"] > 0.0
    assert result["closing_cash"] == pytest.approx(result["external_customer_collections"] - result["external_supplier_payments"])


def test_invalid_terms_and_missing_audit_are_rejected():
    with pytest.raises(ValueError):
        replay_settlement(physical(), customer_terms_days=-1)
    with pytest.raises(ValueError):
        replay_settlement({"days": 2})


def test_integrated_credit_result_cannot_be_replayed_as_legacy_settlement():
    result = physical()
    result["credit_constrained"] = True
    with pytest.raises(ValueError, match="already contain the integrated cash ledger"):
        replay_settlement(result)
