# SYNERGY Sector Capital Optimizer V4

**Status:** illustrative project frontier, not a forecast or investment recommendation.

## Purpose

Choose a portfolio of productive projects that maximizes network-wide productive value rather than the private return of one participant. The optimizer explicitly values four dimensions: incremental annual net residual, additional network spillovers, output growth, unit-cost reduction and labor time released. Critical-sector minimum allocations are hard constraints, while concentration limits prevent a single sector or shared platform from absorbing the entire budget.

## Mathematical formulation

Let `x_j` be dollars allocated to project `j`. The linear program maximizes:

`sum_j x_j * criticality_j * weighted_normalized_value_j`

subject to:

- `sum_j x_j <= available_budget`;
- `0 <= x_j <= project_max_j`;
- each critical sector's allocation is at least its configured floor;
- each sector and the shared-project pool remain under configured budget shares.

The weighted normalized value combines annual net residual yield (direct plus cross-enterprise spillover), output index, unit-cost-reduction index and labor-hours-released index. The weights and normalizers are policy choices, not discovered economic constants. They must be debated, versioned and sensitivity-tested.

## Why spillovers matter

A reusable AI workflow, open technical standard, shared knowledge graph or logistics optimizer can improve many enterprises. The spillover is entered separately from the host project's direct return. It may be counted only once in consolidated network accounts and only after beneficiary-level measurement. A transfer price paid by one SYNERGY participant to another is not a network gain by itself.

## Illustrative project catalogue

The JSON config contains ten hypothetical projects across FOOD, HOUSING, ENERGY, HEALTH, EDUCATION, MOBILITY, COMPUTE and SHARED infrastructure. Their yields, diffusion reach, deployment lags and normalized impact indices are placeholders. They are not observed results. The model includes budget sensitivities of $100k, $250k and $500k and minimum funding floors for FOOD, HEALTH, EDUCATION and MOBILITY.

## Decision protocol before real deployment

1. Record a baseline for each enterprise: physical output, quality, unit cost, OPEX, replacement obligations, working capital, labor hours and energy/compute use.
2. Deploy a pilot with a control or credible before/after design; record implementation cost and deployment lag.
3. Measure direct effects at the adopting enterprise and spillover effects at each beneficiary separately.
4. Deduct incremental OPEX, maintenance, replacement CAPEX, training, integration and failure costs.
5. Feed audited marginal-return curves into the optimizer; replace linear assumptions with diminishing-return or discrete project models.
6. Re-run allocation under alternative weights, budgets, shock scenarios and sector floors. Publish the Pareto frontier rather than hiding policy trade-offs inside one score.
7. Release no dividend or discretionary distribution from a project until essential replacement and resilience obligations are funded.

## Important limits

This is a one-period linear allocation model. It does not yet represent multi-year cash timing, correlated project failure, depreciation, inter-project complementarity, price/market constraints or the labor transition. The labor-hours index is not a cash saving: it becomes social value only if time is redirected to useful activity, care, learning or shorter working hours. All inputs must be calibrated from real pilots before the optimizer is used for capital approvals.
