# SYNERGY ECONOMY 6.3 — consolidated seven-sector research model

**Model ID:** `SYNERGY-ECONOMY-7S-V1`  
**Repository:** `Shtenco/synergy_eurasian`  
**Status:** reproducible illustrative research model; not calibrated to observed enterprise or national-account data.  
**Currency basis:** constant illustrative USD (2026 purchasing-power basis); no nominal inflation model.

## 1. Purpose and relationship to EIIOM

This document consolidates the seven-sector economy models developed in the research conversation and places them inside the existing EURASIAN / Real Economy OS architecture.

It does **not** replace EIIOM. EIIOM remains the multi-country, multi-sector project-allocation optimizer. This model is a smaller transparent reference engine for:

- seven essential-sector capital and replacement accounting;
- public-ownership portfolio accounting;
- a seven-by-seven input-output dependency matrix;
- household basket automation and labor-release sensitivities;
- supply-capacity stress tests;
- long-horizon capital / reserve / dividend mechanics;
- explicit separation of real production, cashflow, ownership claims and transfers.

The executable implementation is `src/synergy_economy_7sector.py`; editable assumptions are in `data/synergy_economy_7sector_v1_assumptions.json`; regression tests are in `tests/test_economy_7sector.py`.

## 2. Evidence labels

Every number in this model belongs to one of these classes:

| Label | Meaning |
|---|---|
| OBSERVED | Measured from an identified source or operating enterprise |
| CONTRACTED | Enforceable contract or verified order |
| MODEL_ASSUMPTION | Explicit input selected for an experiment |
| MODEL_OUTPUT | Result computed from stated assumptions |
| TARGET | Desired threshold, not an achieved result |
| UNCALIBRATED | Requires empirical data before real-world use |

The seven-sector capital costs, sector yields, replacement rates, automation adoption and effectiveness, input-output coefficients, ownership shares and crisis schedule are **MODEL_ASSUMPTION**. The calculated totals are **MODEL_OUTPUT**. None is a statement of current SYNERGY-owned assets, actual revenue, investor return or regional statistical fact.

## 3. Seven sectors and capital intensity

Reference population: 1,000 people.

| Sector | Productive capital | Capital share | Gross cash yield | Replacement rate |
|---|---:|---:|---:|---:|
| FOOD | $1.20m | 3.65% | 3.5% | 4.0% |
| HOUSING | $18.00m | 54.71% | 2.5% | 2.5% |
| ENERGY & WATER | $5.00m | 15.20% | 5.0% | 3.5% |
| HEALTH | $2.50m | 7.60% | 3.0% | 4.0% |
| EDUCATION | $1.50m | 4.56% | 1.5% | 5.0% |
| MOBILITY | $3.50m | 10.64% | 2.0% | 4.5% |
| COMPUTE | $1.20m | 3.65% | 7.0% | 7.0% |
| **Total** | **$32.90m** | **100%** | | |

These are capital-intensity placeholders, not construction estimates. Housing dominates this illustrative asset stock; this does not mean SYNERGY should immediately purchase the entire housing stock. Ownership, long-term supply contracts, leases, concessions and service guarantees are separate instruments.

## 4. Gross cashflow is not free cashflow

This is the most important accounting correction in the model.

For sector (i):

[
GCF_i=K_i y_i
]

[
ReplacementCAPEX_i=K_i d_i
]

[
Residual_i=GCF_i-ReplacementCAPEX_i
]

where (K_i) is productive capital, (y_i) the assumed gross cash yield and (d_i) the annual replacement requirement.

The aggregate result is:

| Measure | Whole seven-sector system |
|---|---:|
| Productive capital | $32,900,000 |
| Gross cashflow before replacement | $993,500 |
| Replacement CAPEX | $1,089,500 |
| Residual after replacement | **−$96,000** |
| Weighted gross cash yield | 3.0198% |
| Weighted replacement rate | 3.3116% |

The initial system therefore does **not** cover the assumed annual replacement requirement. It cannot sustainably distribute dividends or grow capital under these base cash-yield assumptions.

The simple replacement threshold is:

[
y_{min}=rac{sum_i K_i d_i}{sum_i K_i}=3.3116%
]

At 3.3116%, there is no surplus for growth, reserves or distributions. A positive residual is necessary but not sufficient for viability: taxes, debt service, working-capital changes, insurance, environmental liabilities and other costs must also be included if they are not already included in the sector cash-yield inputs.

