# SYNERGY V7.6.5 — Evidence-Qualified Borrowing-Base Calculator

**Status:** implemented calculator integrated with the V7.6.4 credit-aware production CLI.  
**Date:** 2026-11-06

## Purpose

V7.6.4 accepted period borrowing-base limits as external inputs. V7.6.5 adds a transparent calculation from receivable and inventory records, so the credit cap can be traced to eligible collateral rather than supplied as an unexplained number.

## Eligible receivables

A receivable is included only when:
- evidence status is OBSERVED or VERIFIED by default;
- it is within the configured maximum days past due;
- it is not disputed;
- it is not related-party.

UNDERWRITTEN and SCENARIO records can be included only through explicit policy flags. They remain scenario/underwriting evidence, not verified actuals.

The calculator aggregates eligible balances by counterparty and applies a concentration cap equal to the configured percentage of the gross eligible receivables pool. The capped balance is multiplied by the receivables advance rate.

## Eligible inventory

Inventory is included only when:
- evidence status is OBSERVED or VERIFIED by default;
- quality is approved;
- the storage location is controlled;
- the lot is not consigned.

WIP, obsolete, damaged, consigned and unverified stock is excluded unless the eligibility model is deliberately extended. Eligible carrying value is multiplied by the inventory advance rate.

## Borrowing-base formula

`GrossBase[t] = EligibleAR[t] × ARAdvanceRate + EligibleInventory[t] × InventoryAdvanceRate`

`NetBase[t] = max(0, GrossBase[t] - Reserve[t])`

The current policy uses one reserve amount per period. It does not yet model reserve categories such as dilution, returns, taxes, insurance, shrinkage or lender-specific exclusions separately.

The CLI combines calculated net base with any separately supplied `credit_borrowing_base_by_period` by taking the lower amount. The resulting effective borrowing base is passed to the V7.6.4 credit constraint. When collateral calculation is enabled, a missing period snapshot is treated as zero availability (fail-closed), not as an unlimited facility; provide a dated snapshot for every period in which collateral is expected to support debt.

## Inputs

- `receivable_collateral`: period, counterparty, outstanding balance, currency, aging, evidence status, dispute and related-party flags.
- `inventory_collateral`: period, lot/product, carrying value, currency, evidence status, quality, location-control and consignment flags.
- `collateral_policy`: AR/inventory advance rates, maximum days past due, counterparty concentration limit, reserve amount and optional evidence-class inclusion flags.
- A `credit_limit` is required to use collateral-derived limits in the production optimizer.

## Output

Per period, the calculator reports:
- gross eligible AR and counterparty concentration caps;
- AR after concentration limits and AR advance amount;
- eligible inventory and inventory advance amount;
- gross and net borrowing base;
- included and excluded receivable IDs and inventory lot IDs.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.planner_cli examples/synergy_v7_6_2_credit_factory_plan.json
```

## Evidence and legal boundary

The calculator checks supplied fields; it does not independently verify invoices, customer existence, disputes, inventory ownership, lien priority, title, warehouse controls or lender eligibility. Source evidence IDs must point to the actual ERP, AR subledger, WMS, inventory count and quality records. The same asset must not be double-counted as both cash and collateral. No lender certification, collateral valuation, covenant compliance opinion, loan approval or draw authorization is created.

## Next

V7.6.6 should add category-specific reserves, receivable dilution/credit-note history, customer and product concentration, inventory aging/obsolescence haircuts, and eligibility audit trails. V7.7 should couple the collateral model with scenario-specific recourse so supply shocks and collections delays affect both production and borrowing capacity.
