# SYNERGY SUES — Production, GRNI and WIP Bridge V1

Status: executable reference implementation; research branch only.

## 1. Purpose

This module closes a missing boundary between purchasing, physical inventory and manufacturing. It does not replace the V7 event/production research line, the Financial OS, or the payment system. It supplies a typed bridge that can later consume their evidence-bearing events.

The module separates four claims that must not be conflated:

1. A purchase order authorizes a quantity and price; it does not prove delivery.
2. A goods receipt records physical acceptance; it does not prove that the supplier invoice is valid.
3. A supplier invoice creates an AP claim only to the extent it matches received, uninvoiced goods.
4. A production order describes a recipe and target; only a completed, evidenced production event creates finished-goods output.

## 2. Three-way matching and GRNI

For a PO line with ordered quantity Q_PO, accepted receipts R_i, supplier invoices I_j, and PO unit price p:

Q_R = sum(R_i), Q_I = sum(I_j)

Q_GRNI = Q_R - Q_I, Q_open = Q_PO - Q_R

V_GRNI = Q_GRNI * p

Hard controls in V1:
- cumulative receipts cannot exceed PO quantity;
- receipt unit must equal PO unit;
- invoice quantity cannot exceed received but not yet invoiced quantity;
- invoice unit and currency must match the PO;
- invoice amount must equal PO unit price × invoiced quantity;
- price differences are rejected and must go through a separately approved variance workflow;
- GRNI invoice clearing cannot exceed receipts already posted to the journal.

Journal sequence:
- accepted receipt: Dr Inventory / Cr GRNI;
- matched invoice: Dr GRNI / Cr Accounts Payable;
- supplier payment remains a separate settlement event handled by the trade/payment authorities.

V1 journal posting is intentionally limited to PO currency equal to entity functional currency. FX GRNI matching and invoice price/quantity variance accounts are future work. The dedicated GRNI receipt journal helper and the inventory-ledger receipt posting are alternative bridges for the same physical event; an adapter must select exactly one to prevent duplicate inventory and GRNI recognition.

## 3. BOM consumption and production capitalization

Each BOM component defines a positive quantity per output unit. For output quantity Q_O and component coefficient b_k:

Q_k_required = Q_O * b_k

V1 preflights every component pool before consuming any stock. It then issues each component through the existing FIFO inventory ledger. Lot-level issue allocations preserve source lot provenance and exact material cost.

C_DM = sum(C_FIFO,k)

Journal bridge:
- component issue: Dr WIP / Cr Raw-material inventory;
- completed batch: Dr Finished-goods inventory / Cr WIP.

The output inventory lot receives direct-material cost plus evidence-backed conversion-cost events. Each conversion event has an order/entity identity, a cost type, a positive functional-currency amount, an effective date, a source reference and an evidence reference. A configured credit account is required for each cost type. The execution result reconciles finished-goods cost to direct materials plus conversion costs.

## 4. Accounting conservation identities

For a completed batch with no scrap or by-products in V1:

- Raw material quantity changes by the negative of BOM consumption.
- WIP receives direct material cost and clears that same cost on completion.
- Finished goods receives output quantity Q_O and value C_DM.

The gross journal turnover may exceed the final balance because each event is retained. The trial balance equality is the control: total debits equal total credits.

Inventory quantities and values are reconciled separately from the GL; equal journal totals alone do not prove physical stock correctness.

## 5. Explicit limitations

This V1 production execution is a complete-batch direct-material bridge, not a full factory costing system. It does not yet include:
- labor time, wage accruals, payroll, or labor efficiency variance;
- machine hours, energy consumption, depreciation, maintenance or overhead absorption;
- scrap, yield loss, rework, co-products, by-products or quality holds;
- partial production, multi-stage routing, work-center capacity or production scheduling;
- standard-cost variances, purchase-price variance, landed cost or FX revaluation;
- lot expiry, serial numbers, quality certificates or regulatory traceability;
- durable event storage, distributed locking, concurrent posting or rollback across subledgers.

The in-memory reference ledgers are not production infrastructure. Production-grade deployment requires append-only persistence, transaction boundaries across inventory and journal, optimistic concurrency, access controls, signed source evidence, replay, and independent reconciliation.

## 6. Machine-readable contracts

The procurement and production payloads are defined in interfaces/synergy_sues_production.schema.json. The schema covers purchase-order lines, goods receipts, supplier invoice lines, BOM components, production orders, evidence-backed production cost events and execution results. It enforces positive quantities, currency/unit identifiers, event identity and date formats. Cross-record controls such as cumulative received quantity, invoice-to-receipt matching, entity consistency and cost reconciliation remain runtime invariants and are tested in Python.

## 7. Test coverage

The tests in tests/test_synergy_sues_production.py cover:
- PO/receipt/invoice quantity and value matching;
- over-receipt, invoice-before-receipt and price variance rejection;
- GRNI journal accrual and AP reclassification;
- FIFO BOM issue, WIP and finished-goods capitalization;
- preflight protection against partial consumption when one component is unavailable;
- duplicate production-order rejection.

## 8. Next implementation steps

1. GRNI-to-AP foreign-currency posting with dated FX and realized FX variance.
2. Purchase price, quantity, freight/landed-cost and tax variance workflows.
3. Multi-level BOM, routing, work centers, partial completions and WIP ageing.
4. Calculate labor and overhead from measured time, machine-hours, energy quantities and approved rates; reconcile these calculations to source invoices/payroll.
5. Scrap, yield, rework and by-product accounting.
6. Production-event adapters to V7 event envelope and realization chain.
7. Multi-entity close, transfer pricing and intercompany inventory profit elimination.
8. Persistent transactional store and deterministic replay before any operational use.