### Sector residuals

| Sector | Gross cashflow | Replacement CAPEX | Residual |
|---|---:|---:|---:|
| FOOD | $42,000 | $48,000 | −$6,000 |
| HOUSING | $450,000 | $450,000 | $0 |
| ENERGY & WATER | $250,000 | $175,000 | +$75,000 |
| HEALTH | $75,000 | $100,000 | −$25,000 |
| EDUCATION | $22,500 | $75,000 | −$52,500 |
| MOBILITY | $70,000 | $157,500 | −$87,500 |
| COMPUTE | $84,000 | $84,000 | $0 |

Energy's positive residual cannot be treated as a free system-wide dividend while the other sectors' replacement requirements remain unfunded. Transfers from one sector to another must be explicit, governed and limited by the source sector's own renewal and resilience needs.

## 5. Public ownership portfolio

The initial illustrative public ownership shares are:

| Sector | Public share |
|---|---:|
| FOOD | 35% |
| HOUSING | 40% |
| ENERGY & WATER | 70% |
| HEALTH | 55% |
| EDUCATION | 80% |
| MOBILITY | 50% |
| COMPUTE | 30% |

This produces:

| Measure | Public portfolio |
|---|---:|
| Public productive capital | $15,805,000 |
| Share of total productive capital | 48.04% |
| Gross cashflow | $489,150 |
| Replacement CAPEX | $538,250 |
| Residual after replacement | **−$49,100** |
| Public weighted gross cash yield | 3.095% |
| Public weighted replacement rate | 3.4056% |

The public portfolio is a subset of the whole system. Its $489,150 gross cashflow must never be added to the whole-system $993,500; doing so would double count it. The same applies to public replacement CAPEX versus whole-system replacement CAPEX.

The public portfolio also fails its assumed replacement test. Its ownership share does not make it financially self-sustaining. Socially necessary low-cash-yield assets may still be supported by transparent public-service contracts, explicit fiscal transfers or cross-subsidies, but those transfers must be visible and funded.

## 6. Seven-by-seven input-output matrix

Rows are supplying sectors; columns are consuming sectors. (A_{ij}) is the amount of supplier-sector (i)'s intermediate output needed per unit of gross output in consuming sector (j).

| Supplier \ Consumer | FOOD | HOUSING | ENERGY | HEALTH | EDUCATION | MOBILITY | COMPUTE |
|---|---:|---:|---:|---:|---:|---:|---:|
| FOOD | 0.02 | 0.01 | 0.01 | 0.03 | 0.02 | 0.01 | 0.00 |
| HOUSING | 0.01 | 0.03 | 0.01 | 0.02 | 0.02 | 0.01 | 0.01 |
| ENERGY | 0.08 | 0.12 | 0.10 | 0.08 | 0.06 | 0.15 | 0.12 |
| HEALTH | 0.01 | 0.00 | 0.00 | 0.02 | 0.00 | 0.00 | 0.00 |
| EDUCATION | 0.01 | 0.01 | 0.01 | 0.02 | 0.02 | 0.01 | 0.02 |
| MOBILITY | 0.10 | 0.08 | 0.05 | 0.08 | 0.04 | 0.10 | 0.03 |
| COMPUTE | 0.02 | 0.02 | 0.03 | 0.05 | 0.05 | 0.03 | 0.10 |

For final demand (d), gross output is:

[
x=(I-A)^{-1}d
]

For the unit experiment (d=(1,1,1,1,1,1,1)^T):

| Sector | Gross output |
|---|---:|
| FOOD | 1.123683 |
| HOUSING | 1.138930 |
| ENERGY | 1.989641 |
| HEALTH | 1.031874 |
| EDUCATION | 1.130175 |
| MOBILITY | 1.636437 |
| COMPUTE | 1.402375 |
| **Total** | **9.453116** |

Spectral radius:

[
ho(A)=0.250669<1
]

Intermediate output is 2.453116 units, or 25.9503% of gross output in this illustrative experiment.

The matrix is a structural demonstration, not an empirically calibrated input-output table. It omits imports, taxes, inventories, capital formation, household production, substitution, prices, labor coefficients and natural-resource constraints. It must not be interpreted as an official national-accounts multiplier.

## 7. Capacity stress model

Baseline capacity is defined as:

[
c_0=(I-A)^{-1}mathbf{1}
]

