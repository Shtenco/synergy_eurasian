# SYNERGY V6.6.4-I — liquidity-capped federation reserve contributions

**Status:** global contribution allocator and paired financing experiment implemented; CI validation pending.  
**Purpose:** prevent local and federation reserve contributions from jointly exceeding a declared share of any member's opening cash.

## 1. Combined member contribution cap

For each cell (i), the combined reserve funding obligation is constrained by:

[
R_i + F_i leq alpha C_i
]

where:
- (R_i) is the member's contribution to its regional reserve;
- (F_i) is its contribution to the federation-wide reserve;
- (C_i) is its opening cash;
- (alpha) is the maximum combined contribution fraction.

The allocator receives the regional contribution map and computes the remaining headroom for the federation reserve. It does not independently apply the full cap a second time to the federal contribution. If aggregate remaining headroom is insufficient to fund the requested federation reserve, allocation fails rather than exceeding the cap or creating reserve cash.

## 2. Allocation rules

Two deterministic weight schemes are supported:
- equal contribution weights across all cells;
- production-capacity weights for primary, processing and manufacturing cells.

A weighted water-filling procedure redistributes the remaining target when a member reaches its cap. All allocations are deterministic and the final contribution sum is reconciled within floating-point tolerance.

The production-capacity scheme excludes support cells. This is a modeling choice, not a fairness conclusion. It may charge production cells for a guarantee that also benefits logistics, energy, warehouse and service cells.

## 3. Paired experiment

`compare_liquidity_capped_federation_contributions(...)`:
- uses a complete heterogeneous opening-cash fixture;
- takes any existing regional contribution map into account;
- keeps the reserve total fixed across the replay;
- compares financing modes on common seed-specific environments;
- reports the per-cell contribution maps and standard guarantee, service, default, debt and cash-conservation metrics.

The CLI option `--federation-liquidity-cap` writes `outputs/synergy_v66_federation_liquidity_cap.json`. CI runs the scenario with 5 units per region in local reserves, a 10-unit federation reserve and a 10% combined per-member contribution cap.

## 4. Accounting and interpretation

Regional and federation reserve balances remain separate cash accounts. Funding is transferred out of member opening cash; guarantee payments are transfers from reserve balances to sellers. Neither funding nor payouts mint money. The consolidated cash identity continues to include member cash, regional reserves, federation reserve, bank movements and external cash flows.

A percentage of opening cash is only a transparent initial-liquidity constraint. It is not a complete measure of ability to pay, risk, expected benefit, wealth, or fairness. The experiment does not specify legal contribution authority, exemptions, hardship relief, appeals, replenishment or governance.

All values are synthetic. No real-world EAEU guarantee contribution or reserve size is recommended.


## 5. CI smoke-sample observation

The three-seed, 20-day severe synthetic run used a 10-unit federation reserve, 5 units per region in local reserves and a 10% combined member contribution cap. The capacity-weighted federation contribution allocator funded exactly 10 units while keeping each member's combined local-plus-federal contribution within its cap.

| Financing mode | Mean service level | Mean federal guarantee paid | Mean federal reserve remaining | Maximum cash-conservation residual |
|---|---:|---:|---:|---:|
| Mutual credit | 69.533% | 0.279 | 9.721 | 9.1×10⁻¹³ |
| Hybrid | 69.647% | 10.000 | 0.000 | 1.8×10⁻¹² |

In this small fixture, the hybrid path exhausted the federation reserve while the mutual-credit path used only a small fraction. This is a scenario-specific exposure result, not evidence that hybrid is generally riskier or that the reserve size is adequate. The sample does not establish a recommended contribution rule or reserve target.

**Validation:** 148 pytest tests passed on commit `c5f094f3ea46c62fb50e1ac26f48c78e320d331a`. Full EIIOM CI completed successfully, including the new multi-default exhaustion test and federation liquidity-cap experiment. The README integrity check also passed on the preceding model commit. The CI step wrote `outputs/synergy_v66_federation_liquidity_cap.json`.


## 6. Absolute cash floor across both reserve tiers

The federation allocator accepts `minimum_post_contribution_cash`. It computes the combined member cap as the minimum of the declared fraction of opening cash and the amount above the absolute floor, then subtracts the member's already-funded regional contribution. A regional contribution that already breaches the combined floor causes rejection; it is not concealed by assigning zero federation contribution.

The CI fixture uses a 75-unit synthetic minimum post-contribution cash floor. This is a mechanical test threshold, not a real-world liquidity recommendation or an estimate of working-capital requirements.


The ledger also checks the absolute floor after combining both contribution maps. This independent guard prevents a manually constructed regional-plus-federation funding map from bypassing the allocator's feasibility checks; the configured floor is included in snapshots.


**Additional validation:** 158 pytest tests passed and the full EIIOM CI completed successfully on commit `b9d767165ea55e4fb77c37266d5ee3b3614361fd`. This run included the ledger-level absolute cash-floor guard, reserve sizing with the floor, the heterogeneous reserve-allocation comparison and the federation liquidity-cap smoke experiment. Maximum consolidated cash-conservation residuals in the reserve experiments remained at approximately 10⁻¹².


## 6. Absolute post-contribution operating-cash floor

The federation allocator accepts `minimum_post_contribution_cash` in addition to the combined percentage cap. For each member, available federal contribution headroom is:

[
F_i leq maxleft(0,min(alpha C_i, C_i-M)-R_iight)
]

where (C_i) is opening cash, (M) is the absolute minimum cash floor, (R_i) is the regional reserve contribution and (alpha) is the combined contribution fraction. If the requested federation reserve cannot be funded within these remaining caps, allocation fails.

The same floor is passed into the credit ledger, which independently checks regional plus federal contributions before initializing member cash. The floor therefore cannot be bypassed by calling the ledger directly or by supplying a contribution map generated elsewhere. It remains a synthetic liquidity safeguard, not an empirically calibrated operating-cash requirement.


## 7. CI validation of combined caps and cash floor

The latest complete financing experiment on commit `f05e1d5d3ed14648636af810a73ea85b535813f5` passed **160 pytest tests** and the full EIIOM CI workflow. The federation reserve scenario funded 10 units with a 10% combined contribution cap and an absolute 75-unit post-contribution cash floor. The ledger independently enforced the floor after deducting both regional and federation contributions.

In the three-seed, 20-day severe sample, the federation contribution total was exactly 10 units. Maximum consolidated cash residual was approximately (1.8	imes10^{-12}) in hybrid mode and (9.1	imes10^{-13}) in mutual-credit mode. This verifies accounting consistency for the synthetic fixture; it does not validate 75 units as a real operating-liquidity threshold.
