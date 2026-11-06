"""Bank-statement reconciliation against AR/AP documents (SYNERGY V7.2.2)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable
import math

from .trade_ledger import TradeDocument, SettlementEvent, build_trade_ledger


def _date(value):
    try: return date.fromisoformat(value)
    except (TypeError,ValueError) as exc: raise ValueError(f"Invalid ISO date: {value!r}") from exc


@dataclass(frozen=True)
class BankStatementLine:
    line_id: str
    cash_account_id: str
    booked_date: str
    signed_amount: float  # positive inflow, negative outflow
    currency: str
    bank_reference: str
    source_ref: str
    def __post_init__(self):
        if not all((self.line_id,self.cash_account_id,self.currency,self.bank_reference,self.source_ref)):
            raise ValueError("Bank line identity, account, currency and source are required")
        _date(self.booked_date)
        if not math.isfinite(self.signed_amount) or self.signed_amount==0:
            raise ValueError("signed_amount must be finite and non-zero")


@dataclass(frozen=True)
class CashAllocation:
    allocation_id: str
    bank_line_id: str
    document_id: str
    allocated_amount: float  # positive magnitude; direction inferred from document side
    source_ref: str
    def __post_init__(self):
        if not all((self.allocation_id,self.bank_line_id,self.document_id,self.source_ref)):
            raise ValueError("Cash allocation identity and source are required")
        if not math.isfinite(self.allocated_amount) or self.allocated_amount<=0:
            raise ValueError("allocated_amount must be finite and positive")


def reconcile_bank_statement(
    documents: Iterable[TradeDocument],
    prior_settlements: Iterable[SettlementEvent],
    statement_lines: Iterable[BankStatementLine],
    allocations: Iterable[CashAllocation],
    as_of: str,
) -> dict:
    """Reconcile explicit bank-line allocations to AR/AP and report unmatched cash.

    Positive bank lines can settle receivables; negative lines can settle payables.
    Allocation is never guessed from amount/reference similarity. Unallocated bank
    value remains an exception requiring human review.
    """
    cutoff=_date(as_of)
    docs=list(documents); prior=list(prior_settlements); lines=list(statement_lines); allocs=list(allocations)
    docmap={d.document_id:d for d in docs}
    if len(docmap)!=len(docs): raise ValueError("Duplicate trade document ID")
    linemap={x.line_id:x for x in lines}
    if len(linemap)!=len(lines): raise ValueError("Duplicate bank line ID")
    if len({x.allocation_id for x in allocs})!=len(allocs): raise ValueError("Duplicate cash allocation ID")
    if len({x.settlement_id for x in prior})!=len(prior): raise ValueError("Duplicate prior settlement ID")
    for p in prior:
        if p.document_id not in docmap: raise ValueError(f"Unknown prior settlement document: {p.document_id}")
    grouped={}
    generated=[]
    for a in allocs:
        if a.bank_line_id not in linemap: raise ValueError(f"Unknown bank line: {a.bank_line_id}")
        if a.document_id not in docmap: raise ValueError(f"Unknown allocated document: {a.document_id}")
        line=linemap[a.bank_line_id]; doc=docmap[a.document_id]
        if _date(line.booked_date)>cutoff: continue
        if _date(line.booked_date)<_date(doc.issue_date): raise ValueError(f"Bank settlement predates invoice: {a.allocation_id}")
        if line.currency!=doc.currency: raise ValueError(f"Currency mismatch on allocation: {a.allocation_id}")
        if doc.side=="RECEIVABLE" and line.signed_amount<0:
            raise ValueError(f"Outflow cannot settle receivable: {a.allocation_id}")
        if doc.side=="PAYABLE" and line.signed_amount>0:
            raise ValueError(f"Inflow cannot settle payable: {a.allocation_id}")
        grouped.setdefault(line.line_id,0.0)
        grouped[line.line_id]+=a.allocated_amount
        generated.append(SettlementEvent(a.allocation_id,doc.document_id,line.booked_date,
            a.allocated_amount,doc.currency,line.cash_account_id,a.source_ref))
    line_results=[]
    for line in lines:
        if _date(line.booked_date)>cutoff: continue
        allocated=grouped.get(line.line_id,0.0)
        gross=abs(line.signed_amount)
        if allocated>gross+1e-9: raise ValueError(f"Allocations exceed bank line amount: {line.line_id}")
        unmatched=gross-allocated
        status="RECONCILED" if unmatched<=1e-9 else ("PARTIALLY_RECONCILED" if allocated>0 else "UNMATCHED")
        line_results.append({"line_id":line.line_id,"cash_account_id":line.cash_account_id,
            "booked_date":line.booked_date,"signed_amount":line.signed_amount,"currency":line.currency,
            "allocated_amount":allocated,"unmatched_amount":unmatched,"status":status})
    ledger=build_trade_ledger(docs,prior+generated,[],[],as_of)
    totals={}
    for row in line_results:
        k=row["currency"]; slot=totals.setdefault(k,{"statement_net":0.0,"allocated_net":0.0,"unmatched_inflow":0.0,"unmatched_outflow":0.0})
        slot["statement_net"]+=row["signed_amount"]
        direction=1 if row["signed_amount"]>0 else -1
        slot["allocated_net"]+=direction*row["allocated_amount"]
        if direction>0: slot["unmatched_inflow"]+=row["unmatched_amount"]
        else: slot["unmatched_outflow"]+=row["unmatched_amount"]
    return {"as_of":as_of,"bank_lines":line_results,"currency_control_totals":totals,
        "settlements_generated":len(generated),"trade_ledger":ledger,
        "fully_reconciled":all(x["status"]=="RECONCILED" for x in line_results),
        "unmatched_cash_requires_review":any(x["unmatched_amount"]>1e-9 for x in line_results),
        "automatic_matching_performed":False}
