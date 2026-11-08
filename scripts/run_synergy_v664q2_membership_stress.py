#!/usr/bin/env python3
"""
SYNERGY EURASIAN V6.6.4-Q2 — reserve membership stress model.

Deterministic synthetic research fixture; not the production CreditLedger.
Run from repository root:
    python scripts/run_synergy_v664q2_membership_stress.py
Outputs aggregate sensitivity JSON and 400 cycle-level rows for the principal
80-unit inflow case.
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path

REGIONS=("WEST","EAST")
CELLS=tuple([f"W{i}" for i in range(10)]+[f"E{i}" for i in range(10)])
OPENING_CASH=1000.0
CASH_FLOOR=900.0
CONTRIBUTION_RATE=0.10
CAP_30D=80.0
REGIONAL_NEED={"WEST":200.0,"EAST":200.0}
FEDERATION_NEED=300.0
CYCLES=100
DEFAULT_EVENTS={1:("W0",),25:("W1",),50:("E0",)}
DEFAULTED_AT_START=frozenset({"W0"})
FEDERATION_MEMBERS=frozenset({"W2","W3","W4","W5","E2","E3","E4","E5"})
BASE_REGIONAL_MEMBERS={
    "WEST":frozenset({"W0","W1","W2"}),
    "EAST":frozenset({"E0","E1","E2"}),
}
EXPANDED_REGIONAL_MEMBERS={
    "WEST":frozenset({"W0","W1","W2","W3","W4"}),
    "EAST":frozenset({"E0","E1","E2"}),
}

def validate_membership(regional_members,federation_members):
    if set(regional_members)!=set(REGIONS):
        raise ValueError("Regional membership must define WEST and EAST exactly")
    known=set(CELLS)
    for region,iterable in regional_members.items():
        members=tuple(iterable)
        if len(members)!=len(set(members)):
            raise ValueError(f"Duplicate member in {region}")
        if set(members)-known:
            raise ValueError(f"Unknown member(s): {sorted(set(members)-known)}")
        prefix="W" if region=="WEST" else "E"
        wrong=sorted(c for c in members if not c.startswith(prefix))
        if wrong:
            raise ValueError(f"Cross-region local member(s) in {region}: {wrong}")
    fed=tuple(federation_members)
    if len(fed)!=len(set(fed)):
        raise ValueError("Duplicate federation member")
    if set(fed)-known:
        raise ValueError(f"Unknown federation member(s): {sorted(set(fed)-known)}")

def gini(values):
    vals=sorted(max(0.0,float(x)) for x in values)
    total=sum(vals)
    if not vals or total<=0:
        return 0.0
    n=len(vals)
    return 2.0*sum((i+1)*v for i,v in enumerate(vals))/(n*total)-(n+1.0)/n

def allocate(demand,members,remaining,method):
    eligible=sorted(c for c in set(members) if remaining.get(c,0.0)>1e-12)
    capacity=sum(remaining[c] for c in eligible)
    funded=min(float(demand),capacity)
    amounts={c:0.0 for c in eligible}
    if method=="pro_rata":
        if capacity:
            for c in eligible:
                amounts[c]=funded*remaining[c]/capacity
    elif method=="fcfs":
        left=funded
        for c in eligible:
            take=min(left,remaining[c])
            amounts[c]=take
            left-=take
    else:
        raise ValueError("method must be pro_rata or fcfs")
    return amounts,float(demand)-funded

def simulate(method,membership_case,regional_members,inflow,cycles=CYCLES):
    validate_membership(regional_members,FEDERATION_MEMBERS)
    cash={c:OPENING_CASH for c in CELLS}
    defaulted=set(DEFAULTED_AT_START)
    cumulative={c:0.0 for c in CELLS}
    rows=[]
    regional_gap={"WEST":0.0,"EAST":0.0}
    federation_gap=0.0
    for cycle in range(1,cycles+1):
        newly=tuple(DEFAULT_EVENTS.get(cycle,()))
        defaulted.update(newly)
        cycle_inflow=inflow*(len(CELLS)-len(defaulted))
        for c in CELLS:
            if c not in defaulted:
                cash[c]+=inflow
        remaining={}
        for c in CELLS:
            if c in defaulted:
                remaining[c]=0.0
            else:
                if cash[c]<CASH_FLOOR-1e-9:
                    raise AssertionError(f"{c} below cash floor")
                remaining[c]=max(0.0,min(CONTRIBUTION_RATE*cash[c],cash[c]-CASH_FLOOR,CAP_30D))
        paid={c:0.0 for c in CELLS}
        regional_paid={"WEST":0.0,"EAST":0.0}
        gaps={}
        for region in REGIONS:
            allocation,gap=allocate(REGIONAL_NEED[region],regional_members[region],remaining,method)
            gaps[region]=gap
            for c,amount in allocation.items():
                paid[c]+=amount
                regional_paid[region]+=amount
                remaining[c]-=amount
        fed_allocation,fed_gap=allocate(FEDERATION_NEED,FEDERATION_MEMBERS,remaining,method)
        for c,amount in fed_allocation.items():
            paid[c]+=amount
            remaining[c]-=amount
        for c,amount in paid.items():
            assert c not in defaulted or abs(amount)<=1e-9
            assert amount<=CAP_30D+1e-8
            assert cash[c]-amount>=CASH_FLOOR-1e-8
            cash[c]-=amount
            cumulative[c]+=amount
        regional_gap["WEST"]+=gaps["WEST"]
        regional_gap["EAST"]+=gaps["EAST"]
        federation_gap+=fed_gap
        cycle_gap=sum(gaps.values())+fed_gap
        expected=OPENING_CASH*len(CELLS)+sum(
            inflow*(len(CELLS)-len(set(DEFAULTED_AT_START).union(
                *(set(DEFAULT_EVENTS.get(k,())) for k in range(1,t+1)))))
            for t in range(1,cycle+1)
        )-sum(cumulative.values())
        assert abs(sum(cash.values())-expected)<=1e-6
        rows.append({
            "cycle":cycle,
            "new_defaults":";".join(newly),
            "cumulative_defaults":len(defaulted),
            "active_cells":len(CELLS)-len(defaulted),
            "exogenous_inflow":cycle_inflow,
            "west_contribution":regional_paid["WEST"],
            "east_contribution":regional_paid["EAST"],
            "federation_contribution":sum(fed_allocation.values()),
            "total_contribution":sum(paid.values()),
            "west_unfunded":gaps["WEST"],
            "east_unfunded":gaps["EAST"],
            "federation_unfunded":fed_gap,
            "total_unfunded":cycle_gap,
            "minimum_solvent_cash":min((cash[c] for c in CELLS if c not in defaulted),default=0.0),
            "cash_floor_breaches":0,
            "defaulted_member_contribution":sum(paid[c] for c in defaulted),
        })
    values=list(cumulative.values())
    total=sum(values)
    top=sum(sorted(values,reverse=True)[:4])
    return {
        "method":method,"membership_case":membership_case,
        "inflow_per_solvent_cell":inflow,
        "total_contributions":total,
        "total_unfunded":sum(regional_gap.values())+federation_gap,
        "west_unfunded":regional_gap["WEST"],
        "east_unfunded":regional_gap["EAST"],
        "federation_unfunded":federation_gap,
        "contributor_gini":gini(values),
        "top20_contribution_share":top/total if total else 0.0,
        "max_member_contribution":max(values,default=0.0),
        "minimum_final_cash":min(cash.values()),
        "cycle_rows":rows,
    }

def run_tests():
    validate_membership(BASE_REGIONAL_MEMBERS,FEDERATION_MEMBERS)
    validate_membership(EXPANDED_REGIONAL_MEMBERS,FEDERATION_MEMBERS)
    try:
        validate_membership({"WEST":{"E1"},"EAST":BASE_REGIONAL_MEMBERS["EAST"]},FEDERATION_MEMBERS)
    except ValueError:
        pass
    else:
        raise AssertionError("Cross-region local membership accepted")
    assert "W3" not in BASE_REGIONAL_MEMBERS["WEST"] and "W3" in FEDERATION_MEMBERS
    baseline=simulate("pro_rata","baseline",BASE_REGIONAL_MEMBERS,80.0)
    assert baseline["cycle_rows"][0]["defaulted_member_contribution"]==0.0
    assert baseline["cycle_rows"][24]["cumulative_defaults"]==2
    assert baseline["cycle_rows"][49]["cumulative_defaults"]==3
    assert baseline["cycle_rows"][99]["cumulative_defaults"]==3
    assert baseline["minimum_final_cash"]>=CASH_FLOOR-1e-8
    expanded=simulate("fcfs","expanded",EXPANDED_REGIONAL_MEMBERS,80.0)
    assert expanded["west_unfunded"]==0.0
    assert expanded["east_unfunded"]==2040.0
    return 8

def run_all():
    results=[]
    for inflow in (0.0,40.0,60.0,80.0,100.0):
        for name,members in (("baseline_membership",BASE_REGIONAL_MEMBERS),
                             ("expanded_west_membership",EXPANDED_REGIONAL_MEMBERS)):
            for method in ("pro_rata","fcfs"):
                r=simulate(method,name,members,inflow)
                results.append({k:round(v,8) if isinstance(v,float) else v
                                for k,v in r.items() if k!="cycle_rows"})
    return {
        "metadata":{
            "model":"SYNERGY EURASIAN V6.6.4-Q2 local research fixture",
            "classification":"synthetic deterministic scenario; not production ledger output",
            "cycles":CYCLES,"cycle_length_days":30,"opening_cash_per_cell":OPENING_CASH,
            "cash_floor_per_cell":CASH_FLOOR,"contribution_rate":CONTRIBUTION_RATE,
            "contribution_cap_per_30d":CAP_30D,"regional_need_per_cycle":REGIONAL_NEED,
            "federation_need_per_cycle":FEDERATION_NEED,
            "default_events":{str(k):list(v) for k,v in DEFAULT_EVENTS.items()},
            "federation_members":sorted(FEDERATION_MEMBERS),
            "base_regional_members":{k:sorted(v) for k,v in BASE_REGIONAL_MEMBERS.items()},
            "expanded_regional_members":{k:sorted(v) for k,v in EXPANDED_REGIONAL_MEMBERS.items()},
            "inflow_assumption":"Per-cycle external operating inflow is paid equally to each solvent cell; defaulted cells receive no inflow.",
            "priority":"regional funds first, federation second; shared contributor capacity",
            "allocation_methods":["pro_rata","fcfs"],
        },
        "results":results,
    }

def write_outputs():
    out=Path("reports")
    out.mkdir(exist_ok=True)
    summary=run_all()
    (out/"synergy_v664q2_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    fields=["method","membership_case","inflow_per_solvent_cell","cycle","new_defaults",
            "cumulative_defaults","active_cells","exogenous_inflow","west_contribution",
            "east_contribution","federation_contribution","total_contribution",
            "west_unfunded","east_unfunded","federation_unfunded","total_unfunded",
            "minimum_solvent_cash","cash_floor_breaches","defaulted_member_contribution"]
    with (out/"synergy_v664q2_cycle_results.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for name,members in (("baseline_membership",BASE_REGIONAL_MEMBERS),
                             ("expanded_west_membership",EXPANDED_REGIONAL_MEMBERS)):
            for method in ("pro_rata","fcfs"):
                result=simulate(method,name,members,80.0)
                for row in result["cycle_rows"]:
                    writer.writerow({"method":method,"membership_case":name,
                                     "inflow_per_solvent_cell":80.0,**row})
    return summary

def main():
    n=run_tests()
    summary=write_outputs()
    print(f"CONTROL TESTS: {n}/{n} passed")
    print("100-cycle sensitivity grid (synthetic units):")
    for r in summary["results"]:
        print(f'{r["method"]:8s} {r["membership_case"]:24s} inflow={r["inflow_per_solvent_cell"]:5.1f} '
              f'paid={r["total_contributions"]:10.2f} gap={r["total_unfunded"]:10.2f} '
              f'WEST={r["west_unfunded"]:8.2f} EAST={r["east_unfunded"]:8.2f} FED={r["federation_unfunded"]:8.2f}')
    print("Wrote reports/synergy_v664q2_summary.json and reports/synergy_v664q2_cycle_results.csv")
    print("Synthetic fixture only; not production CreditLedger validation.")

if __name__=="__main__":
    main()