This is important: setting baseline capacity to a vector of ones would make the baseline unable to satisfy unit final demand. The previous conversational crisis percentages are reproducible only when the baseline capacity is (c_0).

For a sector-capacity multiplier vector (m), solve:

[
max_y sum_i y_i
]

subject to:

[
(I-A)^{-1}yleq c_0odot m,quad 0leq y_ileq1
]

Equal weights are used only for this first experiment. This is not a welfare-optimal allocation; it does not prioritize essential sectors or distributional fairness.

| Capacity shock | Maximum average service share |
|---|---:|
| Baseline | 100.00% |
| ENERGY −20% | 94.98% |
| ENERGY −40% | 89.95% |
| ENERGY −60% | 81.23% |
| ENERGY −40%, MOBILITY −30% | 85.27% |
| ENERGY −40%, MOBILITY −30%, COMPUTE −30% | 81.26% |
| FOOD −40%, ENERGY −30% | 86.93% |
| HOUSING −40%, ENERGY −40% | 84.66% |

Now impose a 70% minimum service floor on FOOD, HOUSING, ENERGY and HEALTH:

- Baseline: feasible.
- ENERGY −20%: feasible.
- ENERGY −40%: feasible, but other sectors can be severely rationed.
- ENERGY −60%: infeasible.
- FOOD −40% plus ENERGY −30%: infeasible.
- HOUSING −40% plus ENERGY −40%: infeasible.

This demonstrates why maximizing total output is not enough. A real SYNERGY allocator needs explicit minimum-service constraints, equity rules, geographic access and rationing policies.

## 8. Automation, cost of living and labor release

The basket model uses shares:

| Sector | Basket share | Labor share | Adoption | Technical effectiveness |
|---|---:|---:|---:|---:|
| FOOD | 20.0% | 30% | 80% | 70% |
| HOUSING | 25.0% | 25% | 40% | 70% |
| ENERGY | 10.0% | 20% | 60% | 70% |
| HEALTH | 15.0% | 35% | 25% | 70% |
| EDUCATION | 7.5% | 40% | 20% | 70% |
| MOBILITY | 12.5% | 30% | 60% | 70% |
| COMPUTE | 10.0% | 25% | 80% | 70% |

Gross labor-cost saving share of the $1,000 basket:

[
sum_i b_i l_i a_i e=10.26375%
]

After an assumed technology-cost deduction equal to 35% of gross saving:

[
S_{basket}=10.26375%(1-0.35)=6.6714375%
]

Modelled basket cost falls by $66.714 per $1,000 basket, to $933.286.

This is not a forecast: it assumes the full gross saving can be translated into cost reduction and that the 35% technology-cost ratio captures all relevant incremental costs. It does not yet model wages, price pass-through, taxes, financing, quality, market power or rebound effects in the basket calculation.

An earlier distribution experiment allocated the same $66.714 saving per $1,000 basket as follows:

| Use | Share of net saving | Amount per $1,000 basket |
|---|---:|---:|
| Lower delivered price / household saving | 50% | $33.357 |
| Participant dividend | 25% | $16.679 |
| Productive reinvestment | 15% | $10.007 |
| Stability reserve | 10% | $6.671 |

This is an **alternative allocation policy**, not an additional source of value. The four uses sum to the same $66.714; they must not be added on top of the full $66.714 cost reduction. In an actual accounting system, lower prices, retained earnings, reserve funding and dividends must be reconciled to one realized surplus ledger.

The labor-hours model uses a separate employment-share vector and deducts rebound (20%) and additional supply-chain labor (15%):

[
L_{release}=sum_i e_i^{emp}l_i a_i e(1-0.20)(1-0.15)
]

Result:

- Net modelled labor release: 7.43155% of initial labor hours.
- At 40 hours/week: 37.02738 hours/week remain on average.
- For 1,000 people at 160 hours/month: 11,890.48 hours/month are released.

This does **not** imply 7.43% unemployment or a guaranteed shorter workweek. It is a potential labor-time saving. The social outcome depends on demand, work sharing, wages, retraining, bargaining power and ownership of automation.

## 9. Thirty-year productive-capital model

The model separates productive capital (K) from the financial reserve (R).

For each year:

[
GCF_t=yK_t
]

[
Replacement_t=dK_t
]

[
Surplus_t=max(0,GCF_t-Replacement_t)
]

