# SYNERGY V6.6.4-P — production payable-default batch experiment

**Status:** research implementation added; exact-head CI is pending. This experiment uses the real payable-invoice and default-resolution path. It does not replace or reinterpret V6.6.4-O's separate 100-cycle exogenous reserve-liquidity stress test.

## 1. Why this experiment is separate from V6.6.4-O

V6.6.4-O injects exogenous synthetic reserve claims to study repeated reserve depletion and replenishment over 100 cycles. It deliberately bypasses debtor and invoice state.

V6.6.4-P tests the production accounting path instead:

1. issue actual payable invoices through `CreditLedger.authorize_purchase`;
2. settle the cash-funded part immediately;
3. leave the remaining amount as buyer trade payable and seller trade receivable;
4. process the due date through `CreditLedger.process_day`;
5. trigger buyer cross-default and resolve every open invoice through `_resolve_buyer_default` / `_resolve_payable_default`, or through the same-day batch pro-rata path;
6. pay eligible sellers from local regional reserves first, then from the federation reserve;
7. record member assessments and residual seller write-offs;
8. optionally replenish the reserves through the existing non-mutating planner and atomic ledger settlement.

## 2. Cohort construction

Each deterministic seed creates one paired cohort of 100 synthetic invoices:

- 20 economic cells split equally between borrowers and sellers;
- borrowers begin with 20 cash each; sellers begin with 100 cash each;
- borrowers issue 10 invoices each, one to every seller;
- invoice amounts are sampled deterministically from 10.0 to 15.0;
- invoice issuance is day 0 and due date is day 1;
- borrowers have no bank line;
- buyer trade-credit and seller receivable limits are deliberately high enough to authorize the fixture;
- grace period is zero, so remaining unpaid amounts enter the actual default path on day 1;
- all sellers remain solvent and are separate from the borrower cohort.

The first cash available at each borrower is used by the normal cash-first procurement waterfall. The residual credit amounts become the default claims. Thus the experiment has 100 issued invoices, but fewer than 100 unpaid invoice claims; the exact number and amounts are reported from ledger events, not assumed.

Initial reserves are funded from seller opening cash, not minted:

- 20 units per regional reserve, funded by sellers in that region;
- 40 units in the federation reserve, funded by the seller cohort;
- combined initial member cash is conserved;
- minimum post-contribution cash is 20;
- subsequent reserve recovery is capped at 10% of each member's opening cash per ledger-defined 30-day window.

The exact invoice amounts, buyer/seller mapping and opening balances are hashed into a paired-path fingerprint. Both clearing rules and every recovery policy receive the same seed-specific fixture.

## 3. Clearing and recovery comparisons

Clearing rules:

- `first_come_first_served`: production ledger's default invoice-order clearing;
- `batch_pro_rata`: production ledger's same-day federation-reserve pro-rata clearing, with local reserves still first-loss.

Recovery policies:

- `no_replenishment`;
- `equal`;
- `production_capacity`;
- `opening_cash`;
- `adaptive_liquidity`.

This creates ten paired combinations per seed. The experiment reports both aggregate loss allocation and the distribution of guarantee payouts among sellers. FCFS and batch pro-rata may allocate the same finite reserve total differently among individual sellers; no rule is described as legally senior or economically optimal.

## 4. Metrics and invariants

The JSON report includes:

- issued invoice count and actual default-resolution invoice count;
- number of defaulted borrowers and sellers;
- cash settled before default;
- claim amount, local guarantee payout, federation payout, member assessment, and seller write-off;
- claim coverage and claim-reconciliation residual;
- seller guarantee-payout Gini and per-seller payout map;
- recovery requested, funded, unfunded and actual member contributions;
- contribution Gini, top-20% contribution share and maximum contribution/opening-cash ratio;
- contributor cash-floor breaches and 30-day cap excess;
- final local and federation reserve balances;
- cash-conservation residual before default, after default and after recovery;
- bank draws, customer-collection inflows and external supplier outflows.

The report's invariant flags are calculated from observed rows. A successful run must show:

- all borrower cohorts defaulted and no seller defaults;
- every claim reconciled to reserve/member payouts plus write-off;
- zero cash-conservation residual within numerical tolerance;
- zero bank draws and zero external cash inflows/outflows;
- no contributor cash-floor breach;
- no 30-day contribution-cap excess.

The general minimum cash of a defaulted borrower is not treated as a reserve-contribution floor breach. The cash-floor invariant applies specifically to members who actually contribute to replenishment; a borrower may have spent its available cash before default.

## 5. Reproduction

Run:

```bash
python scripts/run_synergy_v664p_production_defaults.py --seed-start 11 --seed-count 10
```

For the CI smoke test:

```bash
python scripts/run_synergy_v664p_production_defaults.py --seed-start 11 --seed-count 3 --output outputs/synergy_v664p_production_default_batch_ci.json
```

## 6. Interpretation limits

This is a synthetic, correlated due-day default cohort of 100 invoices and 10 borrowers. It is **not** a 100-day sequence of 100 independent borrower defaults. It tests whether the actual invoice authorization, cash-first settlement, cross-default, reserve waterfall, seller accounting and replenishment code work together under a controlled batch.

It does not calibrate default probabilities, loss-given-default, EAEU cash flows, recovery rates, reserve adequacy, legal enforceability, creditor ranking, claim eligibility, FX, tax or sovereign risk. FCFS is the software default, not a legal priority recommendation. Batch pro-rata is an analytical alternative, not a legal insolvency rule.

The 100-cycle exogenous stress harness and this production default cohort answer different questions and must remain separately reported.
