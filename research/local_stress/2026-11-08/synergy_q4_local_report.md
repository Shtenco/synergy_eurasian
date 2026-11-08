# SYNERGY EURASIAN — Q4 local stress experiment

**Status:** local standalone research harness; not integrated into the production `CreditLedger`. All balances, invoice amounts, external cash burns, memberships and policy assumptions are synthetic.

## Model design

- 20 member cells split evenly between WEST and EAST; opening member cash = 20,000.
- Opening reserves: 45 per regional fund and 500 federation-wide; total = 590.
- Three correlated default waves: 4 borrowers, 4 borrowers, then 2 borrowers (10 defaults total).
- Each defaulted buyer first pays as much as possible from its remaining cash after an explicit external operating cash burn; only the residual invoice balance enters the reserve waterfall. Every modeled default has a positive unpaid balance and zero buyer cash after cash-first settlement.
- Two claims per defaulted buyer: one cross-region seller and one same-region seller (20 claims).
- Waterfall: debtor-region reserve first, federation reserve second; federation clearing compared as FCFS vs same-day batch pro-rata.
- After each wave, regional reserves are replenished from eligible regional members first; federation recovery follows. The same member-level 10% opening-cash cap and 900 cash floor are shared across both funds. Defaulted members cannot contribute.
- An explicit external operating cash burn (up to the configured amount per new default) is applied before settlement. This is the only modeled external cash outflow. Reserve payouts, buyer-to-seller cash settlements and reserve contributions are internal transfers.

## Accounting identities

`System cash = member cash + regional reserve cash + federation reserve cash`.

`Expected system cash = initial system cash - cumulative external operating burn`.

`Total claims = buyer cash settlement + local reserve payouts + federation reserve payouts + uncovered internal claims`.

Both identities are asserted after every wave. Internal buyer/seller claims are excluded from the consolidated cash-NAV proxy because they cancel on consolidation. The model does not value physical inventory, production assets, external receivables or external debt; therefore its NAV output is explicitly a cash-only proxy, not full economic NAV.

## Sensitivity results

| Regime | Recovery | Federation clearing | Claims | Buyer cash paid | Reserve paid | Uncovered | Reserve coverage | Recovery contributions | Ending reserves | Ending system cash |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| moderate | pro_rata | fcfs | 2793.60 | 1980.87 | 812.73 | 0.00 | 100.00% | 622.72 | 399.99 | 12790.00 |
| moderate | pro_rata | batch_pro_rata | 2793.60 | 1980.87 | 812.73 | 0.00 | 100.00% | 622.72 | 399.99 | 12790.00 |
| moderate | fcfs | fcfs | 2793.60 | 1917.71 | 875.89 | 0.00 | 100.00% | 649.43 | 363.54 | 12790.00 |
| moderate | fcfs | batch_pro_rata | 2793.60 | 1917.71 | 875.89 | 0.00 | 100.00% | 649.43 | 363.54 | 12790.00 |
| base | pro_rata | fcfs | 3104.00 | 1623.08 | 1265.02 | 215.90 | 85.42% | 881.84 | 206.82 | 12590.00 |
| base | pro_rata | batch_pro_rata | 3104.00 | 1623.08 | 1265.02 | 215.90 | 85.42% | 879.92 | 204.89 | 12590.00 |
| base | fcfs | fcfs | 3104.00 | 1555.00 | 1276.40 | 272.60 | 82.40% | 921.06 | 234.66 | 12590.00 |
| base | fcfs | batch_pro_rata | 3104.00 | 1555.00 | 1274.85 | 274.15 | 82.30% | 916.33 | 231.48 | 12590.00 |
| severe | pro_rata | fcfs | 3880.00 | 1000.79 | 1481.19 | 1398.02 | 51.44% | 1089.41 | 198.22 | 12090.00 |
| severe | pro_rata | batch_pro_rata | 3880.00 | 999.93 | 1470.26 | 1409.80 | 51.05% | 1058.29 | 178.02 | 12090.00 |
| severe | fcfs | fcfs | 3880.00 | 926.50 | 1520.10 | 1433.40 | 51.47% | 1167.94 | 237.84 | 12090.00 |
| severe | fcfs | batch_pro_rata | 3880.00 | 923.49 | 1507.59 | 1448.92 | 50.99% | 1134.37 | 216.78 | 12090.00 |
| systemic | pro_rata | fcfs | 4656.00 | 496.06 | 1451.02 | 2708.92 | 34.88% | 1038.71 | 177.69 | 11590.00 |
| systemic | pro_rata | batch_pro_rata | 4656.00 | 498.91 | 1462.23 | 2694.87 | 35.17% | 1048.99 | 176.76 | 11590.00 |
| systemic | fcfs | fcfs | 4656.00 | 410.00 | 1440.00 | 2806.00 | 33.91% | 1069.05 | 219.05 | 11590.00 |
| systemic | fcfs | batch_pro_rata | 4656.00 | 418.58 | 1500.24 | 2737.18 | 35.40% | 1116.28 | 206.04 | 11590.00 |

