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
    assert second == {"authorized": False, "reason": "buyer_trade_credit_limit"}


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
    assert ledger.accounts["WEST-AG1"].cash == pytest.approx(80.0)
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


def test_partial_payments_reduce_buyer_ap_and_seller_ar_symmetrically():
    ledger = CreditLedger(
        initial_cash_per_cell=10.0,
        bank_limit_per_cell=0.0,
        trade_credit_limit_per_cell=20.0,
        grace_days=2,
    )
    purchase = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 20.0, 1, 0, "PARTIAL-PO")
    assert purchase["cash_paid"] == pytest.approx(10.0)
    assert purchase["trade_credit_extended"] == pytest.approx(10.0)
    ledger.issue_customer_invoice("WEST-PR1", 6.0, 1, 0, "CUSTOMER-PAY-1")
    ledger.process_day(1)
    assert ledger.payables["PARTIAL-PO"].status == "partial"
    assert ledger.payables["PARTIAL-PO"].remaining == pytest.approx(4.0)
    assert ledger.accounts["WEST-PR1"].trade_payable == pytest.approx(4.0)
    assert ledger.accounts["WEST-AG1"].trade_receivable == pytest.approx(4.0)
    ledger.issue_customer_invoice("WEST-PR1", 4.0, 2, 1, "CUSTOMER-PAY-2")
    ledger.process_day(2)
    snap = ledger.snapshot()
    assert ledger.payables["PARTIAL-PO"].status == "paid"
    assert snap["trade_payable_by_cell"]["WEST-PR1"] == pytest.approx(0.0)
    assert snap["trade_receivable_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert snap["internal_transfer_in"] == pytest.approx(20.0)
    assert snap["internal_transfer_out"] == pytest.approx(20.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_supplier_receivable_exposure_limit_blocks_only_unsecured_remainder():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        trade_receivable_limit_per_cell=5.0,
    )
    blocked = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 3, 0, "EXPOSURE-BLOCK")
    assert blocked == {"authorized": False, "reason": "seller_exposure_limit"}
    assert ledger.accounts["WEST-PR1"].cash == pytest.approx(0.0)
    assert ledger.accounts["WEST-AG1"].trade_receivable == pytest.approx(0.0)
    assert "EXPOSURE-BLOCK" not in ledger.payables

    cash_ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=0.0,
        trade_receivable_limit_per_cell=0.0,
    )
    cash_purchase = cash_ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 3, 0, "EXPOSURE-CASH")
    assert cash_purchase["authorized"] is True
    assert cash_purchase["trade_credit_extended"] == pytest.approx(0.0)


def test_partial_payment_default_only_applies_to_unpaid_residual_after_grace():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        grace_days=2,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 20.0, 1, 0, "GRACE-PO")
    ledger.issue_customer_invoice("WEST-PR1", 5.0, 2, 0, "GRACE-CUSTOMER")
    ledger.process_day(1)
    assert ledger.accounts["WEST-PR1"].defaulted is False
    ledger.process_day(2)
    assert ledger.payables["GRACE-PO"].remaining == pytest.approx(15.0)
    assert ledger.accounts["WEST-PR1"].defaulted is False
    ledger.process_day(3)
    assert ledger.accounts["WEST-PR1"].defaulted is True
    assert ledger.payables["GRACE-PO"].status == "defaulted"


