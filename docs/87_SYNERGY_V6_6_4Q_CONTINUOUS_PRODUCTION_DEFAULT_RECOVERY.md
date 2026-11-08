# SYNERGY V6.6.4-Q — repeated production-default and reserve-recovery design

**Status:** research specification / implementation gate. No code, test pass, or economic result is claimed by this document.

## 1. Motivation

V6.6.4-O exercises 100 repeated exogenous reserve claims, but it does not create debtor invoices or invoke the production default waterfall. V6.6.4-P creates 100 actual payable invoices and resolves them through the production ledger, but all invoices belong to one correlated due-day cohort. It is not a repeated multi-cycle experiment.

These two experiments must remain separately identified. The next increment must connect the actual invoice/default path to repeated reserve depletion and member-funded recovery without treating exogenous claims as defaults.

## 2. Structural blocker discovered

The current V6.6.2 topology is fixed at 20 cells (10 per region). The P fixture divides those cells into 10 borrowers and 10 sellers. A borrower that defaults is cross-defaulted and permanently excluded from further credit and reserve contributions. Therefore the existing 20-cell fixture cannot honestly represent 100 sequential independent borrower-default cycles.

Do not work around this by resetting a defaulted cell's status; restoring member cash between cycles; constructing a fresh ledger for each cycle while carrying forward only reserve balances; counting several invoices from one same-day borrower cohort as independent cycles; or relabeling exogenous reserve claims as production defaults. Any of these would break path continuity or overstate the number of independent default events.

## 3. Required architecture increment

Add a parameterized, deterministic credit-network fixture for stress experiments. It must be separate from the canonical 20-cell physical production topology unless the production topology itself is deliberately versioned.

The stress fixture must support configurable borrower and solvent-seller populations across both regions; stable cell IDs, region membership, opening cash and production-capacity weights; explicit reserve-funding membership and initial member-funded reserve balances; actual ledger authorization, cash-first settlement, due-date processing and default waterfall; permanent default state for a borrower after cross-default; unique invoice, default-event, recovery-plan and replenishment IDs; one continuous ledger and cash history for the entire run; and a reproducible seed/path fingerprint shared by every paired policy.

If the credit ledger currently hard-codes the canonical cell set, introduce an explicit, validated topology dependency or a separate stress-ledger adapter. Avoid global mutation of the canonical topology maps.

## 4. Proposed paired experiment

Run 100 sequential due-date cycles on one continuous ledger. Each cycle introduces a fresh borrower sub-cohort and solvent counterparties; once a borrower defaults, it never re-enters the active population. Use common seed-specific invoices and shock schedules across policies.

At minimum compare no replenishment; equal contributions; production-capacity-weighted contributions; opening-cash-weighted contributions; and adaptive-liquidity contributions.

Keep clearing rules paired: production FCFS; same-day batch pro-rata, with local reserves still first-loss.

Use at least three deterministic shock regimes: dispersed defaults; correlated regional defaults; and federation-wide systemic defaults. The scenario generator must state how many borrowers default in each cycle, whether invoices are contemporaneous, and how correlation is imposed. Do not infer empirical default probabilities from synthetic parameters.

## 5. Recovery timing and contribution-cap semantics

After each cycle: finish invoice settlement and default resolution; snapshot claims, local/federation payouts, member assessments and write-offs; calculate regional and federation reserve shortfalls against fixed declared targets; construct a non-mutating recovery plan; enforce defaulted-member exclusion, regional membership, cash floors and the ledger-owned cumulative contribution cap; execute the combined regional/federation transfer atomically; verify cash conservation before advancing to the next cycle.

The existing 30-day contribution window is authoritative. A 100-cycle experiment must advance ledger days consistently and may not reset the cap by changing caller-provided period labels or by assigning each cycle a new recovery window. If the intended recovery horizon differs from 30 days, it must be an explicit ledger policy variant and tested separately.

A contribution is a transfer of existing member cash to a reserve account. It is not revenue, credit creation, external inflow, or a write-off reversal.

## 6. Mandatory per-cycle outputs

