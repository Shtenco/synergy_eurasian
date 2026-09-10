# 10 — Sources, Baselines, Assumptions

## Правило классификации данных

Каждая цифра в проекте должна иметь один из четырёх статусов:

```text
EXTERNAL_FACT        — внешний проверяемый факт
MODEL_ASSUMPTION     — коэффициент модели
SCENARIO_TARGET      — целевой ориентир
SOLVER_OUTPUT        — результат конкретного run
```

Нельзя выдавать `MODEL_ASSUMPTION` или `SCENARIO_TARGET` за подтверждённый факт.

## Актуальные внешние якоря

### ЕАЭС 2030/2045

Декларация «Евразийский экономический путь» задаёт горизонт дальнейшего экономического развития интеграции до 2030 года и на период до 2045 года.

Источник: Eurasian Economic Commission

- https://eec.eaeunion.org/news/v-eek-obsuzhdena-podgotovka-plana-po-realizatsii-deklaratsii-2030/
- https://eec.eaeunion.org/upload/medialibrary/564/tbfrz98itikq8l0iyyykxo1bjj611tkc/EEC_CUSTOMS-COOPERATION.pdf

### AI / data-center energy

IEA Base Case: глобальное потребление электроэнергии дата-центрами около **945 TWh к 2030**, а потребление accelerated servers растёт примерно **30%/год** в базовом сценарии.

Источник:

- https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai
- https://www.iea.org/reports/energy-and-ai/energy-supply-for-ai

Статус: `EXTERNAL_FACT / external forecast`.

### Казахстан — Data Center Valley

Правительство Казахстана в 2026 году сообщало о проекте «Долина ЦОДов» в Экибастузе: доступная мощность 300 MW с планом масштабирования до 1 GW; заявлен пакет соглашений в области AI на $10 млрд.

Источник:

- https://primeminister.kz/ru/news/dolina-codov-pravitelstvo-kazaxstana-i-it-giganty-firebird-i-nvidia-podpisali-paket-soglasenii-v-oblasti-ii-na-10-mlrd-31516

Статус: `EXTERNAL_FACT` для объявленных параметров проекта, не гарантия его будущего полного ввода.

### Казахстан — цифровое сельское хозяйство

В 2026 году Минсельхоз Казахстана сообщал, что более 650 сельхозпроизводителей применяют цифровые решения, а пул smart farms превышает 200 хозяйств. Используются precision agriculture, IoT, automation, drones и элементы AI.

Источники:

- https://www.gov.kz/memleket/entities/moa/press/news/details/1189734?lang=ru
- https://www.gov.kz/memleket/entities/moa/press/news/details/1245007?lang=ru
- https://www.gov.kz/memleket/entities/moa/press/news/details/1169275?lang=ru

Статус: `EXTERNAL_FACT`.

### Казахстан — уран

World Nuclear Association (обновление 1 июля 2026): производство Казахстана в 2025 году около **25,839 tU**, примерно 40% мирового производства; также отмечается развитие более глубокой топливной цепочки.

Источник:

- https://world-nuclear.org/information-library/country-profiles/countries-g-n/kazakhstan

Статус: `EXTERNAL_FACT`.

## Seed / agriculture evidence

В проекте следует отдельно поддерживать актуальный реестр официальных источников ЕЭК по:

- взаимной торговле семенами;
- импорту семян из третьих стран;
- продовольственной самообеспеченности;
- механизмам финансирования кооперационных агропроектов;
- унификации seed/variety procedures.

При обновлении модели фиксировать URL, дату публикации и дату извлечения.

## Финансовое и регуляторное право

Перед любой реализацией CFA/RWA/SYNA/settlement слоя необходимо актуализировать:

### Россия

- Банк России — ЦФА / операторы информационных систем;
- требования к квалифицированным/неквалифицированным инвесторам;
- anti-pyramid / warning-list checks;
- AML/KYC;
- правила рекламы финансовых инструментов.

Официальная точка входа:

- https://www.cbr.ru/finm_infrastructure/digital_oper/

### Казахстан / AIFC

- AFSA digital asset / tokenisation framework;
- fund/SPV authorization;
- market conduct;
- custody;
- AML/KYC.

Официальная точка входа:

- https://afsa.aifc.kz/

## MODEL ASSUMPTIONS — BASE v2

### CAPEX envelope

```text
2026–2030: $120bn
2031–2040: $290bn
2041–2045: $240bn
TOTAL:     $650bn
```

Статус: `SCENARIO_TARGET / MODEL_ASSUMPTION`.

### Social/physical targets

```text
Urban renovation:       100m m² by 2045
Rural swing housing:      8m m²
Precision agriculture:   60m ha
Agro-robotics:            15m ha
Rural AI clusters:       160
```

Статус: `SCENARIO_TARGET`.

### Productive Escrow

```text
alpha = 0.25 years of verified productive annual flow
```

Статус: `MODEL_ASSUMPTION` для stress-testing; не норматив и не закон денежного обращения.

### Settlement coverage

```text
130–150% conceptual overcollateralization range
```

Статус: `MODEL_ASSUMPTION`.

### MIDAS systemic cap

```text
5–10% conceptual eligible systemic NAV range
```

Статус: `MODEL_ASSUMPTION`; реальный limit должен определяться risk engine и регулированием.

## Что требует обязательной калибровки до investment-grade версии

- actual electricity generation/capacity by node;
- transmission/substation capacity;
- transformer lead times/costs;
- actual DC shell cost/MW;
- accelerator cost/performance/W by hardware generation;
- industrial labor availability;
- actual housing stock by construction cohort;
- renovation cost/m² by city;
- construction capacity;
- farmland polygons/crop rotations;
- water availability;
- seed import dependency by crop;
- yields and climate stress;
- logistics tariffs/time;
- WACC/FX by country and asset class;
- project tax treatment;
- debt capacity;
- legally eligible collateral/haircuts.

## Reproducibility metadata

Каждый dataset должен иметь:

```text
source_url
publisher
publication_date
retrieved_at
time_period
unit
currency
fx_source
transformations
license/status
confidence
```

## Rule

Если цифра не имеет источника или явно отмеченного статуса `MODEL_ASSUMPTION`, она не должна попадать в public/investor material как факт.