def test_customer_partial_recovery_then_bad_debt_writeoff():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        customer_recovery_rate=0.75,
        customer_grace_days=2,
    )
    issued = ledger.issue_customer_invoice("WEST-MF1", 100.0, 1, 0, "RISK-CUSTOMER")
    assert issued["authorized"] is True
    ledger.process_day(1)
    invoice = ledger.customer_invoices["RISK-CUSTOMER"]
    assert invoice.status == "partial"
    assert invoice.remaining == pytest.approx(25.0)
    assert ledger.accounts["WEST-MF1"].customer_receivable == pytest.approx(25.0)
    ledger.process_day(2)
    assert invoice.status == "overdue"
    ledger.process_day(3)
    snap = ledger.snapshot()
    assert invoice.status == "defaulted"
    assert invoice.remaining == pytest.approx(0.0)
    assert snap["customer_bad_debt"] == pytest.approx(25.0)
    assert snap["customer_collections"] == pytest.approx(75.0)
    assert snap["customer_receivable_by_cell"]["WEST-MF1"] == pytest.approx(0.0)
    assert snap["customer_default_count"] == 1
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_customer_receivable_exposure_limit_blocks_new_sales_invoices():
    ledger = CreditLedger(initial_cash_per_cell=0.0, customer_receivable_limit_per_cell=5.0)
    first = ledger.issue_customer_invoice("WEST-MF1", 5.0, 3, 0, "CUSTOMER-LIMIT-1")
    second = ledger.issue_customer_invoice("WEST-MF1", 1.0, 3, 0, "CUSTOMER-LIMIT-2")
    assert first["authorized"] is True
    assert second == {"authorized": False, "reason": "customer_exposure_limit"}
    snap = ledger.snapshot()
    assert snap["customer_receivable_by_cell"]["WEST-MF1"] == pytest.approx(5.0)
    assert snap["customer_invoice_rejection_count"] == 1


def test_invalid_customer_recovery_policy_is_rejected():
    with pytest.raises(ValueError):
        CreditLedger(customer_recovery_rate=1.1)
    with pytest.raises(ValueError):
        CreditLedger(customer_recovery_rate=float("nan"))
    with pytest.raises(ValueError):
        CreditLedger(customer_grace_days=-1)


def test_regional_pool_tracks_local_net_positions_and_reverses_on_partial_settlement():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=100.0,
        regional_member_debit_limit_per_cell=80.0,
        regional_member_credit_limit_per_cell=80.0,
        grace_days=2,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 2, 0, "POOL-LOCAL")
    assert ledger.accounts["WEST-PR1"].regional_credit_balance == pytest.approx(-30.0)
    assert ledger.accounts["WEST-AG1"].regional_credit_balance == pytest.approx(30.0)
    assert ledger._regional_pool_outstanding("WEST") == pytest.approx(30.0)
    balances = [a.regional_credit_balance for a in ledger.accounts.values() if a.regional_credit_balance]
    assert sum(balances) == pytest.approx(0.0)
    assert sum(max(0.0, x) for x in balances) == pytest.approx(30.0)
    assert sum(max(0.0, -x) for x in balances) == pytest.approx(30.0)
    ledger.issue_customer_invoice("WEST-PR1", 10.0, 2, 0, "POOL-PAY-1")
    ledger.process_day(2)
    assert ledger.accounts["WEST-PR1"].regional_credit_balance == pytest.approx(-20.0)
    assert ledger.accounts["WEST-AG1"].regional_credit_balance == pytest.approx(20.0)
    ledger.issue_customer_invoice("WEST-PR1", 20.0, 3, 2, "POOL-PAY-2")
    ledger.process_day(3)
    snap = ledger.snapshot()
    assert snap["regional_pool_outstanding_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["regional_pool_net_position_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_cross_region_trade_credit_is_not_misbooked_to_either_local_pool():
    ledger = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=100.0,
    )
    result = ledger.authorize_purchase("WEST-PR1", "EAST-AG1", 25.0, 4, 0, "CROSS-REGION-PO")
    assert result["authorized"] is True
    assert ledger.accounts["WEST-PR1"].regional_credit_balance == pytest.approx(0.0)
    assert ledger.accounts["EAST-AG1"].regional_credit_balance == pytest.approx(0.0)
    snap = ledger.snapshot()
    assert snap["regional_pool_outstanding_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["regional_pool_outstanding_by_region"]["EAST"] == pytest.approx(0.0)


def test_regional_pool_limit_rejects_unsecured_trade_but_bank_line_can_replace_it():
    limited = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=5.0,
    )
    rejected = limited.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 2, 0, "POOL-REJECT")
    assert rejected == {"authorized": False, "reason": "regional_pool_limit"}
    assert "POOL-REJECT" not in limited.payables

    banked = CreditLedger(
        initial_cash_per_cell=0.0,
        bank_limit_per_cell=10.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=5.0,
    )
    funded = banked.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 2, 0, "POOL-BANK-FALLBACK")
    assert funded["authorized"] is True
    assert funded["funding_mode"] == "bank_funded_cash"
    assert banked.accounts["WEST-PR1"].regional_credit_balance == pytest.approx(0.0)
    assert banked.accounts["WEST-PR1"].bank_debt == pytest.approx(10.0)


