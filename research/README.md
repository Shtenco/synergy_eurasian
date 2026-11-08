# SYNERGY Research Registry — Network Economics V6.4–V6.5.6

This directory preserves the complete research line from the resilience/economic-network work in the November 2026 conversation. Each version is stored independently. Earlier versions are not overwritten by later prototypes.

## Version inventory

| Version | Research question | Executed experiment | Included artifacts | Status |
|---|---|---:|---|---|
| [V6.4](synergy_v6.4/README.md) | Can production coordination and adaptive cellular-automata thresholds improve output and operating results versus independent firms? | 9,300 distinct scenario combinations; 1,600 repeated verification reruns; 360 post-update invariant scenarios | Kernel, tests, audit manifest, paired raw results, policy summary, price sweep, break-even and CA sensitivity | Research prototype |
| [V6.5.3](synergy_v6.5.3/V6.5.3_RESEARCH_REPORT.md) | How do early payment and non-recourse factoring change liquidity gaps, profitability and tail risk under customer concentration and correlated defaults? | 8,000 main paired scenarios + 4,000 concentration-tail scenarios + 3,000 systemic-correlation scenarios; 45,000 policy paths | Two kernels, tests, full raw scenario CSVs, summaries, economics and break-even grids, report | Synthetic credit/liquidity experiment |
| [V6.5.4](synergy_v6.5.4/V6.5.4_RESEARCH_REPORT.md) | Can liquidity pools and supplier rerouting reduce network defaults and production loss under persistent shocks? | 1,200 main paths + 1,200 systemic precision paths + 700 capital sensitivity paths = 3,100 policy paths | Kernel, tests, all three raw path datasets, summaries, capital sensitivity, report and decision note | Synthetic crisis-resilience prototype |
| [V6.5.5](synergy_v6.5.5/V6.5.5_RESEARCH_REPORT.md) | Can a network detect critical nodes and restore production after concentrated damage? | 100 severe paired seeds × 4 policies + 500 systemic paired seeds × 4 policies = 2,400 paths | Kernel, tests, raw path results, policy summary, paired confidence intervals, report and decision note | Self-healing heuristic prototype |
| [V6.5.6](synergy_v6.5.6/V6.5.6_RESEARCH_REPORT.md) | How should one scarce reserve jointly fund repairs and liquidity support? | 100 severe paired seeds × 4 policies + 300 systemic paired seeds × 4 policies = 1,600 paths | Kernel, tests, raw path results, policy summaries, paired comparisons, report and decision note | Joint-allocation heuristic prototype |

## Reproducibility

Install the shared numerical dependencies:

```bash
python -m pip install numpy pandas scipy
```

Run each version's tests from the repository root:

```bash
python -m unittest discover -s research/synergy_v6.4 -p 'test_*.py'
python -m unittest discover -s research/synergy_v6.5.3 -p 'test_*.py'
python -m unittest discover -s research/synergy_v6.5.4 -p 'test_*.py'
python -m unittest discover -s research/synergy_v6.5.5 -p 'test_*.py'
python -m unittest discover -s research/synergy_v6.5.6 -p 'test_*.py'
```

Full raw results are retained as CSV so that aggregate tables can be independently recomputed.

## Interpretation and limitations

1. Parameters are synthetic and are not calibrated to observed firms, supplier contracts, bank statements or national accounts.
2. A modelled external gross sale is not the same as a collected external cash receipt, free cash flow, GVA or social welfare.
3. Token prices, internal transfers and mark-to-market valuations must not be counted as external economic value or collateral.
4. The V6.5.5 network repair score is heuristic; it is not a globally optimal intervention policy.
5. V6.5.6 rolling_horizon is a discounted ranking heuristic, not a solved multi-period optimization problem.
6. V6.5.6 cvar_robust applies conservative score haircuts and concentration penalties; it does not directly solve a CVaR-constrained optimization.
7. V6.5.4 raw path CSVs were regenerated from the preserved kernel after the original package was found to contain summaries but not path-level raw data. The regenerated datasets preserve the stated seeds and run counts.
8. Paired confidence intervals describe seed-to-seed variability inside these synthetic models only. They are not real-world confidence intervals.

## Research progression

The next scientifically meaningful step is V6.5.7: a joint intervention allocator using paired counterfactual rollouts, explicit inventories and lead times, invoice-level double-entry cash settlement, reserve funding costs, repeated shocks and a genuinely solved rolling-horizon/CVaR-constrained optimization problem.
