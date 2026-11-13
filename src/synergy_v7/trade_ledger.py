"""Invoice, payable, settlement and counterparty exposure ledger for SYNERGY V7.2.1.

Append-only event records are projected into open document balances as of a date.
This is a management-control model, not a statutory accounting subledger.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable
import math


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date must be ISO YYYY-MM-DD: {value!r}") from exc


def _amount(value: float, name: str, allow_zero: bool = False):
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {qualifier}")


@dataclass(frozen=True)
class TradeDocument:
    document_id: str
    side: str  # RECEIVABLE or PAYABLE
    enterprise_id: str
    counterparty_id: str
    issue_date: str
    due_date: str
    currency: str
    original_amount: float
    source_ref: str
    contract_ref: str = ""
    def __post_init__(self):
        if not all((self.document_id,self.enterprise_id,self.counterparty_id,self.currency,self.source_ref)):
            raise ValueError("Trade document identity, currency and source are required")
        if self.side not in {"RECEIVABLE","PAYABLE"}: raise ValueError("side must be RECEIVABLE or PAYABLE")
        issued,due=_day(self.issue_date),_day(self.due_date)
        if due<issued: raise ValueError("due_date cannot precede issue_date")
        _amount(self.original_amount,"original_amount")


@dataclass(frozen=True)
class SettlementEvent:
    settlement_id: str
    document_id: str
    settlement_date: str
    amount: float
    currency: str
    cash_account_id: str
    source_ref: str
    def __post_init__(self):
        if not all((self.settlement_id,self.document_id,self.currency,self.cash_account_id,self.source_ref)):
            raise ValueError("Settlement identity, currency, cash account and source are required")
        _day(self.settlement_date); _amount(self.amount,"settlement amount")


@dataclass(frozen=True)
class DocumentAdjustment:
    adjustment_id: str
    document_id: str
    adjustment_date: str
    amount: float
    currency: str
    reason: str
    source_ref: str
    def __post_init__(self):
        if not all((self.adjustment_id,self.document_id,self.currency,self.reason,self.source_ref)):
            raise ValueError("Adjustment identity, currency, reason and source are required")
        _day(self.adjustment_date); _amount(self.amount,"adjustment amount")


@dataclass(frozen=True)
class DisputeEvent:
    dispute_id: str
    document_id: str
    event_date: str
    amount: float
    currency: str
    action: str  # OPEN or RESOLVE
    source_ref: str
    def __post_init__(self):
        if not all((self.dispute_id,self.document_id,self.currency,self.source_ref)):
            raise ValueError("Dispute identity, currency and source are required")
        _day(self.event_date); _amount(self.amount,"dispute amount")
        if self.action not in {"OPEN","RESOLVE"}: raise ValueError("dispute action must be OPEN or RESOLVE")


@dataclass(frozen=True)
class CreditRiskAssessment:
    counterparty_id: str
    currency: str
    probability_of_default: float
    loss_given_default: float
    assessment_date: str
    source_ref: str
    def __post_init__(self):
        if not all((self.counterparty_id,self.currency,self.source_ref)): raise ValueError("Credit assessment identity is required")
        _day(self.assessment_date)
        if not 0<=self.probability_of_default<=1: raise ValueError("probability_of_default must be in [0,1]")
        if not 0<=self.loss_given_default<=1: raise ValueError("loss_given_default must be in [0,1]")


def build_trade_ledger(
    documents: Iterable[TradeDocument],
    settlements: Iterable[SettlementEvent],
    adjustments: Iterable[DocumentAdjustment],
    disputes: Iterable[DisputeEvent],
    as_of: str,
    credit_assessments: Iterable[CreditRiskAssessment] = (),
) -> dict:
    """Project open AR/AP, aging, disputes and counterparty exposure as of date.

    Settlements and adjustments after as_of are ignored. Disputes are event
    sourced: OPEN adds disputed amount; RESOLVE removes it. A dispute is a
    classification of open balance, not a second liability or receivable.
    """
    cutoff=_day(as_of)
    docs=list(documents); pays=list(settlements); adjs=list(adjustments); ds=list(disputes); risks=list(credit_assessments)
    dmap={d.document_id:d for d in docs}
    if len(dmap)!=len(docs): raise ValueError("Duplicate document_id")
    for rows,label,attr in ((pays,"settlement","settlement_id"),(adjs,"adjustment","adjustment_id"),(ds,"dispute","dispute_id")):
        ids=[getattr(x,attr) for x in rows]
        if len(ids)!=len(set(ids)): raise ValueError(f"Duplicate {label} ID")
    for row in pays:
        if row.document_id not in dmap: raise ValueError(f"Unknown document for settlement: {row.document_id}")
    for row in adjs:
        if row.document_id not in dmap: raise ValueError(f"Unknown document for adjustment: {row.document_id}")
    for row in ds:
        if row.document_id not in dmap: raise ValueError(f"Unknown document for dispute: {row.document_id}")

    balances={d.document_id:d.original_amount for d in docs}
    disputes_open={d.document_id:0.0 for d in docs}
    movements=[]
    timeline=[]
    for row in pays:
        timeline.append((_day(row.settlement_date),row.settlement_date,row.settlement_id,"SETTLEMENT",row))
    for row in adjs:
        timeline.append((_day(row.adjustment_date),row.adjustment_date,row.adjustment_id,"ADJUSTMENT",row))
    for row in ds:
        timeline.append((_day(row.event_date),row.event_date,row.dispute_id,"DISPUTE",row))
    for event_day,event_date,event_id,event_type,row in sorted(timeline,key=lambda x:(x[0],x[2])):
        if event_day>cutoff: continue
        doc=dmap[row.document_id]
        if event_day<_day(doc.issue_date): raise ValueError(f"{event_type} predates document: {event_id}")
        if row.currency!=doc.currency: raise ValueError(f"{event_type} currency mismatch: {event_id}")
        if event_type in {"SETTLEMENT","ADJUSTMENT"}:
            if row.amount>balances[row.document_id]+1e-9:
                raise ValueError(f"{event_type} exceeds open balance: {event_id}")
            balances[row.document_id]-=row.amount
            movements.append((event_date,event_id,event_type,row.document_id,row.amount))
        elif row.action=="OPEN":
            if disputes_open[row.document_id]+row.amount>balances[row.document_id]+1e-9:
                raise ValueError(f"Disputed amount exceeds open balance: {event_id}")
            disputes_open[row.document_id]+=row.amount
        else:
            if row.amount>disputes_open[row.document_id]+1e-9:
                raise ValueError(f"Dispute resolution exceeds disputed amount: {event_id}")
            disputes_open[row.document_id]-=row.amount

    assessments={}
    risk_days={}
    for risk in risks:
        risk_day=_day(risk.assessment_date)
        if risk_day>cutoff: continue
        key=(risk.counterparty_id,risk.currency)
        old=assessments.get(key)
        if old is not None and risk_day==_day(old.assessment_date):
            raise ValueError(f"Conflicting credit assessments on same date: {key}")
        if old is None or risk_day>_day(old.assessment_date): assessments[key]=risk

    buckets=("NOT_DUE","DUE_1_30","DUE_31_60","DUE_61_90","DUE_90_PLUS")
    aggregate={}
    rows=[]
    for doc in docs:
        if _day(doc.issue_date)>cutoff: continue
        outstanding=max(0.0,balances[doc.document_id])
        days_past_due=max(0,(cutoff-_day(doc.due_date)).days)
        if outstanding<=1e-9: bucket="SETTLED_OR_CREDITED"
        elif days_past_due==0: bucket="NOT_DUE"
        elif days_past_due<=30: bucket="DUE_1_30"
        elif days_past_due<=60: bucket="DUE_31_60"
        elif days_past_due<=90: bucket="DUE_61_90"
        else: bucket="DUE_90_PLUS"
        row={"document_id":doc.document_id,"side":doc.side,"enterprise_id":doc.enterprise_id,
            "counterparty_id":doc.counterparty_id,"currency":doc.currency,"original_amount":doc.original_amount,
            "outstanding":outstanding,"due_date":doc.due_date,"days_past_due":days_past_due,
            "aging_bucket":bucket,"disputed_outstanding":min(disputes_open[doc.document_id],outstanding),
            "undisputed_outstanding":max(0.0,outstanding-disputes_open[doc.document_id])}
        rows.append(row)
        key=(doc.side,doc.enterprise_id,doc.counterparty_id,doc.currency)
        slot=aggregate.setdefault(key,{"outstanding":0.0,"disputed":0.0,"overdue":0.0,"aging":{b:0.0 for b in buckets}})
        slot["outstanding"]+=outstanding; slot["disputed"]+=row["disputed_outstanding"]
        if days_past_due>0: slot["overdue"]+=outstanding
        if bucket in slot["aging"]: slot["aging"][bucket]+=outstanding

    exposure=[]
    for key,v in sorted(aggregate.items()):
        side,enterprise,counterparty,currency=key
        risk=assessments.get((counterparty,currency))
        ecl=v["outstanding"]*risk.probability_of_default*risk.loss_given_default if risk and side=="RECEIVABLE" else None
        exposure.append({"side":side,"enterprise_id":enterprise,"counterparty_id":counterparty,
            "currency":currency,**v,"expected_credit_loss":ecl,
            "credit_assessment_date":risk.assessment_date if risk else None})
    totals={}
    for row in exposure:
        k=(row["side"],row["currency"]); totals[k]=totals.get(k,0.0)+row["outstanding"]
    return {"as_of":as_of,"documents":rows,"counterparty_exposure":exposure,
        "totals_by_side_and_currency":{f"{k[0]}::{k[1]}":v for k,v in sorted(totals.items())},
        "settlement_count_in_period":sum(_day(x.settlement_date)<=cutoff for x in pays),
        "adjustment_count_in_period":sum(_day(x.adjustment_date)<=cutoff for x in adjs),
        "dispute_events_in_period":sum(_day(x.event_date)<=cutoff for x in ds),
        "internal_netting_applied":False,
        "expected_credit_loss_is_estimate_not_cash_or_provision":True}
