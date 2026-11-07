# SYNERGY V6.6.1 — Seven-Cell Compatibility Kernel

**Status:** executable research prototype; CI validation in progress. Synthetic assumptions only.

## 1. Purpose

V6.6.1 creates a small deterministic replay environment to establish a common baseline before scaling the economy. It is intentionally compatible with the seven-node topology used by the earlier V6.4 experiment:

- R1, R2 — raw-material suppliers;
- C1, C2 — component manufacturers;
- A1, A2 — final assemblers;
- L — shared logistics provider.

The model is make-to-order and runs on a supplied sequence of daily demand and capacity shocks. Every policy receives the same environment object. A SHA-256 fingerprint is included in paired-run output.

## 2. Implemented policies

| Policy | V6.6.1 behavior | Important limitation |
|---|---|---|
| independent | uses only the preferred supplier; no fallback | deliberately rigid baseline |
| market | selects the available supplier using unit processing cost plus congestion penalty | simplified local price/capacity rule, not a full auction |
| dao | selects the supplier with the greatest remaining capacity | legacy V6.4 greedy balancing proxy; **not** DAO voting, governance or a legal entity |
| ca | prefers local supplier, then local alternate | one-step fallback rule, not a complete cellular automaton |
| ca_t50 | retains preferred supplier while its remaining capacity is at least 50% of eligible remaining capacity | threshold heuristic |
| hybrid | local-first until 35% capacity threshold, then market fallback | heuristic, not an equilibrium solver |

A policy label must not be interpreted as proof that its full institutional mechanism has been implemented. Real DAO governance is scheduled for V6.6.5; a fully specified CA transition system is scheduled for V6.6.4.

## 3. Physical and commercial assumptions

One final batch is 0.25 output units. Each final unit requires 1.25 component units and 1.4375 raw-material units. Component production and raw supply are modeled as same-day make-to-order operations. Logistics capacity is shared.

The environment supports normal, volatile and severe regimes. Demand, node cost factors and capacity shocks are generated from a deterministic seed. These distributions are synthetic stress inputs, not estimates of real-world frequencies.

## 4. Cash-flow identity

For the seven-cell consolidated system:

`ClosingCash = OpeningCash + ExternalSales - ExternalVariableCosts - FixedCostsPaid`

External variable costs include raw input cost, component processing cost, final assembly cost and logistics fuel. Fixed costs are accrued and paid up to available cell cash; unpaid fixed obligations are not silently deducted from cash and are not yet modeled as legal default.

Inter-cell component payments, raw-material payments and freight transfers are tracked as gross internal transfer flows. At consolidation:

`InternalTransferInflows - InternalTransferOutflows = 0`

The kernel reports a numerical cash-conservation error. A non-zero error beyond tolerance invalidates the run.

## 5. Reproducibility

From the repository root:

```bash
python -m pytest -q tests/test_synergy_v66_compatibility.py
```

Example:

```python
import sys
sys.path.insert(0, "src")
from synergy_v66 import run_paired

report = run_paired(seed=17, regime="severe", days=60)
for row in report["policies"]:
    print(row["policy"], row["output_units"], row["cash_change"], row["conservation_error"])
```

## 6. Explicit omissions

V6.6.1 does not yet model:
- persistent inventory lots, work-in-progress or stock aging;
- supplier/customer contract negotiation or price formation;
- delivery lead times, transport routes or qualification delays;
- debt, credit limits, interest, maturity, collateral or factoring;
- FX, multi-currency accounts, taxes, payroll or household distribution;
- legal insolvency, recovery, bankruptcy waterfall or restructuring;
- voting, quorum, capture, disputes or regional/federation governance;
- event-sourced durable state or signed external evidence.

These are not assumed away as solved. They are separate later milestones. In particular, a same-day supplier fallback is only a toy compatibility baseline; real substitution requires qualification, contracts, inventory and transport time.

## 7. Acceptance tests

The V6.6.1 test suite checks deterministic environment generation, identical paired paths, repeatable policy replay, cash conservation, internal-transfer elimination and rejection of invalid regimes/policies.

Passing these tests establishes code properties for this small synthetic model only. It does not establish predictive validity, profitability, institutional feasibility or superiority of any coordination regime.
