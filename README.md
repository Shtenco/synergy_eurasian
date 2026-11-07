<div align="center">

<img src="assets/readme/hero.svg" alt="SYNERGY EURASIAN — евразийская производственная система EIIOM-2045" width="100%" />

<br />

**Евразийская интеллектуально-производственная система**

От наблюдаемого спроса и семейного капитала — к энергии, материалам, технологиям, предприятиям, экспорту и проверяемым денежным результатам.

<br />

![Status](https://img.shields.io/badge/EIIOM--v2-RESEARCH%20SOLVER-25d7bc?style=for-the-badge)
![Status](https://img.shields.io/badge/EIIOM--v4-SPEC%20READY-57bfff?style=for-the-badge)
![Status](https://img.shields.io/badge/DATASET--v4-CALIBRATION%20PENDING-f9c873?style=for-the-badge)
![License](https://img.shields.io/badge/LICENSE-PROPRIETARY-a2aec8?style=for-the-badge)

[Архитектура](#архитектура-системы) · [Страны ЕАЭС](#пять-стран-одна-производственная-сеть) · [EIIOM](#оптимизатор-eiiom-экономический-компилятор) · [Project Factory](#project-factory-проектный-конвейер) · [Финансы](#финансовая-архитектура-и-капитал) · [Доказательность](#научный-статус-и-границы-достоверности) · [Запуск](#быстрый-запуск)

</div>

> **Статус проекта.** EIIOM-v2 — исполняемый исследовательский LP-оптимизатор. EIIOM-v4 — подробно определённая архитектура пространственной стохастической оптимизации, для которой ещё требуются данные, реализация и независимые испытания. Численные результаты ниже относятся к **сценарию**, а не к построенным активам, привлечённым инвестициям или заработанной прибыли.

---

## Что такое SYNERGY EURASIAN

**SYNERGY EURASIAN / Real Economy OS** — исследовательская архитектура экономического планирования и проектного управления в пространстве пяти стран ЕАЭС: **России, Казахстана, Беларуси, Армении и Кыргызстана**. Система задумывается как связующее звено между спросом, реальными ресурсами, производственными цепочками, инвестиционными решениями, подтверждёнными результатами и повторным накоплением капитала.

Её задача — не объявить отдельные отрасли приоритетными, а вычислить, **какие проекты, в каком месте, в какой последовательности и при каких ограничениях** могут создавать проверяемый экономический результат. Подход объединяет промышленную и инфраструктурную экономику, вычислительные мощности, агробиотехнологии, цифровые сервисы, кадровый потенциал и финансовую дисциплину.

<img src="assets/readme/economy-loop.svg" width="100%" alt="Замкнутый цикл от спроса и ресурсов через EIIOM и проекты к реальным активам, расчётам и повторным инвестициям" />

### Четыре масштаба одного проекта

| Масштаб | Цель | Что учитывается |
|:--|:--|:--|
| **L0 · Человек и семья** | Финансовая устойчивость и рост человеческого капитала | Доход, расходы, долги, резерв, образование, добровольные инвестиции |
| **L1 · Предприятие и проект** | Экономически жизнеспособная деятельность | Покупатели, мощности, себестоимость, CAPEX, OPEX, денежный поток |
| **L2 · Регион и кластер** | Развитие связанных производственных цепочек | Электросети, вода, кадры, жильё, логистика, поставщики |
| **L3 · ЕАЭС и внешний рынок** | Кооперация и внешняя покупательная способность | Международная торговля, FX, экспорт, коридоры, санкционные и правовые ограничения |

Подробно: [контекст и цели](docs/00_CONTEXT_AND_VISION.md) · [архитектура](docs/01_SYSTEM_ARCHITECTURE.md) · [Grand Strategy 2045](docs/36_GRAND_STRATEGY_2045.md).

---

## Архитектура системы

Центр EURASIAN — **EIIOM (Eurasian Intelligent Industrial Optimization Model)**, который получает наблюдаемые факты и проектные предложения, строит варианты инвестирования и передаёт их на отдельные стадии проверок. Он **не авторизует денежную эмиссию, платежи или ценные бумаги**.

<img src="assets/readme/eiiom-compiler.svg" width="100%" alt="EIIOM-v2 LP, EIIOM-v4 MILP и DATASET-v4 — сопоставление готовности архитектур" />

**Архитектурное разделение полномочий:**

```text
Наблюдаемый спрос + реальные ресурсы + проекты + ограничения
                         │
                         ▼
                  EIIOM / Real Economy OS
             ProjectProposal + physical evidence
                         │
                         ▼
             Технический и экономический аудит
                         │
                         ▼
                  Financial OS
        CapitalAuthorization / лимиты и учёт
                         │
                         ▼
                 Payment / Settlement
                SettlementReceipt
                         │
                         ▼
              Независимые EvidencePackage
                         │
                         ▼
             Реальные активы + продажи + HardNAV
```

Интерфейсы закреплены в [`interfaces/`](interfaces), включая [`project_proposal.schema.json`](interfaces/project_proposal.schema.json), [`resource_state.schema.json`](interfaces/resource_state.schema.json), [`demand_signal.schema.json`](interfaces/demand_signal.schema.json) и [`evidence_package.schema.json`](interfaces/evidence_package.schema.json). Ролевое распределение всей экосистемы — в [`config/federation_v4.json`](config/federation_v4.json).

---

## Пять стран — одна производственная сеть

<img src="assets/readme/five-countries.svg" width="100%" alt="Гипотезы промышленной специализации России, Казахстана, Беларуси, Армении и Кыргызстана" />

Система должна выявлять наиболее жизнеспособное размещение предприятий с учётом фактических ставок, кадров, материалов, энергообеспечения, таможенных и логистических издержек. Страновые специализации — **гипотезы**, а не жёстко заданная модель разделения труда.

**Пример:** переработка сырья в Казахстане может быть связана с оборудованием из Беларуси, энергетикой и промышленным спросом России, инженерными решениями из Армении и транзитными маршрутами Кыргызстана. Выбор такой цепочки требует доказательств качества, цены, логистики и реального покупателя; географическая близость сама по себе не означает рентабельность.

Документы: [экономическая карта](docs/18_EURASIAN_GEOECONOMIC_GRID.md) · [страновые портфели](docs/37_COUNTRY_PORTFOLIOS.md) · [статистическая база](docs/27_REALITY_BASELINE_2026.md).

---

## Семь промышленных суперцепочек

В экономике важна не отдельная фабрика, а её **роль в целой системе ресурсов, оборудования, услуг и конечного спроса**. Электростанция без сети, завод без инженеров, ЦОД без контрактных нагрузок, агропроизводство без хранилищ или логистики — потенциально недоиспользованный капитал.

<img src="assets/readme/seven-superchains.svg" width="100%" alt="Семь производственных цепочек: энергия, материалы, вычисления, агро, жильё, экспорт и наука" />

**Полная отраслево-производственная карта** содержит 35 направлений: энергетика и сети, критические и специальные материалы, станки, робототехника, промышленный ИИ, дата-центры, электроника, агрогенетика, сельское хозяйство, водные системы, городское обновление, логистика, научная коммерциализация, оборотный капитал малого бизнеса и другие. Это не означает, что по всем направлениям уже существуют предприятия или готовые оптимизационные модели.

См. [35 производственных направлений](docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md) и [архетипы проектов](docs/12_PROJECT_ARCHETYPES.md).

---

## Оптимизатор EIIOM: экономический компилятор

### EIIOM-v2 — воспроизводимый линейный оптимизатор

Исполняемая реализация [`src/eiiom_optimizer.py`](src/eiiom_optimizer.py) использует `scipy.optimize.linprog` и набор жёстких ограничений. Рассматриваются **5 стран × 24 отрасли × 3 временных этапа = 360 переменных распределения капитала**.

В модели учитываются бюджет по этапам, лимиты концентрации, энергетика, передача мощности, ЦОД и compute, цепочки отдельных промышленных технологий, сельскохозяйственные и жилищные целевые показатели. Величины по странам и секторам из [`config/base_scenario.json`](config/base_scenario.json) являются **исследовательскими коэффициентами**, если отдельно не приведён внешний источник.

### BASE-v2 — пример расчётного сценария

<img src="assets/readme/base-v2-scenario.svg" width="100%" alt="Сценарное распределение 650 млрд долларов CAPEX по этапам 2026–2045 и пяти странам, не фактические инвестиции" />

| Показатель модели | Референсное значение | Значение показателя |
|:--|--:|:--|
| Суммарный плановый CAPEX 2026–2045 | **$650 млрд** | Сценарный бюджет, **не привлечённые инвестиции** |
| 2026–2030 / 2031–2040 / 2041–2045 | $120 / $290 / $240 млрд | Сценарное распределение |
| Годовой *GVA-equivalent* в 2045 | **$160,8 млрд/год** | Целевая функция / модельный эквивалент, **не официальный ВВП** |
| Модельный compute IT | ≈1 496 МВт | Не существующие мощности проекта |
| Модернизация городской недвижимости | 100 млн м² | Заложенный сценарный ориентир |
| Точное земледелие | 60 млн га | Заложенный сценарный ориентир |
| Rural AI clusters | 160 | Заложенный сценарный ориентир |

Источник приведённых сценарных величин: [`data/base_v2_reference_summary.json`](data/base_v2_reference_summary.json). Они **не являются прогнозом гарантированной доходности, активами на балансе, выручкой или реализованной добавленной стоимостью**.

### EIIOM-v4 — следующий класс задачи

[`EIIOM-v4 Stochastic Spatial MILP`](docs/23_EIIOM_V4_STOCHASTIC_MILP.md) должен принимать решения о запуске конкретных объектов, расширении мощностей и движении товаров в пространстве с учётом сценариев будущего, риска, задержек строительства, технических зависимостей и неполной информации.

Основные обозначения:

```text
BUILD[p,t]      — решение запустить проект p к моменту t
CAPADD[p,t]     — прирост доступной производственной мощности
FLOW[k,e,t,ω]   — движение товара k по маршруту e при сценарии ω
PROD[p,k,t,ω]   — физический выпуск предприятия
INV[k,n,t,ω]    — запасы на физическом узле
HH_INVEST[h,p,t] — допустимые инвестиции семей
```

Ключевые уравнения:

```text
Производство + Импорт + Входящие поставки + Складской запас
 = Промежуточное использование + Потребление + Экспорт
 + Исходящие поставки + Остаток + Потери

Потребность в ресурсе[i,p] ≥ Норма[i,p] × Выпуск[p]
Выпуск[p] ≤ Доступная мощность[p] × Фактическая доступность[p]
```

> **Степень готовности:** EIIOM-v4 описан как спецификация, но общий калиброванный пространственный MILP и реальные результаты на индустриальной сети **пока не подтверждены**. Отдельно требуется реализовать non-anticipativity: агент не может знать информацию, ещё не доступную в момент решения.

---

## Project Factory: проектный конвейер

Модель создания крупных экономических активов начинается с отсева неподтверждённых идей, а не с максимизации выдачи кредита. Из 1 000 потенциальных инициатив зрелая проектная фабрика *планирует* получать 20–30 решений об инвестиционной готовности за год. Это **проектное целевое значение**, не операционная статистика.

<img src="assets/readme/project-factory.svg" width="100%" alt="Планируемая воронка Project Factory 1000 → 400 → 150 → 60 → 20–30" />

У каждого проекта нужен цифровой паспорт, включая спрос, конкурентов, мощности, воду, электроэнергию, разрешения, землю, кадры, CAPEX/OPEX, сроки, покупателей, кредитные условия, источники подтверждения и сценарии провала. После проверки проект может быть передан в финансовый контур — **но не автоматически профинансирован**.

Источники: [Project Factory 1000](docs/29_PROJECT_FACTORY_1000.md) · [архетипы проектов](docs/12_PROJECT_ARCHETYPES.md) · [риски и комплаенс](docs/08_GOVERNANCE_RISK_COMPLIANCE.md).

---

## Финансовая архитектура и капитал

Основная идея — **Delta**: свободный подтверждённый финансовый ресурс после реальных расходов и обязательств. Она проявляется на уровне семьи, фирмы, проекта, региона и трансграничной системы. У этих уровней разные бухгалтерские смыслы — **переводы между ними нельзя суммировать как новую общественную прибыль**.

<img src="assets/readme/capital-flywheel.svg" width="100%" alt="Финансовая Delta от домохозяйства к бизнесу, проекту, региону и ЕАЭС" />

### Защита капитала семьи

Сначала необходимые расходы и резерв на непредвиденные обстоятельства. Затем — диверсифицированные сбережения. Долгосрочное участие в проектах допускается только из доступного риск-бюджета и с учётом сроков, ликвидности и законодательства.

### Резервирование, productive escrow и эмиссия

В EURASIAN **продуктивная эскроу-эмиссия описана как интерфейс и политика**, но **не реализована в данном репозитории как платёжное или эмиссионное ядро**. Подтверждение проекта не является разрешением на создание денег. Система должна направлять доказательства в Financial OS, а тот — независимо учитывать обязательства, залог, нормативные ограничения и разрешённые транши.

```text
ProjectProposal → техническая проверка → EvidencePackage
                                            ↓
                                Financial OS / Risk Gate
                                            ↓
                                    CapitalAuthorization
                                            ↓
                                  Payment / Settlement
                                            ↓
                                Фактическая закупка актива
```

**Правила:** `эмиссия ≠ прибыль`, `капитализация собственного токена ≠ HardNAV`, `внутренний арбитраж ≠ внешняя выручка`, `денежное обещание ≠ фактическое поступление`.

**Соседние проекты:** [synergy_financial_os](https://github.com/Shtenco/synergy_financial_os) · [synergy_pay_system](https://github.com/Shtenco/synergy_pay_system) · [synergy_ai_economy](https://github.com/Shtenco/synergy_ai_economy) · [synergy_system](https://github.com/Shtenco/synergy_system).

Подробно: [народный капитал](docs/06_PEOPLES_CAPITAL_DELTA.md) · [P2P и взаимный кредит](docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md) · [капитальный маховик](docs/20_MULTI_SCALE_CAPITAL_FLYWHEEL.md) · [финансовые рынки](docs/24_EURASIAN_FINANCIAL_MARKET_AND_SETTLEMENT.md).

---

## Федерация технологий SYNERGY

EURASIAN задумывается не как монолит: спрос может приходить от Business OS, научные технологии — из NEXUS, расчётные разрешения — из Financial OS, платёжные подтверждения — из MetaPay. Каждая подсистема имеет чётко описанные **права на факты и действия**.

<img src="assets/readme/federation.svg" width="100%" alt="Федерация SYNERGY: Real Economy OS, Financial OS, MetaPay, Science, Data Fabric, Human и Business OS" />

В [`config/federation_v4.json`](config/federation_v4.json) перечислены **46 репозиториев** с ролями. Наличие в реестре **не доказывает**, что 46 сервисов развернуты, интегрированы или имеют подтверждённую промышленную эффективность. Там, где полномочия отсутствуют, они явно не подразумеваются.

См. [карта федерации](docs/17_FEDERATION_46_SYSTEM_MAP.md), [архитектура](docs/01_SYSTEM_ARCHITECTURE.md), [интерфейсы](interfaces/) и [инфраструктура](docs/21_EURASIAN_DIGITAL_INFRASTRUCTURE.md).

---

## Control Tower: не один показатель успеха

Главная аналитическая панель EURASIAN должна измерять **не одну модельную добавленную стоимость, а причинные механизмы экономического развития**: реальные мощности, спрос, доходы домохозяйств, занятость, инвестиции, инфляционные и бюджетные риски, внешний оборот и подтверждённые денежные потоки.

<img src="assets/readme/control-tower.svg" width="100%" alt="Пять North Star показателей EURASIAN Control Tower" />

| Уровень | Обязательные метрики |
|:--|:--|
| **Реальная экономика** | Выпуск и ВДС, производительность, загрузка мощностей, локализация, энергия на единицу продукции |
| **Домохозяйства** | Медианный реальный доход, расходы, резерв, долговая нагрузка, благосостояние, доступность жилья |
| **Компании и проекты** | Выручка, OPEX, CAPEX, DSCR, просрочка, сроки строительства, доля МСП в поставках |
| **ЕАЭС** | Взаимная торговля, экспортная выручка, узкие места коридоров, критический импорт, FX-экспозиция |
| **Государство** | Налоги, бюджет, госдолг, расходы на инфраструктуру, социальные результаты |
| **Банковская система** | Ликвидность, капитал, кредитные потери, долгосрочные обязательства, динамика денег и ставок |
| **Наука и технология** | TRL, число воспроизведённых пилотов, патенты, фактическая отдача внедрения |

Источник KPI: [`docs/30_CONTROL_TOWER_AND_KPI.md`](docs/30_CONTROL_TOWER_AND_KPI.md). Панель — **спецификация измерения**, а не публичный dashboard с уже доказанными реальными KPI.

---

## Научный статус и границы достоверности

<img src="assets/readme/safeguards.svg" width="100%" alt="Шесть защитных принципов системы: физика, бухгалтерия, человек, закон, данные, риски" />

| Подсистема | Текущий проверяемый статус |
|:--|:--|
| EIIOM-v2 / SciPy LP | Исполняемый исследовательский код и тесты в репозитории |
| Референсная модель 2026–2045 | Сценарий с опубликованными параметрами и solver snapshot |
| EIIOM-v4 / пространственный MILP | Архитектурная спецификация; не готовый калиброванный runtime |
| DATASET-v4 и промышленная статистика | Схемы и план калибровки; полноценная панель ещё не собрана |
| Project Factory 1000 | Проектная воронка и операционная методология; не подтверждённый объём работ |
| Федерация 46 репозиториев | Каталог компонентов и назначенных ролей; не доказательство полной интеграции |
| Escrow / эмиссия / токенизация | Спецификация взаимодействий; не live settlement в EURASIAN |
| Реальные фабрики, резервные активы, прибыль инвесторов | Не должны заявляться без внешних независимых доказательств |

Ни один сценарный показатель, визуализация или макроэкономическая гипотеза в этом README **не является гарантией, прогнозом инвестиционного дохода, доказательством отсутствия инфляции или фактом строительства**.

### Данные без заглядывания в будущее

Для каждой записи DATASET-v4 нужны `effective_time` (время, к которому относится факт) и `known_at` (момент, когда он стал известен системе). При воспроизведении прошлого решения `known_at` не может быть позже времени принятия решения. Кроме того, статусы `OBSERVED`, `COMMITTED`, `UNDER_CONSTRUCTION`, `PLANNED`, `ANNOUNCED` и `SCENARIO` не смешиваются.

Подробнее: [DATASET-v4](docs/35_DATASET_V4.md) · [допущения и источники](docs/10_SOURCES_AND_ASSUMPTIONS.md) · [риски](docs/34_RESILIENCE_AND_STRESS_TESTING.md).

---

## Дорожная карта 2026–2045

<img src="assets/readme/roadmap.svg" width="100%" alt="Этапы исследований: работающий v2, калибровка DATASET-v4, Project Factory, EIIOM-v4, масштабирование" />

**Ближайший научный приоритет** — не нарисовать ещё больше проектных целей, а подать в оптимизатор реальные региональные физические данные, оценить ошибки сценариев и проверить портфели при дефиците ресурсов и ухудшении внешних условий.

| Этап | Что должно быть сделано | Критерий перехода |
|:--|:--|:--|
| **M0: EIIOM-v2** | Воспроизводимый LP, ограничения и тесты | Повторяемая оптимизация и проверка инвариантов |
| **M1: DATASET-v4** | Статистика стран, отраслей, предприятий, воды и энергии | Известные источники, единицы, временные срезы |
| **M2: Project Factory** | Типизированные паспорта, доказательства, стадии отбора | Устойчивое исключение непригодных проектов |
| **M3: EIIOM-v4** | Пространственный MILP с риском и supply chains | Closed OOS, сценарная устойчивость, независимая проверка |
| **M4: Федеративный пилот** | Отдельные разрешения, расчёты, отчётность | Доказанный end-to-end trace без нарушения прав |
| **2045: долгосрочная цель** | Масштабируемая кооперация и производительность | Реальные измеримые результаты, а не симуляционные цели |

Подробно: [`docs/09_ROADMAP_2026_2045.md`](docs/09_ROADMAP_2026_2045.md) · [`docs/31_V4_EXECUTION_ROADMAP.md`](docs/31_V4_EXECUTION_ROADMAP.md).

---

## Быстрый запуск

Требуются **Python 3.10+**, `numpy`, `scipy`, `pytest`, `jsonschema` (смотрите [`requirements.txt`](requirements.txt)). Команды запускаются из корня репозитория.

```bash
git clone https://github.com/Shtenco/synergy_eurasian.git
cd synergy_eurasian
python -m venv .venv

# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m pytest -q
python src/eiiom_optimizer.py --config config/base_scenario.json --output outputs/base
```

В `outputs/base/` генерируются `summary.json` и `allocation.csv`. Выполнение требует правомерного доступа к исходному коду и соблюдения лицензии репозитория.

### Что смотреть после запуска

| Файл | Что в нём находится |
|:--|:--|
| [`src/eiiom_optimizer.py`](src/eiiom_optimizer.py) | Исполняемая функция оптимизации `solve` |
| [`config/base_scenario.json`](config/base_scenario.json) | Сценарные параметры, технологические кривые и ограничения |
| [`data/base_v2_reference_summary.json`](data/base_v2_reference_summary.json) | Референсная таблица результатов v2 |
| [`data/eiiom_v2_marginal_next_1bn.csv`](data/eiiom_v2_marginal_next_1bn.csv) | Предельные изменения сценарного распределения |
| [`config/scenarios_v4.json`](config/scenarios_v4.json) | Матрица стресс-сценариев для следующего поколения |
| [`tests/`](tests/) | Проверки схем, интеграционных контрактов и инвариантов |

---

## Документация и навигация по репозиторию

Репозиторий уже содержит подробную документацию — она сохранена и доступна по прямым ссылкам.

| Раздел | Где читать |
|:--|:--|
| Видение, системная архитектура | [`docs/00_CONTEXT_AND_VISION.md`](docs/00_CONTEXT_AND_VISION.md), [`docs/01_SYSTEM_ARCHITECTURE.md`](docs/01_SYSTEM_ARCHITECTURE.md) |
| Модель EIIOM, промышленность | [`docs/02_EIIOM_MODEL.md`](docs/02_EIIOM_MODEL.md), [`docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md`](docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md) |
| Сельское хозяйство, биотехнологии | [`docs/03_AI_AGRICULTURE.md`](docs/03_AI_AGRICULTURE.md) |
| Капитал, P2P, цифровые права | [`docs/04_FINANCE_AND_SYNA.md`](docs/04_FINANCE_AND_SYNA.md), [`docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md`](docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md) |
| Человек, жильё, навыки | [`docs/05_HOUSING_RENOVATION.md`](docs/05_HOUSING_RENOVATION.md), [`docs/25_HUMAN_CAPITAL_AND_SOCIAL_INFRASTRUCTURE.md`](docs/25_HUMAN_CAPITAL_AND_SOCIAL_INFRASTRUCTURE.md) |
| Пространственная оптимизация | [`docs/23_EIIOM_V4_STOCHASTIC_MILP.md`](docs/23_EIIOM_V4_STOCHASTIC_MILP.md) |
| Проектная фабрика, мониторинг | [`docs/29_PROJECT_FACTORY_1000.md`](docs/29_PROJECT_FACTORY_1000.md), [`docs/30_CONTROL_TOWER_AND_KPI.md`](docs/30_CONTROL_TOWER_AND_KPI.md) |
| Реальная статистика, ограничения | [`docs/27_REALITY_BASELINE_2026.md`](docs/27_REALITY_BASELINE_2026.md), [`docs/35_DATASET_V4.md`](docs/35_DATASET_V4.md) |
| Экономическая стратегия | [`docs/36_GRAND_STRATEGY_2045.md`](docs/36_GRAND_STRATEGY_2045.md), [`docs/37_COUNTRY_PORTFOLIOS.md`](docs/37_COUNTRY_PORTFOLIOS.md) |
| **SYNERGY Economy 6.3 / семь отраслей** | [Консолидированная модель](docs/38_SYNERGY_ECONOMY_6_3_CONSOLIDATED.md), [исполняемый расчёт](src/synergy_economy_7sector.py), [допущения](data/synergy_economy_7sector_v1_assumptions.json), [тесты](tests/test_economy_7sector.py) |
| Прежняя полная версия главного README | [`docs/README_FULL_PRE_REDESIGN_2026.md`](docs/README_FULL_PRE_REDESIGN_2026.md) |
| Дизайн-ассеты | [`assets/readme/`](assets/readme/) |

---

## Авторские права и ограничения использования

**Copyright © 2026 Evgeniy Koshtenko. All rights reserved.** Проект распространяется под собственной лицензией [`LICENSE`](LICENSE). Публичная доступность GitHub **не означает открытую лицензию** или разрешение на коммерческое использование. Права сторонних компонентов и уже выданные лицензии сохраняются в применимых пределах.

<p align="center"><strong>SYNERGY EURASIAN — капитал имеет смысл тогда, когда превращается в проверяемую реальную производительность, устойчивость и благосостояние.</strong></p>

---

## SYNERGY V6.6 — Federated Self-Organizing Economy

V6.6 is an additive research specification for comparing independent firms, market coordination, centralized planning, local cellular rules, regional DAO coordination and federated self-organization under identical demand and shock paths. It does not claim that decentralization is inherently superior or that a calibrated simulator already exists.

- [V6.6 research specification](docs/64_SYNERGY_V6_6_FEDERATED_SELF_ORGANIZING_ECONOMY.md)
- [V6.6 economic-cell state schema](interfaces/synergy_v66_cell_state.schema.json)
- [Minimal economic-cell fixture](examples/synergy_v6_6_cell_state_minimal.json)
- [V6.6 schema contract tests](tests/test_synergy_v66_contract.py)
- [V6.6.1 seven-cell compatibility kernel](src/synergy_v66/compatibility.py)
- [V6.6.1 experiment and limitations](docs/65_SYNERGY_V6_6_1_SEVEN_CELL_COMPATIBILITY.md)
- [V6.6.1 kernel tests](tests/test_synergy_v66_compatibility.py)
- [Pull request #16](https://github.com/Shtenco/synergy_eurasian/pull/16)

V6.6.0 defines cell state, decision rights, evidence classes, conservation invariants, coordination baselines, staged scale-up, governance attack scenarios and calibration gates. V6.6.1 adds a deterministic seven-cell make-to-order compatibility kernel and paired policy replay. Its DAO label is only a legacy greedy capacity-balancing proxy; CA and market are also deliberately narrow heuristics. Persistent inventory, lead times, credit, FX and real governance remain unimplemented. All scenario outputs remain synthetic research results, not forecasts or proof of policy superiority.


### SYNERGY V6.6.2 — 20-cell inventory network

- [V6.6.2 physical network kernel](src/synergy_v66/network.py)
- [V6.6.2 topology, recipes and environment](src/synergy_v66/network_topology.py)
- [V6.6.2 model specification and limitations](docs/66_SYNERGY_V6_6_2_20_CELL_INVENTORY_NETWORK.md)
- [V6.6.2 physical-network tests](tests/test_synergy_v66_network.py)

V6.6.2 adds a deterministic synthetic 20-cell / two-region network with three production sectors, multi-stage recipes, lot inventory, expiry-aware FIFO consumption, lead-time shipments, regional storage and transport constraints, shipment audit and per-SKU physical conservation. This is the physical submodel only: working capital, payment delays, contracts, FX and governance remain explicit next increments, not implemented capabilities. All parameters and outputs are synthetic research fixtures, not calibrated EAEU data or forecasts.


### SYNERGY V6.6.2-B — dated settlement and working capital

- [Settlement replay engine](src/synergy_v66/settlement.py)
- [Commercial and working-capital specification](docs/67_SYNERGY_V6_6_2B_DATED_SETTLEMENT_AND_WORKING_CAPITAL.md)
- [Settlement tests](tests/test_synergy_v66_settlement.py)

V6.6.2-B adds dated internal invoices, customer receivables, external supplier payables, configurable payment terms, cell cash balances and explicit unfunded working-capital requirements. This is a replay overlay: negative cash is exposed but does not yet constrain production or shipment authorization. Synthetic prices, costs and payment terms are research parameters, not observed market data.


### SYNERGY V6.6.3-A — mutual-credit authorization kernel

- [Stateful mutual-credit kernel](src/synergy_v66/credit.py)
- [Credit and liquidity kernel specification](docs/68_SYNERGY_V6_6_3A_MUTUAL_CREDIT_KERNEL.md)
- [Credit kernel tests](tests/test_synergy_v66_credit.py)

V6.6.3-A adds cell cash accounts, approved bank credit lines, trade-credit limits, internal AR/AP, customer receivables, dated settlement, overdue default/freeze rules and pre-authorization of modeled production costs. The kernel is currently a standalone control layer and is **not yet wired into the V6.6.2 physical production/dispatch loop**. It must pass its accounting and credit-boundary tests before physical integration. No implicit overdraft or unbacked credit is created.


### SYNERGY V6.6.3-B — cash-constrained physical network

- [Integrated cash-constrained simulator](src/synergy_v66/network.py)
- [V6.6.3-B integration specification](docs/69_SYNERGY_V6_6_3B_CASH_CONSTRAINED_PHYSICAL_NETWORK.md)
- [Credit and physical integration tests](tests/test_synergy_v66_network.py)

When `credit_config` is supplied, cash and credit authorization now gate harvest, energy generation, intermediate/final production and supplier dispatch before physical stock is consumed or output/shipment is created. The unconstrained V6.6.2 path remains the default when no credit configuration is supplied. The model is still synthetic and has explicit limits: no partial invoice payments, external customer default, bank capital constraints, interest, collateral or empirical calibration.

Cash-first procurement funding is supported: own cash is used first, then unused trade credit, then an approved bank line for immediate payment; an order is rejected without partial cash loss if no permitted source can cover it.


The integrated credit ledger now also supports partial invoice settlement during grace periods, supplier-side receivable exposure caps, customer receivable limits, deterministic customer recovery/default write-offs, and credit rejection diagnostics. Customer credit limits can block final sales without consuming finished-goods inventory.
