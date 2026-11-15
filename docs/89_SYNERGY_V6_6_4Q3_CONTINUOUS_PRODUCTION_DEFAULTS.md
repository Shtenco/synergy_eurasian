# SYNERGY EURASIAN V6.6.4-Q3 — continuous 100-cycle production defaults

**Status:** executable research experiment committed to the research branch; exact-head CI result pending. Synthetic assumptions only. This is not a calibrated forecast or a claim of reserve adequacy.

## 1. What this experiment changes

V6.6.4-O used exogenous reserve claims. V6.6.4-P used real payable invoices and the production default waterfall, but only as one correlated same-day cohort. Q3 joins the actual production invoice/default path to repeated reserve depletion and member-funded recovery on one continuous ledger.

The runner is:

`scripts/run_synergy_v664q3_continuous_defaults.py`

The engine is:

`src/synergy_v66/continuous_default_experiments.py`

It uses the production `CreditLedger.authorize_purchase`, `CreditLedger.process_day`, `CreditLedger.replenish_reserves` and the state-bound `plan_reserve_recovery` / `execute_reserve_recovery` workflow. It does not substitute exogenous claims for defaults and does not create a fresh ledger between cycles.

## 2. Synthetic topology and path

Each path has 210 cells:
- 100 unique borrowers (50 WEST, 50 EAST);
- 100 unique sellers (50 WEST, 50 EAST);
- 10 dedicated reserve members (five per region).

There are 100 cycles. A fresh borrower in alternating WEST/EAST order issues one seed-varied payable invoice (80–120 units) to a same-region seller. Buyer opening cash is 10 units, so 10 is settled immediately and 70–110 remains as trade credit. The 100 invoice amounts are balanced around 100 and sum to exactly 10,000 units for every seed; therefore aggregate production-default claims remain exactly 9,000 units. The invoice is due the following day. The buyer has no bank line; the remaining payable is resolved through the actual production default path. Each borrower appears exactly once and remains permanently defaulted.

All policies receive the same seed-specific invoice sequence and opening cash. Seeded invoice amounts are now genuinely heterogeneous: 50 deterministic positive/negative shock pairs are shuffled per seed, bounded to 80–120, with an exact 10,000-unit invoice total. Different seeds therefore represent different claim timing/size paths rather than merely different invoice IDs. The scenario fingerprint binds the seed, invoice path, opening cash, reserve member sets and reserve targets.

## 3. Reserve design

| Parameter | Value |
|---|---:|
| Initial and target regional reserve, each region | 45 |
| Initial and target federation reserve | 500 |
| Initial cash per reserve member | 1,000 |
| Minimum reserve-member cash floor | 500 |
| Ledger contribution cap | 10% of opening cash per 30-day window |
| Recovery ordering | local regional deficit first, federation deficit second |
| Bank lines | 0 |
| External customer inflows | 0 |
| External supplier outflows | 0 |

Regional membership is five dedicated reserve members per region. Federation membership is the ten reserve members independently. Each participant has one combined cash floor and one shared 30-day contribution cap across both reserve tiers. The ledger rechecks membership and contribution limits at settlement; the planner is not the sole authorization control.

The initial reserve contribution maps are fully funded by opening member cash. Reserve replenishment is a transfer of existing member cash; it is not revenue or new system wealth.

## 4. Paired policies

Each seed is run through:
1. no replenishment;
2. equal allocation;
3. production-capacity-weighted allocation;
4. opening-cash-weighted allocation;
5. adaptive-liquidity allocation.

The CI runner uses seeds 11, 23 and 37: 15 continuous paths and 1,500 actual invoice/default cycles in total. Each path writes cycle-level records and aggregate metrics to a JSON report, uploaded as the `synergy-v664q3-continuous-defaults` GitHub Actions artifact.

## 5. Mandatory cycle-level accounting

For every cycle the report records:
- unique invoice, buyer, seller, region and ledger day;
- payable amount and actual default resolution;
- local guarantee, federation guarantee, member assessment and seller write-off;
- claim reconciliation and seller bad-debt reconciliation;
- regional and federation reserve balances before the next cycle;
- recovery requested, funded, unfunded and actual replenishment;
- member cash, total system cash and conservation residual;
- bank draws, external inflows and external outflows;
- cumulative number of permanently defaulted borrowers.

