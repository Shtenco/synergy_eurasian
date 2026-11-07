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
- Bank debt and customer bad debt.
- Physical and cash conservation residuals.

A pool limit that never binds is not evidence that the pool is safe; it may simply be too generous for the tested horizon and scale. A limit that binds frequently may preserve solvency while causing excessive lost production. Both sides of the trade-off must be reported.

## 4. Experimental discipline

Use paired seeds, multiple horizons and all three shock regimes. Do not select caps based on a single favorable output metric. Regional credit positions remain memorandum claims; this sensitivity grid does not model a pooled guarantee reserve, loss-sharing waterfall, cross-border clearing, legal enforceability or actual money issuance. All numeric caps are synthetic design probes, not real-world credit recommendations.
