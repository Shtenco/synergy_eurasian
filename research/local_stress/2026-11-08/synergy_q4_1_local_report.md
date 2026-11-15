# SYNERGY EURASIAN — Local continuation Q4.1

## Scope and validation

This is a local synthetic research extension. It does not modify the production repository and does not claim that the production `CreditLedger` has the semantics modeled here.

Executed locally:
- Q2 reserve-membership fixture: 5/5 control tests passed.
- Q4 correlated-default/reserve-recovery harness: 9/9 local tests passed.
- Q4.1 same-day settlement-order diagnostic: 8/8 local tests passed.

The Q2 fixture includes an assumed external inflow of 80 per cell per 30-day cycle (1,600 total per cycle across 20 cells). Its 100-cycle output is therefore conditional on 160,000 of exogenous cash inflows over 100 cycles. It is not a self-financing reserve-survival result and does not include a default waterfall.

The Q4 fixture has 20 cells, two regions, three correlated default waves, 20 invoices, 3,104 total invoice claims, 8,000 of explicit external operating cash burn, local-first and federation-second reserve payouts, and post-wave reserve replenishment. The ending cash identity is 20,590 - 8,000 = 12,590. The cash-only consolidated proxy excludes physical assets, external liabilities and operating assets received for the cash burn.

## Q4.1 finding: same-day settlement is order-sensitive if receipts are reusable

A deliberately small circular cohort:
- A owes B 150.
- B owes C 150.
- C owes A 150.
- Each account opens with cash 100.
- Gross claims total 450; system cash totals 300.

Two settlement semantics were compared.

### Sequential gross settlement

Incoming receipts are immediately spendable by the next invoice in the same processing batch. Across all six possible invoice orders:
- Total cash paid ranges from 350 to 400.
- Unpaid claims range from 50 to 100.
- The identity of the unpaid creditor changes with invoice order.
- Cash conservation remains exact: 300 opening = 300 ending.

### Snapshot batch settlement

Each buyer may spend only its opening cash for the cohort; receipts become spendable after the batch:
- Total cash paid is 300.
- Unpaid claims total 150.
- All three claims receive 100.
- Reversing invoice order does not change the result.
- Cash conservation remains exact.

This is not evidence that one rule is universally correct. Sequential settlement can represent a real-time gross settlement system where final receipts are immediately reusable. Snapshot settlement represents a simultaneous cohort clearing convention. A third possibility is legally and operationally valid multilateral netting. The production implementation must determine which model is actually intended and enforce it consistently. An additional deterministic property test exercised 100 randomized 6-account / 25-invoice cohorts under both sequential and snapshot settlement and both forward/reverse invoice orderings (400 settlement runs), checking cash conservation, nonnegative balances and claim reconciliation.

### Multilateral netting upper bound

The same three-way closed cycle has zero net position for every participant. If an enforceable multilateral set-off agreement applies to all three invoices, the 450 gross claims can be extinguished with zero cash movement. This is a netting result, not a cash payout, and must not be reported as 450 of paid cash. It is an analytical upper bound for liquidity efficiency; actual availability depends on contractual enforceability, insolvency treatment, membership boundaries and settlement-finality rules.

## Why this matters to SYNERGY

The Q4 stress harness intentionally keeps borrowers and sellers disjoint within each due-date wave, so it does not expose circular reuse. In a denser production network, one participant may simultaneously be:
- a debtor on one invoice,
- a creditor on another invoice,
- and a reserve member.

If `process_day` mutates balances invoice-by-invoice and credits sellers immediately, invoice ordering can change:
1. how much same-day debt is paid from cash,
2. which claims reach the guarantee waterfall,
3. which sellers receive cash,
4. which members remain liquid and eligible to replenish reserves,
5. the eventual distribution of uncovered losses.

Therefore reserve coverage percentages from Q4 should not be generalized to cyclic same-day cohorts until this settlement semantic is tested.

## Required production audit before Q5 integration

Inspect the actual production implementation and answer, with line-level evidence:
1. Does `process_day` snapshot opening cash or mutate cash sequentially?
2. Are invoices sorted by ID, due date, buyer, seller, or insertion order?
3. Can a seller receipt from an invoice due today be reused to pay another invoice due today?
4. Are all same-day defaults determined before settlement, or can one payment change another buyer's default status?
5. Does the default waterfall operate on original claims, post-cash residual claims, or netted claims?
6. Are same-day cross-defaults processed atomically or one borrower at a time?
7. Does seller receipt from reserve payout go to a frozen/defaulted seller, and if so, how is it treated?
8. Is the ordering policy a reproducibility detail, a payment-system rule, or a creditor-priority rule?

## Recommendation

Do not silently change production settlement behavior. First add characterization tests for the existing behavior. Then choose and document one of:
- sequential gross settlement with deterministic order and explicit same-day receipt reuse;
- simultaneous snapshot settlement;
- legally reviewed multilateral netting and clearing.

The selected rule must be reflected in ledger code, audit events, default claims, reserve payouts, and NAV reconciliation. Only after this should Q4 be replayed through the real `CreditLedger`.

## Repository boundary

No GitHub files were changed. A local checkout of the production repository was not available because the environment could not resolve `github.com` during the prior clone attempt. The files in this package are standalone local research scripts, not production patches.