Aggregate metrics include claim coverage, uncovered losses, member contributions, contributor Gini, top-20% contribution share, 30-day cap excess, reserve-member cash-floor breaches and ending reserve balances.

## 6. Hard invariants

The runner fails if any path violates:
- 100 distinct production default resolutions;
- identical paired invoice path for every recovery policy;
- claim = local guarantee + federation guarantee + member assessment + write-off;
- seller bad debt equals written-off payable claims;
- cash conservation at every cycle and total system cash conservation;
- zero bank draws and zero external cash flows;
- no defaulted borrower contributions;
- no 30-day contribution-cap excess;
- no reserve-member cash-floor breach;
- no negative reserve balance.

A failed invariant must fail the CI experiment, not be silently omitted from summary statistics.

## 7. Interpretation boundary

This is a deliberately controlled synthetic credit-network stress path. It does not establish a real-world default probability, commercial invoice size, economically optimal reserve target, legally enforceable mutual guarantee, or EAEU member contribution rule. It does not model taxes, FX, customs, operating profits, asset valuation, external investors, sovereign risk or legal insolvency priorities.

The most important structural sensitivity is the priority rule: regional recovery is funded before federation recovery, while local reserves also pay claims first. This may preserve local first-loss capacity but can crowd out federation replenishment when regional deficits consume most of the shared 30-day contribution capacity. The cycle report must be used to quantify this effect rather than assuming either tier is adequately funded.

## 8. Next gate after Q3

After exact-head CI passes and the raw artifact is reviewed:
- extend the path to correlated borrower cohorts and cross-region claims;
- test alternative local/federation recovery priority and shared-cap allocation;
- add endogenous customer collections and operating cash generation only with explicit, auditable assumptions;
- calculate consolidated NAV with reserve cash, member cash, bank debt, receivables, payables, bad debt and conservative asset haircuts;
- compare all scenarios using the same invoice and shock paths.

Do not merge to `main` or label any policy production-ready until the exact branch head passes CI, the output artifact is reconciled independently, and the base-branch divergence is deliberately resolved.

## 9. Deterministic no-replenishment baseline (test oracle)

Before running the engine, the no-replenishment path has an exact accounting oracle:
- Invoice amounts vary by seed from 80 to 120 units and sum to exactly 10,000 units per path; 10 units per invoice are cash-settled at authorization.
- The remaining payable claims at default therefore sum to exactly 10,000 − 1,000 = 9,000 units.
- 100 unique borrowers therefore create 9,000 units of production-default claims in aggregate, while individual cycle claims differ.
- Initial reserves are 45 × 2 regional funds + 500 federation = 590 units.
- With no reserve replenishment and no other guarantee/assessment source, maximum aggregate guarantee payout is 590 units.
- Expected uncovered loss is 9,000 − 590 = 8,410 units.
- Expected claim coverage is 590 / 9,000 = 6.5556%.

This is a deterministic aggregate arithmetic expectation encoded as a regression-test oracle and remains invariant under the seed-specific invoice-size variation. It is not yet a measured GitHub Actions result. The Q3 runner must reproduce it before any replenishment-policy comparison is interpreted.


## 10. Seed diversity correction and regression gate

The first Q3 draft used a fixed 100-unit invoice in every cycle. Although the invoice IDs included the seed, that did not create distinct economic paths. The corrected scenario generator now creates 50 deterministic positive/negative shock pairs per seed, shuffles them, and applies bounded invoice amounts from 80 to 120 units. The exact total remains 10,000 invoice units for every seed, so the 9,000-unit aggregate default-claim oracle and 590-unit no-replenishment reserve payout oracle remain unchanged.

Added focused tests for:
- distinct seed-specific invoice amount sequences and fingerprints;
- exact 10,000 invoice-unit total and positive claims after 10-unit cash settlement;
- the 100-cycle no-replenishment oracle (9,000 requested, 590 paid, 8,410 written off);
- paired recovery policies sharing one identical seed-specific path;
- all cycle and path invariants across recovery strategies.

**Validation status:** these regression tests and the corrected scenario generator are committed to the research branch. They have not yet been executed locally in this environment or confirmed by exact-head GitHub Actions. The exact-head CI and uploaded cycle artifact remain mandatory before interpreting the policy comparisons.
