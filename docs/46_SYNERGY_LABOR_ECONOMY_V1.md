# SYNERGY LABOR ECONOMY (SLE) V1

**Status:** additive research specification; no monetary issuance or payment authority.
**Repository:** `Shtenco/synergy_eurasian`
**Authority boundary:** Real Economy OS records verified physical/economic contribution and emits proposals. `synergy_financial_os` alone recognizes accounting facts and authorizes financial postings. `synergy_pay_system` alone executes authorized settlement.

## 1. Purpose

SLE makes human, collective and AI-assisted work observable and attributable without treating every contribution as money. It creates a portable, privacy-preserving evidence record and a deterministic contribution score. It does not create wages, securities, deposits, stablecoins, credit claims or legal employment status by itself.

V1 is intentionally narrow: validate accepted contribution records, prevent duplicate attribution of the same benefit stream, and calculate a non-monetary score. It does not mint LABOR CREDIT or SDU.

## 2. Four distinct objects

| Object | Meaning | Transferable? | Monetary/accounting meaning |
|---|---|---:|---|
| Labor Evidence Record | Signed evidence that a defined contribution was performed and accepted | No | None |
| Labor Score | Versioned, reproducible measure used for comparison and allocation proposals | No | Not money, not a receivable, not NAV |
| Labor Credit Claim | Future right to a specified good/service from a named issuer, with capacity and redemption terms | Only if contract and policy allow | Issuer liability only after valid issuance and accounting recognition |
| SDU Reward Proposal | Proposed allocation from an identified, funded budget | No | Proposal only; no mint, payable or payment until Financial OS authorization |

A score must never be presented as a guaranteed exchange rate into SDU, cash, wages or credit.

## 3. Contribution evidence contract

Each contribution is keyed by an immutable `contribution_id` and references:
- pseudonymous contributor and project identifiers;
- a controlled contribution category and contributor kind (human, AI agent or joint);
- one `benefit_stream_id` identifying the underlying measurable benefit;
- positive, explicitly dimensioned effort units;
- policy-bounded complexity, quality, outcome and reliability factors;
- an attribution share between 0 and 1;
- at least one content-addressed evidence item;
- an independent verifier, disclosed conflicts and signature reference.

The record must not contain names, government identifiers, health data or other unnecessary personal data. Store evidence off-chain or in an access-controlled evidence service; publish only references and hashes where appropriate.

Accepted records require at least one declared independent evidence item and a declared independent verifier. **V1 validates metadata assertions only:** it does not fetch evidence bytes, recompute their hashes, authenticate verifier identities or cryptographically verify signatures. A production adapter must perform those checks before it can assert acceptance. Self-attestation alone is insufficient.

## 4. V1 score

For accepted contribution (i):

[
S_i=E_i\times C_i\times Q_i\times O_i\times R_i\times A_i
]

where:
- (E_i): verified effort units in the declared work-package unit;
- (C_i): complexity multiplier, bounded by the versioned policy;
- (Q_i): quality factor in ([0,1]);
- (O_i): observed outcome factor, bounded by policy;
- (R_i): reliability factor in ([0,1]);
- (A_i): attribution share in ([0,1]).

The V1 reference policy uses (C_i\in[0.5,2.0]), (O_i\in[0.5,2.0]). These are explicit MODEL_ASSUMPTION bounds, not empirical constants or universal fairness coefficients. Quality and reliability must be supported by evidence. A score of zero is valid when quality or reliability is zero.

Effort units are work-package units, not automatically hours. If hours are recorded by a source system, they remain a separate measured field and must not be silently converted into wages. All records in one scoring batch must use the same standardized effort unit; mixed units are rejected rather than added. Separate batches cannot be compared until an empirically calibrated conversion policy exists. The score is a policy-relative contribution index, not an objective measure of human worth.

### Attribution conservation

For every underlying benefit stream (b):

[
sum_{i\in b} A_i\leq 1
]

If the total attribution exceeds 1, the complete scoring batch is rejected. A repeated `result_digest` cannot be assigned to different benefit streams within one batch. The engine does not silently normalize shares because that would hide duplicate claims and change previously agreed attribution.

A single measured benefit may have several contributors, but the aggregate credited attribution cannot exceed the underlying benefit. Repeated evidence hashes do not by themselves prove separate benefits.

## 5. Revisions, disputes and delayed impact

