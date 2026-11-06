# SYNERGY V7.2 — Working Capital and Cash Waterfall

**Status:** deterministic financial-control primitives; not a full accounting ledger, credit model or calibrated enterprise forecast.  
**Date:** 2026-11-06

## Purpose

V7.2 connects the physical production plan to enterprise liquidity. Production feasibility alone does not guarantee survival: inventory ties up cash, customers may pay late, suppliers extend or shorten terms, replacement CAPEX competes with growth, and financing proceeds can disguise weak operating cash generation.

V7.2 adds two deliberately transparent components:

1. Operating working-capital metrics and the cash impact of a change in net operating working capital.
2. A prioritized cash waterfall that separates operating collections, financing proceeds and internal transfers.

## Working capital

`WorkingCapitalSnapshot` accepts accounts receivable, inventory at cost, accounts payable, other operating current liabilities, annual external revenue and annual COGS.

`NWC = AR + Inventory - AP - OtherOperatingCurrentLiabilities`

`DSO = AR / AnnualExternalRevenue × DayCount`

`DIO = InventoryAtCost / AnnualCOGS × DayCount`

`DPO = AP / AnnualCOGS × DayCount`

`CCC = DSO + DIO - DPO`

A reduction in NWC releases cash; an increase absorbs cash:

`CashImpact = NWC(previous) - NWC(current)`

If revenue or COGS denominators are zero, the corresponding days metric and CCC are undefined (`None`), not zero.

## Cash waterfall

Liquidity sources are itemized as opening cash, customer collections, other external operating receipts, financing proceeds and internal transfers received.

The default allocation priority is:

1. Operating expenses.
2. Replacement obligations.
3. Debt service.
4. Reserve replenishment to target.
5. Growth CAPEX.
6. Distributions.

The existing reserve may fund mandatory shortfalls when explicitly allowed. A distribution is blocked unless all listed mandatory obligations are funded and the reserve target is met.

Financing proceeds are cash liquidity, but **not operating revenue or operating cash generation**. Internal transfers may provide liquidity to an individual enterprise but are excluded from consolidated external operating cash generation. This prevents debt, equity, token issuance or transfers from being presented as newly created productive value.

## Example and tests

The V7.1 integrated factory fixture is a physical production example. V7.2 tests separately validate working-capital days, cash release from NWC reduction, reserve draw, replacement priority, reserve replenishment and distribution gates.

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Deliberate limitations

- This is a period-level cash allocation calculator, not double-entry bookkeeping.
- No invoice-level ageing, payment terms, tax, FX, interest accrual, covenant logic, factoring discount, inventory obsolescence or bad-debt model yet.
- No legal debt seniority or jurisdiction-specific insolvency waterfall is inferred. Priority must be reviewed against contracts and applicable law.
- No cash-flow forecast is inferred from scenario revenue; collections must be supplied as explicit cash inputs.
- Internal transfers are excluded from consolidated operating generation but still appear as cash at the receiving entity. A full consolidation engine must pair both sides and eliminate them exactly once.

## Next

V7.2.1 should add invoice and payable event ledgers with due dates, partial settlements, ageing buckets, disputes, defaults and counterparty exposure. V7.3 can then connect observed production benefits to collections and causal attribution.
