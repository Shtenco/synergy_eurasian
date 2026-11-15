# SYNERGY EURASIAN — Q4.2 scalable netting and reserve-capital experiment

**Status:** standalone local synthetic model; not production `CreditLedger`.

## Design

- 20, 50 and 100 cells; ring, mesh and hub topologies; random, regional-cluster and largest-debtor defaults.
- Reserve ratios: 5%, 10%, 20% of gross invoices; seeds 17, 29, 43; 243 paired cases.
- Paired comparison: gross snapshot settlement vs full-cohort multilateral netting.
- Defaulted member cash is set to zero after an explicit external cash burn. Same-day receipts are not reused.
- Assumes netting is legally enforceable for all cohort obligations, including defaulted members.

## Definitions

`Net position_i = gross payables_i - gross receivables_i`.
`Net debit volume = sum(max(Net position_i, 0)) = sum(max(-Net position_i, 0))`.
`Netting efficiency = 1 - net debit volume / gross invoice claims`.

## 27 aggregated configurations

| Cells | Topology | Default mode | Reserve | Netting efficiency | Gross uncovered | Net uncovered |
|---:|---|---|---:|---:|---:|---:|
| 20 | hub | largest_debtors | 5% | 45.23% | 679.60 | 170.22 |
| 20 | hub | largest_debtors | 10% | 45.23% | 548.63 | 42.47 |
| 20 | hub | largest_debtors | 20% | 45.23% | 286.69 | 0.00 |
| 20 | hub | random | 5% | 45.23% | 430.14 | 127.88 |
| 20 | hub | random | 10% | 45.23% | 299.17 | 23.68 |
| 20 | hub | random | 20% | 45.23% | 56.30 | 0.00 |
| 20 | hub | regional_cluster | 5% | 45.23% | 312.61 | 206.62 |
| 20 | hub | regional_cluster | 10% | 45.23% | 181.64 | 75.65 |
| 20 | hub | regional_cluster | 20% | 45.23% | 0.00 | 0.00 |
| 20 | mesh | largest_debtors | 5% | 88.18% | 511.90 | 4.72 |
| 20 | mesh | largest_debtors | 10% | 88.18% | 378.70 | 0.00 |
| 20 | mesh | largest_debtors | 20% | 88.18% | 112.31 | 0.00 |
| 20 | mesh | random | 5% | 88.18% | 379.27 | 8.73 |
| 20 | mesh | random | 10% | 88.18% | 246.08 | 0.00 |
| 20 | mesh | random | 20% | 88.18% | 21.53 | 0.00 |
| 20 | mesh | regional_cluster | 5% | 88.18% | 438.25 | 12.90 |
| 20 | mesh | regional_cluster | 10% | 88.18% | 305.05 | 0.00 |
| 20 | mesh | regional_cluster | 20% | 88.18% | 38.66 | 0.00 |
| 20 | ring | largest_debtors | 5% | 87.96% | 464.83 | 20.72 |
| 20 | ring | largest_debtors | 10% | 87.96% | 351.16 | 0.00 |
| 20 | ring | largest_debtors | 20% | 87.96% | 123.82 | 0.00 |
| 20 | ring | random | 5% | 87.96% | 366.07 | 0.00 |
| 20 | ring | random | 10% | 87.96% | 252.41 | 0.00 |
| 20 | ring | random | 20% | 87.96% | 33.97 | 0.00 |
| 20 | ring | regional_cluster | 5% | 87.96% | 340.11 | 0.00 |
| 20 | ring | regional_cluster | 10% | 87.96% | 226.44 | 0.00 |
| 20 | ring | regional_cluster | 20% | 87.96% | 2.58 | 0.00 |
| 50 | hub | largest_debtors | 5% | 46.06% | 2001.88 | 613.23 |
| 50 | hub | largest_debtors | 10% | 46.06% | 1660.54 | 271.89 |
| 50 | hub | largest_debtors | 20% | 46.06% | 977.85 | 0.00 |
| 50 | hub | random | 5% | 46.06% | 789.75 | 338.19 |
| 50 | hub | random | 10% | 46.06% | 448.40 | 41.96 |
| 50 | hub | random | 20% | 46.06% | 0.00 | 0.00 |
| 50 | hub | regional_cluster | 5% | 46.06% | 879.23 | 413.88 |
| 50 | hub | regional_cluster | 10% | 46.06% | 537.88 | 72.53 |
| 50 | hub | regional_cluster | 20% | 46.06% | 0.00 | 0.00 |
| 50 | mesh | largest_debtors | 5% | 88.75% | 1322.78 | 45.28 |
| 50 | mesh | largest_debtors | 10% | 88.75% | 994.04 | 0.00 |
| 50 | mesh | largest_debtors | 20% | 88.75% | 336.55 | 0.00 |
| 50 | mesh | random | 5% | 88.75% | 1015.73 | 0.00 |
| 50 | mesh | random | 10% | 88.75% | 686.99 | 0.00 |
| 50 | mesh | random | 20% | 88.75% | 34.98 | 0.00 |
| 50 | mesh | regional_cluster | 5% | 88.75% | 932.78 | 0.00 |
| 50 | mesh | regional_cluster | 10% | 88.75% | 604.04 | 0.00 |
| 50 | mesh | regional_cluster | 20% | 88.75% | 4.52 | 0.00 |
| 50 | ring | largest_debtors | 5% | 92.25% | 1182.33 | 0.00 |
| 50 | ring | largest_debtors | 10% | 92.25% | 897.16 | 0.00 |
| 50 | ring | largest_debtors | 20% | 92.25% | 326.84 | 0.00 |
| 50 | ring | random | 5% | 92.25% | 862.84 | 0.00 |
| 50 | ring | random | 10% | 92.25% | 577.68 | 0.00 |
| 50 | ring | random | 20% | 92.25% | 44.59 | 0.00 |
| 50 | ring | regional_cluster | 5% | 92.25% | 841.95 | 0.00 |
| 50 | ring | regional_cluster | 10% | 92.25% | 556.79 | 0.00 |
| 50 | ring | regional_cluster | 20% | 92.25% | 2.48 | 0.00 |
| 100 | hub | largest_debtors | 5% | 45.13% | 4094.24 | 1339.96 |
| 100 | hub | largest_debtors | 10% | 45.13% | 3411.92 | 657.64 |
| 100 | hub | largest_debtors | 20% | 45.13% | 2047.27 | 0.00 |
| 100 | hub | random | 5% | 45.13% | 2661.74 | 763.90 |
| 100 | hub | random | 10% | 45.13% | 1979.41 | 81.58 |
| 100 | hub | random | 20% | 45.13% | 614.77 | 0.00 |
| 100 | hub | regional_cluster | 5% | 45.13% | 2662.73 | 1004.88 |
| 100 | hub | regional_cluster | 10% | 45.13% | 1980.40 | 322.56 |
| 100 | hub | regional_cluster | 20% | 45.13% | 615.76 | 0.00 |
| 100 | mesh | largest_debtors | 5% | 88.48% | 2625.26 | 99.96 |
| 100 | mesh | largest_debtors | 10% | 88.48% | 1981.74 | 0.00 |
| 100 | mesh | largest_debtors | 20% | 88.48% | 694.69 | 0.00 |
| 100 | mesh | random | 5% | 88.48% | 1976.19 | 0.00 |
| 100 | mesh | random | 10% | 88.48% | 1332.67 | 0.00 |
| 100 | mesh | random | 20% | 88.48% | 78.84 | 0.00 |
| 100 | mesh | regional_cluster | 5% | 88.48% | 1883.61 | 0.00 |
| 100 | mesh | regional_cluster | 10% | 88.48% | 1240.08 | 0.00 |
| 100 | mesh | regional_cluster | 20% | 88.48% | 8.84 | 0.00 |
| 100 | ring | largest_debtors | 5% | 87.85% | 2384.60 | 202.83 |
| 100 | ring | largest_debtors | 10% | 87.85% | 1817.39 | 0.00 |
| 100 | ring | largest_debtors | 20% | 87.85% | 682.96 | 0.00 |
| 100 | ring | random | 5% | 87.85% | 1719.19 | 0.00 |
| 100 | ring | random | 10% | 87.85% | 1151.97 | 0.00 |
| 100 | ring | random | 20% | 87.85% | 43.97 | 0.00 |
| 100 | ring | regional_cluster | 5% | 87.85% | 1729.71 | 0.00 |
| 100 | ring | regional_cluster | 10% | 87.85% | 1162.49 | 0.00 |
| 100 | ring | regional_cluster | 20% | 87.85% | 53.25 | 0.00 |

## Aggregate diagnostics

- Cases: **243**.
- Mean theoretical netting efficiency: **74.43%**.
- Range: **42.12%–92.82%**.
- Cases with lower uncovered amount under netting: **218/243**.
- Mean gross-minus-net uncovered difference: **760.25**.
- Maximum absolute system cash residual: **1.455e-11**.

## Limitations

1. Full-cohort netting is a strong legal/contractual assumption, not established for SYNERGY.
2. No close-out valuation, disputed invoice, collateral, maturity mismatch, FX, tax or settlement-finality risk.
3. Reserve is a single synthetic pool, not a regulatory or economic capital calibration.
4. No member-funded replenishment, bank lines, physical assets, external receivables or external liabilities.
5. Aggregate reduction in net debit does not guarantee every creditor is better off; payout concentration metrics are retained.
6. Synthetic results are not empirical EAEU estimates or policy recommendations.

## Local tests

`pytest -q synergy_q4_2_network_netting.py` — 9 tests, including the full 243-case grid.

## Next

Test insolvency-safe set-off boundaries, maturities, bilateral vs multilateral eligibility, multi-level reserve waterfall and compare against production `CreditLedger`.