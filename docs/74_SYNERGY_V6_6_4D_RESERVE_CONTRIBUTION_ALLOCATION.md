# SYNERGY V6.6.4-D — regional guarantee reserve contribution allocation

**Status:** weighted contribution ledger and paired allocation comparison implemented.  
**Purpose:** make the funding burden of a regional guarantee reserve explicit and auditable.

## 1. Two allocation rules

### Equal all-member contribution

Each of the ten cells in a region contributes one tenth of the reserve. This is simple and predictable, but it charges support cells and production cells equally even when their capacities and expected guarantee benefits differ.

### Production-capacity-weighted contribution

Only primary, processing and manufacturing cells contribute. Each contribution is proportional to the cell's configured production capacity. Warehouse, logistics, energy and maintenance support cells contribute zero under this rule.

This rule links contribution to production capacity, not observed turnover, actual risk, guarantee utilization, wealth or benefit received. It is a sensitivity scenario, not a normative fairness conclusion. It can exclude support cells that still benefit from the regional guarantee.

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

`compare_reserve_contribution_schemes(...)` replays equal and capacity-weighted allocation under identical seed-specific environments and compares the same five financing modes. Reserve size is held constant between allocation rules. It reports the contribution map and all standard credit, service-level, default, reserve-coverage, seller-loss and conservation metrics.

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

Neither rule is proven fair or optimal. A more defensible design may use a hybrid of:
- equal membership dues for basic access;
- usage-based contributions linked to actual guarantee exposure;
- risk-based premiums linked to independently measured default risk;
- a cap on burden relative to member cash flow;
- explicit public-benefit or solidarity subsidies for support infrastructure and smaller members.

Those alternatives require observable and independently auditable data, governance rules, appeals, and protection against risk-model gaming. This increment does not infer real member risk or prescribe actual contributions.
