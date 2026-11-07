# SYNERGY V6.6.4-K — explicit federation reserve replenishment

**Status:** atomic member-funded replenishment method implemented and covered by unit tests.  
**Purpose:** allow a depleted federation guarantee reserve to be replenished only through explicit transfers from member cash.

## 1. Funding rule

`CreditLedger.replenish_federation_reserve(contributions_by_cell, day, replenishment_id)` accepts a complete per-cell contribution map. Contributions are debited from the specified member cash accounts and credited to the federation reserve. The method does not mint money, draw bank credit or treat a memorandum credit balance as cash.

The operation is all-or-nothing:
- the map must contain every known cell exactly once;
- every amount must be finite and non-negative;
- the total must be positive;
- the replenishment ID must be non-empty and unused;
- defaulted members cannot contribute;
- no contributor may fall below the ledger's minimum post-contribution cash floor.

All contributors are validated before any contribution is moved. A failed validation leaves member cash and reserve balances unchanged. The unique replenishment ID prevents accidental duplicate application.

## 2. Timing

The method accepts a non-decreasing ledger day. If the requested day is later than the current day, the ledger first processes collections, payable settlements and any defaults through that day. It then checks contributor eligibility and cash floors against the resulting balances. A member that defaults during that day cannot replenish the reserve afterward.

## 3. Audit and accounting

The snapshot reports:
- original federation reserve funding;
- cumulative replenishment amount;
- total federation reserve funded over its lifetime;
- current federation reserve balance;
- cumulative replenishment by cell;
- event records for each member contribution and the completed replenishment.

The consolidated cash identity includes member cash plus the federation reserve. A replenishment is an internal transfer, so it does not change consolidated cash. Reserve payouts to sellers remain separate guarantee transfers.

## 4. What is not modeled

There is no automatic levy, mandatory dues schedule, interest, penalty, legal enforcement, appeal, insolvency priority or replenishment trigger. This method only records a voluntarily supplied, explicitly funded contribution map. Governance must define who may call it, who is liable, how contributions are approved, and whether defaulted or distressed members receive exemptions.

All values are synthetic. This mechanism is an accounting prototype, not a legal contribution obligation or recommendation for a real EAEU guarantee institution.


## 5. CI validation

The full EIIOM CI workflow passed on code commit `436eee06d48ea01e190f7294b295254bbd90f7e4` with **167 pytest tests passed**. The replenishment tests verify successful member-funded reserve top-ups, cash conservation, duplicate-ID rejection, atomic rejection when any member would breach the floor, and exclusion of defaulted contributors.


## 6. Repeated-default stress fixture

A deterministic two-round fixture now tests depletion, funded replenishment and subsequent use:
- an initial 5-unit federation reserve pays the first cross-region default in full, leaving 5 units of seller loss;
- two non-defaulted service cells explicitly contribute 2 units each, replenishing the pool to 4;
- a second cross-region default consumes those 4 units and leaves 6 units of seller loss.

Total reserve payouts are 9 units, exactly equal to the initial 5-unit funding plus the 4-unit top-up. The cash-conservation residual is zero within numerical tolerance. This verifies that reserve replenishment can support a later claim only by transferring existing member cash; it does not erase the losses from the first default or create new system capital.
