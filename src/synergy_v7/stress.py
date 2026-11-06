"""Monte Carlo resilience evaluation for a fixed V7.1 production schedule."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math
import numpy as np

from .core import ResourceCapacity
from .production import ProductionRecipe,ProductionOrder,InventoryReceipt,ProductDemand,evaluate_production_plan
from .ledger import empirical_cvar


@dataclass(frozen=True)
class ResourceShock:
    resource_id: str
    probability: float
    capacity_factor: float
    def __post_init__(self):
        if not self.resource_id: raise ValueError("resource_id is required")
        if not 0<=self.probability<=1 or not 0<=self.capacity_factor<=1:
            raise ValueError("resource shock probability and factor must be in [0,1]")


@dataclass(frozen=True)
class ReceiptDelay:
    receipt_id: str
    probability: float
    max_delay_periods: int
    def __post_init__(self):
        if not self.receipt_id: raise ValueError("receipt_id is required")
        if not 0<=self.probability<=1: raise ValueError("delay probability must be in [0,1]")
        if not isinstance(self.max_delay_periods,int) or self.max_delay_periods<1:
            raise ValueError("max_delay_periods must be a positive integer")


def stress_test_fixed_schedule(
    recipes: Iterable[ProductionRecipe],
    orders: Iterable[ProductionOrder],
    inventory_receipts: Iterable[InventoryReceipt],
    demands: Iterable[ProductDemand],
    resource_capacities: Iterable[ResourceCapacity],
    scenarios: int=1000,
    seed: int=42,
    common_shock_probability: float=0.0,
    common_capacity_factor: float=0.5,
    resource_shocks: Iterable[ResourceShock]=(),
    receipt_delays: Iterable[ReceiptDelay]=(),
    demand_weights: dict[str,float] | None=None,
    alpha: float=0.95,
) -> dict:
    """Replay one fixed schedule under correlated resource and supplier-delay shocks.

    This estimates conditional schedule fragility under the supplied synthetic
    shock distributions. It does not optimize recourse, infer real-world shock
    probabilities or constitute a formal CVaR-constrained solution.
    """
    if not isinstance(scenarios,int) or scenarios<1: raise ValueError("scenarios must be a positive integer")
    if not isinstance(seed,int): raise ValueError("seed must be an integer")
    if not 0<=common_shock_probability<=1 or not 0<=common_capacity_factor<=1:
        raise ValueError("common shock probability and capacity factor must be in [0,1]")
    if not 0<alpha<1: raise ValueError("alpha must be between 0 and 1")
    recipes=list(recipes); orders=list(orders); receipts=list(inventory_receipts)
    demands=list(demands); capacities=list(resource_capacities)
    shocks=list(resource_shocks); delays=list(receipt_delays)
    if len({x.resource_id for x in shocks})!=len(shocks): raise ValueError("Duplicate resource shock")
    if len({x.receipt_id for x in delays})!=len(delays): raise ValueError("Duplicate receipt delay")
    if len({x.receipt_id for x in receipts})!=len(receipts): raise ValueError("Duplicate inventory receipt")
    receipt_ids={x.receipt_id for x in receipts}; resource_ids={x.resource_id for x in capacities}
    if any(x.receipt_id not in receipt_ids for x in delays): raise ValueError("Receipt delay references unknown receipt")
    if any(x.resource_id not in resource_ids for x in shocks): raise ValueError("Resource shock references unknown capacity")
    demand_weights=demand_weights or {}
    if set(demand_weights)-{x.demand_id for x in demands}: raise ValueError("Unknown demand weight ID")
    for k,v in demand_weights.items():
        if not math.isfinite(v) or v<=0: raise ValueError(f"Demand weight for {k} must be finite and positive")
    rng=np.random.default_rng(seed)
    scores=[]; losses=[]; full_service=0; per_demand={d.demand_id:[] for d in demands}
    common_count=0; resource_shock_counts={x.resource_id:0 for x in shocks}
    delay_counts={x.receipt_id:0 for x in delays}
    for _ in range(scenarios):
        common=rng.random()<common_shock_probability
        if common: common_count+=1
        factors={}
        for shock in shocks:
            hit=rng.random()<shock.probability
            if hit: resource_shock_counts[shock.resource_id]+=1
            factors[shock.resource_id]=min(common_capacity_factor if common else 1.0,
                shock.capacity_factor if hit else 1.0)
        scenario_caps=[ResourceCapacity(c.resource_id,c.period,
            c.available_quantity*factors.get(c.resource_id,common_capacity_factor if common else 1.0),
            c.unit,c.status,c.evidence_id,c.confidence,cost if False else None) if False else
            ResourceCapacity(c.resource_id,c.period,
                c.available_quantity*factors.get(c.resource_id,common_capacity_factor if common else 1.0),
                c.unit,c.status,c.evidence_id,c.confidence,c.security_class,c.notes)
            for c in capacities]
        delayed_receipts=[]
        delay_map={x.receipt_id:x for x in delays}
        for receipt in receipts:
            delay=delay_map.get(receipt.receipt_id); extra=0
            if delay and rng.random()<delay.probability:
                extra=int(rng.integers(1,delay.max_delay_periods+1)); delay_counts[receipt.receipt_id]+=1
            delayed_receipts.append(InventoryReceipt(receipt.receipt_id,receipt.product_id,receipt.quantity,
                receipt.unit,receipt.available_period+extra,receipt.status))
        result=evaluate_production_plan(recipes,orders,delayed_receipts,demands,scenario_caps)
        lines={x["demand_id"]:x for x in result["demand_lines"]}
        weights={d.demand_id:demand_weights.get(d.demand_id,1.0) for d in demands}
        total_weight=sum(weights.values())
        score=sum(weights[k]*(lines[k]["fulfilled"]/lines[k]["requested"]) for k in lines)/total_weight if total_weight else 1.0
        scores.append(score); losses.append(1.0-score)
        if score>=1.0-1e-9: full_service+=1
        for d in demands: per_demand[d.demand_id].append(lines[d.demand_id]["fulfilled"]/lines[d.demand_id]["requested"])
    arr=np.asarray(scores,dtype=float)
    return {"scenario_count":scenarios,"seed":seed,"mean_weighted_service_level":float(arr.mean()),
        "service_level_quantiles":{"p05":float(np.quantile(arr,0.05)),"p50":float(np.quantile(arr,0.50)),"p95":float(np.quantile(arr,0.95))},
        "probability_full_demand_service":full_service/scenarios,
        "mean_service_shortfall":float(np.mean(losses)),"empirical_cvar_service_shortfall":empirical_cvar(losses,alpha),
        "cvar_alpha":alpha,"per_demand_mean_service":{k:float(np.mean(v)) for k,v in per_demand.items()},
        "common_shock_count":common_count,"resource_shock_counts":resource_shock_counts,
        "receipt_delay_counts":delay_counts,
        "shock_assumptions":{"common_shock_probability":common_shock_probability,
            "common_capacity_factor":common_capacity_factor,
            "resource_shocks":[{"resource_id":x.resource_id,"probability":x.probability,"capacity_factor":x.capacity_factor} for x in shocks],
            "receipt_delays":[{"receipt_id":x.receipt_id,"probability":x.probability,"max_delay_periods":x.max_delay_periods} for x in delays]},
        "interpretation":"Conditional Monte Carlo schedule stress; not calibrated real-world probabilities or a CVaR-constrained optimizer."}
