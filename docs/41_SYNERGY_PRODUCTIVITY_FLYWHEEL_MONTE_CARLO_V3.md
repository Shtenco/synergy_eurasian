# SYNERGY Productivity Flywheel Monte Carlo V3

**Model ID:** `SYNERGY-PRODUCTIVITY-FLYWHEEL-MONTE-CARLO-V3`  
**Status:** illustrative probabilistic stress test, not an empirical forecast.  
**Horizon:** 10 years. Each shock scenario: 20,000 paths in the published configuration.

## 1. Purpose

V2 used deterministic expected values. V3 adds year-to-year uncertainty, a correlated downside event, variation in automation yields and discrete R&D project successes. It measures the frequency with which the illustrative reserve is exhausted and the distribution of unfunded replacement gaps.

The initial conditions are the V1 repair target: $1,068,012.50 cashflow after OPEX and before replacement; $1,045,920 annual replacement CAPEX; $32.9m productive capital; and an assumed initial reserve of 5% of capital, or $1.645m.

## 2. Uncertainty assumptions

| Input | Distribution / assumption |
|---|---:|
| Annual cashflow growth | Normal, mean 2.5%, standard deviation 1.5%, clipped to −5%…+8% |
| Replacement inflation | Normal, mean 2%, standard deviation 1%, clipped to −1%…+8% |
| Correlated downside event | Annual probability varied from 0% to 10% |
| Cashflow growth shock | −10 percentage points |
| Replacement inflation shock | +10 percentage points |
| Automation yield per funded cohort | Normal, mean 15%, standard deviation 5%, floor 0% |
| R&D projects per annual cohort | 10 independent projects |
| R&D success probability per project | 20% |
| Successful R&D net residual yield | 30%/year |
| Automation / R&D deployment lags | 1 / 2 years |
| Benefit life | 5 years |

All these distributions are hypothetical. They are not estimated from observed SYNERGY company data, historical frequencies or a validated reference class. The correlated event is a simplified joint shock, not a full macroeconomic model.

## 3. Reference simulation results

With 20,000 paths and random seed 42:

| Annual probability of correlated shock | Probability reserve is exhausted at least once | Median ending reserve | 5th percentile ending reserve | 95th percentile cumulative unfunded gap |
|---:|---:|---:|---:|---:|
| 0% | 0.00% | $1,834,452 | $1,507,877 | $0 |
| 1% | 1.41% | $1,820,158 | $896,589 | $0 |
| 3% | 5.48% | $1,777,786 | $0 | $60,609 |
| 5% | 10.12% | $1,717,908 | $0 | $526,662 |
| 10% | 25.01% | $1,115,697 | $0 | $1,925,655 |

At 3% annual correlated-shock probability:
- mean cumulative unfunded gap: approximately $34,661;
- 99th percentile cumulative unfunded gap: approximately $1.09m;
- among paths that exhausted the reserve, median first exhaustion occurred in year 9.

A zero 5th percentile reserve means at least 5% of paths ended with no reserve. It does not mean that 5% of actual SYNERGY operations will fail. These percentages are conditional on the chosen hypothetical shock distributions.

## 4. Interpretation

The median path can look healthy while the downside tail remains material. Averages alone are insufficient for reserve policy. The reserve should be sized against essential-service obligations, correlated replacement risks, procurement lead times and the probability distribution of cashflow shocks.

The model also exposes an important governance rule: when the reserve is exhausted, the system must not continue funding automation and R&D as if the residual were positive. The model stops positive fund contributions whenever residual is negative and reports any uncovered gap.

## 5. Limitations

- No enterprise-level cashflow or replacement history has been calibrated.
- The same macro growth and inflation distribution is applied across the aggregate portfolio.
- The correlated event is simplified; supply-chain, energy, cyber and weather risks may have different dependencies.
- R&D outcomes are independent within cohorts; real research projects can be correlated.
- Project yields are modeled as net residual yields, but technology obsolescence, competition, adoption delays and cannibalization are not separately modeled.
- No tax, debt, foreign-exchange or working-capital submodel is included beyond costs assumed embedded in starting cashflow.
- The 5% initial reserve is inherited as a scenario assumption, not validated as adequate.

Implementation: `src/synergy_productivity_flywheel_monte_carlo_v3.py`; assumptions: `data/synergy_productivity_flywheel_monte_carlo_v3.json`; tests: `tests/test_productivity_flywheel_monte_carlo_v3.py`.
