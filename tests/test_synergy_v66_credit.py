import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.credit import CreditLedger


def test_production_is_rejected_without_cash_or_approved_bank_credit():
    ledger = CreditLedger(initial_cash_per_cell=0.0, bank_limit_per_cell=0.0)
    result = ledger.authorize_production("WEST-MF1", 12.0, day=0)
    assert result == {"authorized": False, "reason": "insufficient_liquidity", "bank_draw": 0.0}
    snap = ledger.snapshot()
    assert snap["cash_by_cell"]["WEST-MF1"] == 0.0
    assert snap["external_supplier_payments"] == 0.0


def test_production_uses_only_approved_bank_line_and_never_negative_cash():
    ledger = CreditLedger(initial_cash_per_cell=5.0, bank_limit_per_cell=10.0)
    result = ledger.authorize_production("WEST-MF1", 12.0, day=0)
    assert result["authorized"] is True
    assert result["bank_draw"] == pytest.approx(7.0)
    snap = ledger.snapshot()
    assert snap["cash_by_cell"]["WEST-MF1"] == pytest.approx(0.0)
    assert snap["bank_debt_by_cell"]["WEST-MF1"] == pytest.approx(7.0)
    assert all(v >= -1e-9 for v in snap["cash_by_cell"].values())
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_mutual_credit_invoice_settles_and_internal_transfer_eliminates():
    ledger = CreditLedger(initial_cash_per_cell=20.0, bank_limit_per_cell=15.0, trade_credit_limit_per_cell=50.0)
    result = ledger.authorize_purchase(
        buyer="WEST-PR1", seller="WEST-AG1", amount=35.0,
        due_day=2, day=0, invoice_id="PO-001",
    )
    assert result["authorized"] is True
    assert result["cash_paid"] == pytest.approx(20.0)
    assert result["trade_credit_extended"] == pytest.approx(15.0)
    assert ledger.accounts["WEST-PR1"].trade_payable == pytest.approx(15.0)
    assert ledger.accounts["WEST-AG1"].trade_receivable == pytest.approx(15.0)
    ledger.process_day(2)
    snap = ledger.snapshot()
    assert ledger.payables["PO-001"].status == "paid"
    assert snap["trade_payable_by_cell"]["WEST-PR1"] == pytest.approx(0.0)
    assert snap["trade_receivable_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert snap["bank_debt_by_cell"]["WEST-PR1"] == pytest.approx(15.0)
    assert snap["internal_transfer_in"] == pytest.approx(35.0)
    assert snap["internal_transfer_out"] == pytest.approx(35.0)
    assert snap["internal_transfer_net"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_trade_credit_limit_blocks_new_purchase():
    ledger = CreditLedger(initial_cash_per_cell=0.0, trade_credit_limit_per_cell=10.0)
    first = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 8.0, 5, 0, "PO-1")
    second = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 3.0, 5, 0, "PO-2")
    assert first["authorized"] is True
    assert second == {"authorized": False, "reason": "trade_credit_limit"}


def test_unpaid_invoice_causes_default_and_freezes_buyer():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        bank_limit_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        grace_days=1,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 20.0, 1, 0, "PO-DEFAULT")
    ledger.process_day(1)
    assert ledger.accounts["WEST-PR1"].defaulted is False
    ledger.process_day(2)
    assert ledger.accounts["WEST-PR1"].defaulted is True
    blocked = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 1.0, 3, 2, "PO-BLOCKED")
    assert blocked == {"authorized": False, "reason": "buyer_defaulted"}
    rejected_production = ledger.authorize_production("WEST-PR1", 0.0, day=2)
    assert rejected_production["reason"] == "cell_defaulted"


def test_customer_invoice_collects_on_due_date():
    ledger = CreditLedger(initial_cash_per_cell=0.0)
    ledger.issue_customer_invoice("WEST-MF1", 25.0, due_day=3, day=0, invoice_id="INV-C-1")
    assert ledger.accounts["WEST-MF1"].cash == 0.0
    ledger.process_day(2)
    assert ledger.accounts["WEST-MF1"].cash == 0.0
    ledger.process_day(3)
    assert ledger.accounts["WEST-MF1"].cash == pytest.approx(25.0)
    assert ledger.accounts["WEST-MF1"].customer_receivable == pytest.approx(0.0)
    assert ledger.snapshot()["customer_collections"] == pytest.approx(25.0)


def test_duplicate_invoice_ids_and_invalid_amounts_are_rejected():
    ledger = CreditLedger()
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 1.0, 2, 0, "PO-X")
    with pytest.raises(ValueError):
        ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 1.0, 2, 0, "PO-X")
    with pytest.raises(ValueError):
        ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 0.0, 2, 0, "PO-Z")
    with pytest.raises(ValueError):
        ledger.issue_customer_invoice("WEST-MF1", 1.0, 0, 1, "INV-PAST")