If surplus is positive:

- 50% goes to productive growth;
- 20% goes to the financial reserve;
- 30% is distributed as dividends.

If gross cashflow is below replacement, reserve funds cover the shortfall; any uncovered renewal shortfall is treated as productive-capital erosion.

A physical crisis loss is first deducted from productive capital. The financial reserve can then finance repair/reconstruction, converting financial reserve into productive capital. This prevents counting the same reserve dollar as both cash and an asset.

### Five-percent gross cash-yield target

The 5% rate is a **target sensitivity**, not an observed return. Initial productive capital is $32.9m. Initial financial reserve is an additional 5% of productive capital ($1.645m), not part of the $32.9m productive asset stock.

Crisis schedule:

| Year | Physical capital loss | Gross cashflow multiplier |
|---|---:|---:|
| 4 | 2% | 1.00 |
| 11 | 0% | 0.75 |
| 23 | 5% | 0.70 |

Results:

| Measure | No crisis | Three crises |
|---|---:|---:|
| Productive capital at year 30 | $42.338m | $41.762m |
| Cumulative dividends | $5.663m | $5.317m |
| Financial reserve at year 30 | $5.420m | $2.548m |
| Cumulative reserve contributions | $3.607m | $3.545m |
| Cumulative reserve draws | $0 | $2.642m |

These are deterministic scenario outputs, not expected values. Crisis probabilities, correlations, repair delays, price shocks, liquidity haircuts, debt service, tax, construction lead times and sector-specific asset losses are not calibrated.

### Important correction to earlier conversational projections

A previous public-portfolio projection treated the public portfolio's 3.095% gross cash yield as if it could compound without first paying replacement CAPEX. That projection is **superseded**.

The public portfolio's assumed replacement rate is 3.4056%, so its initial residual is negative $49,100/year. It cannot follow a positive compounding trajectory under those assumptions without new external support, better operating performance, a different asset mix or explicit public-service funding.

Likewise, the whole-system 5% scenario must use the surplus **after** replacement CAPEX. It must not use (K_{t+1}=K_t(1+0.5y)), because that formula ignores depreciation/replacement. The correct growth term is based on (0.5(y-d)K) when (y>d).

## 10. Other models developed in the research conversation

### 10.1 Universal Productive Fund / public productive ownership

The proposed fund owns transparent legal interests in real productive assets. It does not treat token supply or market capitalization as asset value. The seven-sector public-ownership shares in this model are a scenario, not an approved portfolio mandate.

### 10.2 Productivity Dividend Protocol

A productivity dividend is paid only from verified surplus after:
1. counterfactual baseline is fixed;
2. useful output and quality are measured;
3. additional labor, materials, energy, maintenance and financing are counted;
4. upstream and environmental costs are deducted;
5. replacement CAPEX and mandatory liabilities are funded;
6. residual surplus is allocated under a disclosed policy.

A payroll reduction alone is not an economic surplus: wages are both enterprise costs and household income. A valid analysis must track both resource hours and income distribution.

### 10.3 Universal Access Rights and CLI

Universal Access Rights represent a contractual/service entitlement, not money, equity, a stablecoin or a guaranteed claim on cash.

The proposed Cash-Lessness Index was:

[
CLI=1-rac{C_{mandatory cash}}{C_{full basic basket}}
]

Example: if $400 of a $1,000 basic basket remains a mandatory cash expense, CLI = 60%. This is only a measure of the share of the basket not paid through household cash purchases; it does not prove that the service is free, costless or efficiently produced.

### 10.4 Endowment capital requirement

For a stable annual distribution (P) and assumed payout rate (q):

[
K=P/q
]

For 1,000 people and a $1,000/month basket, annual coverage is $12m. At a 3% payout assumption, the notional endowment requirement is $400m. For a $600/month basket, it is $240m.

This is an endowment arithmetic exercise, not a claim that the fund can buy or physically operate all required infrastructure. The payout rate is not guaranteed investment return and must be adjusted for fees, taxes, inflation, volatility and asset-liability risk.

### 10.5 Monthly contribution accumulation

A separate illustrative accumulation exercise used $10,007 monthly contributions and a 3% nominal annual rate compounded monthly, contributions at month-end. It is not the same as the seven-sector portfolio model and should not be combined with its cashflows.

Using the ordinary annuity formula `FV = P * (((1 + r/12)^(12*n) - 1) / (r/12))`, with `P = $10,007`, `r = 3%`, and month-end deposits:

