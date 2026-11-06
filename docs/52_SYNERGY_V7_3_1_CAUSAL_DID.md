# SYNERGY V7.3.1 — Matched-Pair Difference-in-Differences

**Status:** statistical research estimator; not an automatic causal certification.  
**Date:** 2026-11-06

## Purpose

A measured increase after technology deployment is not enough to establish that the technology caused the increase. V7.3.1 adds a matched-pair difference-in-differences (DiD) estimator to compare changes in treated enterprises/assets against matched controls over the same pre/post periods.

For matched pair (i):

`DiD_i = (Y_{T,post}-Y_{T,pre}) - (Y_{C,post}-Y_{C,pre})`

The reported estimate is the mean of pair-level effects. A two-sided Student-t interval and p-value are calculated across matched pairs.

## Input contract

Each `matched_pair_id` must contain exactly four observations:
- one treated unit, PRE;
- the same treated unit, POST;
- one control unit, PRE;
- the same control unit, POST.

Unit identity cannot change within a pair. At least two complete pairs are required to estimate uncertainty. The outcome direction can be marked HIGHER_IS_BETTER or LOWER_IS_BETTER; the raw treatment effect is retained and a beneficial-direction estimate is also returned.

## Assumptions and caveats

- Conditional parallel trends: without treatment, treated and control units would have followed comparable trends.
- No material spillovers from treated to control units.
- No treatment-correlated changes in composition, measurement, or missingness.
- Matching quality and treatment assignment are reviewed independently.
- One pre-period is insufficient to test parallel trends. A placebo/pre-trend test requires additional pre-periods and a richer panel design.
- Small matched-pair samples produce wide and fragile intervals; p-values do not measure economic importance.
- This implementation does not provide cluster-robust panel regression, staggered adoption, synthetic controls, instrumental variables or randomized-trial analysis.

The result is a design-conditional estimate, **not proof of causality**. Evidence method, data provenance, pre-analysis plan and independent design review must accompany any material productivity claim.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.3.2 should support multiple pre-treatment periods, placebo/pre-trend diagnostics and clustered panel estimators. A later evidence governance layer should require pre-registered metrics, treatment dates, exclusions, quality safeguards and independent replication.
