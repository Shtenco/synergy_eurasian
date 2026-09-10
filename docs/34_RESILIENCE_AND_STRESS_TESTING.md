# 34 — Resilience & Stress Testing: система должна переживать плохой мир

## Почему средний сценарий недостаточен

Большой интегрированный проект опасно оптимизировать только по `Expected NPV`. Чем больше взаимосвязей, тем больше риск каскада.

Поэтому v4 оптимизирует не только эффективность, но и **survivability**.

## Stress universe

### Financial

- WACC +500/+1000 bps;
- credit market freeze;
- FX devaluation/appreciation;
- refinancing unavailable;
- commodity price collapse;
- external investor outflow;
- MIDAS drawdown;
- MetaPay route disappearance.

### Physical

- transformer shortage;
- power deficit;
- multi-week grid outage;
- accelerator shortage;
- spare-parts disruption;
- rail/road corridor closure;
- port/terminal disruption;
- construction-material shortage.

### Agricultural / climate

- drought;
- flood;
- disease/pest shock;
- seed/import disruption;
- fertilizer/input price shock;
- water allocation reduction.

### Digital/security

- data-center outage;
- cloud/provider loss;
- compromised software supply chain;
- P2P partition;
- bridge failure;
- key compromise;
- ransomware/industrial control incident.

### Social

- labor shortage;
- construction workforce migration;
- household income shock;
- housing program rejection;
- local opposition;
- skill pipeline under-delivery.

## Cascade graph

Stress does not occur independently.

Example:

```text
FX shock
→ imported accelerator CAPEX↑
→ DC commissioning delay
→ AI cloud capacity↓
→ industrial AI rollout↓
→ productivity gains delayed
→ project cashflow↓
→ DSCR↓
→ financing capacity↓
```

EIIOM must simulate connected consequences.

## Essential-service priority

During shortage:

```text
life/safety critical
→ grid/water/heat/health
→ essential food/logistics
→ critical industry
→ contracted commercial
→ flexible compute
```

Exact policy belongs to authorities; model must expose tradeoffs.

## Redundancy value

A second supplier/corridor can have negative standalone NPV but positive resilience option value.

```text
ResilienceOptionValue
 = ExpectedLoss_without_backup
 - ExpectedLoss_with_backup
 - Cost_of_backup
```

If positive, redundancy is economically rational.

## Concentration caps

Track:

- single-country;
- single-region;
- single-grid-node;
- single-vendor;
- single-corridor;
- single-currency;
- single-customer;
- single-model/provider;
- single-custodian/bridge.

Caps vary by criticality.

## Minimum liquidity runway

For project/system:

```text
LiquidityRunwayMonths
 = UnencumberedLiquidAssets / StressedMonthlyCashBurn
```

Critical infrastructure requires explicit runway/reserve policy.

## Debt stress

```text
DSCR_base
DSCR_downside
DSCR_severe
```

Do not approve long-lived project based solely on base DSCR.

## Household stress

Retail contribution system must degrade safely:

```text
income -20%
→ auto contribution reduced/paused
→ reserve preserved
```

System funding cannot assume households will continue investing through unemployment or emergency.

## Financial engines stress

### MIDAS

Assume periods of:

- zero alpha;
- drawdown;
- liquidity stress;
- model failure.

System must remain solvent without trading profit.

### MetaPay / arbitrage

Assume spread disappears to zero. Arbitrage is option/upside, not base funding obligation.

### Print-machine research

Assume external PnL = 0 and internal token values collapse. No core project must fail because synthetic marks vanish.

## Bridge / chain stress

If external bridge quarantined:

```text
affected_chain_liquidity frozen
but unrelated chain/project reserves remain isolated
```

Avoid one omnipotent bridge reserve.

## Data stress

If data are stale or conflicting:

```text
confidence↓
new authorization blocked or reduced
```

Missing evidence must not default to success.

## Model-risk ensemble

Run multiple model families/parameter sets:

- optimistic coefficients;
- conservative coefficients;
- historical analogs;
- expert assumptions;
- adversarial assumptions.

Report distribution, not one magic objective.

## CVaR

For loss random variable `L`:

```text
CVaR_α = E[L | L >= VaR_α]
```

Portfolio objective can penalize tail:

```text
ExpectedValue - λ * CVaR_95
```

## Recovery planning

Every critical service/project has:

```text
RTO — recovery time objective
RPO — recovery point objective
manual fallback
supplier fallback
cash/liquidity fallback
communications fallback
```

## Antifragility candidate

Some systems improve after shocks by learning/reallocation.

Example:

```text
corridor disruption
→ actual disruption-cost data
→ EIIOM updates reliability
→ future portfolios diversify earlier
```

Do not call a system antifragile merely because it survived once.

## Kill conditions

System-level stop conditions:

- accounting conservation breach;
- unresolved double collateral;
- reserve coverage below hard minimum;
- project evidence fraud;
- unauthorized financial authority escalation;
- systemic cyber compromise;
- model data provenance failure.

## Quarterly war game

At least quarterly in mature system:

1. choose severe scenario;
2. freeze one or more critical nodes;
3. run economic/network response;
4. compare to contingency plan;
5. record failures;
6. update model and operational runbooks.

## Ultimate criterion

> **The best Eurasian portfolio is not the one that looks richest in the base case; it is the one that continues producing essential value and remains solvent when several assumptions fail together.**
