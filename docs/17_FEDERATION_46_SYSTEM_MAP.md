# 17 — SYNERGY Federation 46: единая карта системы

## Зачем этот документ

`synergy_eurasian` — productive-economy domain внутри более крупной федерации SYNERGY. Его нельзя проектировать изолированно от Financial OS, MetaPay, MIDAS, NEXUS, Data Fabric, SynergyNet, MetaChain, Business OS и household-capital слоя.

Главное правило федерации:

> **Один тип экономического факта — одна каноническая authority.**

Если несколько репозиториев начинают независимо считать NAV, settlement, authorization или evidence truth, система теряет проверяемость.

## Четыре масштаба экономики

```text
L0 PERSON / FAMILY
   income → expenses → Delta → reserve → savings/investment
                 │
                 ▼
L1 BUSINESS / PROJECT
   demand → project → capital → production → revenue
                 │
                 ▼
L2 REGION / CLUSTER
   power + water + housing + logistics + labor + industry
                 │
                 ▼
L3 EAEU / EURASIA / EXTERNAL WORLD
   cross-border trade + energy + finance + corridors + export
```

EIIOM-v4 должен уметь оптимизировать переходы между всеми четырьмя уровнями.

## Canonical authority graph

```text
HOUSEHOLD / BUSINESS DATA
        │
        ▼
synergy_app / synergychain
        │   intents / demand / Delta / business opportunities
        ▼
synergy_eurasian ───────────────┐
  Real Economy OS               │ ProjectProposal
        │                       ▼
        │               synergy_financial_os
        │                 canonical accounting
        │                       │
        │                       ▼
        │                 capital authority
        │                       │
        └──────────────► synergy_pay_system
                          execution/settlement
                                │
                                ▼
                           external world
                                │
                     SettlementEvidence
                                ▼
                        synergy_financial_os
                                │
                          HardNAV / cash
                                │
                                ▼
                        next capital cycle
```

AI/NEXUS overlays analysis but does not replace authorities.

## 45 technical repositories + master dossier

`synergy_project` is the 46th observed repository and serves as dossier/index. It has no runtime authority.

### A. Market / financial alpha lineage

1. `quantum-trading_metatrader5` — trading R&D.
2. `computer_vision_trading_metatrader_5` — visual/market features.
3. `swap_arbitrage_metatrader_5` — carry/swap research.
4. `cross_forex_arbitrage_trading_metatrader_5` — cross-FX graph research.
5. `global_liquidity_dataminer` — macro/liquidity signals.
6. `3D_bars_market_structure` — market-state representation.
7. `multi_threaded_trading_robot_with_machine_learning_python` — parallel ML lineage.
8. `midas_ai_trading_system` — large MIDAS R&D lineage.
9. `midas_lite` — compact lineage.
10. `midas_ai` — canonical MIDAS target.
11. `ai_trade_terminal` — terminal/DataHub/supervisor lineage.
12. `algotrading_graph_system` — global market graph R&D.

**Canonical economic output:** only reconciled external PnL imported into Financial OS.

### B. Money / liquidity / payment research

13. `synergy_pay_system` — MetaPay routing, compliance, execution, settlement, reconciliation.
14. `ai_financial_system` — AMM/QE/QT/MEV research.
15. `print_money_synergychain` — print-machine falsification / opportunity amplifier.
16. `synergy_graph_print_money` — live Base multigraph/HardNAV research.
17. `usds` — stable-money / reserve R&D.
18. `cashero` — token/liquidity R&D.

**Canonical economic output:** SettlementReceipt / realized external cash movement. No internal mint or LP mark is external profit.

### C. Accounting / capital / household economy

19. `synergy_financial_os` — canonical ledger, HardNAV, liabilities, liquidity, profit recognition, capital capacity.
20. `synergy_matrix_sota` — household savings/maturity/mutual-credit domain.
21. `synergy_app` — Personal Capital / AI-CFO product.
22. `sinergy_app` — legacy application placeholder.

**Canonical authority:** Financial OS for accounting; household app for user intent, never for ledger truth.

### D. Business / demand / public applications

