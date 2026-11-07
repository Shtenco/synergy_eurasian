# SYNERGY V6.6.4-H — federation-wide guarantee reserve

**Status:** separately funded federation reserve and cross-region guarantee waterfall implemented with targeted tests.  
**Purpose:** test whether a federation-level reserve can cover cross-region trade-credit defaults that are intentionally outside a local regional pool.

## 1. Two-tier reserve waterfall

For an internal supplier invoice that defaults:

1. If buyer and seller are in the same region, the local regional reserve pays first.
2. The federation-wide reserve pays next, including for cross-region invoices.
3. For remaining same-region loss only, the optional local capped member assessment is attempted.
4. Any residual loss is recorded as seller-side trade bad debt.

A local regional reserve is never used to cover a cross-region claim. A federation reserve is a separate, explicitly funded pool. It is not a transfer of the regional reserve and is not created by issuing credit.

## 2. Funding and accounting

The constructor accepts:
- `federation_pool_reserve_total`;
- optional `federation_reserve_contributions_by_cell`.

If no per-cell map is supplied, the federation reserve is funded equally across all cells. If a map is supplied, it must contain every known cell exactly once and sum to the declared reserve total. Combined regional and federation contributions cannot exceed any member's opening cash. Heterogeneous opening cash is supported.

The federation reserve is tracked separately from member cash and regional reserves. The consolidated cash-conservation identity includes:
- member cash;
- regional reserve balances;
- federation reserve balance;
- external cash flows and bank movements.

The invoice audit records local guarantee payment, federation guarantee payment, member assessment payment and residual write-off as distinct amounts.

## 3. Targeted tests

Deterministic synthetic fixtures verify:
- a cross-region default receives no local regional guarantee;
- the federation pool can cover part of that cross-region claim;
- a same-region default uses the local reserve before the federation reserve;
- the optional local assessment is attempted only after both reserve tiers;
- funding contributions are fully reconciled and cannot exceed member opening cash;
- cash conservation remains within numerical tolerance.

## 4. Scope and exclusions

This is a two-region synthetic accounting experiment, not a legally constituted supranational guarantee institution. It does not yet model FX conversion, currency mismatch, cross-border settlement delays, sovereign or jurisdictional risk, customs/tax, capital adequacy, legal priority, dispute resolution, or federation governance. The federation reserve is not automatically replenished. No real-world EAEU reserve size or cross-border risk estimate is implied.
