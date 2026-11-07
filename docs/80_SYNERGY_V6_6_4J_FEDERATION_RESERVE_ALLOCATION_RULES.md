# SYNERGY V6.6.4-J — federation reserve allocation rules under multiple claims

**Status:** deterministic comparison implemented; the credit ledger supports FCFS by default and an opt-in batch pro-rata federation-reserve policy.  
**Purpose:** quantify how a finite federation reserve is distributed when several eligible claims compete for insufficient guarantee capital.

## 1. Competing rules

### First-come-first-served

Claims are ordered by `(due_day, invoice_id)`. The reserve pays each claim in that order until the reserve is exhausted. This matches the current ledger's deterministic settlement/default traversal.

### Batch pro-rata

All claims in the supplied batch are treated as simultaneously presented. Each receives the same coverage fraction:

[
lambda = minleft(1,rac{G}{sum_i L_i}ight)
]

[
P_i = lambda L_i
]

where (G) is available reserve capital, (L_i) is the eligible loss claim and (P_i) is the reserve payout.

The pro-rata option is a separate analytical allocation function. It does not silently change the production research ledger or assume that the claims have equal legal priority.

## 2. Deterministic fixture

CI compares three synthetic claims:
- CLAIM-001: 10 units, due day 1;
- CLAIM-002: 20 units, due day 1;
- CLAIM-003: 30 units, due day 2.

Available federation reserve: 25 units.

FCFS sorts the two day-1 claims by invoice ID, pays CLAIM-001 in full, then CLAIM-002 with the remaining 15, and pays nothing to CLAIM-003. Batch pro-rata treats all three as one simultaneous clearing batch and distributes 25/60 of each eligible claim.

Both rules must satisfy:
- total payout does not exceed opening reserve;
- reserve remaining plus payouts equals opening reserve;
- each claim's payout does not exceed its eligible amount;
- total uncovered claims equal eligible claims less total payouts.

## 3. Interpretation

FCFS protects earlier-due claims and creates a strong timing advantage. Batch pro-rata shares scarcity across the batch, but requires a clearly defined clearing cut-off and a legally/contractually recognized common claim class. If claims differ by seniority, collateral, essentiality or legal status, a single pro-rata class may be inappropriate.

The current ledger remains FCFS by due day and invoice ID. That is a reproducibility convention, not a recommendation for a real guarantee institution. A real design would need an explicit claim admission process, cut-off time, priority classes, dispute handling and appeal rights.

All claim amounts are synthetic. This comparison does not estimate real default loss distributions or establish a preferred policy.


## 4. CI smoke-fixture result

CI used a 25-unit reserve against 60 units of eligible claims. Both allocation rules paid 25 units, left zero reserve and left 35 units uncovered.

| Claim | Due day | Eligible loss | FCFS payout | Batch pro-rata payout |
|---|---:|---:|---:|---:|
| CLAIM-001 | 1 | 10.0 | 10.000 | 4.167 |
| CLAIM-002 | 1 | 20.0 | 15.000 | 8.333 |
| CLAIM-003 | 2 | 30.0 | 0.000 | 12.500 |
| **Total** | | **60.0** | **25.000** | **25.000** |

The sample makes the distributional difference explicit: FCFS fully protects the earliest invoice, while batch pro-rata shares the shortfall across all three claims. Neither changes aggregate reserve capacity or total uncovered loss. The difference is who bears the loss and when.

The CLI report was generated in the successful CI run on code commit `6348e85a80e3c46da9770daae29dfe3e6a72bf6a` (154 tests passed). Later commits add member operating-cash floor enforcement; they do not alter this pure allocation function.


## 5. Selectable ledger policy

The credit ledger now accepts `federation_reserve_allocation_rule`:
- `first_come_first_served` (default): preserves the established due-day/invoice-ID resolution path;
- `batch_pro_rata`: when one or more buyers default during the same processing day, the ledger collects all open payables of those cross-defaulted buyers into one batch. Local regional reserves are applied first, in stable order. The remaining eligible internal-supplier claims then share the federation reserve pro-rata. Local member assessment follows the federation reserve for same-region residuals; any remaining loss stays with sellers.

The pro-rata batch therefore applies across all eligible invoices of buyers that default on that processing day, including their other open payables pulled into cross-default. It does not include external supplier invoices in federation guarantee coverage. Regional reserve drawdown itself remains ordered, not pro-rata.

This is an opt-in research mechanism. It does not imply that all same-day claims have equal legal priority, nor does it replace jurisdiction-specific insolvency rules. The default ledger behavior remains FCFS.


## 6. Ledger validation

The latest successful EIIOM CI on commit `d95383f568c48958e33b39a9b8390f3a29e9490a` passed **163 tests**. Targeted fixtures verify:
- two same-day cross-region defaults split a 10-unit federation reserve into 5 units per claim under batch pro-rata;
- FCFS pays the first claim 10 units and the second zero under the same opening conditions;
- local regional reserve is used before the federation pool under batch pro-rata;
- the remaining seller losses and consolidated cash balances reconcile exactly within numerical tolerance.

The batch policy is covered by unit tests and the full CI test suite. The CI allocation-report fixture remains a pure side-by-side FCFS/pro-rata arithmetic comparison; the targeted ledger tests exercise the integrated policy.

Analytical extensions add explicit claim classes and priority-order alternatives (priority-class-then-FCFS and priority-class-then-batch-pro-rata). They are documented separately in [V6.6.4-L](82_SYNERGY_V6_6_4L_FEDERATION_CLAIM_PRIORITY.md) and are not enabled in the operational ledger.
