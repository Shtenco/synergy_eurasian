# SYNERGY Productivity Flywheel Dynamic V2

**Model ID:** `SYNERGY-PRODUCTIVITY-FLYWHEEL-DYNAMIC-V2`  
**Status:** deterministic illustrative scenarios, not a forecast or measured enterprise performance.  
**Horizon:** 10 years. Currency: constant illustrative USD (2026 basis).

## 1. Why V2 exists

V1 showed a static surplus sensitivity. V2 adds time, investment cohorts, deployment lags, finite technology benefit lives, reserve draws and explicit unfunded gaps. It tests whether the system can accumulate productive capacity and R&D capability without treating fund transfers as new wealth.

The starting point is the earlier seven-sector repair target:
- cashflow after operating expenses and before replacement: $1,068,012.50/year;
- replacement CAPEX: $1,045,920/year;
- starting residual: $22,092.50/year;
- illustrative productive capital: $32.9m;
- initial reserve: 5% of productive capital = $1.645m.

## 2. Dynamic assumptions

| Parameter | Base scenario assumption |
|---|---:|
| Annual cashflow growth | 0%, 2.5% or 5% by macro scenario |
| Annual replacement-cost inflation | 2%, 5% or 10% |
| Productive automation share of positive residual | 50% |
| Breakthrough R&D share | 25% |
| Resilience reserve share | 25% |
| Automation project net residual yield | 15%/year |
| Automation deployment lag | 1 year |
| Automation benefit life | 5 years |
| R&D success probability | 20% |
| R&D net residual yield if successful | 30%/year |
| R&D deployment lag | 2 years |
| R&D benefit life | 5 years |

The automation and R&D yields are **scenario assumptions**, not measured returns or claims about AI / cellular automata. They represent incremental cashflow after incremental operating costs and replacement obligations. R&D is modeled in expected value: probability × successful-project yield. Actual R&D outcomes are discrete and volatile; expected value hides failures, concentration risk and long time-to-market.

## 3. Annual mechanics

Each year:
1. cashflow after OPEX but before replacement grows by the scenario rate;
2. replacement CAPEX grows by its own inflation rate;
3. active automation cohorts produce incremental net residual after their deployment lag and until their benefit life expires;
4. R&D cohorts produce probability-weighted expected net residual after their longer lag and within their benefit life;
5. positive residual is allocated 50/25/25 to automation, R&D and reserve;
6. negative residual draws the reserve; any remainder is recorded as an unfunded reproduction gap.

The model does not reduce productive capital silently when the gap is unfunded. That gap would require explicit emergency financing, service prioritization, replacement deferral or recognition of asset erosion in a later model.

## 4. Ten-year scenario results

| Scenario | Cashflow growth | Replacement inflation | Year-10 residual | Year-10 reserve | Unfunded gap over 10y |
|---|---:|---:|---:|---:|---:|
| Stagnation | 0% | 2% | −$206,958 | $643,190 | $0 |
| Moderate growth | 2.5% | 2% | +$133,185 | $1,836,141 | $0 |
| Strong growth | 5% | 2% | +$635,621 | $2,412,523 | $0 |
| Moderate growth / cost pressure | 2.5% | 5% | −$336,547 | $96,243 | $0 |
| Strong growth / cost pressure | 5% | 5% | +$56,275 | $1,744,338 | $0 |
| Severe replacement inflation | 5% | 10% | −$973,167 | $0 | $2,586,184 |

### Fund contributions over 10 years

| Scenario | Automation deployed | R&D funded | Reserve contributions | Reserve draws |
|---|---:|---:|---:|---:|
| Stagnation | $587 | $294 | $294 | $1,002,104 |
| Moderate growth / 2% replacement inflation | $382,283 | $191,141 | $191,141 | $0 |
| Strong growth / 2% replacement inflation | $1,535,047 | $767,523 | $767,523 | $0 |
| Moderate growth / 5% replacement inflation | $0 | $0 | $0 | $1,548,757 |
| Strong growth / 5% replacement inflation | $198,676 | $99,338 | $99,338 | $0 |
| Strong growth / 10% replacement inflation | $0 | $0 | $0 | $1,645,000 |

All fund contributions are allocations of the residual already counted. They must not be added again to the consolidated surplus. In the negative cases, the model correctly stops new investment contributions.

## 5. Break-even growth requirement without project returns

To cover replacement CAPEX in year 10 without relying on automation / R&D project returns, cashflow after OPEX must grow at least:

| Annual replacement inflation | Required annual cashflow growth |
|---:|---:|
| 2% | 1.787% |
| 5% | 4.781% |
| 10% | 9.770% |