def test_regional_member_debit_and_credit_limits_are_enforced():
    debit_limited = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=100.0,
        regional_member_debit_limit_per_cell=5.0,
    )
    debit = debit_limited.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 2, 0, "MEMBER-DEBIT")
    assert debit == {"authorized": False, "reason": "regional_member_debit_limit"}

    credit_limited = CreditLedger(
        initial_cash_per_cell=0.0,
        trade_credit_limit_per_cell=100.0,
        regional_pool_limit_per_region=100.0,
        regional_member_credit_limit_per_cell=5.0,
    )
    credit = credit_limited.authorize_purchase("WEST-PR1", "WEST-AG1", 10.0, 2, 0, "MEMBER-CREDIT")
    assert credit == {"authorized": False, "reason": "regional_member_credit_limit"}


def test_member_funded_regional_reserve_covers_local_default_without_minting_cash():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_limit_per_region=100.0,
        regional_pool_reserve_per_region=20.0,
        grace_days=0,
    )
    assert sum(a.cash for a in ledger.accounts.values()) + sum(ledger.regional_pool_reserve_by_region.values()) == pytest.approx(ledger.opening_cash)
    purchase = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "RESERVE-COVER")
    assert purchase["trade_credit_extended"] == pytest.approx(12.0)
    ledger.process_day(0)
    invoice = ledger.payables["RESERVE-COVER"]
    snap = ledger.snapshot()
    assert invoice.status == "defaulted"
    assert invoice.guarantee_paid == pytest.approx(12.0)
    assert invoice.written_off == pytest.approx(0.0)
    assert snap["regional_pool_guarantee_paid_by_region"]["WEST"] == pytest.approx(12.0)
    assert snap["regional_pool_reserve_by_region"]["WEST"] == pytest.approx(8.0)
    assert snap["trade_bad_debt_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert snap["trade_payable_by_cell"]["WEST-PR1"] == pytest.approx(0.0)
    assert snap["trade_receivable_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_insufficient_regional_reserve_covers_part_and_seller_absorbs_residual():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_limit_per_region=100.0,
        regional_pool_reserve_per_region=5.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "RESERVE-PARTIAL")
    ledger.process_day(0)
    invoice = ledger.payables["RESERVE-PARTIAL"]
    snap = ledger.snapshot()
    assert invoice.guarantee_paid == pytest.approx(5.0)
    assert invoice.written_off == pytest.approx(5.5)
    assert snap["trade_bad_debt_by_cell"]["WEST-AG1"] == pytest.approx(5.5)
    assert snap["regional_pool_reserve_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["regional_pool_outstanding_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_cross_region_default_is_not_covered_by_local_pool_reserve():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_reserve_per_region=20.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", "EAST-AG1", 30.0, 0, 0, "CROSS-DEFAULT")
    ledger.process_day(0)
    snap = ledger.snapshot()
    assert ledger.payables["CROSS-DEFAULT"].guarantee_paid == pytest.approx(0.0)
    assert snap["trade_bad_debt_by_cell"]["EAST-AG1"] == pytest.approx(12.0)
    assert snap["regional_pool_reserve_by_region"]["WEST"] == pytest.approx(20.0)
    assert snap["regional_pool_reserve_by_region"]["EAST"] == pytest.approx(20.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_regional_pool_reserve_cannot_exceed_member_contributions():
    with pytest.raises(ValueError):
        CreditLedger(initial_cash_per_cell=1.0, regional_pool_reserve_per_region=11.0)


def test_cross_default_resolves_all_open_payables_of_failed_buyer():
    ledger = CreditLedger(
        initial_cash_per_cell=10.0,
        trade_credit_limit_per_cell=100.0,
        grace_days=0,
        regional_pool_reserve_per_region=20.0,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 20.0, 0, 0, "DEFAULT-1")
    ledger.authorize_purchase("WEST-PR1", "WEST-AG2", 10.0, 5, 0, "DEFAULT-2")
    ledger.process_day(0)
    snap = ledger.snapshot()
    assert ledger.accounts["WEST-PR1"].defaulted is True
    assert ledger.payables["DEFAULT-1"].status == "defaulted"
    assert ledger.payables["DEFAULT-2"].status == "defaulted"
    assert snap["trade_payable_by_cell"]["WEST-PR1"] == pytest.approx(0.0)
    assert snap["trade_receivable_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    assert snap["trade_receivable_by_cell"]["WEST-AG2"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_external_supplier_default_is_not_paid_from_local_member_guarantee_reserve():
    ledger = CreditLedger(
        initial_cash_per_cell=10.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_reserve_per_region=20.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", None, 20.0, 0, 0, "EXTERNAL-DEFAULT")
    ledger.process_day(0)
    snap = ledger.snapshot()
    assert ledger.payables["EXTERNAL-DEFAULT"].guarantee_paid == pytest.approx(0.0)
    assert snap["external_supplier_bad_debt"] == pytest.approx(12.0)
    assert snap["regional_pool_reserve_by_region"]["WEST"] == pytest.approx(20.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_weighted_regional_reserve_contributions_are_fully_funded_and_auditable():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions

    contributions = build_regional_reserve_contributions("production_capacity_weighted", 20.0)
    ledger = CreditLedger(
        initial_cash_per_cell=150.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_reserve_per_region=20.0,
        regional_reserve_contributions_by_cell=contributions,
    )
    snap = ledger.snapshot()
    for region in ("WEST", "EAST"):
        assert sum(
            contributions[cell_id]
            for cell_id in contributions if cell_id.startswith(region + "-")
        ) == pytest.approx(20.0)
    assert snap["regional_reserve_contributions_by_cell"] == contributions
    assert sum(snap["cash_by_cell"].values()) + sum(snap["regional_pool_reserve_by_region"].values()) == pytest.approx(ledger.opening_cash)
    assert contributions["WEST-WH"] == pytest.approx(0.0)
    assert contributions["WEST-AG1"] > contributions["WEST-AG2"]


def test_reserve_contribution_map_rejects_missing_members_and_unfunded_total():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions

    complete = build_regional_reserve_contributions("equal_all_members", 20.0)
    incomplete = dict(complete)
    incomplete.pop("WEST-SV")
    with pytest.raises(ValueError):
        CreditLedger(regional_pool_reserve_per_region=20.0, regional_reserve_contributions_by_cell=incomplete)
    overfunded = dict(complete)
    overfunded["WEST-AG1"] += 1.0
    with pytest.raises(ValueError):
        CreditLedger(regional_pool_reserve_per_region=20.0, regional_reserve_contributions_by_cell=overfunded)
    excessive = dict(complete)
    excessive["WEST-AG1"] = 201.0
    with pytest.raises(ValueError):
        CreditLedger(initial_cash_per_cell=200.0, regional_pool_reserve_per_region=20.0, regional_reserve_contributions_by_cell=excessive)


def test_zero_contribution_is_supported_for_non_producing_support_cells():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions

    contributions = build_regional_reserve_contributions("production_capacity_weighted", 20.0)
    assert contributions["EAST-WH"] == pytest.approx(0.0)
    assert contributions["EAST-LG"] == pytest.approx(0.0)
    assert sum(v for k, v in contributions.items() if k.startswith("EAST-")) == pytest.approx(20.0)


def test_regional_member_assessment_covers_local_residual_loss_pro_rata():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_assessment_rate=0.10,
        regional_assessment_limit_per_cell=2.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "ASSESSMENT-FULL")
    ledger.process_day(0)
    invoice = ledger.payables["ASSESSMENT-FULL"]
    snap = ledger.snapshot()
    assert invoice.guarantee_paid == pytest.approx(0.0)
    assert invoice.member_assessment_paid == pytest.approx(10.0)
    assert invoice.written_off == pytest.approx(0.0)
    assert snap["regional_assessment_paid_by_region"]["WEST"] == pytest.approx(10.0)
    assert snap["regional_assessment_attempt_count"] == 1
    assert snap["regional_assessment_requested_by_region"]["WEST"] == pytest.approx(10.0)
    assert snap["regional_assessment_eligible_capacity_by_region"]["WEST"] == pytest.approx(16.0)
    assert snap["trade_bad_debt_by_cell"]["WEST-AG1"] == pytest.approx(0.0)
    contributions = snap["regional_assessment_contributed_by_cell"]
    assert contributions["WEST-PR1"] == pytest.approx(0.0)
    assert contributions["WEST-AG1"] == pytest.approx(0.0)
    assert max(contributions.values()) <= 2.0 + 1e-9
    positive = [value for value in contributions.values() if value > 0]
    assert len(positive) == 8
    assert all(value == pytest.approx(1.25) for value in positive)
    assert sum(contributions.values()) == pytest.approx(10.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_regional_member_assessment_cap_leaves_residual_seller_loss():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_assessment_rate=0.10,
        regional_assessment_limit_per_cell=1.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "ASSESSMENT-CAPPED")
    ledger.process_day(0)
    invoice = ledger.payables["ASSESSMENT-CAPPED"]
    snap = ledger.snapshot()
    assert invoice.member_assessment_paid == pytest.approx(8.0)
    assert invoice.written_off == pytest.approx(2.0)
    assert snap["trade_bad_debt_by_cell"]["WEST-AG1"] == pytest.approx(2.0)
    assert sum(snap["regional_assessment_contributed_by_cell"].values()) == pytest.approx(8.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_member_assessment_is_disabled_by_default_and_rejects_invalid_parameters():
    disabled = CreditLedger(initial_cash_per_cell=20.0, trade_credit_limit_per_cell=50.0, grace_days=0)
    disabled.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "ASSESSMENT-OFF")
    disabled.process_day(0)
    assert disabled.payables["ASSESSMENT-OFF"].member_assessment_paid == pytest.approx(0.0)
    with pytest.raises(ValueError):
        CreditLedger(regional_assessment_rate=1.01)
    with pytest.raises(ValueError):
        CreditLedger(regional_assessment_rate=True)
    with pytest.raises(ValueError):
        CreditLedger(regional_assessment_limit_per_cell=-1.0)


def test_cross_region_default_does_not_trigger_local_member_assessment():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_assessment_rate=0.50,
        regional_assessment_limit_per_cell=5.0,
        grace_days=0,
    )
    ledger.authorize_purchase("WEST-PR1", "EAST-AG1", 30.0, 0, 0, "ASSESSMENT-CROSS")
    ledger.process_day(0)
    snap = ledger.snapshot()
    assert ledger.payables["ASSESSMENT-CROSS"].member_assessment_paid == pytest.approx(0.0)
    assert snap["regional_assessment_paid_by_region"]["WEST"] == pytest.approx(0.0)
    assert snap["regional_assessment_paid_by_region"]["EAST"] == pytest.approx(0.0)
    assert snap["cash_conservation_error"] == pytest.approx(0.0)


def test_heterogeneous_member_opening_cash_is_reconciled_with_reserve_contributions():
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 40.0 + index * 3.0 for index, cell in enumerate(CELLS)}
    contributions = {cell.cell_id: 0.0 for cell in CELLS}
    for region in ("WEST", "EAST"):
        members = [cell for cell in CELLS if cell.region == region]
        contributions[members[0].cell_id] = 5.0
        contributions[members[1].cell_id] = 5.0
    ledger = CreditLedger(
        initial_cash_by_cell=cash,
        regional_pool_reserve_per_region=10.0,
        regional_reserve_contributions_by_cell=contributions,
    )
    snapshot = ledger.snapshot()
    assert snapshot["initial_cash_by_cell"] == cash
    assert sum(snapshot["cash_by_cell"].values()) + sum(snapshot["regional_pool_reserve_by_region"].values()) == pytest.approx(sum(cash.values()))
    for cell_id, contribution in contributions.items():
        assert contribution <= cash[cell_id]


def test_heterogeneous_opening_cash_rejects_incomplete_and_underfunded_member_maps():
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 50.0 for cell in CELLS}
    cash.pop(CELLS[0].cell_id)
    with pytest.raises(ValueError):
        CreditLedger(initial_cash_by_cell=cash)
    cash = {cell.cell_id: 50.0 for cell in CELLS}
    contributions = {cell.cell_id: 0.0 for cell in CELLS}
    contributions["WEST-AG1"] = 10.0
    with pytest.raises(ValueError):
        CreditLedger(
            initial_cash_by_cell=cash,
            regional_pool_reserve_per_region=10.0,
            regional_reserve_contributions_by_cell=contributions,
        )


def test_federation_reserve_covers_cross_region_default_without_local_reserve():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        federation_pool_reserve_total=5.0,
        grace_days=0,
    )
    purchase = ledger.authorize_purchase("WEST-PR1", "EAST-AG1", 30.0, 0, 0, "FED-CROSS-1")
    assert purchase["authorized"]
    ledger.process_day(0)
    invoice = ledger.payables[purchase["invoice_id"]]
    snapshot = ledger.snapshot()
    assert invoice.guarantee_paid == pytest.approx(0.0)
    assert invoice.federation_guarantee_paid == pytest.approx(5.0)
    assert invoice.member_assessment_paid == pytest.approx(0.0)
    assert invoice.written_off == pytest.approx(5.25)
    assert snapshot["federation_pool_reserve_balance"] == pytest.approx(0.0)
    assert snapshot["federation_pool_guarantee_paid"] == pytest.approx(5.0)
    assert snapshot["cash_conservation_error"] == pytest.approx(0.0)


def test_local_default_uses_local_reserve_then_federation_reserve_then_member_assessment():
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        trade_credit_limit_per_cell=50.0,
        regional_pool_reserve_per_region=5.0,
        federation_pool_reserve_total=3.0,
        regional_assessment_rate=0.10,
        regional_assessment_limit_per_cell=2.0,
        grace_days=0,
    )
    purchase = ledger.authorize_purchase("WEST-PR1", "WEST-AG1", 30.0, 0, 0, "FED-LOCAL-1")
    assert purchase["authorized"]
    ledger.process_day(0)
    invoice = ledger.payables[purchase["invoice_id"]]
    snapshot = ledger.snapshot()
    assert invoice.guarantee_paid == pytest.approx(5.0)
    assert invoice.federation_guarantee_paid == pytest.approx(3.0)
    assert invoice.member_assessment_paid == pytest.approx(2.65)
    assert invoice.written_off == pytest.approx(0.0)
    assert snapshot["cash_conservation_error"] == pytest.approx(0.0)


