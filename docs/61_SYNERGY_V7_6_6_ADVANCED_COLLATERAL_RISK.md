# SYNERGY V7.6.6 — Advanced Collateral Quality, Dilution and Aging

**Status:** implemented in the V7.6.5 collateral calculator; compatibility retained.  
**Date:** 2026-11-06

## Purpose

V7.6.5 calculated an evidence-filtered borrowing base from receivables and inventory. V7.6.6 adds explicit collateral deterioration and reserve mechanics, plus an asset-level audit trail. A gross invoice or book inventory value is no longer automatically treated as fully eligible value.

## New policy controls

- `receivable_aging_haircuts`: ordered `[days_past_due, haircut_rate]` tiers. The last tier whose threshold has been reached applies to that receivable.
- `inventory_aging_haircuts`: ordered `[age_days, haircut_rate]` tiers. The last reached threshold applies to the inventory lot.
- `receivable_dilution_reserve_rate`: additional percentage reserve against receivables remaining after aging haircuts and counterparty concentration caps.
- `receivable_reserve_amount`: fixed receivable-specific reserve.
- `inventory_reserve_amount`: fixed inventory-specific reserve.
- Existing `reserve_amount` remains the general reserve for backward compatibility.

Tier thresholds must be strictly increasing; haircut and dilution rates must lie in [0,1].

## Calculation sequence

1. Apply evidence, aging-limit, dispute and related-party eligibility filters to each receivable.
2. Apply receivable aging haircuts at asset level.
3. Aggregate post-haircut receivables by counterparty.
4. Apply the counterparty concentration cap against the post-haircut eligible receivables pool.
5. Deduct the dilution reserve, then apply the receivable advance rate.
6. Apply evidence, quality, location-control and consignment filters to each inventory lot.
7. Apply inventory aging haircuts at lot level, then the inventory advance rate.
8. Deduct the general, receivable-specific, inventory-specific and dilution reserves.
9. Floor the resulting net borrowing base at zero.

`NetBase = max(0, ARAdvance + InventoryAdvance - GeneralReserve - ARReserve - InventoryReserve - DilutionReserve)`

## Asset-level audit trail

Every receivable and inventory lot receives an audit record with:
- asset ID and source evidence ID;
- counterparty/product ID;
- gross value and age;
- applied haircut rate and amount;
- post-haircut value;
- eligibility result;
- explicit exclusion reason codes.

The aggregate report also preserves accepted evidence classes, policy parameters, category reserve totals, included/excluded asset IDs and the period borrowing base. This supports review and reconciliation; it does not prove the source evidence is authentic.

## Compatibility and CLI

V7.6.5 inputs remain valid. All new haircut tiers and category reserves are optional and default to zero/no additional haircut. The CLI continues to derive the net base and pass the resulting period limits into the production credit optimizer. If collateral mode is enabled, a missing period snapshot remains zero borrowing-base availability (fail-closed).

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.planner_cli examples/synergy_v7_6_2_credit_factory_plan.json
```

## Financial and governance boundaries

This is an internally consistent planning calculation, not a lender borrowing-base certificate, audited valuation, legal title opinion, invoice confirmation or collateral inspection. Advance rates, eligibility rules, aging tiers and reserves must be approved by authorized credit/risk staff and calibrated against actual lender agreements and loss history. Never count the same asset simultaneously as cash, inventory and receivables. Every period snapshot must have a clear as-of date in the upstream evidence system.

## Next

V7.6.7 should add category-specific dilution history, returns/credit-note reserves, counterparty/product concentration and inventory obsolescence curves calibrated from observed write-offs. V7.7 should evaluate adaptive production recourse under correlated disruptions, with expected loss, tail loss and service-shortfall reporting. A formal two-stage stochastic MILP with non-anticipativity constraints must be treated as a separate, more demanding step; scenario-by-scenario independent solves are not equivalent to that formulation.