Record before and after recovery: active, newly defaulted and cumulatively defaulted borrowers; invoices issued, cash-settled and default-resolved; claims requested, local reserve payout, federation payout, member assessment and seller write-off; regional and federation reserve balances and target deficits; recovery requested, funded, unfunded and actual contributions by member; member cash distribution, minimum cash among contributors and cash-floor breaches; cumulative contributions by member, contribution/opening-cash ratio and rolling 30-day cap usage; cash-conservation residual and claim / seller bad-debt reconciliation residual; bank draws, external inflows and external outflows; reserve exhaustion cycle and cycles with zero or partial claim coverage.

Aggregate outputs must include claim coverage, uncovered losses, reserve recovery ratio, reserve depletion/recovery duration, contributor concentration (Gini and top-20% share), member cash inequality, default concentration by region, and paired differences between policies.

## 7. Hard invariants

Every cycle and final path must satisfy: no negative reserve or member cash; no defaulted member contribution; no contributor cash-floor breach; no cumulative 30-day contribution-cap excess; no duplicate event or transaction IDs; every claim reconciles to guarantee/member-assessment payouts plus write-off; seller trade bad debt reconciles to written-off payable claims; cash conservation residual within the declared numeric tolerance; zero bank draws and external flows in the closed-system baseline; same scenario fingerprint across all paired policies; permanent borrower default state; and recovery plans are state-bound, tamper-evident and settled atomically.

A failed invariant must fail the experiment rather than be filtered from summary statistics.

## 8. Required adversarial tests

Test: one borrower defaults, recovery is assessed, and a later cohort defaults; two regions default in the same cycle while local reserves are asymmetric; federation-wide shock exhausts both reserve tiers; a contributor's cash falls near the floor between planning and execution (stale plan rejected); multiple recovery calls within one 30-day window cannot reset member caps; a new 30-day window permits only the policy-authorized incremental capacity; defaulted borrowers are never charged recovery contributions; one member is eligible regionally but not for another region's local reserve; duplicate invoice/recovery IDs and modified plans are rejected atomically; and no-replenishment and all contribution policies share identical exogenous invoice paths.

## 9. Validation and reporting gate

Before interpreting results: focused tests for the configurable topology and cycle engine pass; the full EIIOM CI passes on the exact branch head; README integrity passes on the exact branch head; the generated report is reproducible from its recorded seed/configuration; cycle-level raw data and aggregate summaries are retained as artifacts; and the report clearly distinguishes a 100-cycle production-default path from the existing 100-cycle exogenous-claim stress and the one-batch 100-invoice experiment.

No policy is ranked as fair, optimal, adequate or suitable for real EAEU deployment on synthetic results alone.

## 10. Decision rule

If the current ledger cannot accept an explicit topology without invasive changes, first deliver and test the topology abstraction as a separate increment. Do not force the repeated-cycle experiment into the existing fixed 20-cell topology. The next release label is provisional: **V6.6.4-Q — continuous production-default recovery stress**.

## 11. Q1 implementation increment — parameterized credit topology

The credit ledger now accepts an optional immutable tuple of `CellSpec` records and an optional explicit region ordering. When omitted, the canonical 20-cell physical topology and its original region ordering remain the defaults.

The reserve recovery planner now derives cell IDs, cell metadata and regions from the ledger instance rather than importing the canonical physical topology. This keeps the recovery planner aligned with the exact ledger against which a plan is fingerprinted and settled.

The ledger validates unique non-empty cell IDs, non-empty region/sector/role metadata, finite non-negative capacities, exact region membership, and exact opening-cash / reserve contribution map coverage. The stress topology is injected per ledger instance; module-level canonical topology maps are never mutated.

Focused tests have been added for:
- unchanged canonical 20-cell defaults and region ordering;
- custom six-cell, two-region credit topology;
- exact map coverage and duplicate-ID rejection;
- malformed topology metadata rejection;
- recovery planning and atomic settlement against a custom topology;
- isolation of the canonical physical topology from custom stress fixtures.

**Validation status:** implementation and tests are committed to the research branch, but the focused tests and full EIIOM CI have not yet been confirmed on the exact branch head. The continuous 100-cycle production-default engine is not implemented by this increment. Do not treat Q1 as evidence of a completed multi-cycle stress experiment.
