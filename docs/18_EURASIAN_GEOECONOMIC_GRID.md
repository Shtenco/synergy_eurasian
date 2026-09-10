# 18 — Eurasian Geoeconomic Grid: от пяти стран к сети континента

## Идея

ЕАЭС — ядро EIIOM, но реальная экономика не заканчивается на таможенной границе Союза. Производительный проект имеет смысл только если его сырьё, энергия, оборудование, кадры и конечный товар могут физически и юридически пройти по маршруту.

Поэтому v4 добавляет отдельный **Geoeconomic Network Layer**.

```text
EAEU Core
  ↕
Central Asia
  ↕
China / East Asia
  ↕
Caspian / Caucasus / Türkiye
  ↕
Iran / Persian Gulf / India
  ↕
Europe / external western markets where legally accessible
```

Это не политический союз. Это граф экономических коридоров.

## Актуальный инфраструктурный baseline 2026

Евразийский банк развития по состоянию на 1 июля 2026 года учитывает в Обсерватории Евразийского транспортного каркаса **402 реализуемых и планируемых проекта общей стоимостью около $345 млрд**, плюс ещё около $100 млрд проектов в перспективном pipeline.

Источник:

- https://eabr.org/en/press/detail/edb-updates-the-eurasian-transport-network-402-projects-worth-345-billion-with-another-100-billion-i/
- https://eabr.org/analytics/special-reports/transport-corridors-infrastructure/

В Центральной Азии — 114 проектов более чем на $71.75 млрд; Казахстан формирует более 45% объёма инвестиций региона. Железные дороги — крупнейший класс по всей Евразийской сети; в Центральной Азии особенно велик road + Middle Corridor pipeline.

**Вывод для EIIOM:** транспорт не надо моделировать как один коэффициент `Logistics`. Нужно импортировать реальные инфраструктурные проекты как network edges с датой ввода, capacity и CAPEX.

## Главные corridor families

### C1 — Northern Eurasian Corridor

Функция:

- восток ↔ запад;
- крупные индустриальные и контейнерные потоки;
- связь российских промышленных кластеров с азиатскими рынками.

EDB оценивает текущий portfolio Northern Eurasian Corridor примерно в $84.8 млрд.

### C2 — International North–South Transport Corridor

Функция:

```text
Russia / Belarus / EAEU
  ↓
Caspian / Caucasus / Kazakhstan-Turkmenistan axes
  ↓
Iran
  ↓
Persian Gulf / India
```

EDB оценивает развитие INSTC примерно в $52.8 млрд без отдельных крупных HSR-проектов.

Для SYNERGY особенно важны:

- зерно;
- металлы;
- химия;
- оборудование;
- food processing;
- контейнеры;
- экспорт высокотехнологичного оборудования.

### C3 — Trans-Caspian / Middle Corridor

```text
China / Kazakhstan
  ↓
Caspian
  ↓
Azerbaijan / Georgia
  ↓
Türkiye / Europe
```

Это дополнительный маршрут диверсификации, а не замена всем остальным коридорам.

### C4 — China–Kyrgyzstan–Uzbekistan and Central Asian connectors

Для Кыргызстана и южного слоя сети этот corridor превращает страну из тупикового узла в транзитный/производственный bridge.

### C5 — Air / high-value logistics

Высокая ценность на килограмм:

- electronics;
- precision equipment;
- pharma/biotech where legal and validated;
- seed genetics;
- urgent components;
- high-value food.

### C6 — Digital corridor

Данные и услуги также имеют географию:

- fiber routes;
- IXPs;
- cloud regions;
- data sovereignty;
- latency;
- cross-border data rules;
- compute capacity.

SynergyNet может стать overlay, но не заменяет физическую international fiber infrastructure.

## Common electricity market as economic edge

ЕЭК указывает, что запуск общего рынка электроэнергии ЕАЭС планируется после вступления всех правил в силу; актуальные материалы 2025–2026 ориентируются на **начало 2027 года**.

Источник:

- https://eec.eaeunion.org/upload/medialibrary/b43/tmyrd1y1oxxbzdj6gn3nmgfwnzqy9pg4/TSUR-angliyskiy.pdf

Для EIIOM это означает будущий отдельный тип edge:

```text
POWER_TRADE_EDGE[country_i, country_j, hour]
```

с ограничениями:

- interstate transfer capacity;
- market rules;
- congestion;
- losses;
- price zones;
- availability;
- national reliability constraints.

Нельзя просто считать всю генерацию ЕАЭС одной общей электростанцией.

## Industrial cooperation as graph, not slogan

В ЕАЭС уже существует механизм поддержки кооперационных промышленных проектов, а долгосрочные документы интеграции предусматривают совместные high-tech projects, научно-технологические программы и инфраструктурные консорциумы.

Источники:

- https://eec.eaeunion.org/upload/medialibrary/820/Strategy_2025.pdf
- https://eec.eaeunion.org/upload/files/dobd/%D0%94%D0%BE%D0%BA%D0%BB%D0%B0%D0%B4%20%D0%B8%D0%BD%D0%B2%D0%B5%D1%81%D1%82%D0%BA%D0%BB%D0%B8%D0%BC%D0%B0%D1%82%20%D0%BD%D0%B0%20%D0%B0%D0%BD.%20%D1%8F%D0%B7..pdf

EIIOM должен использовать это как реальный financing/regulatory constraint: проект получает евразийский bonus только если действительно создаёт cross-border value chain, а не просто имеет слово «Евразийский» в названии.

## Внешние интерфейсы

### China / East Asia Interface

Назначение:

- equipment/components;
- export markets;
- logistics;
- technology partnerships where legally possible;
- compute supply chains;
- machinery and manufacturing cooperation.

### India / Gulf Interface

Назначение:

- food;
- fertilizers/materials;
- energy/industrial services;
- capital;
- North–South corridor demand.

### BRICS+ Interface

Не отдельная «валюта из воздуха», а interoperability layer:

- trade finance;
- FX routing;
- local-currency settlement where available;
- project co-investment;
- standards/data exchange;
- logistics.

### Western Interface

Должен моделироваться **только как legally accessible external market**, с sanctions/compliance/counterparty gates. Никакой оптимизатор не имеет права считать недоступный corridor доступным только ради лучшего NPV.

В долгосрочном peace/normalization scenario может существовать дополнительный western logistics/market bridge, включая украинскую инфраструктуру как потенциальный транспортно-финансовый интерфейс между ЕС, ЕАЭС и другими рынками. Это **сценарная гипотеза**, не current-base assumption.

## Network representation

Каждый corridor edge:

```text
edge_id
origin_node
destination_node
mode
commodity_classes
capacity_per_year
transit_time
variable_cost
fixed_cost
border_time
reliability
legal_access
sanctions/compliance_state
carbon/energy_cost
planned_upgrade_date
capex
source
confidence
```

## Project value with logistics

Вместо:

```text
ProjectNPV = Revenue - OPEX - CAPEX
```

использовать:

```text
DeliveredMargin =
    ExternalSalePrice
  - ProductionCost
  - FinancingCost
  - TransportCost
  - Border/CustomsCost
  - InventoryTimeCost
  - Insurance
  - FXHedge
  - ComplianceCost
  - ExpectedDisruptionLoss
```

И только затем сравнивать проекты.

## Geoeconomic objective

EIIOM-v4 должен искать не минимальный километр пути, а **максимальный устойчивый delivered economic surplus**.

Это автоматически даёт ценность нескольким параллельным коридорам: redundancy имеет экономическую стоимость даже если резервный маршрут чуть дороже.
