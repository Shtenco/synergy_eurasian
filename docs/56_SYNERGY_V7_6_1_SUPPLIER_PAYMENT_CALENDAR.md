# SYNERGY V7.6.1 — Supplier Payment Calendar

**Status:** dated supplier payment commitments integrated into the V7.6 cash-constrained MILP.  
**Date:** 2026-11-06

## Purpose

Production can be blocked by cash commitments that occur before goods arrive: deposits, dispatch milestones, receipt payments and final settlement. V7.6.1 introduces explicit supplier payment commitments, aggregates them into period cash outflows and feeds those outflows into the production optimizer.

## Payment record

Each `SupplierPaymentCommitment` contains:
- payment ID, supplier ID, purchase order ID and input product ID;
- zero-based planning period and positive amount;
- currency;
- stage: `DEPOSIT`, `DISPATCH`, `RECEIPT`, `MILESTONE` or `FINAL`;
- status: `OBSERVED`, `COMMITTED`, `SCENARIO` or `PLANNED`;
- evidence ID.

By default only OBSERVED and COMMITTED commitments reduce available cash. SCENARIO commitments are included only when `include_scenario_supplier_payments=true`; PLANNED entries never count as firm cash obligations. Out-of-horizon payments are reported, not moved into the current horizon.

## Cash integration

The CLI aggregates firm supplier payment commitments by period and adds them to `cash_outflows_by_period`. The cash conservation equation becomes:

`Ending cash = Prior cash + External inflows + Customer collections - Production batch cash costs - Inventory holding costs - Committed supplier/operating outflows`

Do not enter the same supplier payment both as a supplier commitment and again in `cash_outflows_by_period`; that would double-count the obligation.

## Important boundaries

- A supplier payment commitment is not a bank settlement. It does not reduce an invoice's AR/AP balance until a bank-confirmed settlement is recorded in V7.2.2.
- This version does not choose suppliers, negotiate payment terms or optimize deposit schedules. It models explicit payment dates already provided by the user/ERP.
- Amounts must use the optimizer's objective currency. FX conversion and multi-currency cash accounts are not inferred.
- The module does not establish that an obligation is legally due. Status and evidence quality must be reviewed by authorized finance/procurement staff.
- Production batch costs must not duplicate material payments represented by supplier commitments.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.planner_cli examples/synergy_v7_6_cash_constrained_plan.json
```

## Next

V7.6.2 should model financing facilities, drawdowns, repayment dates, interest and covenant headroom. A later procurement optimizer can jointly choose supplier, order quantity, lead time and payment schedule instead of treating supplier commitments as fixed inputs.
