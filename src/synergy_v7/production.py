"""Deterministic time-expanded material/resource feasibility evaluator.

This is a plan validator, not an optimizer. Orders are evaluated in stable ID
order; a solver may later search over alternative schedules and call this kernel
as its feasibility oracle.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math

from .core import ResourceCapacity


def _positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class MaterialRequirement:
    product_id: str
    quantity_per_batch: float
    unit: str
    def __post_init__(self):
        if not self.product_id or not self.unit: raise ValueError("Material requirement identity and unit are required")
        _positive(self.quantity_per_batch, "quantity_per_batch")


@dataclass(frozen=True)
class ResourceRequirement:
    resource_id: str
    quantity_per_batch: float
    unit: str
    def __post_init__(self):
        if not self.resource_id or not self.unit: raise ValueError("Resource requirement identity and unit are required")
        _positive(self.quantity_per_batch, "quantity_per_batch")


@dataclass(frozen=True)
class ProductionRecipe:
    recipe_id: str
    output_product_id: str
    output_quantity_per_batch: float
    output_unit: str
    input_requirements: tuple[MaterialRequirement, ...]
    resource_requirements: tuple[ResourceRequirement, ...]
    lead_time_periods: int
    node_id: str = ""
    def __post_init__(self):
        if not all((self.recipe_id,self.output_product_id,self.output_unit)): raise ValueError("Recipe identity and output unit are required")
        _positive(self.output_quantity_per_batch, "output_quantity_per_batch")
        if not isinstance(self.lead_time_periods,int) or self.lead_time_periods < 1:
            raise ValueError("lead_time_periods must be an integer >= 1")
        for rows,label,key in ((self.input_requirements,"input","product_id"),(self.resource_requirements,"resource","resource_id")):
            ids=[getattr(x,key) for x in rows]
            if len(ids)!=len(set(ids)): raise ValueError(f"Duplicate {label} requirement in recipe {self.recipe_id}")


@dataclass(frozen=True)
class ProductionOrder:
    order_id: str
    recipe_id: str
    start_period: int
    batch_count: int
    def __post_init__(self):
        if not self.order_id or not self.recipe_id: raise ValueError("Production order identity is required")
        if not isinstance(self.start_period,int) or self.start_period < 0: raise ValueError("start_period must be a non-negative integer")
        if not isinstance(self.batch_count,int) or self.batch_count < 1: raise ValueError("batch_count must be a positive integer")


@dataclass(frozen=True)
class InventoryReceipt:
    receipt_id: str
    product_id: str
    quantity: float
    unit: str
    available_period: int
    status: str = "OBSERVED"
    def __post_init__(self):
        if not all((self.receipt_id,self.product_id,self.unit)): raise ValueError("Inventory receipt identity and unit are required")
        _positive(self.quantity, "receipt quantity")
        if not isinstance(self.available_period,int) or self.available_period < 0: raise ValueError("available_period must be a non-negative integer")
        if self.status not in {"OBSERVED","COMMITTED","UNDER_CONSTRUCTION","PLANNED","ANNOUNCED","SCENARIO"}:
            raise ValueError("Invalid inventory receipt status")


@dataclass(frozen=True)
class ProductDemand:
    demand_id: str
    product_id: str
    quantity: float
    unit: str
    due_period: int
    priority: int = 100
    def __post_init__(self):
        if not all((self.demand_id,self.product_id,self.unit)): raise ValueError("Demand identity and unit are required")
        _positive(self.quantity, "demand quantity")
        if not isinstance(self.due_period,int) or self.due_period < 0: raise ValueError("due_period must be a non-negative integer")
        if not isinstance(self.priority,int): raise ValueError("priority must be an integer")


def evaluate_production_plan(
    recipes: Iterable[ProductionRecipe],
    orders: Iterable[ProductionOrder],
    inventory_receipts: Iterable[InventoryReceipt],
    demands: Iterable[ProductDemand],
    resource_capacities: Iterable[ResourceCapacity],
    include_nonfirm_receipts: bool = False,
) -> dict:
    """Evaluate a discrete-period schedule with no implicit backorders.

    At each period: firm receipts and completed batches arrive; production orders
    start in order_id order; customer demand is served by priority then ID.
    A blocked order consumes neither materials nor resources and creates no output.
    Capacity periods are stringified integer buckets ("0", "1", ...).
    """
    recipe_rows=list(recipes); order_rows=list(orders)
    receipt_rows=list(inventory_receipts); demand_rows=list(demands); capacity_rows=list(resource_capacities)
    recipe_map={r.recipe_id:r for r in recipe_rows}
    if len(recipe_map)!=len(recipe_rows): raise ValueError("Duplicate recipe_id")
    if len({o.order_id for o in order_rows})!=len(order_rows): raise ValueError("Duplicate order_id")
    if len({r.receipt_id for r in receipt_rows})!=len(receipt_rows): raise ValueError("Duplicate receipt_id")
    if len({d.demand_id for d in demand_rows})!=len(demand_rows): raise ValueError("Duplicate demand_id")
    for o in order_rows:
        if o.recipe_id not in recipe_map: raise ValueError(f"Unknown recipe_id: {o.recipe_id}")

    product_units={}
    def register_unit(product,unit):
        old=product_units.setdefault(product,unit)
        if old!=unit: raise ValueError(f"Unit mismatch for product {product}: {old} != {unit}")
    for r in recipe_rows:
        register_unit(r.output_product_id,r.output_unit)
        for x in r.input_requirements: register_unit(x.product_id,x.unit)
    for x in receipt_rows: register_unit(x.product_id,x.unit)
    for x in demand_rows: register_unit(x.product_id,x.unit)

    cap_map={}
    for c in capacity_rows:
        key=(c.resource_id,c.period)
        if key in cap_map: raise ValueError(f"Duplicate resource capacity state: {key}")
        cap_map[key]=c

    receipts_by_period={}; orders_by_period={}; demands_by_period={}
    max_period=0; excluded_receipts=[]
    for r in receipt_rows:
        max_period=max(max_period,r.available_period)
        if r.status not in {"OBSERVED","COMMITTED"} and not include_nonfirm_receipts:
            excluded_receipts.append(r.receipt_id); continue
        receipts_by_period.setdefault(r.available_period,[]).append(r)
    for o in order_rows:
        recipe=recipe_map[o.recipe_id]; finish=o.start_period+recipe.lead_time_periods
        max_period=max(max_period,finish); orders_by_period.setdefault(o.start_period,[]).append(o)
    for d in demand_rows:
        max_period=max(max_period,d.due_period); demands_by_period.setdefault(d.due_period,[]).append(d)

    inventory={}; inventory_trace=[]; violations=[]; order_results={}
    resource_used={}; resource_unit={}
    total_completed={}; total_fulfilled={}; total_demand={}
    completions={}
    for period in range(max_period+1):
        for r in sorted(receipts_by_period.get(period,[]),key=lambda x:x.receipt_id):
            inventory[r.product_id]=inventory.get(r.product_id,0.0)+r.quantity
        for order,recipe in sorted(completions.get(period,[]),key=lambda x:x[0].order_id):
            qty=recipe.output_quantity_per_batch*order.batch_count
            inventory[recipe.output_product_id]=inventory.get(recipe.output_product_id,0.0)+qty
            total_completed[recipe.output_product_id]=total_completed.get(recipe.output_product_id,0.0)+qty

        for order in sorted(orders_by_period.get(period,[]),key=lambda x:x.order_id):
            recipe=recipe_map[order.recipe_id]; reasons=[]
            material_needs=[(x,x.quantity_per_batch*order.batch_count) for x in recipe.input_requirements]
            for req,qty in material_needs:
                available=inventory.get(req.product_id,0.0)
                if available+1e-9<qty:
                    reasons.append({"type":"MATERIAL_SHORTAGE","product_id":req.product_id,"required":qty,"available":available,"unit":req.unit})
            resource_needs=[(x,x.quantity_per_batch*order.batch_count) for x in recipe.resource_requirements]
            for req,qty in resource_needs:
                key=(req.resource_id,str(period)); cap=cap_map.get(key)
                if cap is None:
                    reasons.append({"type":"MISSING_RESOURCE_CAPACITY","resource_id":req.resource_id,"period":period})
                    continue
                if cap.unit!=req.unit:
                    reasons.append({"type":"RESOURCE_UNIT_MISMATCH","resource_id":req.resource_id,"expected":req.unit,"actual":cap.unit})
                    continue
                if cap.status not in {"OBSERVED","COMMITTED"}:
                    reasons.append({"type":"NONFIRM_RESOURCE_CAPACITY","resource_id":req.resource_id,"status":cap.status})
                    continue
                used=resource_used.get(key,0.0)
                if used+qty>cap.available_quantity+1e-9:
                    reasons.append({"type":"RESOURCE_CAPACITY_EXCEEDED","resource_id":req.resource_id,"required_total":used+qty,"available":cap.available_quantity,"unit":req.unit})
            if reasons:
                order_results[order.order_id]={"status":"BLOCKED","start_period":period,"finish_period":period+recipe.lead_time_periods,"reasons":reasons}
                violations.extend([{"order_id":order.order_id,**x} for x in reasons])
                continue
            for req,qty in material_needs: inventory[req.product_id]=inventory.get(req.product_id,0.0)-qty
            for req,qty in resource_needs:
                key=(req.resource_id,str(period)); resource_used[key]=resource_used.get(key,0.0)+qty; resource_unit[key]=req.unit
            finish=period+recipe.lead_time_periods
            completions.setdefault(finish,[]).append((order,recipe))
            order_results[order.order_id]={"status":"SCHEDULED","start_period":period,"finish_period":finish,
                "output_product_id":recipe.output_product_id,"planned_output":recipe.output_quantity_per_batch*order.batch_count}

        for demand in sorted(demands_by_period.get(period,[]),key=lambda x:(x.priority,x.demand_id)):
            total_demand[demand.product_id]=total_demand.get(demand.product_id,0.0)+demand.quantity
            available=inventory.get(demand.product_id,0.0); fulfilled=min(available,demand.quantity)
            inventory[demand.product_id]=available-fulfilled
            total_fulfilled[demand.product_id]=total_fulfilled.get(demand.product_id,0.0)+fulfilled
            if fulfilled+1e-9<demand.quantity:
                violations.append({"type":"DEMAND_SHORTFALL","demand_id":demand.demand_id,"product_id":demand.product_id,
                    "period":period,"required":demand.quantity,"fulfilled":fulfilled,"shortfall":demand.quantity-fulfilled,"unit":demand.unit})
        inventory_trace.append({"period":period,"inventory":{k:v for k,v in sorted(inventory.items())}})

    demand_summary={}
    for product,qty in sorted(total_demand.items()):
        fulfilled=total_fulfilled.get(product,0.0)
        demand_summary[product]={"demand":qty,"fulfilled":fulfilled,"shortfall":qty-fulfilled,
            "fulfillment_rate":fulfilled/qty if qty else 1.0,"unit":product_units[product]}
    resource_summary=[{"resource_id":k[0],"period":int(k[1]),"used":v,"available":cap_map[k].available_quantity,
        "unit":resource_unit[k],"utilization":v/cap_map[k].available_quantity if cap_map[k].available_quantity else None}
        for k,v in sorted(resource_used.items())]
    return {"feasible":not violations,"violations":violations,"orders":order_results,
        "demand":demand_summary,"completed_output":total_completed,"resource_usage":resource_summary,
        "inventory_trace":inventory_trace,"excluded_nonfirm_receipts":excluded_receipts,
        "assumptions":{"discrete_periods":True,"lead_time_minimum_periods":1,"backorders":False,
            "order_tie_break":"order_id ascending","demand_priority":"lower integer first, then demand_id",
            "nonfirm_receipts_included":include_nonfirm_receipts,
            "this_is_a_feasibility_evaluator_not_an_optimizer":True}}
