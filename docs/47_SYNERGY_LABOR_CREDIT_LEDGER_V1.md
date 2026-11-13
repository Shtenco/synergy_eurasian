# 47 — SYNERGY Labor Credit Ledger V1

**Status:** research reference kernel; not a currency, deposit, payroll system, regulated credit product or production payment rail.

## 1. Instrument definition

V1 LABOR CREDIT is a claim to a named, measurable good or service from one identified issuer. It is denominated only in the deliverable's unit (for example, `service-hour`, `kg`, or `repair-job`). It has no currency field, no assumed SDU exchange rate and no automatic cash value.

The issuer's obligation is matched one-for-one by the holder's remaining claim. The ledger records the operational obligation; it does not make the claim legally enforceable or book a financial liability. Financial OS remains the sole authority for accounting recognition.

## 2. Issuance conditions

An issuer must have a registered policy for the exact `(issuer, service_code, unit)` tuple. The policy defines a maximum aggregate outstanding amount. Before issuance:
- a unique capacity lot must exist for that issuer, service and unit;
- capacity evidence digest must be unique in this ledger;
- capacity must be open and independently reviewed by a named verifier;
- the requested quantity must not exceed unreserved and unfulfilled capacity;
- aggregate outstanding claims, including overdue and defaulted claims, must remain at or below the issuer cap;
- the issuer must not be frozen.

The reference kernel checks declared evidence metadata only. It does not fetch capacity evidence, authenticate the verifier or cryptographically verify a signature. A trusted evidence-verification adapter is a production prerequisite.

## 3. Capacity conservation

For each capacity lot:

`available = total - reserved - fulfilled`

`reserved >= outstanding claims backed by that lot`

Issuance moves quantity from available to reserved. Redemption moves quantity from reserved to fulfilled. Bilateral cancellation releases only the unfulfilled reserved quantity. Fulfilled capacity is never recycled.

A capacity evidence SHA-256 digest is globally unique within this ledger to prevent the same declared evidence object being registered as multiple lots. This does not prove that distinct evidence documents do not describe the same physical asset or service capacity; semantic asset identity checks remain necessary.

## 4. Claim lifecycle

- `ACTIVE`: transferable by current holder; redeemable.
- `OVERDUE`: past due; not transferable; remains redeemable if issuer can perform.
- `DEFAULTED`: declared after overdue; issuer is frozen for all new issuance; claim and reserved capacity remain outstanding. Default does not erase the obligation or free capacity.
- `SETTLED`: remaining quantity is zero after fulfilment.
- `CANCELLED`: both parties supplied approval references; unfulfilled remainder is released. Already fulfilled quantity remains fulfilled.

A defaulted claim cannot be redeemed or transferred in V1. No automatic write-off, debt forgiveness, reserve draw, cash settlement or re-issuance is implied. Recovery, dispute, hardship and restructuring are later explicit workflows.

## 5. Concurrency, idempotency and audit

SQLite `BEGIN IMMEDIATE` serializes state-changing commands. Each command requires a unique idempotency key; replays with the same request return the original result, while key reuse with a different request is rejected. Credit mutations use optimistic `version` checks to reject stale transfer/redemption/cancellation attempts.

Every successful state transition appends a canonical event with a SHA-256 hash chained to its predecessor. Event rows have update/delete guards. `verify_event_chain()` detects gaps, altered event fields and broken links.

The hash chain is tamper-evident, not tamper-proof: an administrator able to rewrite the entire database can recompute the chain. Production needs signed checkpoints anchored outside the database, authenticated actor identities, key rotation and independent backups. The mutable projection tables are not yet reconstructed from the event log; production recovery must add deterministic replay and projection reconciliation before this kernel can be treated as an authoritative ledger.

## 6. Financial firewall and V6.6 boundary

- No SDU mint, cash transfer, interest, wage calculation, loan origination or payment execution.
- No conversion of LABOR SCORE into a credit amount. The score is evidence/measurement, not a pricing oracle.
- No automatic collateral or NAV recognition.
- No parallel cash reserve is created.
- The service-credit ledger is distinct from V6.6 monetary mutual credit: it tracks in-kind/service performance claims, not buyer/seller cash payables, bank lines or reserve-backed cash settlement.
- Any future bridge to V6.6 must use an explicit adapter and preserve its member limits, reserve ceilings, cumulative contribution caps, cash conservation and default waterfall. The current main branch does not expose a validated production CreditLedger integration surface, so V1 deliberately does not import the research-branch V6.6 module.
- Financial OS must review and recognize any accounting obligation; payment system may act only on separately authorized settlement instructions.

## 7. Implemented reference API

`src/synergy_labor_credit_ledger.py` implements:
- issuer policy registration;
- capacity lot registration;
- issue, transfer, partial/full redeem;
- overdue and default state transitions;
- bilateral cancellation of unfulfilled quantity;
- persistent SQLite transactions, idempotency and event-chain verification.

Focused adversarial tests cover issuer/capacity ceilings, duplicate requests, stale versions, wrong-holder actions, capacity evidence reuse, persistence, tamper detection, default freeze and concurrent issuance.

## 8. Known limitations / next gates

1. Evidence references and approval references are metadata, not cryptographically authenticated credentials.
2. Capacity lots can still double-count the same real-world asset if distinct hashes are supplied; require canonical asset IDs, independent valuation/inspection and cross-lot reservation.
3. No dispute/appeal, restructuring, recovery or default resolution lifecycle yet.
4. No independent event-log replay into projections yet.
5. SQLite is a single-node reference store, not a federated consensus ledger.
6. No jurisdiction-specific legal classification or enforceability assessment is claimed.

Before production: implement signed evidence envelopes, actor authorization, canonical asset identity, event replay/reconciliation, dispute/restructuring controls, independent audit and legal review. Do not enable transferability or external exchange until these gates are satisfied.
