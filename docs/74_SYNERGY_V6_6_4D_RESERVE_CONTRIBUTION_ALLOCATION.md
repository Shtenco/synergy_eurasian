# SYNERGY V6.6.4-D — regional guarantee reserve contribution allocation

**Status:** weighted contribution ledger and paired allocation comparison implemented.  
**Purpose:** make the funding burden of a regional guarantee reserve explicit and auditable.

## 1. Three allocation rules

### Equal all-member contribution

Each of the ten cells in a region contributes one tenth of the reserve. This is simple and predictable, but it charges support cells and production cells equally even when their capacities and expected guarantee benefits differ.

### Production-capacity-weighted contribution

Only primary, processing and manufacturing cells contribute. Each contribution is proportional to the cell's configured production capacity. Warehouse, logistics, energy and maintenance support cells contribute zero under this rule.

This rule links contribution to production capacity, not observed turnover, actual risk, guarantee utilization, wealth or benefit received. It is a sensitivity scenario, not a normative fairness conclusion. It can exclude support cells that still benefit from the regional guarantee.

### Opening-cash-weighted contribution

Each cell contributes in proportion to its own opening cash. Within a region, all members therefore contribute the same fraction of their opening cash when the uncapped rule is feasible. It avoids a flat nominal burden on low-cash cells, but it is not a measure of ability to pay: opening cash is only a point-in-time balance and says nothing about operating cash needs, future obligations, wealth, risk or benefit received.

## 2. Accounting contract

The constructor accepts `regional_reserve_contributions_by_cell`. If omitted, the existing equal-all-member contribution remains the default. If supplied:

- every known cell must appear exactly once;
- all values must be finite and non-negative;
- no contribution may exceed that member's initial cash;
- contributions in each region must sum exactly (within numerical tolerance) to `regional_pool_reserve_per_region`;
- each member's opening cash is reduced by its own contribution;
- reserve balances remain separate from member cash and mutual-credit memorandum positions.

The snapshot exposes the per-cell contribution map. Consolidated cash conservation includes both member cash and reserve cash.

## 3. Paired comparison

`compare_reserve_contribution_schemes(...)` replays equal-member, production-capacity-weighted and opening-cash-weighted allocation under identical seed-specific environments and compares the same five financing modes. Reserve size is held constant between allocation rules. It reports the contribution map and all standard credit, service-level, default, reserve-coverage, seller-loss and conservation metrics.

Example:

```python
from synergy_v66.financing_experiments import compare_reserve_contribution_schemes

report = compare_reserve_contribution_schemes(
    seeds=range(2026, 2036),
    days=45,
    shock_regime="severe",
    reserve_per_region=20.0,
)
```

## 4. What this does not decide

None of the three rules is proven fair or optimal. A more defensible design may use a hybrid of:
- equal membership dues for basic access;
- usage-based contributions linked to actual guarantee exposure;
- risk-based premiums linked to independently measured default risk;
- a cap on burden relative to member cash flow;
- explicit public-benefit or solidarity subsidies for support infrastructure and smaller members.

Those alternatives require observable and independently auditable data, governance rules, appeals, and protection against risk-model gaming. This increment does not infer real member risk or prescribe actual contributions.


## 5. CI smoke-sample observations

The updated three-seed, 20-day severe-regime sample uses a heterogeneous synthetic opening-cash fixture and 20 units of reserve per region. All three allocation rules fund the same reserve target on the same seed-specific environments. The table reports mean outcomes across the three seeds.

| Contribution rule | Financing mode | Service level | Defaults per run | Guarantee paid | Seller trade bad debt | Reserve remaining |
|---|---|---:|---:|---:|---:|---:|
| Equal all-members | Mutual credit | 69.731% | 1.33 | 7.532 | 0.000 | 32.468 |
| Capacity-weighted | Mutual credit | 69.731% | 1.33 | 6.555 | 0.000 | 33.445 |
| Opening-cash-weighted | Mutual credit | 69.731% | 1.33 | 7.384 | 0.000 | 32.616 |
| Equal all-members | Hybrid | 69.647% | 1.33 | 14.192 | 15.556 | 25.808 |
| Capacity-weighted | Hybrid | 69.647% | 1.33 | 14.983 | 15.820 | 25.017 |
| Opening-cash-weighted | Hybrid | 69.647% | 1.33 | 14.062 | 15.507 | 25.938 |

In this small sample, opening-cash weighting sits between equal-member and production-capacity allocation on mutual-credit reserve payouts, and has slightly lower hybrid reserve payouts and seller bad debt than the other two rules. These differences are descriptive only: three seeds are not enough to rank the schemes, and the fixture does not represent observed EAEU member liquidity or guarantee risk.

## 6. Heterogeneous opening cash and capped contributions

The ledger accepts `initial_cash_by_cell`. The allocation experiment uses that same map when computing opening-cash weights. This allows the comparison to vary contribution allocation without accidentally using a different cash endowment.

A separate liquidity-capped allocator (V6.6.4-F) supports hard member caps as a fraction of opening cash and uses deterministic water-filling to redistribute the target among eligible members. The cap is a constraint, not a fairness criterion. If the aggregate eligible cap is insufficient, the requested reserve is rejected rather than silently underfunded or financed by newly created cash.