Evidence records are append-only. A correction creates a new revision referencing the prior record, the reason, new evidence and an authorized reviewer. It does not overwrite the original record.

A dispute freezes the affected reward proposal, not the person's entire portable history. A successful appeal appends a resolution event and a replacement score snapshot.

Long-term impact may be recognized in a later measurement period. It must be represented as a new evidence-backed outcome/revision with an explicit link to the original benefit stream. It must not create a second copy of the same underlying benefit.

## 6. Human, AI and joint work

The contributor kind is explicit:
- HUMAN: contribution attributable to a person;
- AI_AGENT: contribution attributable to a registered agent identity;
- JOINT: a joint contribution with a separately evidenced attribution schedule.

The same output cannot be credited at 100% to both a human and an AI agent. For joint work, shares across all attributable contributors must satisfy the benefit-stream conservation rule. Tool ownership, compute expenditure and capital provision are separate inputs, not labor contributions.

Care, education, coordination, maintenance, community and voluntary work may be recorded under appropriate categories. Recognition does not imply that the work is unpaid by choice, legally voluntary, or a substitute for wages. Participation must be voluntary; no housing, essential service or access to basic rights may be conditioned on accepting tokenized work.

## 7. Financial and monetary firewall

The following are prohibited in V1:
- automatic SDU minting from a Labor Score;
- treating Labor Score as collateral, HardNAV or external profit;
- treating token issuance, modelled GVA, labor hours released or internal transfers as cash;
- issuing a transferable Labor Credit without an identified issuer, enforceable service specification, redemption capacity, limits and independent accounting review;
- using EIIOM or an AI agent as the authority to approve a payment, wage, loan, security or monetary issuance.

A future Labor Credit must be a two-sided obligation: the holder's claim must map to an issuer's recorded obligation and a specific redemption/service capacity. Issuance must reserve capacity, respect member and issuer limits, and settle or expire only through explicit lifecycle events. A credit network cannot create consolidated NAV by issuing claims against itself.

A future SDU reward must be backed by an identified, available funding source and pass Financial OS controls. The SLE engine may emit a proposal only; Financial OS decides whether to recognize a payable or authorize a payment. Payment execution belongs to the settlement authority.

## 8. Relationship to existing SYNERGY models

- Economy 6.3 / seven-sector model: labor-hours, productivity and released-time metrics remain physical/economic indicators; they are not cash savings.
- Productivity Flywheel V1–V6: labor-time release is a separate benefit stream and cannot be booked as both wage savings and additional output without evidence.
- EIIOM: consumes aggregated, permissioned labor-supply and skill-capacity signals; it does not receive unnecessary personal evidence.
- V6.6 mutual credit: any future labor credit integration must reuse member limits, reserve constraints, cumulative contribution caps, cash conservation and explicit replenishment rules. No parallel reserve or money-creation path is introduced.
- V7 event graph: contribution and evidence events should eventually be represented as typed events with idempotency and provenance; this V1 module does not claim V7 runtime integration.
- Financial OS: canonical accounting and financial authority.
- Payment system: settlement execution after authorization.

## 9. V1 implementation and acceptance criteria

The reference implementation in `src/synergy_labor_economy.py`:
1. uses Decimal arithmetic;
2. rejects duplicate contribution IDs;
3. rejects unaccepted, unverified or unsupported records;
4. rejects missing content hashes and non-independent verification;
5. enforces policy bounds;
6. rejects attribution totals above 1 per benefit stream;
7. produces deterministic scores without currency fields or side effects.

Focused tests are in `tests/test_synergy_labor_economy.py`. These tests establish only the local scoring contract. They do not prove employment-law compliance, economic fairness, external demand, financial solvency or production readiness.

## 10. Roadmap

- V1: evidence contract, contribution scoring, attribution conservation.
- V1.1: append-only revision/dispute lifecycle and signed evidence envelope.
- V2: funded reward-pool proposal with deterministic minor-unit allocation; no payment execution.
- V3: issuer-specific service credits with capacity reservation, limits, expiry, redemption and default handling.
- V4: Financial OS and settlement adapters with idempotency, accounting mapping and reconciliation.
- V5: privacy-preserving portable credentials, selective disclosure and federated verification.
- V6: AI/human joint contribution graph, longitudinal impact and anti-collusion stress tests.

Each stage requires source-grounded tests, explicit legal review for its deployment jurisdictions, and evidence that its authority boundary is preserved.
