# SYNERGY V6.6.3-C — bilateral exposure, partial settlement and customer credit risk

**Status:** executable synthetic extension to the integrated V6.6.3-B network.  
**Scope:** partial payable settlement, seller-side receivable exposure caps, customer exposure caps and deterministic customer bad-debt handling.

## 1. Bilateral supplier exposure

A purchase can be funded through:
1. buyer cash paid immediately;
2. trade credit for the uncovered amount, if buyer AP capacity permits;
3. an approved bank line for immediate payment if the trade-credit route cannot cover the residual.

For the trade-credit portion, two independent limits apply:
- buyer-side trade payable limit;
- seller-side trade receivable exposure limit.

The seller's exposure limit applies only to the unpaid trade-credit portion. A fully cash-funded purchase does not consume seller receivable capacity. Rejected orders do not debit cash, create an invoice, consume supplier stock or create a shipment.

## 2. Partial payable settlement

On each simulation day:
1. customer receipts due that day are processed;
2. payable invoices are sorted by due date and stable invoice ID;
3. each payable is settled up to available cash plus undrawn bank credit;
4. buyer AP and seller AR decrease by the same paid amount;
5. any residual remains open/overdue through the buyer grace period;
6. residual debt at the grace deadline triggers buyer default and freezes new procurement and production.

This is deterministic waterfall settlement. It is not a negotiated installment plan, and it does not model payment priority across legal creditor classes.

## 3. Customer credit exposure and default

Each selling cell may have a customer receivable limit. A new final-sale invoice is rejected if it would exceed that limit. In the integrated physical simulator, a rejected customer invoice means the sale is not completed: finished goods remain in inventory and unmet demand increases.

Customer invoice collection uses a configurable deterministic recovery fraction:
- at due date, the configured fraction of the invoice balance is collected once;
- the unpaid residual remains as a receivable during the customer grace period;
- at the grace deadline, the residual is written off to customer bad debt.

This fixed recovery fraction is a controlled stress parameter, not a calibrated default probability or a stochastic customer-credit model. Customer bad debt reduces the seller's receivable asset; it does not directly create a new cash outflow.

## 4. Configuration

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

## 5. Accounting invariants

- Buyer AP equals seller AR for every outstanding internal invoice in aggregate.
- Each partial payment reduces buyer AP and seller AR by exactly the same amount.
- Buyer and seller exposure utilization never exceed their configured limits.
- Customer receivables reconcile to unpaid customer invoices; written-off residuals are separately accumulated as bad debt.
- Customer collections enter cash once only; bad-debt write-off does not fabricate cash.
- Consolidated cash identity remains: opening cash + bank draws + customer collections - external supplier payments - bank principal repayments.
- Internal cash transfers net to zero at system level.
- Physical per-SKU stock-flow conservation remains closed, including sales blocked by customer exposure limits.

## 6. Known limitations

No stochastic customer default timing, external buyer identity concentration, legal claims recovery, collateral, guarantees, credit insurance, invoice factoring, interest, penalty charges, debt seniority, cross-default clauses, bankruptcy waterfall or macroprudential bank-capital constraints. Customer recovery is a single fixed fraction per ledger instance. Supplier and customer exposure caps are per cell, not portfolio- or group-wide.

## 7. Validation

The credit tests cover partial payment and grace-period default, matching AP/AR reductions, supplier exposure rejection, cash-funded procurement despite zero trade-credit limit, customer recovery and bad-debt write-off, customer exposure rejection, and cash/physical conservation in integrated network scenarios.
