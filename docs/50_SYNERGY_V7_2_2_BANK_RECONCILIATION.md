# SYNERGY V7.2.2 — Bank Statement Reconciliation

**Status:** explicit allocation and reconciliation controls; not an automated bank-feed connector or audited cash book.  
**Date:** 2026-11-06

## Purpose

V7.2.2 connects cash evidence to V7.2.1 trade documents. It reconciles bank statement lines to explicitly selected receivable/payable documents and produces settlement events for the trade ledger.

## Inputs

- `BankStatementLine`: bank account, booked date, signed amount, currency, bank reference and source evidence.
- `CashAllocation`: explicit allocation of a positive amount to one trade document and bank line.
- Existing trade documents and prior settlements.
- `as_of` cutoff date.

Positive bank lines are inflows and can settle receivables. Negative bank lines are outflows and can settle payables. The amount allocated to a line cannot exceed its absolute statement amount.

## Controls

- No fuzzy or automatic invoice matching. Human or upstream ERP approval must supply explicit allocations.
- Unallocated residuals remain visible as unmatched cash; they are not silently classified as revenue.
- Wrong-direction allocations, unknown documents, duplicate IDs, currency mismatch and over-allocation are rejected.
- A generated settlement carries the bank account and source reference into the AR/AP projection.
- Future-dated statement lines are excluded at the cutoff date.
- Multi-currency conversion, fees, bank charges, reversals, chargebacks, cash pooling and suspense-account classification are not yet modeled.

## Outputs

The report contains line-level reconciliation status, allocated and unmatched amounts, net control totals by currency, generated settlement count and the updated trade-ledger projection. `fully_reconciled` is true only if every in-scope bank line is fully allocated.

A bank line can include a bank fee or other non-invoice item. Until a dedicated fee/suspense classification is introduced, such amount correctly remains unmatched and requires review.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.2.3 should add explicit bank-fee, interest, tax and suspense classifications, reversal/chargeback links and duplicate-statement detection. V7.3 should join verified cash, customer delivery acceptance, production evidence and net incremental benefit.
