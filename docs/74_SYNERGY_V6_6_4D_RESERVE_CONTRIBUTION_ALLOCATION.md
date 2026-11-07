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

A three-seed, 20-day severe-regime sample was run with 20 synthetic currency units of reserve per region. Both allocation schemes fund the same total reserve. The table reports mean outcomes across the three seeds.

| Contribution rule | Financing mode | Service level | Defaults per run | Guarantee paid | Seller trade bad debt | Reserve remaining |
|---|---|---:|---:|---:|---:|---:|
| Equal all-members | Mutual credit | 69.979% | 1.00 | 5.113 | 6.828 | 34.887 |
| Capacity-weighted | Mutual credit | 70.035% | 1.00 | 5.721 | 7.010 | 34.279 |
| Equal all-members | Hybrid | 70.535% | 1.00 | 12.742 | 7.873 | 27.258 |
| Capacity-weighted | Hybrid | 70.535% | 1.00 | 13.533 | 7.873 | 26.467 |

The smoke run is not a fairness verdict. It shows that changing who contributes changes member liquidity and can change reserve utilization and downstream losses even when total reserve capital is fixed. The opening-cash-weighted rule is now available for explicit heterogeneous opening-cash maps; with a uniform cash map it mathematically collapses to equal-all-member contributions. A larger paired sample is needed before drawing conclusions. The first displayed service-level value should be read from the CI log rather than inferred; the raw CI observation is 0.6997929 for equal mutual-credit and 0.7003472 for capacity-weighted mutual-credit.


## 6. Heterogeneous opening cash and capped contributions

The ledger accepts `initial_cash_by_cell`. The allocation experiment uses that same map when computing opening-cash weights. This allows the comparison to vary contribution allocation without accidentally using a different cash endowment.

A separate liquidity-capped allocator (V6.6.4-F) supports hard member caps as a fraction of opening cash and uses deterministic water-filling to redistribute the target among eligible members. The cap is a constraint, not a fairness criterion. If the aggregate eligible cap is insufficient, the requested reserve is rejected rather than silently underfunded or financed by newly created cash.
