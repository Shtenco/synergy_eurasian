# SYNERGY V7.3 — Realized Production-to-Cash Evidence Chain

**Status:** deterministic evidence-link validator and reporting layer; not causal inference, audited revenue recognition or statutory accounting.  
**Date:** 2026-11-06

## Purpose

V7.3 joins the physical and financial evidence chain:

`observed output → customer acceptance → invoice allocation → bank settlement → explicit collection attribution`

Cost evidence is joined by enterprise, project, benefit stream and period. The model reports physical output, baseline delta, accepted quantity, invoiced amount, collected cash and cost categories separately.

## Core entities

- `OutputObservation`: actual output, baseline, product, project, benefit stream, period, method and evidence.
- `DeliveryAcceptance`: customer-accepted quantity linked to a specific output observation.
- `InvoiceDeliveryAllocation`: accepted delivery quantity and invoice value linked to an AR document.
- `SettlementEvent`: cash settlement already tied to an invoice document.
- `CollectionAttribution`: explicit amount from one settlement allocated to one invoice-delivery line.
- `CostObservation`: direct cost, incremental OPEX or replacement obligation tied to the same project/benefit stream.

## Invariants

1. Total accepted delivery quantity for an output cannot exceed observed output.
2. Invoice quantity allocated to a delivery cannot exceed customer-accepted quantity.
3. Invoice value allocated across deliveries cannot exceed the receivable document amount.
4. Settlements are replayed through the V7.2.1 trade ledger, preserving chronology and rejecting over-settlement.
5. A collection attribution must reference the same invoice as its settlement and invoice-delivery allocation.
6. Attributions cannot exceed either the settlement amount or the invoiced line value.
7. Costs without a matching output evidence group are rejected.
8. Cash collection is never inferred from invoiced revenue; every attribution must be explicit.
9. No pro-rata cash distribution across invoices or delivery lines is performed.

## Causal boundary

The output delta `observed_quantity - baseline_quantity` is reported as a descriptive comparison only. A pre/post change is **not automatically causal**. Evidence methods are tagged as control group, matched control, pre/post, engineering model or scenario, but this kernel does not estimate treatment effects or validate control-group design.

Likewise, invoiced revenue is not collected cash. The module reports both separately. It does not compute a universal net incremental benefit or NPV because counterfactual revenue, costs, taxes, working capital, quality, price effects and displacement must be established first.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.realization_cli examples/synergy_v7_3_realization_chain_demo.json
```

## Limitations and next steps

- No credit notes, invoice amendments, foreign-exchange valuation, tax, refunds or chargebacks in this realization chain yet.
- Output quantity must be sourced and linked to actual production evidence; this module does not independently verify meters or ERP.
- Delivery acceptance is an explicit input; disputes and returns require a future event model.
- Cost observations are categorized but not automatically tied to bank payments.
- The next stage should add causal evaluation design, quality and returns, external demand/counterfactuals, and independent evidence verification before any claim is classified as a verified productivity gain.
