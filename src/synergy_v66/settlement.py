"""Dated invoice and payment replay over the V6.6.2 physical event ledger.

This overlay measures cash timing and working-capital needs. It does not yet
feed liquidity constraints back into production or shipment authorization.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any
from .network import CELLS, CELL_BY_ID
from .credit import TRANSFER_PRICE, EXTERNAL_SALE_PRICE, EXTERNAL_PRODUCTION_COST

def replay_settlement(
    physical_result:dict[str,Any],
    initial_cash_per_cell:float=200.0,
    customer_terms_days:int=2,
    supplier_terms_days:int=2,
    local_terms_days:int=3,
    cross_border_terms_days:int=5,
    credit_limit_per_cell:float=0.0,
)->dict[str,Any]:
    """Replay invoices and settlements; negative cash is reported, not financed."""
    if initial_cash_per_cell<0 or credit_limit_per_cell<0:
        raise ValueError("cash and credit limit must be >= 0")
    terms=(customer_terms_days,supplier_terms_days,local_terms_days,cross_border_terms_days)
    if any(x<0 for x in terms): raise ValueError("payment terms must be >= 0 days")
    required=("days","shipment_dispatch_audit","sales_audit","production_audit")
    if any(k not in physical_result for k in required):
        raise ValueError("physical result is missing commercial audit fields")

    cash={c.cell_id:float(initial_cash_per_cell) for c in CELLS}
    opening_cash=sum(cash.values())
    internal_due=defaultdict(list); customer_due=defaultdict(list); supplier_due=defaultdict(list)
    dispatch_by_day=defaultdict(list); sales_by_day=defaultdict(list); production_by_day=defaultdict(list)
    for e in physical_result["shipment_dispatch_audit"]:
        dispatch_by_day[int(e["dispatch_day"])].append(e)
    for e in physical_result["sales_audit"]:
        sales_by_day[int(e["day"])].append(e)
    for e in physical_result["production_audit"]:
        production_by_day[int(e["day"])].append(e)

    internal_ar=internal_ap=customer_ar=supplier_ap=0.0
    internal_gross=internal_in=internal_out=0.0
    external_collected=external_paid=external_sales=external_cost=0.0
    minimum_cash=dict(cash); shortfall={c.cell_id:0.0 for c in CELLS}
    daily=[]; invoice_no=0

    for day in range(int(physical_result["days"])):
        day_internal=day_customer=day_cost=0.0
        # Invoice dates are anchored to physical dispatch, sale and production events.
        for e in dispatch_by_day[day]:
            invoice_no+=1; src=e["origin"]; dst=e["destination"]
            cross=CELL_BY_ID[src].region!=CELL_BY_ID[dst].region
            amount=float(e["quantity"])*TRANSFER_PRICE[e["sku"]]
            due=day+(cross_border_terms_days if cross else local_terms_days)
            internal_due[due].append({"id":f"INT-{invoice_no}","seller":src,"buyer":dst,"amount":amount})
            internal_ar+=amount; internal_ap+=amount
        for e in sales_by_day[day]:
            invoice_no+=1; amount=float(e["quantity"])*EXTERNAL_SALE_PRICE[e["sku"]]
            customer_due[day+customer_terms_days].append({"id":f"CUS-{invoice_no}","seller":e["cell_id"],"amount":amount})
            customer_ar+=amount; external_sales+=amount
        for e in production_by_day[day]:
            invoice_no+=1; amount=float(e["quantity"])*EXTERNAL_PRODUCTION_COST[e["sku"]]
            supplier_due[day+supplier_terms_days].append({"id":f"SUP-{invoice_no}","buyer":e["cell_id"],"amount":amount})
            supplier_ap+=amount; external_cost+=amount

        # Due internal invoices transfer cash; external flows change consolidated cash.
        for e in internal_due.pop(day,[]):
            amount=e["amount"]; cash[e["buyer"]]-=amount; cash[e["seller"]]+=amount
            internal_ar-=amount; internal_ap-=amount
            internal_gross+=amount; internal_out+=amount; internal_in+=amount; day_internal+=amount
        for e in customer_due.pop(day,[]):
            cash[e["seller"]]+=e["amount"]; customer_ar-=e["amount"]
            external_collected+=e["amount"]; day_customer+=e["amount"]
        for e in supplier_due.pop(day,[]):
            cash[e["buyer"]]-=e["amount"]; supplier_ap-=e["amount"]
            external_paid+=e["amount"]; day_cost+=e["amount"]

        for cell,value in cash.items():
            minimum_cash[cell]=min(minimum_cash[cell],value)
            shortfall[cell]=max(shortfall[cell],max(0.0,-credit_limit_per_cell-value))
        daily.append({
            "day":day,"internal_settlements_gross":day_internal,
            "external_customer_collections":day_customer,
            "external_supplier_payments":day_cost,"cash_total":sum(cash.values()),
            "internal_ar":internal_ar,"internal_ap":internal_ap,
            "customer_ar":customer_ar,"supplier_ap":supplier_ap,
        })

    closing_cash=sum(cash.values())
    internal_ar=0.0 if abs(internal_ar)<1e-8 else internal_ar
    internal_ap=0.0 if abs(internal_ap)<1e-8 else internal_ap
    customer_ar=0.0 if abs(customer_ar)<1e-8 else customer_ar
    supplier_ap=0.0 if abs(supplier_ap)<1e-8 else supplier_ap
    expected=opening_cash+external_collected-external_paid
    return {
        "model_id":"SYNERGY_V6.6.2B_DATED_SETTLEMENT_REPLAY",
        "days":int(physical_result["days"]),"currency_unit":"synthetic_currency_unit",
        "opening_cash":opening_cash,"closing_cash":closing_cash,"cash_by_cell":cash,
        "minimum_cash_by_cell":minimum_cash,
        "peak_unfunded_working_capital_by_cell":shortfall,
        "peak_unfunded_working_capital":max(shortfall.values(),default=0.0),
        "external_sales_accrued":external_sales,
        "external_customer_collections":external_collected,
        "customer_receivables_outstanding":customer_ar,
        "external_production_cost_accrued":external_cost,
        "external_supplier_payments":external_paid,
        "supplier_payables_outstanding":supplier_ap,
        "internal_invoice_receivables_outstanding":internal_ar,
        "internal_invoice_payables_outstanding":internal_ap,
        "internal_settlements_gross":internal_gross,
        "internal_transfer_cash_in":internal_in,
        "internal_transfer_cash_out":internal_out,
        "internal_settlement_net_system":internal_in-internal_out,
        "cash_conservation_error":closing_cash-expected,
        "daily_ledger":daily,
    }