## Base case interpretation

Base case uses claim multiplier 1.0 and an external cash burn of 800 per newly defaulted buyer (8,000 total). Total claims are 3,104. After buyer cash-first settlement, the aggregate invoice claims are 3,104. The guarantee reserve waterfall then covers the residual claims. Depending on recovery allocation and federation clearing, reserve payouts and uncovered amounts are shown in the sensitivity table; buyer cash settlement is reported separately. Ending reserve cash ranges from approximately 204.89 to 234.66. These differences are path-dependent: the distribution of reserve payouts changes seller cash, which changes who can contribute to the next recovery period. They do not establish that one policy is generally superior.

## Structural findings

1. In wave 1, local and federation reserves can be restored to target (590 total) under the stated synthetic liquidity assumptions.
2. By wave 2, the original local reserve members have defaulted. Both regional funds fall to zero and cannot be replenished by their own membership. The recovery waterfall therefore becomes structurally dependent on federation members.
3. By wave 3, only two non-defaulted federation members remain in the federation membership set. Recovery capacity is severely reduced; the final reserve balance remains far below its 590 target.
4. Every defaulting buyer exhausts its remaining cash against due invoices before the guarantee waterfall is used. The protected 900 cash floor is maintained for all non-defaulted members. Defaulted members are excluded from contributions.
5. Batch pro-rata versus FCFS changes who receives federation payouts. Because sellers may also be reserve members, that distribution changes later recovery capacity. Thus clearing policy and recovery policy cannot be evaluated independently.
6. The model demonstrates liquidity concentration and membership concentration risk; it does not prove insolvency of the real SYNERGY system, because the inputs are synthetic and physical assets, outside liabilities and production cash flows are not represented.

## Local validation

- `python -m py_compile /mnt/data/synergy_q4_local.py` — passed.
- `pytest -q /mnt/data/synergy_q4_local.py` — 9 tests passed.
- The tests include cross-region/local claims, local-first waterfall, cash-first buyer settlement, FCFS vs batch-pro-rata payout conservation, defaulted-member exclusion, shared caps, cash floors, deterministic replay and a 16-combination sensitivity invariant sweep.
- Maximum observed cash-conservation residual is numerical floating-point noise (below 1e-7); each run independently checks claim reconciliation.

## Limitations / next work

- This is an independent local harness, not a replay of the repository production ledger.
- Default events are represented by correlated invoice cohorts and explicit cash burns, not by calling the repository `authorize_purchase`, `process_day` or production default APIs.
- No empirical EAEU data, legal priority, FX, taxes, bank credit, external debt, inventory valuation, receivable valuation or operational cash inflows are included.
- Next required step: run the same cohorts through the actual `CreditLedger` implementation and compare every per-invoice event and balance against this oracle. This requires a local repository checkout; GitHub DNS is unavailable in this runtime, so production integration and GitHub push have not been performed.