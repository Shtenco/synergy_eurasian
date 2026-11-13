"""Dated supplier payment commitments for V7.6 cash-constrained planning."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class SupplierPaymentCommitment:
    payment_id: str
    supplier_id: str
    purchase_order_id: str
    input_product_id: str
    period: int
    amount: float
    currency: str
    payment_stage: str
    status: str
    evidence_id: str
    def __post_init__(self):
        if not all((self.payment_id,self.supplier_id,self.purchase_order_id,self.input_product_id,self.currency,self.evidence_id)):
            raise ValueError("Supplier payment identity, currency and evidence are required")
        if not isinstance(self.period,int) or self.period<0:
            raise ValueError("Supplier payment period must be a non-negative integer")
        if not math.isfinite(self.amount) or self.amount<=0:
            raise ValueError("Supplier payment amount must be finite and positive")
        if self.payment_stage not in {"DEPOSIT","DISPATCH","RECEIPT","MILESTONE","FINAL"}:
            raise ValueError("Unsupported supplier payment stage")
        if self.status not in {"OBSERVED","COMMITTED","SCENARIO","PLANNED"}:
            raise ValueError("Unsupported supplier payment status")


def aggregate_supplier_payment_commitments(
    payments: Iterable[SupplierPaymentCommitment],
    horizon_periods: int,
    objective_currency: str,
    include_scenarios: bool=False,
) -> dict:
    """Aggregate firm dated supplier cash obligations by planning period.

    Only OBSERVED and COMMITTED payments are firm by default. SCENARIO entries
    are included only when explicitly requested. PLANNED entries never count
    as firm. Payments outside the horizon are reported, not pulled into period 0.
    """
    rows=list(payments)
    if not isinstance(horizon_periods,int) or horizon_periods<1:
        raise ValueError("horizon_periods must be a positive integer")
    if not objective_currency: raise ValueError("objective_currency is required")
    ids=[x.payment_id for x in rows]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate supplier payment_id")
    totals={}; included=[]; excluded=[]; deferred=[]
    for row in rows:
        if row.currency!=objective_currency:
            raise ValueError(f"Supplier payment currency mismatch: {row.payment_id}")
        if row.status not in ({"OBSERVED","COMMITTED","SCENARIO"} if include_scenarios else {"OBSERVED","COMMITTED"}):
            excluded.append(row.payment_id); continue
        if row.period>=horizon_periods:
            deferred.append(row.payment_id); continue
        totals[row.period]=totals.get(row.period,0.0)+row.amount
        included.append(row.payment_id)
    return {"cash_outflows_by_period":totals,"included_payment_ids":included,
        "excluded_nonfirm_payment_ids":excluded,"out_of_horizon_payment_ids":deferred,
        "currency":objective_currency,"scenario_payments_included":include_scenarios,
        "payment_commitments_are_not_bank_settlements":True}
