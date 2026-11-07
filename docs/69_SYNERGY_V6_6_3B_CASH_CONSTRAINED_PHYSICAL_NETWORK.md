# SYNERGY V6.6.3-B — cash-constrained physical production and procurement

**Status:** first integrated synthetic research mode.  
**Model ID:** `SYNERGY_V6.6.3B_CASH_CONSTRAINED_NETWORK`

## 1. What changed

V6.6.3-A provided a standalone credit authorization kernel. V6.6.3-B calls that kernel inside the V6.6.2 physical simulation. Financial state now changes physical outcomes.

When `credit_config` is omitted, V6.6.2 behavior is retained. When supplied, production and procurement must pass credit authorization before any physical mutation is made.

## 2. Where authorization occurs

### Production gates
- Grain and oilseed harvest are authorized against the farm cell's available cash plus undrawn approved bank line.
- Energy generation is authorized against the energy cell's available cash plus bank line.
- Flour, oil, bread and packaged-food production are authorized before input lots are consumed.
- The configured synthetic conversion overhead is paid to an external supplier before output is added to inventory.
- If authorization fails, the operation creates no output and consumes no recipe inputs.

### Procurement gates
- A supplier dispatch creates a buyer payable and seller receivable before source stock is consumed and a shipment is created.
- Buyer trade-credit limits and (for the unsecured remainder) seller receivable-exposure limits are checked before dispatch. The buyer's cash is applied first; any uncovered remainder may use available trade credit. If trade credit cannot cover it, an approved bank line may fund immediate full payment. A purchase with sufficient cash therefore remains possible even when the trade-credit limit is zero. Due payables can be partially settled from available cash and undrawn bank credit; the unpaid residual remains outstanding through the configured grace period.
- Defaulted buyers cannot procure; defaulted suppliers cannot receive new purchase orders.
- Local and cross-region invoice due dates use separate configurable terms.
- If authorization fails, no stock is removed from the supplier and no shipment enters transit.

### Customer sales and credit risk
- Final sales create customer invoices only if the seller's customer-receivable exposure limit has room.
- Customer invoices collect the configured recovery fraction on the due date; unpaid residuals remain receivable through the customer grace period and are then written off as bad debt.
- A defaulted final producer cannot issue new customer invoices or make new sales.
- Customer exposure rejection prevents the physical sale and leaves finished goods in inventory.

## 3. Configuration

```python
credit_config = {
    "initial_cash_per_cell": 200.0,
    "bank_limit_per_cell": 50.0,
    "trade_credit_limit_per_cell": 100.0,
    "trade_receivable_limit_per_cell": 150.0,
    "customer_receivable_limit_per_cell": 250.0,
    "customer_recovery_rate": 0.85,
    "customer_grace_days": 2,
    "grace_days": 2,
    "customer_terms_days": 2,
    "local_terms_days": 3,
    "cross_border_terms_days": 5,
}
```

Then:

```python
from synergy_v66.network import make_environment, simulate

environment = make_environment(seed=2026, days=45, regime="severe")
report = simulate(environment, credit_config=credit_config)
print(report["unmet_demand_by_sku"])
print(report["credit_ledger"]["defaulted_cells"])
print(report["credit_ledger"]["cash_conservation_error"])
print(report["credit_ledger"]["production_rejection_count"])
print(report["credit_ledger"]["trade_credit_utilization_by_cell"])
```

All prices, costs, limits and terms are synthetic research parameters. Production conversion costs are paid immediately; internal input invoices are settled from available cash and undrawn bank credit, allowing partial payment until the grace period expires. Customer invoices collect a configured deterministic recovery fraction once on the due date; the residual becomes bad debt after the customer grace period. These assumptions isolate liquidity, bilateral trade credit and customer default channels; they are not empirical claims.

## 4. Required invariants

- Cash never becomes negative.
- Bank debt never exceeds the approved per-cell bank line.
- Cash-funded purchases are possible without trade credit; mixed cash/trade-credit and bank-funded cash purchases reconcile without partial cash loss on rejected orders.
- Production rejected for insufficient liquidity does not consume inputs or create output.
- Procurement rejected by trade-credit policy does not consume supplier stock or create a shipment.
- Internal AR/AP match and internal transfer cash-in equals cash-out.
- Consolidated cash reconciles to opening cash, bank draws, customer collections, external production payments and bank principal repayments.
- The physical per-SKU mass balance remains closed.
- Credit diagnostics expose production/purchase/customer-invoice rejections, buyer and supplier credit utilization, customer bad debt, default events and bank-line utilization.
- With sufficiently large funding and trade-credit limits, the physical path must match the unconstrained V6.6.2 path under the same exogenous environment.
- With zero cash, zero bank lines and zero trade credit, no cash-costed production or supplier procurement is authorized.

## 5. Explicit limitations

This is not yet a complete financial institution or legal mutual-credit system. It does not model partial invoice payments, interest, collateral, guarantees, automatic bank-debt sweeps, external customer default, supplier credit-risk limits, bank capital constraints, intraday liquidity, FX, taxes, customs, legal enforceability, insolvency proceedings or recovery waterfalls. Bank principal repayment is manual in the kernel. The physical network's support-cell maintenance behavior remains outside this increment.

The current model also uses fixed synthetic unit prices and conversion costs; it does not solve market-clearing prices or optimize production plans under scarce credit. No country calibration or policy superiority claim is made.

## 6. Validation gate

The tests must prove both directions: ample funding reproduces the baseline physical path, while zero liquidity blocks production and procurement without breaking physical conservation. Credit and physical accounting tests are run in the repository's full pytest CI.
