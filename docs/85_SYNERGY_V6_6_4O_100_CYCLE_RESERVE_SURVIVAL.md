# SYNERGY V6.6.4-O — 100-cycle reserve survival experiment

**Status:** research implementation added; 20 focused reserve-recovery tests are present, including a repeated-run determinism check. Full EIIOM CI on the exact current V6.6.4-O head is pending.  
**Purpose:** compare no-replenishment and four contribution-allocation policies over 100 repeated reserve-claim / recovery cycles with paired exogenous paths and no external cash inflows.

## 1. What is being tested

V6.6.4-O adds a reproducible stress harness around the V6.6.4-N recovery planner. Each seed creates one heterogeneous opening-cash profile and one 100-day two-region claim path. Every allocation policy receives the exact same opening balances and claim path for that seed.

Policies compared:

1. `no_replenishment` — reserve claims are paid, but no recovery is attempted;
2. `equal` — equal member weights;
3. `production_capacity` — weights by synthetic production capacity;
4. `opening_cash` — weights by opening member cash;
5. `adaptive_liquidity` — weights by currently available contribution capacity.

The claim-size regimes are explicit synthetic inputs:

| Regime | Claim per region per cycle |
|---|---:|
| moderate | 1.0–2.0 |
| severe | 4.0–6.0 |
| systemic | 7.0–10.0 |

These ranges are scenario parameters, not estimates of actual EAEU default losses.

## 2. Claim semantics and an important limitation

The experiment uses `CreditLedger.apply_exogenous_guarantee_claim(...)`. It is a stress-only ledger operation. It transfers existing regional reserve cash to a beneficiary in the same region, then uses the federation reserve for the remaining claim. Any amount beyond both reserves is reported as uncovered.

It does **not** create a borrower, invoice, default, bank draw, new credit, cash or external inflow. It does not replace the production default-resolution path. In particular, it deliberately does not mark the beneficiary or a debtor as defaulted, allowing repeated portfolio-level claims to be applied over 100 cycles.

Therefore this is a reserve liquidity / recovery survival experiment, not a full simulation of 100 independent debtor defaults. A separate paired default-resolution experiment must later use actual payable invoices and the real default waterfall.

## 3. Funding and recovery assumptions

- 20 synthetic economic cells across WEST and EAST;
- heterogeneous opening member cash sampled deterministically from 80 to 120;
- initial regional reserve target: 20 per region;
- initial federation reserve target: 40;
- member minimum post-contribution cash: 20;
- ledger-owned maximum recovery contribution: 10% of opening cash per fixed 30-day simulation window;
- regional reserve deficits are funded by members of the matching region first;
- federation deficits use only the capacity remaining after regional allocations;
- no external cash inflows and no bank draws.

Initial reserve funding is already part of member opening cash: it is allocated from that same opening pool. It must never be double-counted as additional initial system money.

## 4. Metrics

For each seed and policy, the experiment records:

- total claim requested, paid and uncovered;
- claim coverage ratio;
- total member contributions and unfunded recovery requirement;
- any-reserve, regional-reserve and federation-reserve exhaustion cycles, each measured immediately after claims and before recovery;
- cycles ending with both regional reserves and the federation reserve restored to target;
- member cash floor breaches and minimum closing member cash;
- final member-cash Gini coefficient;
- cumulative contribution Gini, top-20% contribution share, maximum member contribution and contribution-to-opening-cash ratio;
- final regional and federation reserve balances;
- maximum cash-conservation residual;
- maximum excess over the ledger-owned 30-day member contribution cap;
- total system cash change;
- measured customer-collection inflows and external-supplier outflows;
- bank draws and external inflows.

The output preserves per-cycle observations as well as paired summaries across seeds, including cumulative member burden and contribution concentration. Paired path fingerprints must match across all five policies for each seed. Water-filling sums and ledger settlement iteration are explicitly sorted so repeated runs with the same inputs are bitwise reproducible. Recovery-plan fingerprints also bind the opening-cash capacity schedule, not just current cash and reserve balances.

## 5. Accounting invariant

The system's conserved cash is:

`Sum(MemberCash) + Sum(RegionalReserves) + FederationReserve`

At initialization this equals the sum of opening member cash, because initial reserve contributions are carved out of member opening cash. A reserve claim transfers cash from a reserve to a member beneficiary. Recovery transfers cash from members back into reserves. Neither operation creates or destroys cash.

Every cycle checks the ledger's cash-conservation residual immediately after claims and again after recovery. The experiment separately verifies zero bank draws, zero external inflows, no cash-floor breach and no 30-day contribution-cap excess.

## 6. Reproducibility

Run:

```bash
python scripts/run_synergy_v664o_reserve_survival.py --seed-start 11 --seed-count 10 --cycles 100 --shock-regime severe
```

The script writes a JSON report to:

`outputs/synergy_v664o_100_cycle_reserve_survival.json`

For a broader stress sweep, repeat with `moderate` and `systemic` regimes and preserve the same seed range when comparing policies.

## 7. Interpretation rules

A policy is not superior merely because it produces a higher reserve balance. Compare claim coverage, uncovered claims, contribution burden, cash-floor pressure, cash concentration and time spent at target together.

The zero-replenishment baseline measures the contribution of the initial reserve only. Recovery policies can increase covered claims by transferring member cash into the reserve and then to claim beneficiaries. This is redistribution of existing liquidity, not an increase in aggregate wealth.

A successful unit test proves the tested code path and invariants, not real-world solvency. Before production claims, the next research phase must connect this reserve stress harness to actual invoice/default events, empirical loss distributions, legal enforceability and observed member cash-flow data.
