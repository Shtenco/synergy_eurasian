"""Scenario-wise adaptive recourse evaluation for SYNERGY V7.7.

This is a wait-and-see scenario evaluator, not a non-anticipative stochastic MILP.
Each scenario is re-optimized independently after its shock is revealed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
import math
from typing import Any, Iterable
from .planner_cli import evaluate_document


@dataclass(frozen=True)
class EconomicShockScenario:
    scenario_id: str
    probability: float
    resource_capacity_multipliers: dict[str,float]=field(default_factory=dict)
    demand_quantity_multipliers: dict[str,float]=field(default_factory=dict)
    inventory_receipt_quantity_multipliers: dict[str,float]=field(default_factory=dict)
    cash_inflow_multipliers: dict[str,float]=field(default_factory=dict)
    cash_outflow_multipliers: dict[str,float]=field(default_factory=dict)
    supplier_payment_multipliers: dict[str,float]=field(default_factory=dict)
    receivable_collateral_multipliers: dict[str,float]=field(default_factory=dict)
    inventory_collateral_multipliers: dict[str,float]=field(default_factory=dict)
    credit_borrowing_base_multipliers: dict[str,float]=field(default_factory=dict)

    def __post_init__(self):
        if not self.scenario_id: raise ValueError("scenario_id is required")
        if not math.isfinite(self.probability) or not 0<=self.probability<=1:
            raise ValueError("scenario probability must be in [0,1]")
        for name in ("resource_capacity_multipliers","demand_quantity_multipliers",
                     "inventory_receipt_quantity_multipliers","cash_inflow_multipliers",
                     "cash_outflow_multipliers","supplier_payment_multipliers",
                     "receivable_collateral_multipliers","inventory_collateral_multipliers",
                     "credit_borrowing_base_multipliers"):
            for key,value in getattr(self,name).items():
                if not key or not math.isfinite(value) or value<0:
                    raise ValueError(f"{name} values must have non-empty keys and finite non-negative multipliers")


def _scale_rows(rows:list[dict], id_field:str, multipliers:dict[str,float], value_field:str):
    known=set()
    for row in rows:
        key=row[id_field]; known.add(key)
        factor=multipliers.get(key,1.0)
        row[value_field]*=factor
    unknown=set(multipliers)-known
    if unknown: raise ValueError(f"Unknown {id_field} multiplier keys: {sorted(unknown)}")


def _scale_period_map(document:dict, field_name:str, multipliers:dict[str,float]):
    values=document.get(field_name,{})
    for period,factor in multipliers.items():
        key=str(period)
        if key not in values and int(period) not in values:
            # A multiplier for an absent cash flow is harmless and remains zero.
            continue
        actual_key=key if key in values else int(period)
        values[actual_key]*=factor
    document[field_name]=values


def apply_scenario(base_document:dict, scenario:EconomicShockScenario)->dict:
    doc=deepcopy(base_document)
    _scale_rows(doc.get("resource_capacities",[]),"resource_id",{}, "available_quantity")
    resource_multipliers=scenario.resource_capacity_multipliers
    for row in doc.get("resource_capacities",[]):
        period=str(row.get("period",""))
        factor=resource_multipliers.get(f"{row['resource_id']}@{period}",
            resource_multipliers.get(row["resource_id"],1.0))
        row["available_quantity"]*=factor
    _scale_rows(doc.get("demands",[]),"demand_id",scenario.demand_quantity_multipliers,"quantity")
    _scale_rows(doc.get("inventory_receipts",[]),"receipt_id",scenario.inventory_receipt_quantity_multipliers,"quantity")
    _scale_period_map(doc,"cash_inflows_by_period",scenario.cash_inflow_multipliers)
    _scale_period_map(doc,"cash_outflows_by_period",scenario.cash_outflow_multipliers)
    _scale_rows(doc.get("supplier_payment_commitments",[]),"payment_id",scenario.supplier_payment_multipliers,"amount")
    _scale_rows(doc.get("receivable_collateral",[]),"receivable_id",scenario.receivable_collateral_multipliers,"outstanding_amount")
    _scale_rows(doc.get("inventory_collateral",[]),"lot_id",scenario.inventory_collateral_multipliers,"carrying_value")
    if scenario.credit_borrowing_base_multipliers:
        base=doc.setdefault("credit_borrowing_base_by_period",{})
        for period,factor in scenario.credit_borrowing_base_multipliers.items():
            key=str(period)
            if key in base: base[key]*=factor
            elif int(period) in base: base[int(period)]*=factor
            else: base[key]=0.0
    return doc


def weighted_cvar(losses:list[tuple[float,float]],alpha:float)->dict:
    """Exact discrete Rockafellar-Uryasev CVaR for finite scenario losses."""
    if not 0<alpha<1: raise ValueError("alpha must be in (0,1)")
    if not losses: raise ValueError("At least one scenario loss is required")
    candidates=sorted({loss for loss,_ in losses})
    evaluated=[]
    for eta in candidates:
        value=eta+sum(prob*max(loss-eta,0.0) for loss,prob in losses)/(1-alpha)
        evaluated.append((value,eta))
    cvar,threshold=min(evaluated,key=lambda x:(x[0],x[1]))
    return {"cvar":cvar,"var_threshold":threshold,"confidence_level":alpha}


def evaluate_scenario_set(base_document:dict,scenarios:Iterable[EconomicShockScenario|dict],
                          risk_alpha:float=0.95,risk_weight:float=0.5)->dict:
    rows=[x if isinstance(x,EconomicShockScenario) else EconomicShockScenario(**x) for x in scenarios]
    if not rows: raise ValueError("At least one scenario is required")
    if len({x.scenario_id for x in rows})!=len(rows): raise ValueError("Duplicate scenario_id")
    total=sum(x.probability for x in rows)
    if not math.isclose(total,1.0,rel_tol=0,abs_tol=1e-9):
        raise ValueError(f"Scenario probabilities must sum to 1.0, got {total}")
    if not 0<risk_alpha<1: raise ValueError("risk_alpha must be in (0,1)")
    if not math.isfinite(risk_weight) or not 0<=risk_weight<=1:
        raise ValueError("risk_weight must be in [0,1]")
    baseline=evaluate_document(deepcopy(base_document))
    if not baseline.get("feasible") or not baseline.get("optimality_proven"):
        raise RuntimeError("Baseline plan must be feasible and proven optimal before scenario comparison")
    scenario_results=[]
    for scenario in rows:
        altered=apply_scenario(base_document,scenario)
        result=evaluate_document(altered)
        feasible=bool(result.get("feasible"))
        proven=bool(result.get("optimality_proven"))
        row={"scenario_id":scenario.scenario_id,"probability":scenario.probability,
             "feasible":feasible,"optimality_proven":proven,"solver_status":result.get("solver_status"),
             "solver_message":result.get("solver_message")}
        if feasible:
            objective=float(result["objective_value"])
            baseline_objective=float(baseline["objective_value"])
            loss=max(0.0,baseline_objective-objective)
            shortfall_value=sum(x["shortfall"]*x["unit_value"]*x.get("priority_weight",1.0)
                                for x in result["demand"])
            row.update({"objective_value":objective,"baseline_objective_value":baseline_objective,
                "objective_delta":objective-baseline_objective,"loss_vs_baseline":loss,
                "served_value":result["served_value"],"unserved_demand_value":shortfall_value,
                "production_cost":result["production_cost"],"holding_cost":result["holding_cost"],
                "interest_cost":result["credit_facility"]["total_interest_cost"],
                "schedule":result["schedule"],"ending_cash_by_period":result["ending_cash_by_period"],
                "ending_credit_balance_by_period":result["credit_facility"]["ending_balance_by_period"]})
        scenario_results.append(row)
    complete=all(x["feasible"] and x["optimality_proven"] for x in scenario_results)
    metrics=None
    if complete:
        losses=[(x["loss_vs_baseline"],x["probability"]) for x in scenario_results]
        expected_loss=sum(loss*prob for loss,prob in losses)
        cvar=weighted_cvar(losses,risk_alpha)
        expected_objective=sum(x["objective_value"]*x["probability"] for x in scenario_results)
        metrics={"expected_loss_vs_baseline":expected_loss,"expected_objective_value":expected_objective,
            "cvar_loss":cvar["cvar"],"var_loss_threshold":cvar["var_threshold"],
            "risk_alpha":risk_alpha,"risk_weight":risk_weight,
            "mean_cvar_loss":(1-risk_weight)*expected_loss+risk_weight*cvar["cvar"],
            "worst_scenario_loss":max(x["loss_vs_baseline"] for x in scenario_results),
            "probability_weighted_loss":expected_loss}
    return {"model":"SYNERGY_V7_7_SCENARIO_RECOURSE_EVALUATOR",
        "baseline":{"objective_value":baseline["objective_value"],"served_value":baseline["served_value"],
            "production_cost":baseline["production_cost"],"schedule":baseline["schedule"]},
        "scenarios":scenario_results,"risk_metrics":metrics,"complete":complete,
        "decision_timing":"WAIT_AND_SEE_INDEPENDENT_SCENARIO_REOPTIMIZATION",
        "non_anticipativity_enforced":False,
        "formal_two_stage_stochastic_milp":False,
        "interpretation":"Scenario-specific reoptimization is a wait-and-see recourse benchmark, not a deployable policy chosen before uncertainty is observed. Do not interpret its expected value as an implementable policy value."}
