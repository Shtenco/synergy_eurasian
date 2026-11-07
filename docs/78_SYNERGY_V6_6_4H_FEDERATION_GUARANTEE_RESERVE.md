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


## 5. Liquidity feedback from reserve funding

Federation reserve contributions are debited from member opening cash, including the buyer and seller in a later default scenario unless an explicit contribution map exempts them. This can reduce the buyer's ability to settle its invoice before default and therefore increase the residual claim presented to the guarantee waterfall. The reserve's gross payout cannot be interpreted in isolation from this funding-side liquidity effect. A production design would need to test alternative contribution timing, exemptions, replenishment rules and liquidity floors without assuming that any one rule is fair.


## 6. CI validation

CI on code commit `633a7568978820a5176174c1d2dc74319230c327` completed successfully with **138 tests passed**. The targeted federation fixtures confirmed:
- cross-region claim with a federation reserve: federation guarantee paid 5.0, seller write-off 5.75, cash-conservation residual 0.0;
- same-region claim: local reserve paid 5.0, federation reserve paid 3.0, local member assessment paid 2.65, residual write-off 0.0, cash-conservation residual 0.0.

The 5.75 cross-region residual is intentionally higher than the 5.5 no-federation baseline in the targeted fixture: the regional and federation reserves are both funded by member opening cash, so the defaulting buyer has less cash available to pay its invoice. This illustrates why reserve coverage and reserve-funding liquidity effects must be assessed together.

The latest full CI run on commit `864166836b7c7d57a818afe3adb78be7a6897988` also completed successfully: 138 tests passed, the financing stress experiment succeeded, and README integrity checks passed.


## 7. Multiple-default exhaustion test

A deterministic two-claim cross-region fixture now checks reserve drawdown under concurrent stress. Both buyers have a 30-unit payable and 20 units of cash; the federation reserve is funded with 7 units. Payables share the same due day and are resolved in stable invoice-ID order. The first eligible claim receives 7 units from the federation reserve and leaves 3 units of seller loss; the second receives zero after reserve exhaustion and leaves 10 units of seller loss. Consolidated cash remains conserved.

This test verifies the deterministic allocation order and the fact that a finite federation reserve cannot cover all claims once exhausted. It does not model simultaneous clearing, priority classes, pro-rata haircut among creditors or legal insolvency ranking. The present ordering rule is a software determinism rule, not a normative creditor-priority rule.