def test_federation_reserve_contributions_are_separately_funded_and_cash_safe():
    from synergy_v66.network_topology import CELLS

    contributions = {cell.cell_id: 0.0 for cell in CELLS}
    contributions["WEST-PR1"] = 2.0
    contributions["EAST-PR1"] = 3.0
    ledger = CreditLedger(
        initial_cash_per_cell=20.0,
        federation_pool_reserve_total=5.0,
        federation_reserve_contributions_by_cell=contributions,
    )
    snapshot = ledger.snapshot()
    assert snapshot["federation_reserve_contributions_by_cell"] == contributions
    assert snapshot["federation_pool_reserve_balance"] == pytest.approx(5.0)
    assert sum(snapshot["cash_by_cell"].values()) + sum(snapshot["regional_pool_reserve_by_region"].values()) + snapshot["federation_pool_reserve_balance"] == pytest.approx(ledger.opening_cash)
    overdrawn = dict(contributions)
    overdrawn["WEST-PR1"] = 21.0
    overdrawn["EAST-PR1"] = 0.0
    with pytest.raises(ValueError):
        CreditLedger(
            initial_cash_per_cell=20.0,
            federation_pool_reserve_total=21.0,
            federation_reserve_contributions_by_cell=overdrawn,
        )


def test_federation_reserve_rejects_incomplete_or_mismatched_contribution_maps():
    from synergy_v66.network_topology import CELLS

    contributions = {cell.cell_id: 0.0 for cell in CELLS}
    contributions["WEST-PR1"] = 2.0
    with pytest.raises(ValueError):
        CreditLedger(
            federation_pool_reserve_total=3.0,
            federation_reserve_contributions_by_cell=contributions,
        )
    contributions.pop("WEST-PR1")
    with pytest.raises(ValueError):
        CreditLedger(
            federation_pool_reserve_total=0.0,
            federation_reserve_contributions_by_cell=contributions,
        )