This is a useful structural threshold. If replacement costs inflate faster than operational cashflow for long enough, the system eventually consumes its reserve even if the initial year is marginally positive.

## 6. What this proves — and what it does not

The model demonstrates the mechanics of a conditional flywheel:
- positive verified residual finances new automation, R&D and reserves;
- deployed automation and successful R&D can contribute future net residual after explicit lags;
- finite benefit lives prevent assuming every technology yields forever;
- reserves absorb temporary deficits;
- severe replacement inflation can overwhelm even strong operating growth.

It does **not** prove that the assumed 2.5–5% annual cashflow growth, 15% automation yield, 20% R&D success rate or 30% successful R&D yield are achievable. Those parameters require enterprise-level evidence and should be calibrated by sector and technology cohort.

## 7. Next calibration and risk work

Before using this model to approve investments:
1. replace the single portfolio with enterprise-level cohorts by sector;
2. measure output, price, quality, OPEX, compute, working capital and replacement obligations before and after deployment;
3. estimate automation yields from completed deployments, not vendor claims;
4. estimate R&D success probability and time-to-deployment from all projects, including failures;
5. add correlated failure, energy / compute price shocks, supply interruption, cyber incidents and delayed procurement;
6. add a Monte Carlo cohort engine to show probability of reserve exhaustion and distribution of outcomes;
7. add a reserve target based on essential-service months and replacement risk, not a fixed 5% assumption.

Implementation: `src/synergy_productivity_flywheel_dynamic_v2.py`; assumptions: `data/synergy_productivity_flywheel_dynamic_v2.json`; tests: `tests/test_productivity_flywheel_dynamic_v2.py`.


## 5A. Sector-level reality check: aggregate surplus can hide essential-sector deficits

The portfolio-level dynamic engine is not sufficient for service guarantees. The starting repair scenario has these sector cashflow / replacement pairs after the first repair targets:

| Sector | Cashflow before replacement | Replacement CAPEX |
|---|---:|---:|
| FOOD | $45,150 | $46,080 |
| HOUSING | $483,750 | $432,000 |
| ENERGY | $268,750 | $168,000 |
| HEALTH | $80,625 | $96,000 |
| EDUCATION | $24,187.50 | $72,000 |
| MOBILITY | $75,250 | $151,200 |
| COMPUTE | $90,300 | $80,640 |

At year 10, before adding portfolio-level automation / R&D project returns:

| Sector | 2.5% cashflow growth / 2% replacement inflation | 5% cashflow growth / 5% replacement inflation |
|---|---:|---:|
| FOOD | +$1,625 | −$1,515 |
| HOUSING | +$92,635 | +$84,295 |
| ENERGY | +$139,232 | +$164,111 |
| HEALTH | −$13,817 | −$25,044 |
| EDUCATION | −$56,806 | −$77,882 |
| MOBILITY | −$87,986 | −$123,715 |
| COMPUTE | +$17,292 | +$15,735 |
| **Net** | **+$92,176** | **+$35,986** |

The 2.5% / 2% case has a positive consolidated balance, but Health, Education and Mobility still need $158,608 of cross-subsidy in year 10. The 5% / 5% case has a positive consolidated balance, but Food, Health, Education and Mobility still need $228,155. The positive sector pools are $250,783 and $264,142 respectively. Cross-subsidies can cover these gaps in the illustrative arithmetic, but they remain internal transfers, not new system-wide value.

### Required annual cashflow growth for each sector to cover its own replacement in year 10

| Sector | Replacement inflation 2% | Replacement inflation 5% | Replacement inflation 10% |
|---|---:|---:|---:|
| FOOD | 2.21% | 5.21% | 10.22% |
| HOUSING | 0.85% | 3.82% | 8.76% |
| ENERGY | −2.68% | 0.18% | 4.95% |
| HEALTH | 3.80% | 6.85% | 11.94% |
| EDUCATION | 13.76% | 17.10% | 22.68% |
| MOBILITY | 9.37% | 12.59% | 17.95% |
| COMPUTE | 0.85% | 3.82% | 8.76% |

Negative required growth means the sector begins with enough margin to absorb some cashflow decline while still covering replacement by year 10. Education and Mobility are the structurally hardest sectors in this illustrative portfolio. They require explicit public-service contracts, productivity programs, or durable cross-subsidy commitments; they must not be assumed to become self-financing merely because the whole portfolio is positive.

The V2 engine now emits sector-level year-10 cashflow, replacement, residual and required growth thresholds in `sector_reconciliation_before_project_returns`. Project returns are still reported at portfolio level until investment cohorts can be assigned to actual sectors and enterprises. This prevents portfolio-level returns from being falsely attributed to sectors that did not receive the investment.