def test_days_cannot_move_backwards():
    ledger = CreditLedger()
    ledger.process_day(4)
    with pytest.raises(ValueError):
        ledger.process_day(3)


def test_non_finite_amounts_and_limits_are_rejected():
    with pytest.raises(ValueError):
        CreditLedger(initial_cash_per_cell=float("nan"))
    ledger = CreditLedger()
    with pytest.raises(ValueError):
        ledger.authorize_production("WEST-MF1", float("inf"), day=0)
    with pytest.raises(ValueError):
        ledger.authorize_purchase("WEST-PR1", "WEST-AG1", float("nan"), 2, 0, "PO-NAN")


def test_bank_credit_can_be_repaid_only_from_available_cash():
    ledger = CreditLedger(initial_cash_per_cell=5.0, bank_limit_per_cell=10.0)
    ledger.authorize_production("WEST-MF1", 12.0, day=0)
    insufficient = ledger.repay_bank_credit("WEST-MF1", 1.0, day=0)
    assert insufficient == {"repaid": False, "reason": "insufficient_cash", "amount": 0.0}
    ledger.issue_customer_invoice("WEST-MF1", 8.0, due_day=1, day=0, invoice_id="CASH-IN")
    ledger.process_day(1)
    repaid = ledger.repay_bank_credit("WEST-MF1", 5.0, day=1)
    assert repaid["repaid"] is True
    snap = ledger.snapshot()
    assert snap["bank_debt_by_cell"]["WEST-MF1"] == pytest.approx(2.0)
    assert snap["cash_by_cell"]["WEST-MF1"] == pytest.approx(3.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_invalid_credit_command_does_not_advance_ledger_day():
    ledger = CreditLedger()
    with pytest.raises(ValueError):
        ledger.authorize_purchase("WEST-PR1", "WEST-AG1", float("nan"), 9, 8, "PO-BAD")
    assert ledger.current_day == -1
    assert ledger.events == []


def test_defaulted_supplier_cannot_receive_new_purchase_orders():
    ledger = CreditLedger(initial_cash_per_cell=0.0, trade_credit_limit_per_cell=100.0, grace_days=0)
    ledger.authorize_purchase("WEST-AG1", None, 10.0, 0, 0, "SUPPLIER-DEFAULT")
    ledger.process_day(0)
    assert ledger.accounts["WEST-AG1"].defaulted is True
    result = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 1.0, 1, 0, "PO-FROM-DEFAULT")
    assert result == {"authorized": False, "reason": "seller_defaulted"}


def test_cash_purchase_works_without_any_trade_credit():
    ledger = CreditLedger(initial_cash_per_cell=50.0, trade_credit_limit_per_cell=0.0)
    result = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 4, 0, "CASH-PO")
    assert result["authorized"] is True
    assert result["funding_mode"] == "cash"
    assert result["cash_paid"] == pytest.approx(30.0)
    assert result["trade_credit_extended"] == pytest.approx(0.0)
    assert ledger.accounts["WEST-PR1"].cash == pytest.approx(20.0)
    assert ledger.accounts["WEST-AG1"].cash == pytest.approx(50.0)
    assert ledger.payables["CASH-PO"].status == "paid"
    assert ledger.snapshot()["internal_transfer_net"] == pytest.approx(0.0)


def test_bank_line_can_fund_immediate_purchase_without_trade_credit():
    ledger = CreditLedger(initial_cash_per_cell=5.0, bank_limit_per_cell=20.0, trade_credit_limit_per_cell=0.0)
    result = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 15.0, 4, 0, "BANK-PO")
    assert result["authorized"] is True
    assert result["funding_mode"] == "bank_funded_cash"
    assert result["bank_draw"] == pytest.approx(10.0)
    assert ledger.accounts["WEST-PR1"].cash == pytest.approx(0.0)
    assert ledger.accounts["WEST-PR1"].bank_debt == pytest.approx(10.0)
    assert ledger.payables["BANK-PO"].status == "paid"
    assert ledger.snapshot()["cash_conservation_error"] == pytest.approx(0.0)


def test_purchase_rejection_does_not_spend_partial_cash():
    ledger = CreditLedger(initial_cash_per_cell=5.0, bank_limit_per_cell=0.0, trade_credit_limit_per_cell=2.0)
    result = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 4, 0, "REJECT-PO")
    assert result["authorized"] is False
    assert ledger.accounts["WEST-PR1"].cash == pytest.approx(5.0)
    assert ledger.accounts["WEST-AG1"].cash == pytest.approx(5.0)
    assert "REJECT-PO" not in ledger.payables
