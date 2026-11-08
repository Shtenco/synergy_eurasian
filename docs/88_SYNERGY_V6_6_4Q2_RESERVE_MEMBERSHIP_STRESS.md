# SYNERGY EURASIAN V6.6.4-Q2 — independent reserve membership stress

**Status:** local deterministic research experiment. Synthetic parameters only.
This is not a production CreditLedger run, not an empirical forecast, and not
evidence of real reserve sufficiency.

## Purpose

Test whether regional reserve membership and federation reserve membership can
be independent while every participant retains one shared contribution capacity
across both tiers. The experiment also tests permanent member exclusion after
default and the effect of adding eligible WEST participants.

## Model configuration

| Parameter | Value |
|---|---:|
| Physical cells in fixture | 20 (10 WEST, 10 EAST) |
| Opening cash per cell | 1,000 |
| Protected cash floor | 900 |
| Contribution rate | 10% of current cash |
| Maximum contribution per 30-day period | 80 |
| WEST reserve need per cycle | 200 |
| EAST reserve need per cycle | 200 |
| Federation reserve need per cycle | 300 |
| Number of cycles | 100 |
| Default events | W0 at start; W1 at cycle 25; E0 at cycle 50 |
| Contribution order | regional funds first, federation second |
| Allocation policies | pro-rata and deterministic FCFS |

A cycle represents one completed 30-day contribution window. The period cap
refreshes only because a new 30-day period has elapsed. Member cash and the
protected floor carry forward continuously. Every member's regional and
federation contributions consume the same per-cycle cap.

### Membership cases

**Baseline**
- WEST: W0, W1, W2
- EAST: E0, E1, E2
- Federation: W2, W3, W4, W5, E2, E3, E4, E5

**Expanded WEST**
- WEST: W0, W1, W2, W3, W4
- EAST: E0, E1, E2
- Federation unchanged

The expanded case adds W3 and W4 to WEST's local fund; both remain federation
members. This is a sensitivity test, not a governance recommendation.

### External inflow sensitivity

Each solvent cell receives the same exogenous operating inflow per cycle:
0, 40, 60, 80, or 100 units. Defaulted cells receive no further inflow.
This is an explicit input, not internally generated money or modeled profit.
The system cash identity is checked each cycle:

    ending member cash = opening member cash + cumulative external inflow
                         - cumulative contributions

Reserve contributions are transfers of existing member cash. They are not
revenue, credit creation, or net new system wealth. The fixture models
contribution capacity and unmet reserve funding demand; it does not simulate
reserve claim payouts or seller loss recoveries.

## 100-cycle results

All values are synthetic units. "Unfunded" is the cumulative amount of reserve
funding demand that eligible members could not contribute.

| Inflow / solvent cell / cycle | Membership | Method | Contributions | Unfunded | WEST gap | EAST gap | Federation gap |
|---:|---|---|---:|---:|---:|---:|---:|
| 0 | Baseline | Pro-rata | 1,100 | 68,900 | 19,800 | 19,708.11 | 29,391.89 |
| 0 | Baseline | FCFS | 1,100 | 68,900 | 19,800 | 19,740 | 29,360 |
| 40 | Baseline | Pro-rata | 40,020 | 29,980 | 14,840 | 9,761.92 | 5,378.08 |
| 40 | Baseline | FCFS | 40,020 | 29,980 | 14,840 | 9,820 | 5,320 |
| 60 | Baseline | Pro-rata | 52,811.02 | 17,188.98 | 12,360 | 4,828.98 | 0 |
| 60 | Baseline | FCFS | 52,680 | 17,320 | 12,360 | 4,960 | 0 |
| 60 | Expanded WEST | Pro-rata | 59,285.99 | 10,714.01 | 1,510.99 | 4,836.33 | 4,366.70 |
| 60 | Expanded WEST | FCFS | 59,480 | 10,520 | 1,500 | 4,960 | 4,060 |
| 80 | Baseline | Pro-rata | 57,880 | 12,120 | 10,080 | 2,040 | 0 |
| 80 | Baseline | FCFS | 57,880 | 12,120 | 10,080 | 2,040 | 0 |
| 80 | Expanded WEST | Pro-rata | 67,960 | 2,040 | 0 | 2,040 | 0 |
| 80 | Expanded WEST | FCFS | 67,960 | 2,040 | 0 | 2,040 | 0 |
| 100 | Baseline | Pro-rata | 57,880 | 12,120 | 10,080 | 2,040 | 0 |
| 100 | Baseline | FCFS | 57,880 | 12,120 | 10,080 | 2,040 | 0 |
| 100 | Expanded WEST | Pro-rata | 67,960 | 2,040 | 0 | 2,040 | 0 |
| 100 | Expanded WEST | FCFS | 67,960 | 2,040 | 0 | 2,040 | 0 |

