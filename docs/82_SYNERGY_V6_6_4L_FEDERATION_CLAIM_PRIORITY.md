# SYNERGY V6.6.4-L — federation guarantee claim classes and priority rules

**Status:** analytical allocation alternatives implemented; FCFS and batch pro-rata remain the only selectable ledger policies. Claim-class priority variants are currently comparison functions, not active ledger settlement modes.

## 1. Claim classes

A claim may carry a synthetic `claim_class` label. The caller supplies an explicit `priority_order`, for example:

`["essential", "ordinary"]`

Classes are processed in that order. Every class present in the claim batch must appear exactly once in the priority order. The labels are not inferred from invoice size, supplier identity, political status or model scoring.

## 2. Four allocation rules

- **FCFS:** all claims compete in due-day and invoice-ID order.
- **Batch pro-rata:** all claims in the batch share the same coverage fraction.
- **Priority class then FCFS:** classes are processed in explicit priority order; within each class, claims are ordered by due day and invoice ID.
- **Priority class then batch pro-rata:** classes are processed in explicit priority order; within a class, the available reserve is shared pro-rata. If a class consumes the remaining reserve, lower classes receive nothing.

The priority rules create a hierarchy between classes, while the within-class rule determines how scarce coverage is shared among claims at the same level.

## 3. CI synthetic fixture

CI compares four policies on the same 60-unit claim batch with 25 units of federation reserve:

| Invoice | Class | Due day | Eligible claim |
|---|---|---:|---:|
| CLAIM-003 | ordinary | 0 | 30.0 |
| CLAIM-001 | essential | 2 | 10.0 |
| CLAIM-002 | essential | 1 | 20.0 |

Priority order: `essential` before `ordinary`.

Expected allocation:

| Rule | CLAIM-003 ordinary | CLAIM-001 essential | CLAIM-002 essential | Reserve used |
|---|---:|---:|---:|---:|
| FCFS | 25.000 | 0.000 | 0.000 | 25.000 |
| Batch pro-rata | 12.500 | 4.167 | 8.333 | 25.000 |
| Priority then FCFS | 0.000 | 5.000 | 20.000 | 25.000 |
| Priority then batch pro-rata | 0.000 | 8.333 | 16.667 | 25.000 |

All four rules pay the same total reserve amount and leave 35 units uncovered. They differ only in the distribution of the uncovered loss. The example shows that a priority class can override an earlier due date.

## 4. Governance and legal boundary

Priority labels are not legal seniority. A real guarantee institution would need a contractually valid definition of eligible claims, claim cut-off times, class membership, evidence standards, appeal rights, conflicts-of-interest controls and jurisdiction-specific insolvency priority. An arbitrary class hierarchy can shift losses toward lower-priority members and create incentives to relabel claims.

The operational ledger currently supports FCFS by default and opt-in batch pro-rata. The class-priority variants are deliberately limited to analysis until governance and legal rules are independently specified.

All amounts and labels are synthetic. No real-world EAEU claim priority or guarantee policy is recommended.


## 5. CI validation

The CI allocation report ran all four rules on the three-claim, 60-unit batch with 25 units of reserve. Each rule allocated exactly 25 units, left zero reserve and 35 units uncovered. The targeted unit test verifies the distinct invoice-level payouts shown above, including the effect of priority overriding due-date order.

The full EIIOM CI run on code commit `4a55946af813ec44b7090ba7d684f233148dfb73` passed **170 pytest tests** and wrote `outputs/synergy_v66_federation_reserve_allocation_rules.json`. This validates the synthetic implementation and its accounting arithmetic, not the legitimacy of any real-world claim class.


The CI runner now writes the four-rule comparison using the explicit `essential` then `ordinary` priority order. The full test suite also includes repeated reserve replenishment stress checks; no claim-class rule has been enabled in the operational ledger.


The subsequent full EIIOM CI run on code commit `d9c1f37664614f46353a320071b345669e049dd2` passed **172 tests** and included the adversarial relabeling sensitivity report.
