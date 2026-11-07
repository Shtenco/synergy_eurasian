# SYNERGY V6.6.4-N — adaptive multi-level reserve recovery

**Status:** additive research implementation; GitHub Actions validation pending for the implementation commit.  
**Purpose:** plan and execute repeated member-funded restoration of regional and federation guarantee reserves without creating cash or bypassing member liquidity limits.

## 1. Scope

V6.6.4-K provided explicit federation-reserve replenishment. V6.6.4-N extends the accounting interface to fund both regional and federation reserves in one atomic settlement and adds a non-mutating recovery planner.

The planner supports four allocation rules:

- `equal`: equal weights among eligible members;
- `production_capacity`: weights by the synthetic cell capacity in the network topology;
- `opening_cash`: weights by opening member cash;
- `adaptive_liquidity`: weights by the member's currently available contribution capacity.

All four rules use deterministic capped weighted water-filling. Regional shortfalls are allocated to members of the matching region first. The remaining eligible capacity is then available for the federation reserve. A member's regional and federation contributions share one capacity limit.

## 2. Member contribution capacity

For member i, the per-period ceiling is:

`PeriodLimit_i = alpha * OpeningCash_i`

Prior recovery contributions in the same `recovery_period_id` consume this ceiling. Current cash-floor capacity is:

`CashCapacity_i = max(0, CurrentCash_i - MinimumCashFloor)`

Available capacity is:

`K_i = max(0, min(CashCapacity_i, PeriodLimit_i - PriorPeriodContributions_i))`

Defaulted members have zero capacity. A period identifier is therefore part of the control, not merely a reporting label: a caller cannot reset the period limit by submitting another replenishment ID.

The period identifier is not caller-selectable. The research ledger derives it from its simulation day using fixed 30-day windows (`day-window-{day // 30}`) and rejects arbitrary labels. The maximum fraction is owned by the ledger configuration (`reserve_recovery_contribution_fraction`, default 10% of opening cash). The planner may request a lower fraction but cannot raise the ledger ceiling, and the ledger independently rejects caller-supplied per-member caps above its own setting. The 10% value is a synthetic policy parameter. A production policy would require calendar-period semantics, a governed assessment schedule, evidence-backed cash availability, exemptions and appeals.

## 3. Targeting and allocation

The caller supplies explicit regional and federation targets. The planner calculates each reserve's deficit:

`RegionalDeficit_r = max(0, RegionalTarget_r - RegionalBalance_r)`

`FederationDeficit = max(0, FederationTarget - FederationBalance)`

Regional deficits are funded first, within their own region. Federation funding is then allocated across all members using the remaining combined capacity. If capacity is insufficient, the plan is partial and reports the unfunded amount; it does not invent money or silently relax the target.

This release accepts explicit targets. A stress-quantile / CVaR target-calibration engine is a later research increment; no target is claimed to be an empirically calibrated EAEU capital requirement.

## 4. Plan / execute separation

`plan_reserve_recovery(...)` is non-mutating. It records a deterministic fingerprint of:
- ledger day;
- member cash and default status;
- regional and federation reserve balances;
- prior contributions in the named recovery period.

`execute_reserve_recovery(...)` rejects a stale plan. It also requires the ledger day to match the planning day. The underlying ledger validates the complete regional and federation contribution maps, every member's combined cash floor, default status, duplicate operation ID and cumulative period limit before changing any balance.

The ledger requires the canonical ledger-derived period ID and the complete per-member period ceiling map; direct callers cannot omit the cumulative-cap control or choose a fresh arbitrary period label. The ledger then debits member cash and credits the matching regional and federation reserve accounts. Regional contributions can only be credited to the contributor's own region. Each leg is recorded as an audit event.

The older `replenish_federation_reserve(...)` API remains available for compatibility with V6.6.4-K.

## 5. Accounting invariants

The consolidated cash identity remains:

`MemberCash + RegionalReserveCash + FederationReserveCash`

Internal reserve replenishment changes the location of cash but not the consolidated total. It must therefore leave the existing cash-conservation residual unchanged within floating-point tolerance.

For every member:

`RegionalContribution_i + FederationContribution_i <= CurrentCash_i - MinimumCashFloor`

For every recovery period:

`CumulativeRegionalContribution_i + CumulativeFederationContribution_i <= alpha * OpeningCash_i`

No bank draw, credit creation, token mint, external cash flow or implicit liability is created by reserve recovery.

## 6. Repeated-cycle research protocol

The next stress experiment should run repeated sequences of:
1. apply a common exogenous default/shock path;
2. resolve claims using the existing local-first / federation-second waterfall;
3. calculate both reserve deficits;
4. plan and execute member-funded recovery;
5. record member cash, reserve balances, funded and unfunded deficits, cumulative burden and conservation residual;
6. repeat under correlated defaults and declining member liquidity.

Required comparisons include all four allocation rules, no-replenishment baseline, fixed targets and externally specified stress targets. Report recovery ratio, time-to-target, uncovered loss, reserve exhaustion frequency, member cash-floor breaches, contribution concentration and total cash residual.

A passing deterministic unit test is not evidence of long-run economic sustainability. The repeated-cycle experiment and independent parameter calibration remain outstanding.

## 7. Validation boundary

The new unit tests cover non-mutating planning, two-level cash settlement, regional membership boundaries, production-capacity weights, stale-plan rejection, cumulative period caps and atomic floor rejection. Full EIIOM CI must pass on the exact implementation commit before this increment is treated as validated.

All values and capacities in this kernel are synthetic. The code is a research/accounting prototype, not a legal guarantee fund, mandatory levy, solvency standard, calibrated reserve recommendation or production deployment approval.
