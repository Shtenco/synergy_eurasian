# 27 — Reality Baseline 2026: что уже существует вокруг EIIOM

**Дата среза: 2026-09-11.**

Этот документ отделяет реальный внешний baseline от нашей архитектуры и сценарных целей.

---

## 1. ЕАЭС — уже крупный общий экономический контур

Официальные материалы Евразийской экономической комиссии показывают, что к 2024 году объём взаимной торговли товарами в ЕАЭС приблизился к **$100 млрд**, практически удвоившись относительно 2015 года. Доля взаимной торговли во внешнеторговом обороте Союза выросла с 13.5% в 2015 году до **19.8% в 2024 году**.

Источник:

- https://eec.eaeunion.org/en/news/obrashchenie-predseda?PAGEN_1=62&visually_impaired=yes

Статус: `EXTERNAL_FACT`.

### Вывод для EIIOM

У нас не нулевой рынок. Уже существует значительный внутренний поток товаров, который можно использовать для:

- выявления persistent demand;
- поиска импортозависимых цепочек;
- supplier-network modelling;
- localization candidates;
- cross-border project pipelines.

---

## 2. У ЕАЭС уже есть формальный горизонт 2030/2045

ЕЭК сообщает, что Совет Комиссии утвердил дорожную карту реализации Декларации о дальнейшем развитии экономических процессов в ЕАЭС до 2030 года и на период до 2045 года — «Евразийский экономический путь».

Источник:

- https://eec.eaeunion.org/upload/medialibrary/564/tbfrz98itikq8l0iyyykxo1bjj611tkc/EEC_CUSTOMS-COOPERATION.pdf

Статус: `EXTERNAL_FACT`.

### Вывод

EIIOM-2045 не должен позиционироваться как альтернативная политическая программа. Он может быть **техническим цифровым master-plan layer**, который помогает выбирать проекты внутри уже существующего горизонта экономической интеграции.

---

## 3. Евразийский транспортный каркас уже огромен

Евразийский банк развития по состоянию на **1 июля 2026 года** включает в Обсерваторию Евразийского транспортного каркаса:

- **402** реализуемых и планируемых транспортных проекта;
- совокупный инвестиционный объём около **$345 млрд**;
- ещё около **$100 млрд** проектов, которые предстоит запустить;
- 123 из 402 проектов предполагают участие частного бизнеса;
- 27 проектов реализуются или рассматриваются как PPP;
- железные дороги — 42.8% портфеля по стоимости;
- Central Asia — 114 проектов более чем на $71.75 млрд;
- Казахстан — более 45% транспортных инвестиций Центральной Азии;
- Northern Eurasian Corridor — около $84.8 млрд;
- INSTC — около $52.8 млрд без отдельного Moscow–St Petersburg HSR;
- TRACECA / Middle Corridor — около $42.8 млрд вложений в Central Asian portfolio.

Источники:

- https://eabr.org/en/press/detail/edb-updates-the-eurasian-transport-network-402-projects-worth-345-billion-with-another-100-billion-i/
- https://eabr.org/analytics/special-reports/transport-corridors-infrastructure/

Статус: `EXTERNAL_FACT`.

### Вывод

Новая пространственная модель должна **импортировать ETN projects как реальные nodes/edges**, а не создавать synthetic logistics cost из одного среднего коэффициента.

---

## 4. Казахстан уже превращается в ключевой цифрово-логистический узел

В десятилетнем обзоре ЕАЭС указано, что взаимная торговля Казахстана с государствами Союза выросла с $16.3 млрд в 2015 году до **$30.4 млрд в 2024 году**, а экспорт Казахстана в ЕАЭС — с $5.1 млрд до $11.0 млрд.

Источник:

- https://eec.eaeunion.org/upload/iblock/69c/mutq450gxmmn90861uvhvu1t98xedekl/EAEU-over-10-Years-oct-2025.pdf

Статус: `EXTERNAL_FACT`.

Кроме того, ЕАБР в 2026 году сопровождает проекты в Казахстане по энергетике, irrigation, складской и транспортно-логистической инфраструктуре.

Источник:

