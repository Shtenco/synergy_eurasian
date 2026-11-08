"""SYNERGY Q4.1 — same-day circular settlement and ordering sensitivity.

Local diagnostic only. Compares sequential gross settlement (receipts can be
reused immediately) with snapshot batch settlement (each buyer can spend only
cash held at batch opening). This is a semantics experiment, not a claim about
the production ledger's behavior.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, List
import json
import random
from itertools import permutations

EPS = 1e-9

@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    buyer: str
    seller: str
    amount: float


def settle_sequential(invoices: Iterable[Invoice], opening_cash: Dict[str, float],
                      order: str = "invoice_id"):
    """Gross sequential settlement; seller receipts become spendable immediately."""
    if order == "invoice_id":
        ordered = sorted(invoices, key=lambda x: x.invoice_id)
    elif order == "reverse_invoice_id":
        ordered = sorted(invoices, key=lambda x: x.invoice_id, reverse=True)
    elif order == "provided":
        ordered = list(invoices)
    else:
        raise ValueError("unsupported order")
    cash = dict(opening_cash)
    paid, unpaid = {}, {}
    for inv in ordered:
        if inv.amount < 0 or inv.buyer not in cash or inv.seller not in cash:
            raise ValueError("invalid invoice or account")
        amount = min(cash[inv.buyer], inv.amount)
        cash[inv.buyer] -= amount
        cash[inv.seller] += amount
        paid[inv.invoice_id] = amount
        unpaid[inv.invoice_id] = inv.amount - amount
    assert abs(sum(cash.values()) - sum(opening_cash.values())) < 1e-8
    return {"cash": cash, "paid": paid, "unpaid": unpaid,
            "total_paid": sum(paid.values()), "total_unpaid": sum(unpaid.values()),
            "opening_cash_total": sum(opening_cash.values()),
            "ending_cash_total": sum(cash.values()),
            "semantics": "sequential_gross_receipts_reusable"}


def settle_snapshot(invoices: Iterable[Invoice], opening_cash: Dict[str, float],
                    order: str = "invoice_id"):
    """Batch settlement; receipts are not spendable until the batch closes."""
    ordered = (sorted(invoices, key=lambda x: x.invoice_id, reverse=(order == "reverse_invoice_id"))
               if order in ("invoice_id", "reverse_invoice_id") else None)
    if ordered is None:
        raise ValueError("unsupported order")
    budgets = dict(opening_cash)
    cash = dict(opening_cash)
    paid, unpaid = {}, {}
    credits = {account: 0.0 for account in cash}
    debits = {account: 0.0 for account in cash}
    for inv in ordered:
        if inv.amount < 0 or inv.buyer not in cash or inv.seller not in cash:
            raise ValueError("invalid invoice or account")
        amount = min(budgets[inv.buyer], inv.amount)
        budgets[inv.buyer] -= amount
        debits[inv.buyer] += amount
        credits[inv.seller] += amount
        paid[inv.invoice_id] = amount
        unpaid[inv.invoice_id] = inv.amount - amount
    for account in cash:
        cash[account] = cash[account] - debits[account] + credits[account]
    assert abs(sum(cash.values()) - sum(opening_cash.values())) < 1e-8
    return {"cash": cash, "paid": paid, "unpaid": unpaid,
            "total_paid": sum(paid.values()), "total_unpaid": sum(unpaid.values()),
            "opening_cash_total": sum(opening_cash.values()),
            "ending_cash_total": sum(cash.values()),
            "semantics": "snapshot_batch_receipts_not_reusable"}



def settle_multilateral_netting(invoices: Iterable[Invoice], opening_cash: Dict[str, float]):
    """Analytical full multilateral set-off for a closed cohort.

    This diagnostic recognizes reciprocal claims across all participants. It is
    only legally/operationally available where enforceable multilateral netting
    and close-out rules exist; it is not a cash payment.
    """
    invoices = list(invoices)
    net_positions = {account: 0.0 for account in opening_cash}
    gross_claims = 0.0
    for inv in invoices:
        if inv.amount < 0 or inv.buyer not in net_positions or inv.seller not in net_positions:
            raise ValueError("invalid invoice or account")
        gross_claims += inv.amount
        net_positions[inv.buyer] -= inv.amount
        net_positions[inv.seller] += inv.amount
    assert abs(sum(net_positions.values())) < 1e-8
    net_cash_required = sum(max(0.0, -v) for v in net_positions.values())
    net_creditor_positions = sum(max(0.0, v) for v in net_positions.values())
    assert abs(net_cash_required - net_creditor_positions) < 1e-8
    return {
        "gross_claims": gross_claims,
        "net_positions": net_positions,
        "net_cash_required": net_cash_required,
        "net_creditor_positions": net_creditor_positions,
        "cash_paid": 0.0 if net_cash_required < EPS else None,
        "unsettled_net_debit": net_cash_required,
        "settlement_type": "multilateral_setoff_not_cash_payment",
    }


def run_cycle():
    # Three-way cycle: each cell owes the next 150 but starts with only 100.
    # The order can recycle cash through the cycle under sequential gross settlement.
    invoices = [
        Invoice("01-A-to-B", "A", "B", 150.0),
        Invoice("02-B-to-C", "B", "C", 150.0),
        Invoice("03-C-to-A", "C", "A", 150.0),
    ]
    opening = {"A": 100.0, "B": 100.0, "C": 100.0}
    cases = {}
    for order in ("invoice_id", "reverse_invoice_id"):
        cases[f"sequential_{order}"] = settle_sequential(invoices, opening, order)
        cases[f"snapshot_{order}"] = settle_snapshot(invoices, opening, order)
    netting = settle_multilateral_netting(invoices, opening)
    permutation_results = []
    for index, perm in enumerate(permutations(invoices), start=1):
        case = settle_sequential(perm, opening, order="provided")
        permutation_results.append({
            "order": [inv.invoice_id for inv in perm],
            "total_paid": case["total_paid"],
            "total_unpaid": case["total_unpaid"],
            "unpaid_claims": [k for k, v in case["unpaid"].items() if v > EPS],
            "ending_cash": case["cash"],
        })
    return {"invoices": [inv.__dict__ for inv in invoices],
            "opening_cash": opening, "cases": cases,
            "multilateral_netting": netting,
            "all_sequential_permutations": permutation_results,
            "finding": {
                "sequential_paid_min": min(x["total_paid"] for x in permutation_results),
                "sequential_paid_max": max(x["total_paid"] for x in permutation_results),
                "sequential_paid_range": max(x["total_paid"] for x in permutation_results) - min(x["total_paid"] for x in permutation_results),
                "sequential_unpaid_claim_patterns": sorted({",".join(x["unpaid_claims"]) for x in permutation_results}),
                "sequential_gross_paid": cases["sequential_invoice_id"]["total_paid"],
                "snapshot_batch_paid": cases["snapshot_invoice_id"]["total_paid"],
                "sequential_ordering_changes_unpaid_claim_identity":
                    cases["sequential_invoice_id"]["unpaid"] !=
                    cases["sequential_reverse_invoice_id"]["unpaid"],
                "snapshot_ordering_changes_paid_allocation":
                    cases["snapshot_invoice_id"]["paid"] !=
                    cases["snapshot_reverse_invoice_id"]["paid"],
            }}


def test_cash_conservation_all_semantics():
    result = run_cycle()
    for case in result["cases"].values():
        assert abs(case["ending_cash_total"] - case["opening_cash_total"]) < 1e-8


def test_sequential_receipt_reuse_increases_gross_paid():
    result = run_cycle()
    seq = result["cases"]["sequential_invoice_id"]
    snap = result["cases"]["snapshot_invoice_id"]
    assert seq["total_paid"] == 400.0
    assert snap["total_paid"] == 300.0
    assert seq["total_unpaid"] == 50.0
    assert snap["total_unpaid"] == 150.0


def test_sequential_order_changes_which_claim_is_unpaid():
    result = run_cycle()
    assert result["finding"]["sequential_ordering_changes_unpaid_claim_identity"]


def test_snapshot_is_order_invariant_for_this_cycle():
    result = run_cycle()
    a = result["cases"]["snapshot_invoice_id"]
    b = result["cases"]["snapshot_reverse_invoice_id"]
    assert a["paid"] == b["paid"]
    assert a["cash"] == b["cash"]


def test_sequential_order_permutation_changes_aggregate_recovery():
    result = run_cycle()
    values = [x["total_paid"] for x in result["all_sequential_permutations"]]
    assert min(values) == 350.0
    assert max(values) == 400.0
    assert len(set(values)) > 1


def test_multilateral_netting_closes_pure_cycle_without_cash():
    result = run_cycle()
    netting = result["multilateral_netting"]
    assert netting["gross_claims"] == 450.0
    assert netting["net_cash_required"] == 0.0
    assert all(abs(v) < EPS for v in netting["net_positions"].values())
    assert netting["settlement_type"] == "multilateral_setoff_not_cash_payment"


def test_randomized_cohorts_preserve_cash_and_claims():
    rng = random.Random(20261108)
    accounts = [f"C{i}" for i in range(6)]
    for sample in range(100):
        opening = {account: rng.uniform(50.0, 500.0) for account in accounts}
        invoices = []
        for index in range(25):
            buyer = rng.choice(accounts)
            seller = rng.choice([x for x in accounts if x != buyer])
            invoices.append(Invoice(f"{sample:03d}-{index:03d}", buyer, seller,
                                    rng.uniform(1.0, 220.0)))
        total_claims = sum(x.amount for x in invoices)
        for settlement in (settle_sequential, settle_snapshot):
            for order in ("invoice_id", "reverse_invoice_id"):
                case = settlement(invoices, opening, order)
                assert abs(case["ending_cash_total"] - case["opening_cash_total"]) < 1e-7
                assert all(v >= -EPS for v in case["cash"].values())
                assert abs(case["total_paid"] + case["total_unpaid"] - total_claims) < 1e-7
                assert case["total_paid"] <= total_claims + EPS


def test_total_claim_reconciliation():
    result = run_cycle()
    for case in result["cases"].values():
        total_claims = sum(inv["amount"] for inv in result["invoices"])
        assert abs(case["total_paid"] + case["total_unpaid"] - total_claims) < 1e-8


def main():
    tests = [test_cash_conservation_all_semantics,
             test_sequential_receipt_reuse_increases_gross_paid,
             test_sequential_order_changes_which_claim_is_unpaid,
             test_snapshot_is_order_invariant_for_this_cycle,
             test_sequential_order_permutation_changes_aggregate_recovery,
             test_multilateral_netting_closes_pure_cycle_without_cash,
             test_randomized_cohorts_preserve_cash_and_claims,
             test_total_claim_reconciliation]
    for test in tests:
        test()
    result = run_cycle()
    print(f"LOCAL TESTS: {len(tests)}/{len(tests)} passed")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("\nINTERPRETATION: gross settlement can reuse same-day incoming payments;")
    print("snapshot settlement cannot. Multilateral set-off can eliminate pure-cycle cash")
    print("needs only where enforceable netting rules exist. Production semantics must be established from")
    print("CreditLedger.process_day and its invoice ordering before interpreting Q4 coverage.")

if __name__ == "__main__":
    main()