23. `synergychain` — Business/Growth OS, CRM, demand, supplier and commercial networks.
24. `sinergy-super-app` — super-app lineage.
25. `synergychain.github.io` — public portal.
26. `shtenco.github.io` — public provenance.
27. `shtencoauantai.github.io` — public showcase.

**Key signal for Eurasian:** persistent real demand, import flows, supplier gaps, localization opportunities.

### E. Productive real economy

28. `synergy_eurasian` — Real Economy OS / EIIOM.
29. `blochain_budget` — budget/procurement evidence and public-project traceability.

**Canonical output:** ProjectProposal + physical/resource constraints + evidence requirements.

### F. Intelligence / science / bounded autonomy

30. `agi_nexus` — canonical reasoning target.
31. `agi_olga` — research lineage.
32. `agi_autopilot` — bounded action orchestration.
33. `nexus_science_agent` — evidence/falsification/science→industry pipeline.
34. `binary_quantum_theory` — scientific R&D.
35. `cold_nuclear` — materials/LENR research; experimental evidence required.
36. `ai_coder` — evidence-backed software engineering.
37. `ai_language` — semantic engineering/traceability.

**Rule:** model output is proposal/evidence hypothesis, not economic or scientific truth by itself.

### G. Data / network / compute / host

38. `ai_compress` — canonical Data Fabric codecs/archive target.
39. `qr_compress` — offline payload/evidence transport.
40. `synergynet` — P2P content/evidence transport.
41. `synergy_meta_os` — node runtime orchestration.
42. `turbo_linux` — host/kernel/virtualization R&D.
43. `motherboard_xpu_xml` — XPU/dataflow compute R&D.

**Rule:** network/compute privilege never implies financial authority.

### H. Trust / blockchain

44. `synergy_ai_blockchain` — PQ blockchain/trust commitments.
45. `synergy_metachain` — checkpointed cross-chain trust integration.

**Rule:** blockchain commits canonical bytes produced elsewhere; it does not invent NAV, settlement or project approval.

### I. Dossier

46. `synergy_project` — federation master dossier, architecture narrative, technology audit and valuation research.

## Eight canonical economic objects

Чтобы 46 репозиториев не превратились в 46 несовместимых систем, v4 фиксирует восемь объектов обмена:

```text
1. DemandSignal
2. ResourceState
3. ProjectProposal
4. CapitalAuthorization
5. PaymentIntent
6. SettlementReceipt
7. EvidencePackage
8. AccountingSnapshot
```

### DemandSignal

Источник: Business OS, households, public procurement, import statistics, external markets.

Содержит реальный наблюдаемый спрос, но не обещание будущих продаж.

### ResourceState

Источник: Real Economy OS + verified datasets.

Содержит power, grid, water, land, labor, logistics, material, compute and construction constraints.

### ProjectProposal

Источник: EIIOM.

Это предложение, а не финансирование.

### CapitalAuthorization

Источник: Financial OS + human/regulatory governance.

Устанавливает сумму, seniority, source-of-funds, covenants and expiry.

### PaymentIntent

Источник: authorized finance/business domain.

Исполняется MetaPay только после compliance/readiness.

### SettlementReceipt

Источник: MetaPay/external rails.

Доказывает, что деньги действительно переместились.

### EvidencePackage

Источник: независимые технические/операционные источники.

Доказывает физический milestone.

### AccountingSnapshot

Источник: Financial OS.

Фиксирует cash, assets, liabilities, HardNAV/LiquidNAV/EconomicNAV and distributable capacity.

## Сквозной экономический цикл

```text
DemandSignal
  ↓
EIIOM optimization
  ↓
ProjectProposal
  ↓
Underwriting
  ↓
CapitalAuthorization
  ↓
PaymentIntent
  ↓
MetaPay settlement
  ↓
construction / production
  ↓
EvidencePackage
  ↓
external sales / cashflow
  ↓
SettlementReceipt
  ↓
Financial OS recognition
  ↓
AccountingSnapshot
  ↓
new capital capacity
  ↺
```

## Самая важная граница

Вся федерация должна пройти тест:

```text
Can we trace one final unit of external cash
back to the exact project, settlement evidence,
physical production and original capital authorization?
```

Если нет — система ещё не является единой Economic OS.
