# SYNERGY V6.6.4-F — liquidity-capped reserve contributions

**Status:** heterogeneous member opening cash, capped contribution allocator and paired financing experiment implemented.  
**Purpose:** test whether a regional guarantee reserve can be funded without forcing any member to contribute above a declared share of its opening cash.

## 1. Heterogeneous opening cash

The credit ledger now accepts `initial_cash_by_cell`, a complete map from every economic-cell ID to its opening cash. The existing scalar `initial_cash_per_cell` remains the compatibility default.

The map must contain every known cell exactly once. Values must be finite and non-negative. Reserve contributions are checked against each member's own opening cash, not against a system-wide or average amount. Consolidated opening cash is the sum of the member balances. The reserve remains a separate cash account and the system cash identity includes both member cash and reserve cash.

If an explicit heterogeneous cash map is supplied with an equal contribution map that exceeds one member's opening balance, initialization fails. The system does not silently redistribute that member's obligation.

## 2. Liquidity-capped allocation

`build_liquidity_capped_reserve_contributions(...)` supports two contribution weights:
- `equal_all_members`;
- `production_capacity_weighted`.

Each member has a hard contribution cap:

[
cap_i = opening_cash_i 	imes max_contribution_fraction
]

The allocator uses a deterministic weighted water-filling procedure. Members that reach their caps are removed from the active set and the remaining reserve target is reallocated among the remaining eligible members. If aggregate eligible caps cannot fund the requested regional reserve, the allocator raises an error instead of exceeding the cap or creating reserve cash.

The capacity-weighted scheme continues to exclude support cells from the contribution weights. The cap limits the burden on included members; it does not establish that the allocation is fair.

## 3. Paired experiment

`compare_liquidity_capped_reserve_contributions(...)` passes the heterogeneous opening-cash map and exact per-cell reserve contributions into the existing common-environment financing replay. It reports the map, reserve target, cap fraction, service level, defaults, guarantee use, debt and cash-conservation metrics.

The CLI option `--liquidity-capped-reserve` runs a deterministic synthetic cash fixture and writes `outputs/synergy_v66_liquidity_capped_reserve.json`. CI runs this scenario alongside the other V6.6 financing experiments.

## 4. Limits

The heterogeneous cash fixture is synthetic and deterministic, not empirical data about firms or regions. A percentage of opening cash is only a transparent liquidity constraint; it is not a complete measure of ability to pay, risk, benefit received, wealth, or fairness. The allocator does not yet account for cash-flow volatility, essential operating reserves, debt seniority, or future liquidity needs. No legal contribution obligation is implied.


## 5. CI smoke-sample observation

CI ran three seeds for 20 days in the severe synthetic regime with 10 units of reserve per region and a 10% maximum contribution of each member's opening cash. The two-region total contribution was 20 units. In the mutual-credit mode, mean service level was 69.731%, mean defaults were 1.333 per run, mean guarantee payments were 6.725 units, and the maximum cash-conservation residual was zero. In hybrid mode, mean service level was 69.647%, mean defaults were 1.333, mean guarantee payments were 8.675, and the maximum cash-conservation residual was approximately 1.36×10⁻¹².

These are smoke-test observations from a small synthetic sample, not estimates of real-world performance and not a comparison against an otherwise identical uncapped allocation. The key verified properties are that the requested reserve was funded, no member exceeded the 10% contribution cap, and cash remained conserved.
