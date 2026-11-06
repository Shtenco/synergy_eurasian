
from __future__ import annotations
import os, math
from statistics import NormalDist
import numpy as np
import pandas as pd

OPERATING_DAYS=120
SETTLEMENT_DAYS=150
DAILY_REVENUE=150.0
VARIABLE_COST_RATE=0.60
SUPPLIER_LAG=7
FIXED_COST=20.0
START_CASH=200.0
ADVANCE_RATE=0.80
PD_HORIZON=0.05
RECOVERY=0.30
FACTOR_FEE=0.005
RHO_GRID=[0.0,0.1,0.3,0.6,0.9,1.0]
N_SEEDS=500
WEIGHTS=np.asarray([0.10]+[0.90/99]*99,dtype=float)

def simulate(defaults):
    n=len(WEIGHTS)
    days=np.broadcast_to(np.arange(OPERATING_DAYS)[:,None],(OPERATING_DAYS,n))
    dd=np.broadcast_to(np.asarray(defaults)[None,:],(OPERATING_DAYS,n))
    amt=DAILY_REVENUE*WEIGHTS[None,:]*(days<dd)
    valid=amt>0
    due14=days+14
    due7=days+7

    def14=(dd<=due14)&valid
    base_days=np.where(def14,np.minimum(SETTLEMENT_DAYS,dd+30),due14)
    base_receipts=np.where(def14,amt*RECOVERY,amt)
    base_flow=np.bincount(base_days[valid].astype(int).ravel(),
                          weights=base_receipts[valid].ravel(),
                          minlength=SETTLEMENT_DAYS+1)
    base_bad=float((amt[def14]*(1-RECOVERY)).sum())

    def7=(dd<=due7)&valid
    early_days=np.where(def7,np.minimum(SETTLEMENT_DAYS,dd+30),due7)
    early_receipts=np.where(def7,amt*RECOVERY,amt*(1-FACTOR_FEE))
    early_flow=np.bincount(early_days[valid].astype(int).ravel(),
                           weights=early_receipts[valid].ravel(),
                           minlength=SETTLEMENT_DAYS+1)
    early_bad=float((amt[def7]*(1-RECOVERY)).sum())
    early_discount=float((amt[(dd>due7)&valid]*FACTOR_FEE).sum())

    advance_flow=np.bincount(days[valid].astype(int).ravel(),
                             weights=amt[valid]*(ADVANCE_RATE-FACTOR_FEE),
                             minlength=SETTLEMENT_DAYS+1)
    factor_default=(dd<=due14)&valid
    factor_paid=(dd>due14)&valid
    reserve_flow=np.bincount(due14[factor_paid].astype(int).ravel(),
                             weights=amt[factor_paid]*(1-ADVANCE_RATE),
                             minlength=SETTLEMENT_DAYS+1)
    reserve_loss=float((amt[factor_default]*(1-ADVANCE_RATE)).sum())
    factor_fee=float((amt[valid]*FACTOR_FEE).sum())
    factor_flow=advance_flow+reserve_flow

    fixed=np.zeros(SETTLEMENT_DAYS+1)
    fixed[:OPERATING_DAYS]-=FIXED_COST
    variable=np.zeros(SETTLEMENT_DAYS+1)
    variable[np.arange(OPERATING_DAYS)+SUPPLIER_LAG]-=amt.sum(axis=1)*VARIABLE_COST_RATE
    flows=[base_flow+fixed+variable,early_flow+fixed+variable,factor_flow+fixed+variable]
    gaps=[max(0.0,-float((START_CASH+np.cumsum(x)).min())) for x in flows]

    sales=float(amt.sum())
    gross=sales*(1-VARIABLE_COST_RATE)-FIXED_COST*OPERATING_DAYS
    base_profit=gross-base_bad
    early_profit=gross-early_bad-early_discount
    factor_profit=gross-factor_fee-reserve_loss
    return {
        "sales":sales,"bad_debt":base_bad,"sales_lost":DAILY_REVENUE*OPERATING_DAYS-sales,
        "defaults":int(np.sum(np.asarray(defaults)<OPERATING_DAYS)),
        "baseline_gap":gaps[0],"factoring_gap":gaps[2],
        "gap_reduction":gaps[0]-gaps[2],
        "factor_profit_delta":factor_profit-base_profit,
        "early_profit_delta":early_profit-base_profit
    }

def top_tail_mean(values, alpha=.95):
    x=np.sort(np.asarray(values,dtype=float))
    k=max(1,int(math.ceil((1-alpha)*len(x))))
    return float(x[-k:].mean())

def run():
    threshold=NormalDist().inv_cdf(PD_HORIZON)
    rows=[]
    for rho in RHO_GRID:
        for seed in range(N_SEEDS):
            rng=np.random.default_rng(88000000+int(rho*10000)*10000+seed)
            common=rng.normal()
            eps=rng.normal(size=100)
            latent=np.sqrt(rho)*common+np.sqrt(1-rho)*eps
            default_mask=latent<threshold
            defaults=np.full(100,SETTLEMENT_DAYS+1,dtype=int)
            defaults[default_mask]=rng.integers(0,OPERATING_DAYS,size=int(default_mask.sum()))
            rows.append({"rho":rho,"seed":seed,**simulate(defaults)})
    raw=pd.DataFrame(rows)
    summary=[]
    for rho,g in raw.groupby("rho"):
        summary.append({
            "rho":rho,"scenarios":len(g),"mean_defaults":g.defaults.mean(),
            "mean_bad_debt":g.bad_debt.mean(),"bad_debt_p95":g.bad_debt.quantile(.95),
            "bad_debt_cvar95":top_tail_mean(g.bad_debt),
            "sales_loss_p95":g.sales_lost.quantile(.95),
            "sales_loss_cvar95":top_tail_mean(g.sales_lost),
            "baseline_gap_p95":g.baseline_gap.quantile(.95),
            "mean_gap_reduction":g.gap_reduction.mean(),
            "mean_factor_profit_delta":g.factor_profit_delta.mean()
        })
    return raw,pd.DataFrame(summary)

if __name__=="__main__":
    raw,summary=run()
    out=os.path.join(os.path.dirname(__file__),"results")
    os.makedirs(out,exist_ok=True)
    raw.to_csv(os.path.join(out,"systemic_correlation_raw.csv"),index=False)
    summary.to_csv(os.path.join(out,"systemic_correlation_summary.csv"),index=False)
    print(summary.to_string(index=False))
