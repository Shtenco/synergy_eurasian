# SYNERGY V6.4 — auditable supply-chain kernel

**Status: research prototype / synthetic assumptions / not production-ready.**

This branch contains a small, reproducible supply-chain simulation intended to
test one narrow hypothesis: can cross-cell supplier discovery and capacity
reallocation improve physical output and liquidity resilience under matched
supply shocks?

## Network

Seven nodes:
- `R1`, `R2`: raw-material suppliers
- `C1`, `C2`: component manufacturers
- `A1`, `A2`: final assemblers
- `L`: shared logistics provider

The model runs for 60 days. Each seed creates one environment; every policy is
run against the exact same environment for paired comparison.

## Policies

- `independent`: fixed supplier links, no fallback.
- `market`: supplier selection by marginal cost plus a congestion penalty.
- `dao`: central balancing of remaining supplier capacity.
- `ca`: local supplier preference with only a local alternate.
- `hybrid`: local-first routing with a market fallback when local capacity is
  congested.

`ca` is deliberately a minimal local-rule baseline. It is **not** a complete
cellular automaton, governance protocol, or adaptive multi-agent system.

## Accounting

Internal payments for raw materials, components, and logistics cancel in
consolidated cash. The cash-conservation identity is:

`ending_cash = opening_cash + external_sales - external_variable_costs
               - fixed_costs_paid - debt_service_paid`

The kernel separately reports:
- `operating_result_accrual`: external sales less external variable costs,
  fixed obligations accrued, and interest accrued (principal excluded);
- `cash_after_financing_change`: actual cash change after paid operating
  expenses and principal/interest debt service;
- unpaid fixed and debt arrears;
- remaining debt principal;
- FIFO inventory quantities and book values.

The opening cash balance is an input assumption; opening debt is tracked as a
liability. No token issuance, internal revaluation, or internal trade is
counted as external revenue.

## Run

Requires Python 3.10+ and no third-party packages:

```bash
python -m unittest -v
```

A small experiment can be run with:

```python
from synergy_v64_kernel import make_environment, simulate

env = make_environment(seed=123, regime="severe")
result = simulate("market", env, final_price=15.0, return_trace=True)
print(result["operating_result_accrual"])
print(result["cash_after_financing_change"])
```

## Important limitations

This prototype is not an audited industrial or credit model:
- seven nodes are aggregate entities; 147 participants are not individually
  modelled;
- inventory lots are FIFO-tracked, but the present make-to-order chain mostly
  consumes each batch immediately; persistent stock policies are not yet
  implemented;
- fixed costs and debt schedules are synthetic and not calibrated to real
  companies;
- default is triggered by accumulated arrears, with no legal insolvency,
  workout, collateral recovery, or bankruptcy waterfall;
- no taxes, payroll distribution to households, demand elasticity, price
  bargaining, or working-capital credit facility;
- the logistics node is a single shared bottleneck;
- `ca` is a deliberately simple local heuristic, not the full eight-rule
  cellular economy described in the architecture.

All numeric outputs are scenario results, not empirical forecasts or proof of
profitability. Before production use, add double-entry journal events,
persistent FIFO lots, supplier contracts, full maturity schedules, ECL/PD/LGD,
and independent validation.
