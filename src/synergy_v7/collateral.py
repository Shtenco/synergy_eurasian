"""Evidence-qualified borrowing-base calculation for SYNERGY V7.6.5."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class ReceivableCollateral:
    receivable_id: str
    counterparty_id: str
    period: int
    outstanding_amount: float
    currency: str
    days_past_due: int
    status: str
    disputed: bool
    related_party: bool
    evidence_id: str
    def __post_init__(self):
        if not all((self.receivable_id,self.counterparty_id,self.currency,self.evidence_id)):
            raise ValueError("Receivable collateral identity and evidence are required")
        if not isinstance(self.period,int) or self.period<0: raise ValueError("Receivable period must be non-negative")
        if not math.isfinite(self.outstanding_amount) or self.outstanding_amount<0:
            raise ValueError("Receivable balance must be finite and non-negative")
        if not isinstance(self.days_past_due,int) or self.days_past_due<0:
            raise ValueError("days_past_due must be a non-negative integer")
        if self.status not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}:
            raise ValueError("Unsupported receivable evidence status")


@dataclass(frozen=True)
class InventoryCollateral:
    lot_id: str
    product_id: str
    period: int
    carrying_value: float
    currency: str
    status: str
    quality_approved: bool
    location_controlled: bool
    consigned: bool
    evidence_id: str
    def __post_init__(self):
        if not all((self.lot_id,self.product_id,self.currency,self.evidence_id)):
            raise ValueError("Inventory collateral identity and evidence are required")
        if not isinstance(self.period,int) or self.period<0: raise ValueError("Inventory period must be non-negative")
        if not math.isfinite(self.carrying_value) or self.carrying_value<0:
            raise ValueError("Inventory carrying value must be finite and non-negative")
        if self.status not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO","OBSOLETE","WIP","DAMAGED"}:
            raise ValueError("Unsupported inventory evidence status")


@dataclass(frozen=True)
class BorrowingBasePolicy:
    receivable_advance_rate: float
    inventory_advance_rate: float
    max_days_past_due: int
    counterparty_concentration_limit: float
    reserve_amount: float
    include_underwritten: bool=False
    include_scenarios: bool=False
    def __post_init__(self):
        for name in ("receivable_advance_rate","inventory_advance_rate","counterparty_concentration_limit"):
            value=getattr(self,name)
            if not math.isfinite(value) or not 0<=value<=1:
                raise ValueError(f"{name} must be in [0,1]")
        if not isinstance(self.max_days_past_due,int) or self.max_days_past_due<0:
            raise ValueError("max_days_past_due must be a non-negative integer")
        if not math.isfinite(self.reserve_amount) or self.reserve_amount<0:
            raise ValueError("reserve_amount must be finite and non-negative")


def calculate_borrowing_base(
    receivables: Iterable[ReceivableCollateral],
    inventory: Iterable[InventoryCollateral],
    policy: BorrowingBasePolicy,
    objective_currency: str,
) -> dict:
    """Calculate a transparent collateral borrowing base by period.

    Eligible AR excludes overdue beyond policy, disputed, related-party, and
    non-accepted evidence classes. Counterparty concentration is capped against
    the gross eligible AR pool. Inventory requires accepted evidence, approved
    quality, controlled location and non-consigned status. Reserves are deducted
    once per period. This is a model calculation, not a lender eligibility audit.
    """
    ar=list(receivables); stock=list(inventory)
    if not objective_currency: raise ValueError("objective_currency is required")
    if len({x.receivable_id for x in ar})!=len(ar): raise ValueError("Duplicate receivable_id")
    if len({x.lot_id for x in stock})!=len(stock): raise ValueError("Duplicate inventory lot_id")
    accepted={"OBSERVED","VERIFIED"}
    if policy.include_underwritten: accepted.add("UNDERWRITTEN")
    if policy.include_scenarios: accepted.add("SCENARIO")
    periods=sorted({x.period for x in ar}|{x.period for x in stock})
    result={}
    for period in periods:
        period_ar=[x for x in ar if x.period==period]
        period_stock=[x for x in stock if x.period==period]
        for row in period_ar+period_stock:
            if row.currency!=objective_currency:
                raise ValueError(f"Collateral currency mismatch at period {period}")
        eligible_ar=[x for x in period_ar if x.status in accepted and
            x.days_past_due<=policy.max_days_past_due and not x.disputed and not x.related_party]
        ar_gross=sum(x.outstanding_amount for x in eligible_ar)
        concentration_cap=ar_gross*policy.counterparty_concentration_limit
        counterparty_gross={}
        for x in eligible_ar:
            counterparty_gross[x.counterparty_id]=counterparty_gross.get(x.counterparty_id,0.0)+x.outstanding_amount
        counterparty_eligible={k:min(v,concentration_cap) for k,v in counterparty_gross.items()}
        eligible_ar_after_caps=sum(counterparty_eligible.values())
        eligible_stock=[x for x in period_stock if x.status in accepted and x.quality_approved
            and x.location_controlled and not x.consigned]
        ar_advance=eligible_ar_after_caps*policy.receivable_advance_rate
        inventory_gross=sum(x.carrying_value for x in eligible_stock)
        inventory_advance=inventory_gross*policy.inventory_advance_rate
        gross_base=ar_advance+inventory_advance
        net_base=max(0.0,gross_base-policy.reserve_amount)
        result[period]={"eligible_receivables_gross":ar_gross,
            "receivables_after_concentration_caps":eligible_ar_after_caps,
            "counterparty_receivables_gross":counterparty_gross,
            "counterparty_receivables_eligible":counterparty_eligible,
            "receivable_advance_rate":policy.receivable_advance_rate,
            "receivable_advance_amount":ar_advance,
            "eligible_inventory_gross":inventory_gross,
            "inventory_advance_rate":policy.inventory_advance_rate,
            "inventory_advance_amount":inventory_advance,
            "gross_borrowing_base":gross_base,"reserve_deduction":policy.reserve_amount,
            "net_borrowing_base":net_base,
            "excluded_receivable_ids":[x.receivable_id for x in period_ar if x not in eligible_ar],
            "excluded_inventory_lot_ids":[x.lot_id for x in period_stock if x not in eligible_stock],
            "eligible_receivable_ids":[x.receivable_id for x in eligible_ar],
            "eligible_inventory_lot_ids":[x.lot_id for x in eligible_stock]}
    return {"currency":objective_currency,"periods":result,
        "evidence_classes_accepted":sorted(accepted),
        "calculation_is_not_lender_certification":True,
        "collateral_must_not_be_double_counted_as_cash":True}
