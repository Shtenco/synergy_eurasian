# 48 — SLE ↔ Financial OS Handoff Contract V1

**Status:** integration contract proposal; no cross-repository adapter is implemented by this document.

## 1. Repository and promotion facts

SLE implementation is developed in `Shtenco/synergy_eurasian`, PR #17.

Financial OS exposes a substantial terminal accounting lineage in feature branches. The observed canonicalization target is `Shtenco/synergy_financial_os` PR #33, head `d21ce6b5bd91422c45f938b2d4ec641974106944`. PR #33 explicitly remains open/draft and says hosted CI has not exposed executed step/log PASS evidence. Therefore its interfaces are research-lineage observations, not a stable dependency available from Financial OS `main`.

This contract intentionally does not import Financial OS code into SLE and does not create a competing accounting ledger.

## 2. Authority split

| Action | SLE / Real Economy OS | Financial OS | Payment / settlement |
|---|---|---|---|
| Record contribution evidence | Propose and retain provenance | Independently verify/consume evidence | None |
| Score labor | Calculate non-monetary score | No authority to redefine score | None |
| Authorize award | No | Only through separately approved reward/accounting policy | None |
| Issue service claim | Operational obligation registry; issuer capacity gate | Decide whether and how it is recognized in accounts | None |
| Recognize monetary liability | No | Exclusive accounting authority | None |
| Pay cash / SDU | No | Issue approved handoff only | Execute only authorized instruction |
| Confirm delivery/redemption | Record operational fulfillment evidence | Recognize corresponding accounting effect when justified | None |

SLE must never call Financial OS ledger mutation APIs directly as an AI/optimizer side effect. A human/authorized service boundary must authenticate the event and submit a canonical evidence package.

## 3. Proposed handoff envelope

The producer should emit an immutable envelope with:
- `schema = "sle.financial-handoff/v1"`;
- globally unique `event_id`, `idempotency_key`, and `award_authorization_ref`;
- `event_type`: `SERVICE_CLAIM_ISSUED`, `SERVICE_CLAIM_REDEEMED`, `SERVICE_CLAIM_CANCELLED`, `SERVICE_CLAIM_DEFAULTED`;
- `credit_id`, `issuer_id`, `holder_id`;
- `source_contribution_id`, `result_digest`;
- `service_code`, `unit`, `quantity`;
- `capacity_id`, `capacity_evidence_digest`;
- `effective_at`, `due_at` where relevant;
- `policy_version`, `ledger_event_seq`, `ledger_event_hash`;
- references to verifier credentials, award authorization and evidence package.

The envelope carries quantity and provenance. It must not contain an invented currency amount, exchange rate, NAV value, payable or journal account mapping.

## 4. Financial OS recognition mapping

The observed Financial OS terminal lineage defines:
- `ReportingAccountSpec` with explicit account class and consolidation class;
- `ReportingEntry` and `ReportingLedger.post(...)`;
- `FlowType.LIABILITY_ISSUANCE` and `FlowType.LIABILITY_REDEMPTION`;
- balanced debit/credit validation and required evidence digest for non-internal flows;
- `ledger.event/v2` export/verification and accounting-close snapshots.

These are useful candidate interfaces, but they are not assumed to be merged into Financial OS `main`.

If and only if the Financial OS accounting policy concludes that a particular service obligation is a recognized monetary liability, Financial OS may classify it as a liability issuance/redemption and construct balanced reporting-currency lines. SLE does not choose the debit account, reporting-currency value, valuation rule, recognition date or consolidation perimeter. Those require Financial OS account registry, valuation policy and evidence review.

In-kind quantity is not automatically a reporting-currency amount. A unit-price or fair-value model must be explicit, sourced, versioned, independently reviewed and applied by Financial OS. If no defensible valuation exists, the event may remain operational/memo evidence rather than a monetary journal entry.

Default is not automatically a write-off. Cancellation is not automatically a reversal. Any impairment, write-off, restatement or reversal requires Financial OS policy and authorization.

## 5. Cross-system duplicate prevention

The local SLE service-credit database enforces unique `source_contribution_id` and `award_authorization_ref` within that database only.

Before any monetary reward or second service-credit rail is enabled, both SLE and Financial OS must atomically reserve/consume the same globally unique award ID. Required protocol:
1. Reward Engine creates a signed, immutable award authorization against an accepted contribution and approved budget.
2. A shared idempotency registry reserves the award ID once for a specific beneficiary, amount/unit and destination.
3. SLE or Financial OS consumes that reservation with compare-and-swap semantics; the other destination must reject an already-consumed award.
4. Outbox/inbox delivery is at-least-once, while consumers are idempotent by award ID and event ID.
5. Reconciliation proves one authorization maps to at most one economic reward allocation, with explicit cancellation/reversal events.

A pair of independent unique constraints in separate databases is insufficient to prevent cross-system double issuance.

## 6. Fail-closed conditions

Reject or quarantine the handoff if:
- the award authorization is missing, expired, revoked or not cryptographically authenticated;
- contribution evidence or result digest cannot be verified;
- source contribution or award ID was already consumed;
- capacity evidence is missing, stale or disputed;
- issuer or capacity is frozen/defaulted;
- event sequence/hash chain does not reconcile;
- currency/valuation/account mapping is inferred rather than policy-authorized;
- Financial OS account registry or valuation-policy digest is stale;
- accounting entry is unbalanced or evidence digest is absent.

## 7. Promotion gates

No cross-repository production adapter until:
- Financial OS PR #33 or a later canonical branch is promoted with exact-head CI and documented API stability;
- Ed25519 (or an approved equivalent) signed evidence/award envelopes are verified against a governed key registry;
- shared award reservation is implemented and concurrency-tested across both systems;
- Financial OS independently recognizes/rejects sample issue, redemption, cancellation and default events;
- end-to-end replay, reconciliation, reversal and restore tests pass;
- legal review confirms the instrument's classification and enforceability in each deployment jurisdiction.

Until then, SLE service-credit ledger remains a research reference implementation with no cash, SDU or accounting authority.
