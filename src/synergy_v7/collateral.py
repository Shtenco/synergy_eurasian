"""Evidence-qualified borrowing-base calculation for SYNERGY V7.6.6."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable

@dataclass(frozen=True)
class ReceivableCollateral:
    receivable_id:str
    counterparty_id:str
    period:int
    outstanding_amount:float
    currency:str
    days_past_due:int
    status:str
    disputed:bool
    related_party:bool
    evidence_id:str
    def __post_init__(self):
        if not all((self.receivable_id,self.counterparty_id,self.currency,self.evidence_id)): raise ValueError("Receivable collateral identity and evidence are required")
        if not isinstance(self.period,int) or self.period<0: raise ValueError("Receivable period must be non-negative")
        if not math.isfinite(self.outstanding_amount) or self.outstanding_amount<0: raise ValueError("Receivable balance must be finite and non-negative")
        if not isinstance(self.days_past_due,int) or self.days_past_due<0: raise ValueError("days_past_due must be a non-negative integer")
        if self.status not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}: raise ValueError("Unsupported receivable evidence status")

@dataclass(frozen=True)
class InventoryCollateral:
    lot_id:str
    product_id:str
    period:int
    carrying_value:float
    currency:str
    status:str
    quality_approved:bool
    location_controlled:bool
    consigned:bool
    evidence_id:str
    age_days:int=0
    def __post_init__(self):
        if not all((self.lot_id,self.product_id,self.currency,self.evidence_id)): raise ValueError("Inventory collateral identity and evidence are required")
        if not isinstance(self.period,int) or self.period<0: raise ValueError("Inventory period must be non-negative")
        if not math.isfinite(self.carrying_value) or self.carrying_value<0: raise ValueError("Inventory carrying value must be finite and non-negative")
        if not isinstance(self.age_days,int) or self.age_days<0: raise ValueError("Inventory age_days must be a non-negative integer")
        if self.status not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO","OBSOLETE","WIP","DAMAGED"}: raise ValueError("Unsupported inventory evidence status")

@dataclass(frozen=True)
class BorrowingBasePolicy:
    receivable_advance_rate:float
    inventory_advance_rate:float
    max_days_past_due:int
    counterparty_concentration_limit:float
    reserve_amount:float
    include_underwritten:bool=False
    include_scenarios:bool=False
    receivable_aging_haircuts:tuple[tuple[int,float],...]=()
    inventory_aging_haircuts:tuple[tuple[int,float],...]=()
    receivable_dilution_reserve_rate:float=0.0
    receivable_reserve_amount:float=0.0
    inventory_reserve_amount:float=0.0
    def __post_init__(self):
        for name in ("receivable_advance_rate","inventory_advance_rate","counterparty_concentration_limit","receivable_dilution_reserve_rate"):
            value=getattr(self,name)
            if not math.isfinite(value) or not 0<=value<=1: raise ValueError(f"{name} must be in [0,1]")
        if not isinstance(self.max_days_past_due,int) or self.max_days_past_due<0: raise ValueError("max_days_past_due must be a non-negative integer")
        for name in ("reserve_amount","receivable_reserve_amount","inventory_reserve_amount"):
            value=getattr(self,name)
            if not math.isfinite(value) or value<0: raise ValueError(f"{name} must be finite and non-negative")
        for name in ("receivable_aging_haircuts","inventory_aging_haircuts"):
            previous=-1
            for tier in getattr(self,name):
                if len(tier)!=2: raise ValueError(f"{name} entries must be [age_days, haircut_rate]")
                age,rate=tier
                if not isinstance(age,int) or age<0 or age<=previous: raise ValueError(f"{name} thresholds must be strictly increasing non-negative integers")
                if not math.isfinite(rate) or not 0<=rate<=1: raise ValueError(f"{name} haircut rates must be in [0,1]")
                previous=age

def _haircut(age_days,tiers):
    rate=0.0
    for threshold,haircut in tiers:
        if age_days<threshold: break
        rate=haircut
    return rate

def calculate_borrowing_base(receivables:Iterable[ReceivableCollateral],inventory:Iterable[InventoryCollateral],policy:BorrowingBasePolicy,objective_currency:str)->dict:
    """Calculate period borrowing capacity with an asset-level evidence and haircut audit trail."""
    ar=list(receivables); stock=list(inventory)
    if not objective_currency: raise ValueError("objective_currency is required")
    if len({x.receivable_id for x in ar})!=len(ar): raise ValueError("Duplicate receivable_id")
    if len({x.lot_id for x in stock})!=len(stock): raise ValueError("Duplicate inventory lot_id")
    accepted={"OBSERVED","VERIFIED"}
    if policy.include_underwritten: accepted.add("UNDERWRITTEN")
    if policy.include_scenarios: accepted.add("SCENARIO")
    periods=sorted({x.period for x in ar}|{x.period for x in stock}); result={}
    for period in periods:
        period_ar=[x for x in ar if x.period==period]; period_stock=[x for x in stock if x.period==period]
        for row in period_ar+period_stock:
            if row.currency!=objective_currency: raise ValueError(f"Collateral currency mismatch at period {period}")
        ar_audit=[]; ar_eligible=[]
        for x in period_ar:
            reasons=[]
            if x.status not in accepted: reasons.append("EVIDENCE_STATUS_NOT_ACCEPTED")
            if x.days_past_due>policy.max_days_past_due: reasons.append("PAST_DUE_LIMIT_EXCEEDED")
            if x.disputed: reasons.append("DISPUTED")
            if x.related_party: reasons.append("RELATED_PARTY")
            h=_haircut(x.days_past_due,policy.receivable_aging_haircuts); hv=x.outstanding_amount*h; net=max(0.0,x.outstanding_amount-hv)
            if not reasons: ar_eligible.append((x,net))
            ar_audit.append({"asset_type":"RECEIVABLE","asset_id":x.receivable_id,"counterparty_or_product_id":x.counterparty_id,"evidence_id":x.evidence_id,"gross_value":x.outstanding_amount,"age_days":x.days_past_due,"aging_haircut_rate":h,"aging_haircut_amount":hv,"value_after_aging_haircut":net,"eligible":not reasons,"exclusion_reasons":reasons})
        ar_gross=sum(x.outstanding_amount for x,_ in ar_eligible); ar_after_aging=sum(v for _,v in ar_eligible)
        cap=ar_after_aging*policy.counterparty_concentration_limit; cp_gross={}; cp_aged={}
        for x,v in ar_eligible:
            cp_gross[x.counterparty_id]=cp_gross.get(x.counterparty_id,0.0)+x.outstanding_amount
            cp_aged[x.counterparty_id]=cp_aged.get(x.counterparty_id,0.0)+v
        cp_eligible={k:min(v,cap) for k,v in cp_aged.items()}; ar_after_caps=sum(cp_eligible.values())
        dilution=ar_after_caps*policy.receivable_dilution_reserve_rate
        ar_advance=max(0.0,ar_after_caps-dilution)*policy.receivable_advance_rate
        stock_audit=[]; stock_eligible=[]
        for x in period_stock:
            reasons=[]
            if x.status not in accepted: reasons.append("EVIDENCE_STATUS_NOT_ACCEPTED")
            if not x.quality_approved: reasons.append("QUALITY_NOT_APPROVED")
            if not x.location_controlled: reasons.append("LOCATION_NOT_CONTROLLED")
            if x.consigned: reasons.append("CONSIGNED")
            h=_haircut(x.age_days,policy.inventory_aging_haircuts); hv=x.carrying_value*h; net=max(0.0,x.carrying_value-hv)
            if not reasons: stock_eligible.append((x,net))
            stock_audit.append({"asset_type":"INVENTORY","asset_id":x.lot_id,"counterparty_or_product_id":x.product_id,"evidence_id":x.evidence_id,"gross_value":x.carrying_value,"age_days":x.age_days,"aging_haircut_rate":h,"aging_haircut_amount":hv,"value_after_aging_haircut":net,"eligible":not reasons,"exclusion_reasons":reasons})
        inv_gross=sum(x.carrying_value for x,_ in stock_eligible); inv_aged=sum(v for _,v in stock_eligible)
        inv_advance=inv_aged*policy.inventory_advance_rate
        reserves=policy.reserve_amount+policy.receivable_reserve_amount+policy.inventory_reserve_amount+dilution
        gross=ar_advance+inv_advance; net_base=max(0.0,gross-reserves)
        result[period]={"eligible_receivables_gross":ar_gross,"receivables_after_aging_haircuts":ar_after_aging,"receivables_after_concentration_caps":ar_after_caps,"counterparty_receivables_gross":cp_gross,"counterparty_receivables_after_aging":cp_aged,"counterparty_receivables_eligible":cp_eligible,"receivable_advance_rate":policy.receivable_advance_rate,"receivable_dilution_reserve_rate":policy.receivable_dilution_reserve_rate,"receivable_dilution_reserve":dilution,"receivable_advance_amount":ar_advance,"eligible_inventory_gross":inv_gross,"inventory_after_aging_haircuts":inv_aged,"inventory_advance_rate":policy.inventory_advance_rate,"inventory_advance_amount":inv_advance,"gross_borrowing_base":gross,"general_reserve":policy.reserve_amount,"receivable_reserve":policy.receivable_reserve_amount,"inventory_reserve":policy.inventory_reserve_amount,"reserve_deduction":reserves,"net_borrowing_base":net_base,"excluded_receivable_ids":[x["asset_id"] for x in ar_audit if not x["eligible"]],"excluded_inventory_lot_ids":[x["asset_id"] for x in stock_audit if not x["eligible"]],"eligible_receivable_ids":[x.receivable_id for x,_ in ar_eligible],"eligible_inventory_lot_ids":[x.lot_id for x,_ in stock_eligible],"asset_audit_trail":ar_audit+stock_audit}
    return {"currency":objective_currency,"periods":result,"evidence_classes_accepted":sorted(accepted),"policy":{"receivable_advance_rate":policy.receivable_advance_rate,"inventory_advance_rate":policy.inventory_advance_rate,"max_days_past_due":policy.max_days_past_due,"counterparty_concentration_limit":policy.counterparty_concentration_limit,"receivable_aging_haircuts":[list(x) for x in policy.receivable_aging_haircuts],"inventory_aging_haircuts":[list(x) for x in policy.inventory_aging_haircuts],"receivable_dilution_reserve_rate":policy.receivable_dilution_reserve_rate,"general_reserve_amount":policy.reserve_amount,"receivable_reserve_amount":policy.receivable_reserve_amount,"inventory_reserve_amount":policy.inventory_reserve_amount},"calculation_is_not_lender_certification":True,"collateral_must_not_be_double_counted_as_cash":True}