def test_heterogeneous_opening_cash_cannot_be_overcommitted_across_both_reserves():
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 25.0 for cell in CELLS}
    regional = {cell.cell_id: 0.0 for cell in CELLS}
    federation = {cell.cell_id: 0.0 for cell in CELLS}
    regional["WEST-AG1"] = 15.0
    federation["WEST-AG1"] = 11.0
    with pytest.raises(ValueError):
        CreditLedger(
            initial_cash_by_cell=cash,
            regional_pool_reserve_per_region=15.0,
            regional_reserve_contributions_by_cell={
                **regional,
                **{cell.cell_id: (15.0 if cell.region == "EAST" and cell.cell_id == "EAST-AG1" else regional[cell.cell_id]) for cell in CELLS},
            },
            federation_pool_reserve_total=11.0,
            federation_reserve_contributions_by_cell=federation,
        )


def test_heterogeneous_opening_cash_and_both_reserves_conserve_consolidated_cash():
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 30.0 + index for index, cell in enumerate(CELLS)}
    regional = {cell.cell_id: 0.0 for cell in CELLS}
    federation = {cell.cell_id: 0.0 for cell in CELLS}
    regional["WEST-AG1"] = 2.0
    regional["EAST-AG1"] = 2.0
    federation["WEST-PR1"] = 3.0
    federation["EAST-PR1"] = 3.0
    ledger = CreditLedger(
        initial_cash_by_cell=cash,
        regional_pool_reserve_per_region=2.0,
        regional_reserve_contributions_by_cell=regional,
        federation_pool_reserve_total=6.0,
        federation_reserve_contributions_by_cell=federation,
    )
    snapshot = ledger.snapshot()
    consolidated = (
        sum(snapshot["cash_by_cell"].values())
        + sum(snapshot["regional_pool_reserve_by_region"].values())
        + snapshot["federation_pool_reserve_balance"]
    )
    assert consolidated == pytest.approx(sum(cash.values()))
    assert snapshot["cash_conservation_error"] == pytest.approx(0.0)