- https://eabr.org/en/about/country/kazakhstan/news/

### Вывод

Казахстан в EIIOM должен моделироваться не только как источник сырья, а как сочетание:

```text
materials
+ agriculture
+ logistics
+ power
+ data/compute
+ cross-border trade
```

---

## 5. Общий рынок электроэнергии — отдельный будущий economic edge

Актуальные материалы ЕЭК 2025–2026 указывают ориентир запуска общего электроэнергетического рынка после вступления необходимых правил в силу, с целевым горизонтом **начала 2027 года**.

Источник:

- https://eec.eaeunion.org/upload/medialibrary/b43/tmyrd1y1oxxbzdj6gn3nmgfwnzqy9pg4/TSUR-angliyskiy.pdf

Статус: `EXTERNAL_POLICY_TIMELINE`, требующий обновления перед practical deployment.

### Вывод

EIIOM-v4 должен моделировать два режима:

```text
PRE_COMMON_MARKET
POST_COMMON_MARKET
```

с разными доступными power-trade edges, congestion policy и settlement assumptions.

---

## 6. Интеграция уже включает промышленную кооперацию

Стратегические документы ЕАЭС предусматривают развитие совместных high-tech проектов, научно-технологических программ, инфраструктурных инициатив и механизмов поддержки промышленной кооперации.

Источники:

- https://eec.eaeunion.org/upload/medialibrary/820/Strategy_2025.pdf
- https://eec.eaeunion.org/upload/files/dobd/%D0%94%D0%BE%D0%BA%D0%BB%D0%B0%D0%B4%20%D0%B8%D0%BD%D0%B2%D0%B5%D1%81%D1%82%D0%BA%D0%BB%D0%B8%D0%BC%D0%B0%D1%82%20%D0%BD%D0%B0%20%D0%B0%D0%BD.%20%D1%8F%D0%B7..pdf

Статус: `EXTERNAL_FACT / POLICY`.

### Вывод

Для EIIOM не нужно изобретать отдельную «евразийскую инвестиционную реальность» поверх существующих институтов. Нужно создать **machine-readable project/evidence layer**, который способен подключаться к:

- EDB;
- national development institutions;
- PPP;
- industrial cooperation mechanisms;
- private equity/debt;
- project bonds/CFA/RWA where lawful;
- export-credit and vendor finance.

---

## 7. Что этот baseline НЕ доказывает

Он не доказывает:

- что $650 млрд EIIOM BASE обязательно нужно потратить;
- что каждый текущий инфраструктурный проект эффективен;
- что общий рынок электроэнергии заработает строго по текущему timetable;
- что SYNERGY получит доступ к государственным программам;
- что MIDAS/MetaPay принесут стабильную прибыль;
- что Productive Escrow будет разрешён регуляторами;
- что любая токенизация автоматически привлечёт внешний капитал;
- что страна с ресурсом имеет локальную инфраструктуру для его глубокой переработки.

---

## 8. Три слоя данных

EIIOM-v4 должен хранить:

### Observed

```text
actual production
actual trade
actual installed capacity
actual infrastructure
actual prices
actual labor
actual logistics
actual laws
```

### Committed / Under Construction

```text
projects with real financing/FID/construction evidence
```

### Planned / Scenario

```text
announced projects
policy targets
EIIOM candidate projects
research assumptions
```

Никогда не складывать три категории как одинаково существующую мощность.

---

## 9. Confidence model

Каждый baseline object:

```text
value
unit
as_of
source
source_class
observed_or_planned
confidence
last_verified
```

Recommended confidence classes:

```text
A — audited / regulator / operational meter/ledger
B — official statistical / institutional source
C — company/project announcement
D — secondary estimate
E — internal model assumption
```

---

## 10. Главный вывод

Евразия уже строит транспортную, энергетическую и торговую инфраструктуру на масштабе **сотен миллиардов долларов**. Поэтому миссия EIIOM не в том, чтобы заменить эти проекты собственной красивой цифрой.

Миссия:

> **связать существующие и новые проекты одним input-output графом, найти реальные bottlenecks и направить следующий капитал туда, где он создаёт максимальную проверяемую производительную ценность.**
