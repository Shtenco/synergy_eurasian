# 33 — Public Investment / Budget OS / PPP

## Роль государства в EIIOM

Государство не должно финансировать весь master-plan. Его наиболее ценный капитал часто **каталитический**: снять инфраструктурный bottleneck, принять часть policy risk, стандартизировать данные/право, запустить конкурс и дать частному капиталу возможность войти.

## Public-capital functions

### 1. Common infrastructure

- grid;
- roads/rail interfaces;
- water;
- public digital infrastructure;
- schools/health for new settlements;
- research infrastructure.

### 2. First-loss / guarantee only where justified

Гарантия не должна превращать плохой проект в хороший.

```text
PublicGuaranteeValue
  < ExpectedSystemValueUnlocked
```

и budget must price contingent liability.

### 3. R&D / early TRL

Когда cashflow ещё невозможно project-finance, grant/public R&D may be rational if knowledge spillovers are large.

### 4. Standards / certification / evidence

Низкая стоимость для бюджета, большой systemic effect.

## Blockchain Budget integration

Связанный `blochain_budget` domain должен давать доказуемую цепочку:

```text
BudgetDecision
→ Appropriation
→ Commitment
→ Procurement
→ Contract
→ DeliveryEvidence
→ PaymentIntent
→ SettlementReceipt
→ AccountingRecognition
→ AuditCommitment
```

Blockchain/hash — доказательство неизменности/происхождения, не доказательство разумности закупки.

## Public Project Passport

```text
project_id
public_objective
beneficiaries
capex
public_share
private_share
contingent_liability
procurement_method
lifecycle_opex
service_KPI
construction_KPI
independent_audit
owner_after_completion
```

## Lifecycle budget

Главная ошибка infrastructure planning:

```text
CAPEX funded
OPEX forgotten
```

EIIOM requires:

```text
LifecycleFiscalCost
 = CAPEX_public
 + OPEX_public_PV
 + Maintenance_PV
 + ExpectedGuaranteeLoss
 - Tax/fee/dividend recovery where legitimate
```

## PPP decision test

PPP is useful only if risk can actually be allocated to the party able to manage it.

### Private side may better manage

- construction;
- operations;
- demand in commercially testable services;
- maintenance;
- technology procurement.

### Public side may retain

- land/public rights;
- regulatory/policy risk it controls;
- social service requirements;
- strategic network planning.

Bad PPP merely hides public debt/off-balance-sheet liabilities.

## Availability-payment PPP

For non-commercial infrastructure:

```text
Payment = ServiceAvailable * QualityFactor
```

not arbitrary guaranteed return regardless of performance.

## Revenue-risk PPP

Only where user/payment demand can be reasonably measured. Stress-test low-demand case.

## Land-value capture

For urban renovation/infrastructure:

Potential sources:

- incremental development rights;
- sale/lease of additional commercial/residential area;
- betterment/land value mechanisms where lawful;
- developer obligations;
- municipal/project bonds backed by clear revenues.

Do not book estimated land appreciation as cash before realization.

## Public procurement as demand signal

Procurement can help create a domestic supplier market, but specifications must avoid unnecessary lock-in.

```text
Problem / Performance Spec
  → competitive technical solutions
  → qualification
  → lifecycle-cost ranking
```

rather than writing a tender around one favored vendor.

## Local-content policy

Local content has value if it builds capability without making total delivered value worse beyond explicit strategic tolerance.

```text
StrategicLocalizationPremium
= accepted extra cost for resilience/learning
```

Make the premium explicit, not hidden.

## Budget multipliers

Do not use generic «1 ruble → 5 rubles GDP» claims.

Measure:

```text
PrivateCapitalMobilized / PublicCapital
ExternalCashflowUnlocked / PublicCapital
BottleneckValueUnlocked / PublicCapital
```

alongside fiscal risk.

## Catalytic-capital target

The earlier BASE-v2 illustrative funding mix allocated only a minority of the $650bn gross CAPEX to direct state/development catalytic capital. v4 does not hard-code that percentage as truth; it optimizes public support where shadow value is highest.

Examples where $1 public may unlock much more private investment:

- substation for an industrial zone;
- shared rail/road terminal;
- water treatment for a cluster;
- seed trial infrastructure;
- certification/testing lab;
- training center;
- public guarantee on a well-underwritten first-of-kind asset.

## Fiscal risk dashboard

```text
DirectPublicCAPEX
CommittedSubsidies
GuaranteesOutstanding
ExpectedGuaranteeLoss
PPPAvailabilityPaymentsPV
MaintenanceBacklog
ProjectTaxRecovery
DividendRecovery
```

## Anti-corruption / integrity design

- beneficial ownership disclosure where lawful;
- conflict-of-interest register;
- competitive procurement or explicit exception;
- immutable tender/version history;
- delivery evidence;
- price benchmark;
- related-party flag;
- independent audit;
- whistleblower/complaint channel.

## Public-investment stop gate

A politically announced project still can receive:

```text
EIIOM status = ECONOMICALLY_UNDERJUSTIFIED
```

Model does not possess legal authority to cancel it, but must not falsify the result.

## KPI

- private capital mobilized;
- project completion;
- lifecycle cost variance;
- service quality;
- contingent liabilities;
- supplier competition;
- local capability created;
- external revenue/tax base unlocked;
- audit findings;
- maintenance performance.

## Principle

> **Public money should buy public capacity or unlock productive private capacity — not merely make the total CAPEX number larger.**
