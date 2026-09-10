# 24 — Eurasian Financial Market / Settlement without premature common currency

## Principle

A deep economic union does not require starting with one currency. The more practical sequence is:

```text
common data standards
→ interoperable payments
→ transparent FX
→ cross-border settlement
→ common project-finance standards
→ portable collateral/evidence
→ deeper capital markets
→ only then evaluate whether a common monetary instrument is useful
```

## Current design assumption

EIIOM-v4 treats RUB, KZT, BYN, AMD and KGS as separate national currencies, with USD/EUR/CNY/AED and other external currencies as market interfaces.

No implicit 1:1 conversion is allowed.

## MetaPay role

`synergy_pay_system` already defines a compliance-first route graph across fiat, crypto, CBDC adapters, CEX, DEX and bridges.

For Eurasian productive economy, MetaPay should expose a narrower institutional API:

```text
QuoteRequest
FXQuote
PaymentIntent
FundingReservation
SettlementState
SettlementReceipt
ReconciliationResult
```

EIIOM consumes **settlement cost and availability**, not raw private credentials.

## FX-aware project economics

Every project has at least:

```text
CAPEX currency vector
OPEX currency vector
Revenue currency vector
Debt currency vector
```

Project cashflow in reporting currency:

```text
CF_report[t,ω] = Σ_c FX[c→report,t,ω] * CF_c[t,ω]
```

Stress scenarios must include FX moves and basis/hedging cost.

## Currency mismatch limit

```text
OpenFXExposure[p,c]
<= PolicyLimit[p,c]
```

Long-lived local-currency revenue should not casually fund large unhedged foreign-currency debt.

## Common project-finance passport

Instead of one currency, first standardize project information:

```text
ProjectID
LegalIssuer
Country
Currency
CAPEX
Debt
Equity
Seniority
Collateral
Offtake
PhysicalMilestones
CashflowWaterfall
RiskClass
AuditStandard
EvidenceHashes
```

This makes cross-border capital easier without pretending legal systems are identical.

## CFA / RWA interoperability

Potential digital rights can represent claims only if recognized by the relevant jurisdiction.

Architecture:

```text
Local legal instrument
  ↓
Canonical Economic Descriptor
  ↓
Evidence + valuation
  ↓
Cross-border investor interface where legally permitted
```

The canonical descriptor does not magically make a Russian CFA, AIFC tokenized security or another jurisdiction's instrument legally identical.

## SYNA-CAP role

If legally implemented, SYNA-CAP is best treated as a **floating capital/NAV participation layer**, not a synthetic common currency.

Possible structure:

```text
Fund/SPV eligible assets
- liabilities
= audited eligible NAV

NAV per unit = eligible NAV / units outstanding
```

Own token market capitalization is not collateral.

## Settlement asset role

A separate settlement asset, if ever used, should be:

- conservative;
- overcollateralized;
- liquidity-first;
- legally segregated;
- independently attested;
- operationally redeemable.

It should not carry the same junior project risk as SYNA-CAP.

## Legacy ALTYN reserve-token research

Earlier SYNERGY research considered a reserve-linked `ALTYN` concept backed by baskets such as gold, energy, currencies, bonds or strategic metals.

In v4 this remains **legacy research**, not a production recommendation.

Before any such instrument could be considered, it would require:

- legal issuer;
- custody;
- audited reserves;
- redemption mechanics;
- valuation policy;
- liquidity;
- sanctions/compliance analysis;
- investor protection;
- stress testing.

A commodity basket can reduce single-asset concentration but does not guarantee price stability.

## CBDC interfaces

MetaPay may define adapters for digital national currencies as they become legally/technically accessible.

Rule:

```text
AdapterExists != OperatorHasAccess
```

Production requires real contracts, participant status, credentials and legal approval.

## Cross-border netting

For groups of project companies, bilateral gross payments can create unnecessary liquidity demand.

A legal/operational netting layer may calculate:

```text
NetPosition_i = Receivables_i - Payables_i
```

and reduce settlement volume, but only where obligations are legally eligible for netting and settlement finality is clear.

## DvP / PvP

For asset/currency exchange:

- Delivery-versus-Payment for securities/assets;
- Payment-versus-Payment for FX where infrastructure supports it.

Goal: reduce principal risk, not merely speed up transactions.

## Trade finance

EIIOM project chains need:

- letters/guarantees where available;
- receivables finance;
- purchase-order finance;
- inventory finance;
- export credit;
- supplier finance;
- insurance.

These can unlock more industrial CAPEX than a new speculative token.

## Common financial-market objective

The correct KPI is not number of tokens. It is:

```text
CrossBorderCost↓
SettlementTime↓
FailedSettlement↓
FXRisk↓
ProjectFundingDepth↑
EligibleCollateralMobility↑
ExternalInvestment↑
```

## Hard boundary

`synergy_eurasian` can estimate required settlement flows and project currencies, but Financial OS/MetaPay and regulated institutions retain execution/accounting authority.