| Horizon | Accumulated balance | 3% annual payout equivalent / month |
|---|---:|---:|
| 10 years | $1,398,392 | $3,496 |
| 20 years | $3,285,318 | $8,213 |
| 30 years | $5,831,448 | $14,579 |
| 40 years | $9,267,077 | $23,168 |

This assumes an unchanged contribution in real terms only if the contribution is indexed; the stated 3% is a nominal accumulation assumption in this isolated example. Fees, taxes, default, volatility, contribution interruptions and inflation treatment are not modelled. The payout column is 3% of accumulated capital divided by 12; it is not guaranteed income.

### 10.6 Three ownership architectures

The conversation compared market-led, mixed and cooperative/public ownership structures. These remain hypotheses. A valid comparison must hold physical technology, demand, initial capital and external shocks constant, then vary governance, investment decisions, financing costs, risk allocation and service obligations. Ownership share alone does not generate productivity.

## 11. Reconciliation ledger: previous results and status

| Earlier result | Status | Treatment in this repository |
|---|---|---|
| $32.9m total capital | MODEL_ASSUMPTION | Retained as seven-sector reference capital |
| $15.805m public capital / 48.04% | MODEL_OUTPUT | Retained |
| $993.5k whole-system gross cashflow | MODEL_OUTPUT | Retained; not FCF |
| $489.15k public gross cashflow | MODEL_OUTPUT | Retained; subset of whole system |
| $1.0895m whole-system replacement | MODEL_OUTPUT | Retained |
| $538.25k public replacement | MODEL_OUTPUT | Retained |
| −$96k whole-system residual | MODEL_OUTPUT | Retained |
| −$49.1k public residual | MODEL_OUTPUT | Retained |
| 6.6714% basket reduction | MODEL_OUTPUT | Retained as uncalibrated automation sensitivity |
| 7.43155% labor release | MODEL_OUTPUT | Retained as potential hours saving, not employment forecast |
| Leontief output 9.453116 | MODEL_OUTPUT | Retained with matrix orientation and assumptions |
| Capacity stress service percentages | MODEL_OUTPUT | Retained with correct baseline capacity definition |
| Earlier public-fund growth at 3.095% | SUPERSEDED | Rejected because replacement CAPEX was omitted |
| 5% gross-yield 30-year scenario | MODEL_OUTPUT | Retained with replacement-first waterfall and crisis schedule |
| Equal sector service weights | LIMITATION | Not a welfare or equity optimum |
| Crisis losses and cash multipliers | MODEL_ASSUMPTION | Explicit scenario only, no probabilities |

## 12. What is required for calibration

Before using this model for investment, budget or policy decisions, replace each assumed input with documented evidence:

- asset inventories and replacement values by sector;
- age profile, useful life, maintenance and replacement schedule;
- audited operating cashflow, taxes, debt service and working capital;
- physical output and service quality;
- actual capacity, utilization, downtime and bottlenecks;
- input-output purchases and import content;
- regional energy, water, logistics and labor coefficients;
- demand by household income group and geography;
- actual ownership rights, contracts and service obligations;
- historical crisis data, correlations and recovery times.

Every observation needs source, unit, geography, effective time, known-at time, method and confidence level. No parameter should be promoted from MODEL_ASSUMPTION to OBSERVED without evidence.

## 13. Reproduction

From repository root:

```bash
python -m pip install -r requirements.txt
python src/synergy_economy_7sector.py --output outputs/synergy_economy_7sector_v1.json
python -m pytest -q
```

The generated report contains sector accounting, public portfolio reconciliation, Leontief outputs, capacity stress cases, automation sensitivities and 30-year reserve/capital projections.

## 14. Design rules

1. No token issuance is counted as productive output.
2. Market capitalization is not liquidity, cashflow or asset backing.
3. Internal transfers are not external revenue or net social value.
4. Loan principal is not income; credit creates an asset and a matching liability.
5. Wages are not automatically an economic loss; labor hours and household income must both be tracked.
6. Replacement CAPEX precedes growth, reserves and dividends.
7. Socially necessary low-cash-yield services require explicit funding, not hidden cross-subsidies.
8. Ownership and access are distinct: a long-term enforceable supply contract can secure access without buying the entire asset.
9. The model must expose uncertainty and be calibrated before operational claims.
