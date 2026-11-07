# SYNERGY V6.6.4-B — regional mutual-credit pool sensitivity grid

**Status:** deterministic synthetic sensitivity runner.  
**Purpose:** test whether regional pool ceilings and member debit/credit caps bind under paired economic shocks.

## 1. Parameters

The runner sweeps:
- `pool_limits`: maximum net debit outstanding per region;
- `member_limits`: maximum absolute net debit and net credit position per cell.

For each pair of limits, the existing five financing modes are replayed on identical seed-specific environments. Cash-only and bank-only provide controls; mutual-credit and hybrid use the configured regional pool limits.

## 2. Use

```python
from synergy_v66.financing_experiments import compare_regional_pool_sensitivities

report = compare_regional_pool_sensitivities(
    seeds=range(2026, 2036),
    days=45,
    shock_regime="severe",
    pool_limits=(10.0, 25.0, 150.0),
    member_limits=(5.0, 15.0, 80.0),
)
for case in report["sensitivity_reports"]:
    print(
        case["pool_limit_per_region"],
        case["member_debit_and_credit_limit_per_cell"],
        case["summary"]["mutual_credit"]["regional_pool_rejections"],
        case["summary"]["hybrid"]["regional_pool_rejections"],
    )
```

## 3. What to inspect

- Regional pool outstanding and utilization.
- Regional-pool rejection frequency.
- Buyer and seller credit-limit rejection frequency.
- Service level and unmet demand.
- Defaulted cells and outstanding trade payables.
- Bank debt, customer bad debt, regional guarantee reserve coverage and seller-side trade bad debt.
- Physical and cash conservation residuals.

A pool limit that never binds is not evidence that the pool is safe; it may simply be too generous for the tested horizon and scale. A limit that binds frequently may preserve solvency while causing excessive lost production. Both sides of the trade-off must be reported.

## 4. Experimental discipline

Use paired seeds, multiple horizons and all three shock regimes. Do not select caps based on a single favorable output metric. Regional credit positions remain memorandum claims; this sensitivity grid does not model a pooled guarantee reserve, loss-sharing waterfall, cross-border clearing, legal enforceability or actual money issuance. All numeric caps are synthetic design probes, not real-world credit recommendations.


## 5. CI smoke sensitivity

The repository CI runs a compact severe-regime sample with three seeds, two regional pool ceilings (5 and 150) and two member caps (2 and 80). It writes a machine-readable report under `outputs/synergy_v66_regional_pool_sensitivity.json`. This is a smoke/sensitivity check, not a statistically powered policy evaluation.


## 6. Earlier CI smoke-sample observation

The table below was generated before the member-funded guarantee reserve was added to mutual-credit and hybrid modes. It demonstrates pool/member cap interaction, but is not directly comparable to subsequent runs with the reserve enabled. The current CI run regenerates the sensitivity output with the reserve included.

## 7. Earlier cap interaction results

A three-seed, 20-day severe-regime CI sample produced the following mean outcomes. These are synthetic smoke-test values, not calibrated forecasts.

| Regional pool cap | Member cap | Mutual-credit pool rejections / run | Hybrid pool rejections / run | Mutual-credit service level | Hybrid service level |
|---:|---:|---:|---:|---:|---:|
| 5 | 2 | 4.33 | 1.33 | 70.03% | 70.14% |
| 5 | 80 | 2.00 | 1.33 | 69.98% | 70.14% |
| 150 | 2 | 4.33 | 1.33 | 70.03% | 70.14% |
| 150 | 80 | 0.00 | 0.00 | 69.98% | 70.86% |

The equal rejection rates at member cap 2, despite changing the pool cap from 5 to 150, indicate that the individual member limit is binding in that case. At member cap 80, reducing the regional ceiling to 5 produces rejections. The hybrid mode can substitute bank funding for some blocked mutual-credit purchases, but not all.

The sample is too small to rank policies. It demonstrates that the two limits operate as distinct controls and that their interaction should be studied over longer horizons and larger seed sets.
