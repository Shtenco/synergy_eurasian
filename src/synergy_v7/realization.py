"""Evidence chain from observed output to accepted delivery, invoice and collected cash."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math

from .trade_ledger import TradeDocument, SettlementEvent, build_trade_ledger


def _positive(value,name,zero=True):
    if not math.isfinite(value) or value<0 or (not zero and value==0):
        raise ValueError(f"{name} must be finite and {'non-negative' if zero else 'positive'}")


@dataclass(frozen=True)
class OutputObservation:
    output_id: str
    enterprise_id: str
    project_id: str
    benefit_stream_id: str
    period: str
    product_id: str
    observed_quantity: float
    baseline_quantity: float
    unit: str
    evidence_method: str
    evidence_id: str
    source_class: str="OBSERVED"
    def __post_init__(self):
        if not all((self.output_id,self.enterprise_id,self.project_id,self.benefit_stream_id,self.period,self.product_id,self.unit,self.evidence_id)):
            raise ValueError("Output observation identity and evidence are required")
        _positive(self.observed_quantity,"observed_quantity")
        _positive(self.baseline_quantity,"baseline_quantity")
        if self.evidence_method not in {"CONTROL_GROUP","MATCHED_CONTROL","PRE_POST","ENGINEERING_MODEL","SCENARIO"}:
            raise ValueError("Unsupported evidence_method")
        if self.source_class not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}:
            raise ValueError("Unsupported source_class")


@dataclass(frozen=True)
class DeliveryAcceptance:
    delivery_id: str
    output_id: str
    customer_id: str
    accepted_date: str
    accepted_quantity: float
    unit: str
    acceptance_ref: str
    source_class: str="VERIFIED"
    def __post_init__(self):
        if not all((self.delivery_id,self.output_id,self.customer_id,self.acceptance_ref,self.unit,self.accepted_date)):
            raise ValueError("Delivery acceptance identity and evidence are required")
        from datetime import date
        try: date.fromisoformat(self.accepted_date)
        except ValueError as exc: raise ValueError("accepted_date must be ISO YYYY-MM-DD") from exc
        _positive(self.accepted_quantity,"accepted_quantity",zero=False)
        if self.source_class not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}:
            raise ValueError("Unsupported source_class")


@dataclass(frozen=True)
class InvoiceDeliveryAllocation:
    allocation_id: str
    delivery_id: str
    invoice_document_id: str
    invoiced_quantity: float
    unit: str
    invoiced_amount: float
    currency: str
    source_ref: str
    def __post_init__(self):
        if not all((self.allocation_id,self.delivery_id,self.invoice_document_id,self.unit,self.currency,self.source_ref)):
            raise ValueError("Invoice allocation identity and evidence are required")
        _positive(self.invoiced_quantity,"invoiced_quantity",zero=False)
        _positive(self.invoiced_amount,"invoiced_amount",zero=False)


@dataclass(frozen=True)
class CollectionAttribution:
    attribution_id: str
    settlement_id: str
    invoice_allocation_id: str
    amount: float
    currency: str
    source_ref: str
    def __post_init__(self):
        if not all((self.attribution_id,self.settlement_id,self.invoice_allocation_id,self.currency,self.source_ref)):
            raise ValueError("Collection attribution identity and evidence are required")
        _positive(self.amount,"collection amount",zero=False)


@dataclass(frozen=True)
class CostObservation:
    cost_id: str
    enterprise_id: str
    project_id: str
    benefit_stream_id: str
    period: str
    cost_type: str
    amount: float
    currency: str
    evidence_id: str
    source_class: str="VERIFIED"
    def __post_init__(self):
        if not all((self.cost_id,self.enterprise_id,self.project_id,self.benefit_stream_id,self.period,self.currency,self.evidence_id)):
            raise ValueError("Cost observation identity and evidence are required")
        if self.cost_type not in {"DIRECT_COST","INCREMENTAL_OPEX","REPLACEMENT_OBLIGATION"}:
            raise ValueError("Unsupported cost_type")
        _positive(self.amount,"cost amount")
        if self.source_class not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}:
            raise ValueError("Unsupported source_class")


def evaluate_realization_chain(
    outputs: Iterable[OutputObservation],
    deliveries: Iterable[DeliveryAcceptance],
    invoice_allocations: Iterable[InvoiceDeliveryAllocation],
    invoices: Iterable[TradeDocument],
    settlements: Iterable[SettlementEvent],
    collection_attributions: Iterable[CollectionAttribution],
    costs: Iterable[CostObservation],
    as_of: str,
) -> dict:
    """Validate explicit links and report separate physical, billing and cash metrics.

    The function does not assert that pre/post output deltas are causal. It never
    prorates a bank receipt across invoices or deliveries: collection attribution
    must be explicit and sourced.
    """
    from datetime import date
    try: cutoff=date.fromisoformat(as_of)
    except ValueError as exc: raise ValueError("as_of must be ISO YYYY-MM-DD") from exc
    output_rows=list(outputs); delivery_rows=list(deliveries); allocation_rows=list(invoice_allocations)
    invoice_rows=list(invoices); settlement_rows=list(settlements); collection_rows=list(collection_attributions); cost_rows=list(costs)
    def unique(rows,key,label):
        ids=[getattr(x,key) for x in rows]
        if len(ids)!=len(set(ids)): raise ValueError(f"Duplicate {label}")
    unique(output_rows,"output_id","output_id"); unique(delivery_rows,"delivery_id","delivery_id")
    unique(allocation_rows,"allocation_id","invoice allocation_id"); unique(invoice_rows,"document_id","invoice document_id")
    unique(settlement_rows,"settlement_id","settlement_id"); unique(collection_rows,"attribution_id","collection attribution_id")
    unique(cost_rows,"cost_id","cost_id")
    omap={x.output_id:x for x in output_rows}; dmap={x.delivery_id:x for x in delivery_rows}
    imap={x.document_id:x for x in invoice_rows}; smap={x.settlement_id:x for x in settlement_rows}
    amap={x.allocation_id:x for x in allocation_rows}
    for d in delivery_rows:
        if d.output_id not in omap: raise ValueError(f"Unknown output for delivery: {d.delivery_id}")
        out=omap[d.output_id]
        if d.unit!=out.unit: raise ValueError(f"Delivery unit mismatch: {d.delivery_id}")
    accepted_by_output={}
    for d in delivery_rows:
        if d.accepted_date and d.accepted_date>as_of: continue
        accepted_by_output[d.output_id]=accepted_by_output.get(d.output_id,0.0)+d.accepted_quantity
    for oid,qty in accepted_by_output.items():
        if qty>omap[oid].observed_quantity+1e-9: raise ValueError(f"Accepted delivery exceeds observed output: {oid}")

    invoice_qty_by_delivery={}; invoice_value_by_document={}
    for a in allocation_rows:
        if a.delivery_id not in dmap: raise ValueError(f"Unknown delivery for invoice allocation: {a.allocation_id}")
        if a.invoice_document_id not in imap: raise ValueError(f"Unknown invoice document: {a.invoice_document_id}")
        doc=imap[a.invoice_document_id]
        if doc.side!="RECEIVABLE": raise ValueError(f"Invoice allocation must reference a receivable: {a.allocation_id}")
        if a.currency!=doc.currency: raise ValueError(f"Invoice allocation currency mismatch: {a.allocation_id}")
        delivery=dmap[a.delivery_id]
        if a.unit!=delivery.unit: raise ValueError(f"Invoice allocation unit mismatch: {a.allocation_id}")
        invoice_qty_by_delivery[a.delivery_id]=invoice_qty_by_delivery.get(a.delivery_id,0.0)+a.invoiced_quantity
        invoice_value_by_document[a.invoice_document_id]=invoice_value_by_document.get(a.invoice_document_id,0.0)+a.invoiced_amount
    for did,qty in invoice_qty_by_delivery.items():
        accepted=accepted_by_output.get(dmap[did].output_id,0.0)
        # Enforce delivery-specific accepted quantity, not just output-level aggregate.
        accepted_delivery=dmap[did].accepted_quantity if dmap[did].accepted_date<=as_of else 0.0
        if qty>accepted_delivery+1e-9: raise ValueError(f"Invoiced quantity exceeds accepted delivery: {did}")
    for iid,amount in invoice_value_by_document.items():
        if amount>imap[iid].original_amount+1e-9: raise ValueError(f"Allocated invoice value exceeds document amount: {iid}")

    # Reuse the trade subledger's chronology, currency and over-settlement controls.
    build_trade_ledger(invoice_rows,settlement_rows,[],[],as_of)
    settled_by_id={x.settlement_id:x for x in settlement_rows}
    for s in settlement_rows:
        if s.document_id not in imap: raise ValueError(f"Settlement references unknown invoice: {s.settlement_id}")
        if imap[s.document_id].side!="RECEIVABLE": raise ValueError(f"Settlement invoice must be a receivable: {s.settlement_id}")
        if s.currency!=imap[s.document_id].currency: raise ValueError(f"Settlement currency mismatch: {s.settlement_id}")
    collected_by_allocation={}; collected_by_settlement={}
    for c in collection_rows:
        if c.settlement_id not in smap: raise ValueError(f"Unknown settlement attribution: {c.settlement_id}")
        if c.invoice_allocation_id not in amap: raise ValueError(f"Unknown invoice allocation: {c.invoice_allocation_id}")
        s=smap[c.settlement_id]; a=amap[c.invoice_allocation_id]
        if s.document_id!=a.invoice_document_id: raise ValueError(f"Collection attribution invoice mismatch: {c.attribution_id}")
        if c.currency!=s.currency or c.currency!=a.currency: raise ValueError(f"Collection attribution currency mismatch: {c.attribution_id}")
        if s.settlement_date>as_of: continue
        collected_by_allocation[a.allocation_id]=collected_by_allocation.get(a.allocation_id,0.0)+c.amount
        collected_by_settlement[s.settlement_id]=collected_by_settlement.get(s.settlement_id,0.0)+c.amount
    for sid,amount in collected_by_settlement.items():
        if amount>smap[sid].amount+1e-9: raise ValueError(f"Collection attribution exceeds settlement: {sid}")
    for aid,amount in collected_by_allocation.items():
        if amount>amap[aid].invoiced_amount+1e-9: raise ValueError(f"Collection attribution exceeds invoice allocation: {aid}")

    output_metrics={}
    for out in output_rows:
        accepted=accepted_by_output.get(out.output_id,0.0)
        output_metrics[out.output_id]={"enterprise_id":out.enterprise_id,"project_id":out.project_id,
            "benefit_stream_id":out.benefit_stream_id,"period":out.period,"product_id":out.product_id,
            "baseline_quantity":out.baseline_quantity,"observed_quantity":out.observed_quantity,
            "observed_delta_vs_baseline":out.observed_quantity-out.baseline_quantity,
            "accepted_delivery_quantity":accepted,"unit":out.unit,"evidence_method":out.evidence_method,
            "source_class":out.source_class,"delta_is_not_causal_proof":True}

    group={}
    for out in output_rows:
        key=(out.enterprise_id,out.project_id,out.benefit_stream_id,out.period)
        slot=group.setdefault(key,{"output_ids":[],"baseline_quantity":0.0,"observed_quantity":0.0,
            "accepted_quantity":0.0,"invoiced_quantity":0.0,"invoiced_amount_by_currency":{},
            "collected_cash_by_currency":{},"costs_by_currency":{},"evidence_classes":set()})
        slot["output_ids"].append(out.output_id); slot["baseline_quantity"]+=out.baseline_quantity
        slot["observed_quantity"]+=out.observed_quantity; slot["accepted_quantity"]+=accepted_by_output.get(out.output_id,0.0)
        slot["evidence_classes"].add(out.source_class)
    for a in allocation_rows:
        d=dmap[a.delivery_id]; out=omap[d.output_id]
        key=(out.enterprise_id,out.project_id,out.benefit_stream_id,out.period); slot=group[key]
        slot["invoiced_quantity"]+=a.invoiced_quantity
        slot["invoiced_amount_by_currency"][a.currency]=slot["invoiced_amount_by_currency"].get(a.currency,0.0)+a.invoiced_amount
        collected=collected_by_allocation.get(a.allocation_id,0.0)
        slot["collected_cash_by_currency"][a.currency]=slot["collected_cash_by_currency"].get(a.currency,0.0)+collected
    for c in cost_rows:
        key=(c.enterprise_id,c.project_id,c.benefit_stream_id,c.period)
        if key not in group: raise ValueError(f"Cost has no matching output evidence group: {c.cost_id}")
        slot=group[key]; currency_slot=slot["costs_by_currency"].setdefault(c.currency,{"DIRECT_COST":0.0,"INCREMENTAL_OPEX":0.0,"REPLACEMENT_OBLIGATION":0.0,"evidence_classes":{}})
        currency_slot[c.cost_type]+=c.amount
        currency_slot["evidence_classes"][c.source_class]=currency_slot["evidence_classes"].get(c.source_class,0.0)+c.amount
    reports=[]
    for key,slot in sorted(group.items()):
        reports.append({"enterprise_id":key[0],"project_id":key[1],"benefit_stream_id":key[2],"period":key[3],
            "output_ids":sorted(slot["output_ids"]),"baseline_quantity":slot["baseline_quantity"],
            "observed_quantity":slot["observed_quantity"],"observed_delta_vs_baseline":slot["observed_quantity"]-slot["baseline_quantity"],
            "accepted_quantity":slot["accepted_quantity"],"invoiced_quantity":slot["invoiced_quantity"],
            "invoiced_amount_by_currency":slot["invoiced_amount_by_currency"],
            "collected_cash_by_currency":slot["collected_cash_by_currency"],"costs_by_currency":slot["costs_by_currency"],
            "evidence_classes":sorted(slot["evidence_classes"]),
            "revenue_is_not_cash":True,"output_delta_is_not_causal_proof":True})
    return {"as_of":as_of,"output_evidence":output_metrics,"benefit_stream_reports":reports,
        "explicit_collection_attribution_required":True,"internal_transfers_not_included":True,
        "causal_effect_not_inferred_from_pre_post_delta":True}
