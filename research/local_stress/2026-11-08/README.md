# SYNERGY EURASIAN — Local research validation package

**Branch target:** `research/synergy-v6.6-foundation`  
**PR:** #16  
**Scope:** standalone local research harnesses. These files are not production `CreditLedger` changes and must not be interpreted as production behavior.

## Contents

| File | Purpose | Local pytest |
|---|---|---:|
| `synergy_q2_local.py` | Reserve membership / recovery allocation fixture | 5 passed |
| `synergy_q4_local.py` | Correlated defaults, local-first/federation-second waterfall, reserve recovery | 9 passed |
| `synergy_q4_1_settlement_semantics.py` | Same-day settlement order, snapshot settlement and multilateral netting diagnostic | 8 passed |
| `synergy_q4_local_report.md` | Q4 assumptions, sensitivity matrix, accounting identities and limitations | — |
| `synergy_q4_1_local_report.md` | Q2/Q4 caveats, Q4.1 findings and production audit questions | — |
| `synergy_q4_sensitivity.csv` | Q4 policy/regime sensitivity results | — |
| `synergy_q4_results.json` | Full Q4 experiment output | — |
| `synergy_q4_1_results.json` | Q4.1 detailed settlement permutations and netting diagnostic | — |

## Local validation performed

Executed each script directly with Python: all three returned exit code 0.

Executed:
- `python -m pytest -q synergy_q2_local.py` — 5 passed.
- `python -m pytest -q synergy_q4_local.py` — 9 passed.
- `python -m pytest -q synergy_q4_1_settlement_semantics.py` — 8 passed.
- In-memory Python compilation via `compile(source, filename, "exec")` — all three sources passed.

Pytest emitted a cache-permission warning because the mounted `/mnt/data` location is not writable for `.pytest_cache`; this did not change the successful test exit codes. The runtime also emitted an unrelated spreadsheet warm-up diagnostic on interpreter startup; it did not cause script or pytest failures.

## Important corrections and interpretation boundaries

1. Q2's 100-cycle recurring-need output assumes an exogenous cash inflow of 80 per cell per 30-day cycle (1,600 per cycle across 20 cells; 160,000 across 100 cycles). It is **not** a self-financing reserve-survival result and does not run a production default waterfall.
2. Q4 is a synthetic standalone stress harness. It models 20 cells, two regions, three correlated default waves, 20 invoices, 3,104 total invoice claims in the base regime, and 8,000 external operating cash burn. Its cash-only consolidated proxy is 20,590 opening cash less 8,000 external burn = 12,590. It does not value physical assets, outside receivables, external liabilities or production assets.
3. Q4 results vary by recovery allocation and federation clearing. For example, the base case `pro_rata` recovery + `fcfs` clearing reports 215.90 uncovered; `fcfs` recovery + `batch_pro_rata` reports 274.15 uncovered. Do not quote one result without naming its policy combination.
4. Q4.1 shows that sequential gross settlement with same-day receipt reuse is order-sensitive in the deliberately circular three-account fixture. Snapshot settlement is order-invariant in that fixture. Multilateral set-off is a separate non-cash legal/contractual operation; 450 of gross claims extinguished by netting must not be represented as 450 cash paid.
5. None of these harnesses establishes the actual semantics of the repository's `CreditLedger`. Production integration requires local source access and line-level inspection of `process_day`, due-date ordering, cash-first settlement, default processing and reserve payout code.
6. GitHub CI is separate from these local tests. No production integration, merge to `main`, empirical calibration, legal enforceability opinion or real-world policy ranking is claimed.

## Reproduction

Run from this directory:

```bash
python synergy_q2_local.py
python -m pytest -q synergy_q2_local.py

python synergy_q4_local.py
python -m pytest -q synergy_q4_local.py

python synergy_q4_1_settlement_semantics.py
python -m pytest -q synergy_q4_1_settlement_semantics.py
```

## Q4.2 — scalable network netting and reserve-capital stress

- Added `synergy_q4_2_network_netting.py`, a standalone synthetic model comparing gross snapshot settlement with full-cohort multilateral netting.
- 243 paired cases: 20/50/100 cells; ring, sparse mesh and hub topologies; random, regional-cluster and largest-debtor defaults; 5%/10%/20% reserve ratios; three deterministic seeds.
- Nine local pytest tests passed, including full-grid cash reconciliation. Local results: mean theoretical netting efficiency 74.43% (range 42.12%–92.82%); aggregate uncovered claims fell in 218/243 cases, were equal in 25, and were worse in none under the stated assumptions.
- Summary: `synergy_q4_2_summary.csv`; interpretation and limitations: `synergy_q4_2_report.md`.
- Critical assumption: full-cohort multilateral set-off is treated as legally enforceable even for defaulted participants. This is not an established SYNERGY legal property. Defaulted cash is an explicit external pre-settlement burn; same-day receipts are not reusable.
- Maximum system cash reconciliation residual: approximately 1.46e-11. Synthetic results only; not production CreditLedger tests, empirical EAEU estimates, capital adequacy conclusions or policy recommendations.
