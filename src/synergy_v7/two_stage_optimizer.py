"""Small, explicit two-stage non-anticipative MILP prototype for SYNERGY V7.8.

One product / one planning epoch. Shared first-stage commitment x is chosen
before scenario realization. Production, emergency procurement and lost sales
are scenario-specific recourse variables. This is a formal stochastic MILP for
this deliberately narrow prototype, not yet the full recipe-network optimizer.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


@dataclass(frozen=True)
class TwoStageScenario:
    scenario_id:str
    probability:float
    demand_quantity:int
    available_capacity:int
    def __post_init__(self):
        if not self.scenario_id: raise ValueError("scenario_id is required")
        if not math.isfinite(self.probability) or not 0<=self.probability<=1: raise ValueError("probability must be in [0,1]")
        for name in ("demand_quantity","available_capacity"):
            value=getattr(self,name)
            if not isinstance(value,int) or value<0: raise ValueError(f"{name} must be a non-negative integer")


def _validate_scenarios(scenarios):
    rows=[x if isinstance(x,TwoStageScenario) else TwoStageScenario(**x) for x in scenarios]
    if not rows: raise ValueError("At least one scenario is required")
    if len({x.scenario_id for x in rows})!=len(rows): raise ValueError("Duplicate scenario_id")
    total=sum(x.probability for x in rows)
    if not math.isclose(total,1.0,rel_tol=0,abs_tol=1e-9):
        raise ValueError(f"Scenario probabilities must sum to 1.0, got {total}")
    return rows


def _weighted_cvar(losses,alpha):
    candidates=sorted({float(loss) for loss,_ in losses})
    values=[(eta+sum(p*max(loss-eta,0.0) for loss,p in losses)/(1-alpha),eta) for eta in candidates]
    value,threshold=min(values,key=lambda x:(x[0],x[1]))
    return value,threshold


def _solve(scenarios,precommit_capacity,precommit_unit_cost,production_unit_cost,
           emergency_unit_cost,lost_sales_penalty,risk_alpha,risk_weight,
           mip_rel_gap,time_limit_seconds):
    n=len(scenarios)
    x=0
    p0=1
    e0=1+n
    u0=1+2*n
    eta=1+3*n
    z0=2+3*n
    nvars=2+4*n
    objective=np.zeros(nvars)
    integrality=np.zeros(nvars,dtype=int)
    lower=np.zeros(nvars); upper=np.full(nvars,np.inf)
    upper[x]=precommit_capacity; integrality[x]=1
    objective[x]=precommit_unit_cost
    for s,row in enumerate(scenarios):
        p=p0+s; e=e0+s; u=u0+s; z=z0+s
        upper[p]=min(precommit_capacity,row.available_capacity)
        upper[e]=row.demand_quantity; upper[u]=row.demand_quantity
        integrality[p]=integrality[e]=integrality[u]=1
        probability=row.probability
        objective[p]=(1-risk_weight)*probability*production_unit_cost
        objective[e]=(1-risk_weight)*probability*emergency_unit_cost
        objective[u]=(1-risk_weight)*probability*lost_sales_penalty
        objective[z]=risk_weight*probability/(1-risk_alpha)
    lower[eta]=-np.inf
    objective[eta]=risk_weight
    rows=[]; cols=[]; vals=[]; lb=[]; ub=[]
    def constraint(coefficients,lo,hi):
        index=len(lb)
        for col,value in coefficients.items():
            if value: rows.append(index); cols.append(col); vals.append(value)
        lb.append(lo); ub.append(hi)
    for s,row in enumerate(scenarios):
        p=p0+s; e=e0+s; u=u0+s; z=z0+s
        constraint({p:1,x:-1},-np.inf,0)                 # scenario production <= common commitment
        constraint({p:1},-np.inf,row.available_capacity) # realized capacity shock
        constraint({p:1,e:1,u:1},row.demand_quantity,row.demand_quantity)
        # Recourse cost_s - eta - excess_s <= 0
        constraint({p:production_unit_cost,e:emergency_unit_cost,
                    u:lost_sales_penalty,eta:-1,z:-1},-np.inf,0)
    matrix=coo_matrix((vals,(rows,cols)),shape=(len(lb),nvars)).tocsr()
    result=milp(c=objective,integrality=integrality,bounds=Bounds(lower,upper),
        constraints=LinearConstraint(matrix,np.asarray(lb),np.asarray(ub)),
        options={"mip_rel_gap":mip_rel_gap,"time_limit":time_limit_seconds})
    if result.x is None:
        return {"feasible":False,"optimality_proven":False,"solver_status":int(result.status),
            "solver_message":str(result.message)}
    sol=result.x
    recourse=[]
    losses=[]
    for s,row in enumerate(scenarios):
        prod=int(round(sol[p0+s])); emergency=int(round(sol[e0+s])); lost=int(round(sol[u0+s]))
        cost=prod*production_unit_cost+emergency*emergency_unit_cost+lost*lost_sales_penalty
        losses.append((cost,row.probability))
        recourse.append({"scenario_id":row.scenario_id,"probability":row.probability,
            "demand":row.demand_quantity,"available_capacity":row.available_capacity,
            "common_commitment":int(round(sol[x])),"internal_production":prod,
            "emergency_procurement":emergency,"lost_sales":lost,
            "service_level":(prod+emergency)/row.demand_quantity if row.demand_quantity else 1.0,
            "recourse_cost":cost})
    expected_recourse=sum(cost*prob for cost,prob in losses)
    cvar,threshold=_weighted_cvar(losses,risk_alpha)
    first_stage_cost=int(round(sol[x]))*precommit_unit_cost
    total=first_stage_cost+(1-risk_weight)*expected_recourse+risk_weight*cvar
    return {"feasible":True,"optimality_proven":int(result.status)==0,
        "solver_status":int(result.status),"solver_message":str(result.message),
        "common_commitment_quantity":int(round(sol[x])),"first_stage_cost":first_stage_cost,
        "expected_recourse_cost":expected_recourse,"cvar_recourse_cost":cvar,
        "cvar_var_threshold":threshold,"mean_cvar_recourse_cost":(1-risk_weight)*expected_recourse+risk_weight*cvar,
        "total_mean_cvar_objective":total,"scenario_recourse":recourse,
        "solver_objective_value":float(result.fun),"mip_gap":getattr(result,"mip_gap",None)}


def optimize_two_stage_recourse(precommit_capacity:int,precommit_unit_cost:float,
    production_unit_cost:float,emergency_unit_cost:float,lost_sales_penalty:float,
    scenarios,risk_alpha:float=0.95,risk_weight:float=0.5,
    mip_rel_gap:float=0.0,time_limit_seconds:float=30.0)->dict:
    """Optimize shared first-stage commitment and scenario-specific recourse."""
    if not isinstance(precommit_capacity,int) or precommit_capacity<0:
        raise ValueError("precommit_capacity must be a non-negative integer")
    for name,value in (("precommit_unit_cost",precommit_unit_cost),("production_unit_cost",production_unit_cost),
        ("emergency_unit_cost",emergency_unit_cost),("lost_sales_penalty",lost_sales_penalty)):
        if not math.isfinite(value) or value<0: raise ValueError(f"{name} must be finite and non-negative")
    if not 0<risk_alpha<1: raise ValueError("risk_alpha must be in (0,1)")
    if not math.isfinite(risk_weight) or not 0<=risk_weight<=1: raise ValueError("risk_weight must be in [0,1]")
    if not 0<=mip_rel_gap<1 or not math.isfinite(mip_rel_gap): raise ValueError("mip_rel_gap must be in [0,1)")
    if not math.isfinite(time_limit_seconds) or time_limit_seconds<=0: raise ValueError("time_limit_seconds must be positive")
    rows=_validate_scenarios(scenarios)
    risk_aware=_solve(rows,precommit_capacity,precommit_unit_cost,production_unit_cost,
        emergency_unit_cost,lost_sales_penalty,risk_alpha,risk_weight,mip_rel_gap,time_limit_seconds)
    if not risk_aware["feasible"] or not risk_aware["optimality_proven"]:
        return {"complete":False,"risk_aware_solution":risk_aware}
    risk_neutral=_solve(rows,precommit_capacity,precommit_unit_cost,production_unit_cost,
        emergency_unit_cost,lost_sales_penalty,risk_alpha,0.0,mip_rel_gap,time_limit_seconds)
    if not risk_neutral["feasible"] or not risk_neutral["optimality_proven"]:
        return {"complete":False,"risk_aware_solution":risk_aware,"risk_neutral_solution":risk_neutral}
    perfect_information_cost=0.0; perfect_information_rows=[]
    for scenario in rows:
        single=_solve([TwoStageScenario(scenario.scenario_id,1.0,scenario.demand_quantity,scenario.available_capacity)],
            precommit_capacity,precommit_unit_cost,production_unit_cost,emergency_unit_cost,
            lost_sales_penalty,risk_alpha,0.0,mip_rel_gap,time_limit_seconds)
        if not single["feasible"] or not single["optimality_proven"]:
            return {"complete":False,"risk_aware_solution":risk_aware,
                "risk_neutral_solution":risk_neutral,"perfect_information_complete":False}
        perfect_information_cost+=scenario.probability*single["total_mean_cvar_objective"]
        perfect_information_rows.append({"scenario_id":scenario.scenario_id,"probability":scenario.probability,
            "scenario_specific_commitment":single["common_commitment_quantity"],
            "scenario_specific_cost":single["total_mean_cvar_objective"]})
    evpi=max(0.0,risk_neutral["total_mean_cvar_objective"]-perfect_information_cost)
    return {"model":"SYNERGY_V7_8_TWO_STAGE_NONANTICIPATIVE_MILP",
        "complete":True,"non_anticipativity_enforced":True,
        "first_stage_decisions":["common_commitment_quantity"],
        "second_stage_decisions":["internal_production","emergency_procurement","lost_sales"],
        "risk_alpha":risk_alpha,"risk_weight":risk_weight,
        "risk_aware_solution":risk_aware,"risk_neutral_solution":risk_neutral,
        "wait_and_see_expected_cost":perfect_information_cost,
        "expected_value_of_perfect_information":evpi,
        "wait_and_see_scenarios":perfect_information_rows,
        "model_scope":"Single product, one planning epoch, integer quantities. Not yet the full multi-product, multi-period recipe/cash/credit/collateral production network.",
        "interpretation":"The common commitment is chosen once before scenario revelation; scenario-specific production, emergency procurement and lost sales are recourse decisions. The wait-and-see benchmark may choose a different commitment in each scenario and is not an implementable policy."}
