# SYNERGY V6.6.3-D — paired financing-mode experiments

**Status:** deterministic synthetic experiment runner.  
**Purpose:** compare cash-only, bank-only, bilateral mutual-credit and hybrid financing against an unconstrained reference on the same exogenous environment.

## 1. Financing modes

| Mode | Bank line | Buyer trade-credit limit | Interpretation |
|---|---:|---:|---|
| Unconstrained reference | N/A | N/A | Physical upper-reference path without financial authorization |
| Cash only | 0 | 0 | Own cash funds production and immediate supplier purchases |
| Bank only | 80 | 0 | Own cash plus approved bank line; no supplier trade credit |
| Mutual credit | 0 | 80 | Own cash plus bilateral supplier credit; no bank line |
| Hybrid | 80 | 80 | Own cash, bilateral supplier credit and bank line |

All modes use the same base cash, seller exposure cap, customer exposure cap, customer recovery fraction, payment terms and grace periods unless overridden. The numeric values are synthetic experimental settings, not recommendations for real firms.

## 2. Paired design

For each seed, the environment is generated once and replayed under all five modes. The output records the environment hash for each mode; the hashes must be identical within each seed. Seeds are independent replicates. The runner reports mean, median, minimum and maximum for every metric.

Metrics include:
- finished output and sold units;
- unmet demand and service level;
- expired goods and closing inventory;
- defaulted cells and outstanding trade payables;
- bank debt and bank draws;
- customer bad debt;
- production, procurement and customer-invoice rejections;
- physical balance and cash conservation errors.

The unconstrained reference is a benchmark, not a feasible financing policy. No regime is assumed to win.

## 3. Use

```python
from synergy_v66.financing_experiments import compare_financing_modes

report = compare_financing_modes(
    seeds=range(100, 120),
    days=45,
    shock_regime="severe",
)
print(report["summary"])
```

Tests:

```bash
python -m pytest -q tests/test_synergy_v66_financing_experiments.py
```

## 4. Interpretation discipline

Do not rank regimes from one seed or one shock regime. Compare paired differences across many seeds and all three regimes (`normal`, `volatile`, `severe`). Report downside quantiles and failure frequency, not just means. A policy that raises output while increasing defaults, customer bad debt or concentrated exposures may be less resilient. Before any real-world inference, replace synthetic prices, costs, capacities, payment terms and recovery rates with sourced data and sensitivity ranges.

## 5. Validation requirements

- Each seed has one shared environment hash across all financing modes.
- Replays are deterministic.
- Every mode preserves per-SKU physical balance.
- Every credit-constrained mode preserves consolidated cash conservation.
- Service level remains within [0, 1].
- Invalid seed sets, horizons and regimes are rejected.