The complete 20-scenario aggregate sensitivity grid is retained in
reports/synergy_v664q2_summary.json. Cycle-level records for all 100 cycles
under the principal 80-unit inflow assumption (both membership cases and both
allocation methods; 400 rows) are retained in
reports/synergy_v664q2_cycle_results.csv. The Python runner deterministically
reconstructs all cycle paths for the other inflow sensitivities.

## Findings

1. **Independent membership has a measurable local effect.** At 80 units of
   inflow per solvent cell per cycle, adding W3 and W4 to WEST removes WEST's
   cumulative 10,080-unit gap. It does not remove EAST's 2,040-unit gap after
   E0 defaults at cycle 50.
2. **Membership cannot create contribution capacity.** At zero inflow, only
   the initial cash buffer above the protected floor can be transferred. Total
   contributions across the 100-cycle path are only 1,100 units.
3. **The contribution cap becomes binding.** Increasing inflow from 80 to 100
   does not improve the results because the 80-unit per-window cap, not cash,
   is then binding for solvent eligible members.
4. **Default exclusion is path-dependent.** W1's default at cycle 25 reduces
   the baseline WEST membership to W2 only. E0's default at cycle 50 reduces
   EAST's eligible local contributors to E1 and E2.
5. **No universal ranking of pro-rata and FCFS is established.** Their results
   differ modestly at some intermediate inflow levels and coincide in other
   scenarios. Allocation fairness, concentration, timing and robustness need
   separate evaluation using production-compatible ledger semantics.

## Contribution and ending-cash concentration at 80-unit inflow

The aggregate report also calculates the Gini coefficient of cumulative member
contributions, the top-20% share of contributions, and the Gini coefficient
of final member cash. These are separate distributions and should not be
confused.

| Membership | Method | Contribution Gini | Top-20% contribution share | Final-cash Gini | Min final cash | Max final cash |
|---|---|---:|---:|---:|---:|---:|
| Baseline | Pro-rata | 0.54597069 | 48.418% | 0.34379101 | 1,000 | 9,000 |
| Baseline | FCFS | 0.62684865 | 55.287% | 0.38285879 | 1,000 | 9,000 |
| Expanded WEST | Pro-rata | 0.53502455 | 45.138% | 0.39204001 | 1,000 | 9,000 |
| Expanded WEST | FCFS | 0.56297822 | 47.087% | 0.42121858 | 1,000 | 9,000 |

In this fixture, pro-rata spreads contribution burden more evenly than FCFS:
both its contribution Gini and top-20% share are lower. Expanding WEST
membership also lowers contribution concentration while closing the WEST
funding gap. However, final-cash inequality rises in the expanded-membership
case. The reason is structural: cells outside the reserve membership continue
to accumulate the assumed operating inflow but are not assessed. This is a
warning against treating a better reserve coverage ratio as proof of fair
system-wide burden sharing. Membership scope, contribution weights and
governance need to be designed together.

## Invariants checked by the local fixture

- Unknown cell IDs and cross-region local membership are rejected.
- Regional and federation membership are independent.
- Defaulted cells contribute zero and remain excluded.
- Regional assessments execute before federation assessments.
- A dual member has one shared per-cycle contribution capacity.
- No solvent member falls below the protected cash floor.
- Member cash conservation reconciles to exogenous inflow less contributions.
- No negative or non-finite scenario outputs are accepted.

The runner includes eight internal control assertions; the pytest module adds
seven regression tests. Passing these tests validates this standalone fixture
only. It does not validate the production CreditLedger, reserve recovery
planner, real invoice settlement, or GitHub CI.

## Limitations and next gate

This Q2 fixture does **not** yet model:
- production purchase authorization and payable invoices;
- cash-first seller settlement and the production default waterfall;
- reserve balances, claims, reserve payouts and seller write-offs;
- bank draws, external borrowing or external investor capital;
- endogenous operating revenue, costs, payroll, taxes or asset valuation;
- NAV, mark-to-market, liquidity haircuts or insolvency recovery;
- a legally governed admission/removal process for reserve members.

Therefore the experiment must not be described as the required 100-cycle
production-default experiment. The next gate is to implement and test explicit
regional/federation membership in the production ledger, then connect it to the
actual invoice/default/recovery path. Only after that can a continuous 100-cycle
production-default simulation support conclusions about reserve adequacy.
