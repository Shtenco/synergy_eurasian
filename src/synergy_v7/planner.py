"""MILP production, cash and credit scheduler for SYNERGY V7.6.2 (SciPy HiGHS)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .core import ResourceCapacity
from .production import ProductionRecipe, InventoryReceipt


@dataclass(frozen=True)
class PlanDemand:
    demand_id: str
    product_id: str
    quantity: float
    unit: str
    due_period: int
    unit_value: float
    currency: str
    priority_weight: float=1.0
    def __post_init__(self):
        if not all((self.demand_id,self.product_id,self.unit,self.currency)):
            raise ValueError("Planning demand identity and currency are required")
        for name in ("quantity","unit_value","priority_weight"):
            value=getattr(self,name)
            if not math.isfinite(value) or value<0: raise ValueError(f"{name} must be finite and non-negative")
        if self.quantity<=0: raise ValueError("quantity must be positive")
        if self.priority_weight<=0: raise ValueError("priority_weight must be positive")
        if not isinstance(self.due_period,int) or self.due_period<0:
            raise ValueError("due_period must be a non-negative integer")


def optimize_production_schedule(
    recipes: Iterable[ProductionRecipe],
    demands: Iterable[PlanDemand],
    inventory_receipts: Iterable[InventoryReceipt],
    resource_capacities: Iterable[ResourceCapacity],
    horizon_periods: int,
    batch_limits: dict[str,int],
    batch_costs: dict[str,float] | None = None,
    holding_costs: dict[str,float] | None = None,
    objective_currency: str="USD",
    mip_rel_gap: float=0.0,
    time_limit_seconds: float=30.0,
    minimum_inventory: dict[str,float] | None = None,
    storage_limits: dict[str,float] | None = None,
    cash_opening_balance: float | None = None,
    cash_minimum_balance: float | dict[int,float] | None = None,
    cash_inflows_by_period: dict[int,float] | None = None,
    cash_outflows_by_period: dict[int,float] | None = None,
    collection_lag_by_demand: dict[str,int] | None = None,
    collection_fraction_by_demand: dict[str,float] | None = None,
    credit_limit: float | None = None,
    credit_opening_balance: float = 0.0,
    credit_draw_limits_by_period: dict[int,float] | None = None,
    credit_repayment_limits_by_period: dict[int,float] | None = None,
    credit_interest_rates_by_period: dict[int,float] | None = None,
    terminal_credit_balance_limit: float | None = None,
    credit_maturity_period: int | None = None,
    credit_borrowing_base_by_period: dict[int,float] | None = None,
) -> dict:
    """Maximize demand value net of modeled costs under physical, cash and credit constraints.

    Integer recipe batches are scheduled over discrete periods. Inventory balance
    couples periods; outputs become available after recipe lead time. Only firm
    (OBSERVED/COMMITTED) resource capacities and inventory receipts count. Optional
    cash equations model dated collections/outflows; an optional revolving facility
    adds draws, prior-balance repayments, interest and a terminal debt ceiling.
    """

    recipe_rows=list(recipes); demand_rows=list(demands); receipts=list(inventory_receipts); caps=list(resource_capacities)
    if not isinstance(horizon_periods,int) or horizon_periods<1: raise ValueError("horizon_periods must be a positive integer")
    if not objective_currency: raise ValueError("objective_currency is required")
    if not 0<=mip_rel_gap<1: raise ValueError("mip_rel_gap must be in [0,1)")
    if not math.isfinite(time_limit_seconds) or time_limit_seconds<=0: raise ValueError("time_limit_seconds must be positive")
    rmap={r.recipe_id:r for r in recipe_rows}
    if not rmap or len(rmap)!=len(recipe_rows): raise ValueError("Recipes must be non-empty with unique recipe_id")
    if len({d.demand_id for d in demand_rows})!=len(demand_rows): raise ValueError("Duplicate demand_id")
    if len({x.receipt_id for x in receipts})!=len(receipts): raise ValueError("Duplicate receipt_id")
    if len({(c.resource_id,c.period) for c in caps})!=len(caps): raise ValueError("Duplicate resource capacity state")
    if set(batch_limits)!=set(rmap): raise ValueError("batch_limits must define every recipe exactly once")
    for rid,limit in batch_limits.items():
        if not isinstance(limit,int) or limit<0: raise ValueError(f"batch limit for {rid} must be a non-negative integer")
    batch_costs=batch_costs or {}; holding_costs=holding_costs or {}
    minimum_inventory=minimum_inventory or {}; storage_limits=storage_limits or {}
    credit_enabled=credit_limit is not None
    cash_enabled=any(x is not None for x in (cash_opening_balance,cash_minimum_balance,cash_inflows_by_period,cash_outflows_by_period,collection_lag_by_demand,collection_fraction_by_demand,credit_limit)) or credit_enabled
    cash_opening_balance=0.0 if cash_opening_balance is None else cash_opening_balance
    cash_inflows_by_period=cash_inflows_by_period or {}
    cash_outflows_by_period=cash_outflows_by_period or {}
    collection_lag_by_demand=collection_lag_by_demand or {}
    collection_fraction_by_demand=collection_fraction_by_demand or {}
    credit_draw_limits_by_period=credit_draw_limits_by_period or {}
    credit_repayment_limits_by_period=credit_repayment_limits_by_period or {}
    credit_interest_rates_by_period=credit_interest_rates_by_period or {}
    credit_borrowing_base_by_period=credit_borrowing_base_by_period or {}
    if credit_enabled:
        if terminal_credit_balance_limit is not None and (not math.isfinite(terminal_credit_balance_limit)
            or terminal_credit_balance_limit<0 or terminal_credit_balance_limit>credit_limit):
            raise ValueError("terminal_credit_balance_limit must be between zero and credit_limit")
        if credit_maturity_period is not None and (not isinstance(credit_maturity_period,int)
            or credit_maturity_period<0 or credit_maturity_period>=horizon_periods):
            raise ValueError("credit_maturity_period must be an integer inside the planning horizon")
        if set(credit_borrowing_base_by_period)-set(range(horizon_periods)):
            raise ValueError("credit_borrowing_base_by_period contains period outside horizon")
        for period,amount in credit_borrowing_base_by_period.items():
            if not math.isfinite(amount) or amount<0 or amount>credit_limit:
                raise ValueError(f"Invalid borrowing base for period {period}")
        if not math.isfinite(credit_limit) or credit_limit<0: raise ValueError("credit_limit must be finite and non-negative")
        if not math.isfinite(credit_opening_balance) or credit_opening_balance<0 or credit_opening_balance>credit_limit:
            raise ValueError("credit_opening_balance must be between zero and credit_limit")
        for name,values in (("credit_draw_limits_by_period",credit_draw_limits_by_period),
            ("credit_repayment_limits_by_period",credit_repayment_limits_by_period),
            ("credit_interest_rates_by_period",credit_interest_rates_by_period)):
            if set(values)-set(range(horizon_periods)): raise ValueError(f"{name} contains period outside horizon")
            for period,value in values.items():
                if not math.isfinite(value) or value<0: raise ValueError(f"Invalid {name} value for period {period}")
        if any(v>credit_limit for v in credit_draw_limits_by_period.values()):
            raise ValueError("Per-period credit draw limit cannot exceed facility limit")
        if any(v>credit_limit for v in credit_repayment_limits_by_period.values()):
            raise ValueError("Per-period repayment limit cannot exceed facility limit")
    elif credit_opening_balance or credit_draw_limits_by_period or credit_repayment_limits_by_period or credit_interest_rates_by_period or terminal_credit_balance_limit is not None:
        raise ValueError("Credit terms require credit_limit")
    if not math.isfinite(cash_opening_balance) or cash_opening_balance<0:
        raise ValueError("cash_opening_balance must be finite and non-negative")
    if set(cash_inflows_by_period)-set(range(horizon_periods)):
        raise ValueError("cash_inflows_by_period contains period outside horizon")
    for period,amount in cash_inflows_by_period.items():
        if not math.isfinite(amount) or amount<0: raise ValueError(f"Invalid cash inflow for period {period}")
    if set(cash_outflows_by_period)-set(range(horizon_periods)):
        raise ValueError("cash_outflows_by_period contains period outside horizon")
    for period,amount in cash_outflows_by_period.items():
        if not math.isfinite(amount) or amount<0: raise ValueError(f"Invalid cash outflow for period {period}")
    if set(collection_lag_by_demand)-{d.demand_id for d in demand_rows}:
        raise ValueError("collection_lag_by_demand contains unknown demand_id")
    if set(collection_fraction_by_demand)-{d.demand_id for d in demand_rows}:
        raise ValueError("collection_fraction_by_demand contains unknown demand_id")
    for demand_id,lag in collection_lag_by_demand.items():
        if not isinstance(lag,int) or lag<0: raise ValueError(f"Collection lag for {demand_id} must be a non-negative integer")
    for demand_id,fraction in collection_fraction_by_demand.items():
        if not math.isfinite(fraction) or not 0<=fraction<=1:
            raise ValueError(f"Collection fraction for {demand_id} must be in [0,1]")
    if isinstance(cash_minimum_balance,dict):
        if set(cash_minimum_balance)-set(range(horizon_periods)):
            raise ValueError("cash_minimum_balance contains period outside horizon")
        for period,amount in cash_minimum_balance.items():
            if not math.isfinite(amount) or amount<0: raise ValueError(f"Invalid minimum cash for period {period}")
    elif cash_minimum_balance is not None and (not math.isfinite(cash_minimum_balance) or cash_minimum_balance<0):
        raise ValueError("cash_minimum_balance must be finite and non-negative")
    if set(batch_costs)-set(rmap): raise ValueError("batch_costs contains unknown recipe_id")
    for k,v in batch_costs.items():
        if not math.isfinite(v) or v<0: raise ValueError(f"Invalid batch cost for {k}")
    for k,v in holding_costs.items():
        if not math.isfinite(v) or v<0: raise ValueError(f"Invalid holding cost for {k}")
    if any(d.currency!=objective_currency for d in demand_rows):
        raise ValueError("All planning demand values must use objective_currency")
    if any(d.due_period>=horizon_periods for d in demand_rows):
        raise ValueError("Demand due_period must be inside the planning horizon")

    product_units={}
    def register(product,unit):
        old=product_units.setdefault(product,unit)
        if old!=unit: raise ValueError(f"Product unit mismatch for {product}: {old} != {unit}")
    for r in recipe_rows:
        register(r.output_product_id,r.output_unit)
        for x in r.input_requirements: register(x.product_id,x.unit)
    for x in receipts: register(x.product_id,x.unit)
    for d in demand_rows: register(d.product_id,d.unit)
    products=sorted(product_units)
    if set(minimum_inventory)-set(products): raise ValueError("minimum_inventory contains unknown product_id")
    if set(storage_limits)-set(products): raise ValueError("storage_limits contains unknown product_id")
    if set(holding_costs)-set(products): raise ValueError("holding_costs contains unknown product_id")
    for p,v in minimum_inventory.items():
        if not math.isfinite(v) or v<0: raise ValueError(f"Invalid minimum inventory for {p}")
    for p,v in storage_limits.items():
        if not math.isfinite(v) or v<0: raise ValueError(f"Invalid storage limit for {p}")
        if v<minimum_inventory.get(p,0.0): raise ValueError(f"Storage limit below safety stock for {p}")
    for cap in caps:
        try: cap_period=int(cap.period)
        except (TypeError,ValueError) as exc: raise ValueError(f"Resource capacity period must be an integer bucket: {cap.period}") from exc
        if str(cap_period)!=cap.period or cap_period<0 or cap_period>=horizon_periods:
            raise ValueError(f"Resource capacity period outside planning horizon: {cap.period}")
    capmap={(c.resource_id,c.period):c for c in caps}
    receipt_qty={}; excluded_receipts=[]; out_of_horizon_receipts=[]
    for x in receipts:
        if x.available_period>=horizon_periods:
            out_of_horizon_receipts.append(x.receipt_id); continue
        if x.status not in {"OBSERVED","COMMITTED"}:
            excluded_receipts.append(x.receipt_id); continue
        key=(x.product_id,x.available_period)
        receipt_qty[key]=receipt_qty.get(key,0.0)+x.quantity

    x_keys=[]
    blocked=[]
    for rid,r in sorted(rmap.items()):
        for period in range(horizon_periods):
            if period+r.lead_time_periods>=horizon_periods: continue
            firm=True
            for req in r.resource_requirements:
                cap=capmap.get((req.resource_id,str(period)))
                if cap is None or cap.status not in {"OBSERVED","COMMITTED"}:
                    firm=False; blocked.append({"recipe_id":rid,"period":period,"resource_id":req.resource_id,"reason":"NO_FIRM_CAPACITY"})
                    break
                if cap.unit!=req.unit: raise ValueError(f"Resource unit mismatch for {req.resource_id} in period {period}")
            x_keys.append((rid,period,batch_limits[rid] if firm else 0))
    # Variables: integer batch decisions, end-period inventory, fulfilled demand.
    x_index={}; upper=[]; integrality=[]; objective=[]
    for rid,period,limit in x_keys:
        x_index[(rid,period)]=len(upper); upper.append(limit); integrality.append(1)
        objective.append(batch_costs.get(rid,0.0)+1e-8)
    y_index={}
    for d in demand_rows:
        y_index[d.demand_id]=len(upper); upper.append(d.quantity); integrality.append(0)
        objective.append(-d.unit_value*d.priority_weight)
    inv_index={}
    for p in products:
        for period in range(horizon_periods):
            inv_index[(p,period)]=len(upper); upper.append(storage_limits.get(p,math.inf)); integrality.append(0)
            objective.append(holding_costs.get(p,0.0))
    cash_index={}
    if cash_enabled:
        for period in range(horizon_periods):
            cash_index[period]=len(upper); upper.append(math.inf); integrality.append(0)
            objective.append(0.0)
    credit_draw_index={}; credit_repay_index={}; credit_balance_index={}
    if credit_enabled:
        for period in range(horizon_periods):
            credit_draw_index[period]=len(upper)
            upper.append(credit_draw_limits_by_period.get(period,credit_limit)); integrality.append(0); objective.append(0.0)
            credit_repay_index[period]=len(upper)
            upper.append(credit_repayment_limits_by_period.get(period,credit_limit)); integrality.append(0); objective.append(0.0)
            credit_balance_index[period]=len(upper)
            upper.append(credit_limit); integrality.append(0)
            next_rate=credit_interest_rates_by_period.get(period+1,0.0)
            objective.append(next_rate)
    nvars=len(upper); lower=np.zeros(nvars); upper=np.asarray(upper,dtype=float)
    for p in products:
        for period in range(horizon_periods):
            lower[inv_index[(p,period)]]=minimum_inventory.get(p,0.0)
    if cash_enabled:
        for period in range(horizon_periods):
            minimum=(cash_minimum_balance.get(period,0.0) if isinstance(cash_minimum_balance,dict)
                else (cash_minimum_balance or 0.0))
            lower[cash_index[period]]=minimum
    rows=[]; cols=[]; vals=[]; row_lb=[]; row_ub=[]; row_names=[]
    def add_constraint(coeffs,lb,ub,name):
        row=len(row_lb); row_names.append(name); row_lb.append(lb); row_ub.append(ub)
        for idx,val in coeffs.items():
            if abs(val)>1e-14: rows.append(row); cols.append(idx); vals.append(val)
    # Inventory conservation per product and period:
    # ending inventory - prior inventory + inputs - completed outputs + fulfilled demand = receipts.
    for p in products:
        for period in range(horizon_periods):
            coeff={inv_index[(p,period)]:1.0}
            if period>0: coeff[inv_index[(p,period-1)]]=-1.0
            for rid,r in rmap.items():
                for req in r.input_requirements:
                    if req.product_id==p:
                        idx=x_index.get((rid,period))
                        if idx is not None: coeff[idx]=coeff.get(idx,0.0)+req.quantity_per_batch
                start=period-r.lead_time_periods
                if start>=0:
                    idx=x_index.get((rid,start))
                    if idx is not None and r.output_product_id==p:
                        coeff[idx]=coeff.get(idx,0.0)-r.output_quantity_per_batch
            for d in demand_rows:
                if d.product_id==p and d.due_period==period:
                    coeff[y_index[d.demand_id]]=1.0
            add_constraint(coeff,receipt_qty.get((p,period),0.0),receipt_qty.get((p,period),0.0),f"inventory::{p}::{period}")
    # Shared resource capacity across all recipes in each period.
    resource_keys=sorted({(req.resource_id,period) for r in recipe_rows for req in r.resource_requirements for period in range(horizon_periods)})
    for resource,period in resource_keys:
        cap=capmap.get((resource,str(period)))
        if cap is None or cap.status not in {"OBSERVED","COMMITTED"}: continue
        coeff={}
        for rid,r in rmap.items():
            idx=x_index.get((rid,period))
            if idx is None: continue
            for req in r.resource_requirements:
                if req.resource_id==resource:
                    if req.unit!=cap.unit: raise ValueError(f"Resource unit mismatch for {resource} in period {period}")
                    coeff[idx]=coeff.get(idx,0.0)+req.quantity_per_batch
        if coeff: add_constraint(coeff,-math.inf,cap.available_quantity,f"resource::{resource}::{period}")
    deferred_collections=[]
    if cash_enabled:
        # Cash is paid for production at start period and inventory holding at
        # period end. Demand value enters cash only at the modeled collection period.
        for d in demand_rows:
            collection_period=d.due_period+collection_lag_by_demand.get(d.demand_id,0)
            if collection_period>=horizon_periods:
                deferred_collections.append(d.demand_id)
        for period in range(horizon_periods):
            coeff={cash_index[period]:1.0}
            if period>0: coeff[cash_index[period-1]]=-1.0
            for rid,r in rmap.items():
                idx=x_index.get((rid,period))
                if idx is not None and batch_costs.get(rid,0.0):
                    coeff[idx]=coeff.get(idx,0.0)+batch_costs.get(rid,0.0)
            for p in products:
                cost=holding_costs.get(p,0.0)
                if cost: coeff[inv_index[(p,period)]]=coeff.get(inv_index[(p,period)],0.0)+cost
            for d in demand_rows:
                collection_period=d.due_period+collection_lag_by_demand.get(d.demand_id,0)
                if collection_period==period:
                    cash_value=d.unit_value*collection_fraction_by_demand.get(d.demand_id,1.0)
                    coeff[y_index[d.demand_id]]=coeff.get(y_index[d.demand_id],0.0)-cash_value
            if credit_enabled:
                coeff[credit_draw_index[period]]=coeff.get(credit_draw_index[period],0.0)-1.0
                coeff[credit_repay_index[period]]=coeff.get(credit_repay_index[period],0.0)+1.0
                rate=credit_interest_rates_by_period.get(period,0.0)
                if period>0 and rate:
                    coeff[credit_balance_index[period-1]]=coeff.get(credit_balance_index[period-1],0.0)+rate
            interest_on_opening_debt=(credit_interest_rates_by_period.get(0,0.0)*credit_opening_balance if credit_enabled and period==0 else 0.0)
            rhs=(cash_inflows_by_period.get(period,0.0)-cash_outflows_by_period.get(period,0.0)
                +(cash_opening_balance if period==0 else 0.0)-interest_on_opening_debt)
            add_constraint(coeff,rhs,rhs,f"cash_balance::{period}")
    if credit_enabled:
        for period in range(horizon_periods):
            coeff={credit_balance_index[period]:1.0,credit_draw_index[period]:-1.0,credit_repay_index[period]:1.0}
            if period>0: coeff[credit_balance_index[period-1]]=-1.0
            rhs=credit_opening_balance if period==0 else 0.0
            add_constraint(coeff,rhs,rhs,f"credit_balance::{period}")
            repay_cap={credit_repay_index[period]:1.0}
            if period>0:
                repay_cap[credit_balance_index[period-1]]=-1.0
                add_constraint(repay_cap,-math.inf,0.0,f"credit_repay_prior_balance::{period}")
            else:
                add_constraint(repay_cap,-math.inf,credit_opening_balance,f"credit_repay_prior_balance::{period}")
    if credit_enabled:
        for period,borrowing_base in credit_borrowing_base_by_period.items():
            add_constraint({credit_balance_index[period]:1.0},-math.inf,borrowing_base,
                f"credit_borrowing_base::{period}")
    if credit_enabled and terminal_credit_balance_limit is not None:
        add_constraint({credit_balance_index[horizon_periods-1]:1.0},-math.inf,
            terminal_credit_balance_limit,"terminal_credit_balance_limit")
    if credit_enabled and credit_maturity_period is not None:
        for period in range(credit_maturity_period,horizon_periods):
            add_constraint({credit_balance_index[period]:1.0},0.0,0.0,
                f"credit_maturity_repayment::{period}")
    matrix=coo_matrix((vals,(rows,cols)),shape=(len(row_lb),nvars)).tocsr()
    constraints=LinearConstraint(matrix,np.asarray(row_lb),np.asarray(row_ub))
    result=milp(c=np.asarray(objective),integrality=np.asarray(integrality),
        bounds=Bounds(lower,upper),constraints=constraints,
        options={"mip_rel_gap":mip_rel_gap,"time_limit":time_limit_seconds})
    if result.x is None:
        return {"feasible":False,"optimality_proven":False,"solver_status":int(result.status),
            "solver_message":str(result.message),"schedule":[],"demand":[],"inventory":[],"resource_usage":[],
            "excluded_nonfirm_receipts":excluded_receipts,"out_of_horizon_receipts":out_of_horizon_receipts,
            "blocked_recipe_periods":blocked,"objective_currency":objective_currency}
    sol=result.x
    schedule=[]
    for (rid,period,limit),idx in zip(x_keys,[x_index[k[:2]] for k in x_keys]):
        batches=int(round(sol[idx]))
        if batches:
            r=rmap[rid]; schedule.append({"recipe_id":rid,"start_period":period,
                "finish_period":period+r.lead_time_periods,"batch_count":batches,
                "output_product_id":r.output_product_id,"output_quantity":batches*r.output_quantity_per_batch})
    demand_report=[]
    served_value=0.0
    for d in demand_rows:
        fulfilled=max(0.0,min(d.quantity,float(sol[y_index[d.demand_id]])))
        value=fulfilled*d.unit_value*d.priority_weight; served_value+=value
        demand_report.append({"demand_id":d.demand_id,"product_id":d.product_id,"requested":d.quantity,
            "fulfilled":fulfilled,"shortfall":d.quantity-fulfilled,"unit":d.unit,
            "fulfillment_rate":fulfilled/d.quantity,"value_contribution":value,"currency":d.currency})
    inventory_report=[]; holding_cost_total=0.0
    for p in products:
        for period in range(horizon_periods):
            qty=max(0.0,float(sol[inv_index[(p,period)]]))
            cost=qty*holding_costs.get(p,0.0); holding_cost_total+=cost
            inventory_report.append({"product_id":p,"period":period,"ending_quantity":qty,"unit":product_units[p],"holding_cost":cost,
                "minimum_inventory":minimum_inventory.get(p,0.0),"storage_limit":storage_limits.get(p)})
    production_cost_total=sum(x["batch_count"]*batch_costs.get(x["recipe_id"],0.0) for x in schedule)
    resource_usage=[]
    for resource,period in resource_keys:
        used=0.0; unit=None
        for x in schedule:
            if x["start_period"]!=period: continue
            r=rmap[x["recipe_id"]]
            for req in r.resource_requirements:
                if req.resource_id==resource: used+=req.quantity_per_batch*x["batch_count"]; unit=req.unit
        if used:
            cap=capmap.get((resource,str(period)))
            resource_usage.append({"resource_id":resource,"period":period,"used":used,
                "available":cap.available_quantity if cap else 0.0,"unit":unit,
                "utilization":used/cap.available_quantity if cap and cap.available_quantity else None})
    ending_cash=([max(0.0,float(sol[cash_index[t]])) for t in range(horizon_periods)] if cash_enabled else None)
    credit_draws=([max(0.0,float(sol[credit_draw_index[t]])) for t in range(horizon_periods)] if credit_enabled else [])
    credit_repayments=([max(0.0,float(sol[credit_repay_index[t]])) for t in range(horizon_periods)] if credit_enabled else [])
    credit_balances=([max(0.0,float(sol[credit_balance_index[t]])) for t in range(horizon_periods)] if credit_enabled else [])
    interest_costs=([credit_opening_balance*credit_interest_rates_by_period.get(0,0.0)]+[
        credit_balances[t-1]*credit_interest_rates_by_period.get(t,0.0) for t in range(1,horizon_periods)] if credit_enabled else [])
    total_interest=sum(interest_costs)
    return {"feasible":True,"optimality_proven":int(result.status)==0,"solver_status":int(result.status),
        "solver_message":str(result.message),"objective_currency":objective_currency,
        "objective_value":served_value-production_cost_total-holding_cost_total-total_interest,
        "served_value":served_value,"production_cost":production_cost_total,"holding_cost":holding_cost_total,
        "schedule":schedule,"demand":demand_report,"inventory":inventory_report,
        "resource_usage":resource_usage,"ending_cash_by_period":ending_cash,
        "deferred_collection_demands":deferred_collections if cash_enabled else [],
        "cash_constraint_enabled":cash_enabled,
        "credit_facility":{"enabled":credit_enabled,"facility_limit":credit_limit if credit_enabled else None,
            "opening_balance":credit_opening_balance if credit_enabled else None,"draws_by_period":credit_draws,
            "repayments_by_period":credit_repayments,"ending_balance_by_period":credit_balances,
            "interest_cost_by_period":interest_costs,"total_interest_cost":total_interest,
            "repayment_cannot_exceed_prior_period_balance":True,
            "terminal_balance_limit":terminal_credit_balance_limit},
        "cash_model":{"opening_balance":cash_opening_balance if cash_enabled else None,
            "minimum_balance":cash_minimum_balance if cash_enabled else None,
            "exogenous_inflows":cash_inflows_by_period if cash_enabled else {},
            "committed_outflows":cash_outflows_by_period if cash_enabled else {},
            "collection_lags":collection_lag_by_demand if cash_enabled else {},
            "collection_fractions":collection_fraction_by_demand if cash_enabled else {},
            "production_cost_paid_at_start_period":True,
            "holding_cost_paid_at_end_period":True,
            "cash_receipts_are_scenario_assumptions_not_bank_reconciled_actuals":True},
        "excluded_nonfirm_receipts":excluded_receipts,
        "out_of_horizon_receipts":out_of_horizon_receipts,"blocked_recipe_periods":blocked,
        "mip_gap":float(result.mip_gap) if getattr(result,"mip_gap",None) is not None else None,
        "assumptions":{"integer_batches":True,"discrete_periods":True,"firm_capacity_only":True,
            "nonfirm_receipts_excluded":True,"no_backorders":True,"no_inventory_expiry":True,
            "no_transport_constraints":True,"storage_limits_enforced_at_period_end":True,
            "minimum_inventory_enforced_at_period_end":True,
            "economic_values_are_scenario_inputs_not_observed_cash":True},
        "inventory_policy":{"minimum_inventory":minimum_inventory,"storage_limits":storage_limits}}
