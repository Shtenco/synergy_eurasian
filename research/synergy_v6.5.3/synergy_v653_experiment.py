
from __future__ import annotations
import os, json, math
import numpy as np
import pandas as pd

PD_GRID = [0.005, 0.02, 0.05, 0.10]
RECOVERY_GRID = [0.10, 0.30, 0.60, 0.90]
FEE_GRID = [0.0, 0.0025, 0.005, 0.01, 0.02]
CONC = {
    "single_customer": [1.0],
    "top50pct_10": [0.50] + [0.50/9]*9,
    "top25pct_50": [0.25] + [0.75/49]*49,
    "top10pct_100": [0.10] + [0.90/99]*99,
}
N_SEEDS=25
OPERATING_DAYS=120
SETTLEMENT_DAYS=150
DAILY_REVENUE=150.0
VARIABLE_COST_RATE=0.60
SUPPLIER_LAG=7
DSO=14
FIXED_COST=20.0
START_CASH=200.0
ADVANCE_RATE=0.80

def simulate_three_policies(seed, pd_horizon, recovery, fee_or_discount, weights):
    rng=np.random.default_rng(seed)
    n=len(weights)
    defaults=np.full(n, SETTLEMENT_DAYS+1,dtype=int)
    for j in range(n):
        if rng.random()<pd_horizon:
            defaults[j]=int(rng.integers(0,OPERATING_DAYS))
    noise=np.maximum(0.0,rng.normal(1.0,0.08,size=(OPERATING_DAYS,n)))
    sales=np.zeros((OPERATING_DAYS,n))
    for day in range(OPERATING_DAYS):
        sales[day]=DAILY_REVENUE*np.asarray(weights)*noise[day]*(defaults>day)
    flows=[np.zeros(SETTLEMENT_DAYS+1) for _ in range(3)]
    for d in range(OPERATING_DAYS):
        for f in flows: f[d]-=FIXED_COST
        vc=float(sales[d].sum())*VARIABLE_COST_RATE
        for f in flows: f[d+SUPPLIER_LAG]-=vc
    bad_debt=[0.0,0.0,0.0]
    fees=[0.0,0.0,0.0]
    reserve_losses=[0.0,0.0,0.0]
    total=float(sales.sum())
    for day in range(OPERATING_DAYS):
        for j in range(n):
            amount=float(sales[day,j])
            if amount<=0: continue
            dd=int(defaults[j])
            due14=day+14
            if dd<=due14:
                flows[0][min(SETTLEMENT_DAYS,dd+30)]+=amount*recovery
                bad_debt[0]+=amount*(1-recovery)
            else:
                flows[0][due14]+=amount
            due7=day+7
            if dd<=due7:
                flows[1][min(SETTLEMENT_DAYS,dd+30)]+=amount*recovery
                bad_debt[1]+=amount*(1-recovery)
            else:
                flows[1][due7]+=amount*(1-fee_or_discount)
                fees[1]+=amount*fee_or_discount
            flows[2][day]+=amount*ADVANCE_RATE-amount*fee_or_discount
            fees[2]+=amount*fee_or_discount
            if dd<=due14:
                reserve_losses[2]+=amount*(1-ADVANCE_RATE)
            else:
                flows[2][due14]+=amount*(1-ADVANCE_RATE)
    balances=[START_CASH+np.cumsum(f) for f in flows]
    gaps=[max(0.0,-float(b.min())) for b in balances]
    gross=total*(1-VARIABLE_COST_RATE)-FIXED_COST*OPERATING_DAYS
    profits=[gross-bad_debt[0],gross-bad_debt[1]-fees[1],gross-bad_debt[2]-fees[2]-reserve_losses[2]]
    return {
        "sales":total,
        "baseline_gap":gaps[0],"earlypay_gap":gaps[1],"factoring_gap":gaps[2],
        "earlypay_gap_reduction":gaps[0]-gaps[1],
        "factoring_gap_reduction":gaps[0]-gaps[2],
        "baseline_profit":profits[0],"earlypay_profit":profits[1],"factoring_profit":profits[2],
        "earlypay_profit_delta":profits[1]-profits[0],
        "factoring_profit_delta":profits[2]-profits[0],
        "baseline_bad_debt":bad_debt[0],"earlypay_bad_debt":bad_debt[1],
        "factoring_fees":fees[2],"earlypay_discount_cost":fees[1],
        "factoring_reserve_loss":reserve_losses[2],
        "portfolio_sales_loss":DAILY_REVENUE*OPERATING_DAYS-total,
    }

def run_grid():
    rows=[]
    sid=0
    for pdv in PD_GRID:
        for recovery in RECOVERY_GRID:
            for cost in FEE_GRID:
                for cname,weights in CONC.items():
                    for seed_i in range(N_SEEDS):
                        # Common random numbers across PD, recovery and fee levels.
                        seed=20261106+seed_i*100000+len(weights)*101
                        result=simulate_three_policies(seed,pdv,recovery,cost,np.asarray(weights,dtype=float))
                        sid+=1
                        rows.append({"scenario_id":sid,"pd":pdv,"recovery":recovery,
                                     "discount_or_fee":cost,"concentration":cname,
                                     "seed_index":seed_i,**result})
    return pd.DataFrame(rows)

def run_tail_study():
    rows=[]
    for cname,weights in CONC.items():
        for seed_i in range(1000):
            seed=77123000+seed_i*31+len(weights)*101
            result=simulate_three_policies(seed,0.05,0.30,0.005,np.asarray(weights,dtype=float))
            rows.append({"concentration":cname,"seed":seed,**result})
    return pd.DataFrame(rows)

def top_tail_mean(values, alpha=0.95):
    x=np.sort(np.asarray(values,dtype=float))
    k=max(1,int(math.ceil((1-alpha)*len(x))))
    return float(x[-k:].mean())

def summarize_tail(tail):
    rows=[]
    for name,g in tail.groupby("concentration"):
        rows.append({
            "concentration":name,"scenarios":len(g),
            "mean_bad_debt":g.baseline_bad_debt.mean(),
            "bad_debt_p95":g.baseline_bad_debt.quantile(.95),
            "bad_debt_cvar95":top_tail_mean(g.baseline_bad_debt),
            "sales_loss_p95":g.portfolio_sales_loss.quantile(.95),
            "sales_loss_cvar95":top_tail_mean(g.portfolio_sales_loss),
            "baseline_gap_p95":g.baseline_gap.quantile(.95),
            "factoring_gap_reduction_mean":g.factoring_gap_reduction.mean(),
            "factoring_profit_delta_mean":g.factoring_profit_delta.mean(),
            "earlypay_profit_delta_mean":g.earlypay_profit_delta.mean()
        })
    return pd.DataFrame(rows)

if __name__=="__main__":
    out=os.path.join(os.path.dirname(__file__),"results")
    os.makedirs(out,exist_ok=True)
    grid=run_grid()
    tail=run_tail_study()
    grid.to_csv(os.path.join(out,"three_policy_results.csv"),index=False)
    tail.to_csv(os.path.join(out,"concentration_tail_risk_raw.csv"),index=False)
    summarize_tail(tail).to_csv(os.path.join(out,"concentration_tail_risk_summary.csv"),index=False)
    print(f"main_grid={len(grid)} paired scenarios; policy_paths={len(grid)*3}")
    print(f"tail_study={len(tail)} paired scenarios; policy_paths={len(tail)*3}")
