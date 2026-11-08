
from __future__ import annotations
import numpy as np
import pandas as pd

N=80
DAYS=100
SECTORS=4
PER=20
START_CASH=30.0
REVENUE_PER_NODE=10.0
VARIABLE_COST_PER_UNIT=6.0
FIXED_COST_PER_DAY=2.0
DEBT_SERVICE_PER_DAY=0.5
POLICIES=("isolated","liquidity_pool","firewall","adaptive_synergy")
REGIMES=("moderate","severe","systemic")
PERSIST={"moderate":(0.00,0.08,0.08),
         "severe":(-0.20,0.12,0.30),
         "systemic":(-0.38,0.18,0.42)}
REGIME_SEED_OFFSET={"moderate":10000,"severe":20000,"systemic":30000}

def build_network(seed):
    rng=np.random.default_rng(seed)
    sectors=np.repeat(np.arange(SECTORS),PER)
    suppliers=np.zeros((N,2),dtype=int)
    for i in range(N):
        s=sectors[i]
        if s>0:
            candidates=np.concatenate([
                np.where(sectors==s-1)[0],
                np.where((sectors==s)&(np.arange(N)!=i))[0]
            ])
        else:
            candidates=np.where((sectors==0)&(np.arange(N)!=i))[0]
        suppliers[i]=rng.choice(candidates,2,replace=False)
    return sectors,suppliers

def simulate(seed,regime,policy,pool_start=0.0,reserve_start=0.0):
    if regime not in REGIMES or policy not in POLICIES:
        raise ValueError("Unknown regime or policy")
    rng=np.random.default_rng(seed+REGIME_SEED_OFFSET[regime])
    sectors,suppliers=build_network(seed)
    cash=np.full(N,START_CASH,dtype=float)
    alive=np.ones(N,dtype=bool)
    # Invoice destinations are frozen at invoice origination.
    payables=np.zeros((DAYS+4,N,N),dtype=float)
    pool=float(pool_start)
    reserve=float(reserve_start)
    transfers=0.0
    total_sales=variable_costs=fixed_costs=debt_service=production_lost=0.0
    macro_mu,macro_sd,sector_sd=PERSIST[regime]
    persistent_macro=rng.normal(macro_mu,macro_sd)
    persistent_sector=rng.normal(0,sector_sd,SECTORS)
    for day in range(DAYS):
        due=payables[day]
        buyer_due=due.sum(axis=1)
        cash-=buyer_due*alive
        # Only solvent buyers settle; receipts go to the supplier named on the invoice.
        incoming=(due*alive[:,None]).sum(axis=0)
        cash+=incoming
        macro=persistent_macro+rng.normal(0,0.035)
        sector=persistent_sector+rng.normal(0,0.04,SECTORS)
        idiosyncratic=rng.normal(0,0.05,N)
        demand=np.clip(1+macro+sector[sectors]+idiosyncratic,0.08,1.25)

        # Supplier rerouting changes future purchases only, never old invoices.
        if policy in ("firewall","adaptive_synergy"):
            for i in range(N):
                if not alive[i]:
                    continue
                for k in np.where(~alive[suppliers[i]])[0]:
                    candidates=np.where(alive & (np.abs(sectors-sectors[i])<=1))[0]
                    candidates=candidates[candidates!=i]
                    if len(candidates):
                        suppliers[i,k]=candidates[np.argmin(np.abs(sectors[candidates]-sectors[i]))]

        live_suppliers=alive[suppliers].sum(axis=1)
        production=demand*np.where(alive,0.30+0.35*live_suppliers,0.0)
        sales=REVENUE_PER_NODE*production
        total_sales+=float(sales.sum())
        cash+=sales

        for buyer in range(N):
            if alive[buyer]:
                payables[day+3,buyer,suppliers[buyer,0]]+=sales[buyer]*0.175
                payables[day+3,buyer,suppliers[buyer,1]]+=sales[buyer]*0.175

        variable=VARIABLE_COST_PER_UNIT*production
        fixed=FIXED_COST_PER_DAY*alive
        debt=DEBT_SERVICE_PER_DAY*alive
        variable_costs+=float(variable.sum())
        fixed_costs+=float(fixed.sum())
        debt_service+=float(debt.sum())
        cash-=variable+fixed+debt
        production_lost+=float(np.maximum(0,demand-production).sum())

        if policy in ("liquidity_pool","adaptive_synergy"):
            needy=np.where(alive & (cash<4.0))[0]
            needy=needy[np.argsort(cash[needy])]
            for i in needy:
                transfer=min(4.0-cash[i],pool)
                cash[i]+=transfer
                pool-=transfer
                transfers+=transfer
                if policy=="adaptive_synergy" and cash[i]<0 and reserve>0:
                    transfer=min(-cash[i]+1.0,reserve)
                    cash[i]+=transfer
                    reserve-=transfer
                    transfers+=transfer

        failed=alive & (cash < -1e-8)
        if policy=="adaptive_synergy" and reserve>0:
            for i in np.where(failed)[0]:
                transfer=min(-cash[i]+1.0,reserve)
                cash[i]+=transfer
                reserve-=transfer
                transfers+=transfer
            failed=alive & (cash < -1e-8)
        alive[failed]=False

    return {
        "defaults":int((~alive).sum()),
        "survival_rate":float(alive.mean()),
        "external_sales":total_sales,
        "variable_costs":variable_costs,
        "fixed_costs":fixed_costs,
        "debt_service":debt_service,
        "operating_surplus":total_sales-variable_costs-fixed_costs-debt_service,
        "production_lost":production_lost,
        "pool_transfers":transfers,
        "pool_remaining":pool,
        "reserve_remaining":reserve
    }

def run_main_grid(seeds=100):
    rows=[]
    for regime in REGIMES:
        for seed in range(seeds):
            for policy in POLICIES:
                pool=100.0 if policy in ("liquidity_pool","adaptive_synergy") else 0.0
                reserve=100.0 if policy=="adaptive_synergy" else 0.0
                result=simulate(69000+seed,regime,policy,pool,reserve)
                rows.append({"regime":regime,"seed":seed,"policy":policy,**result})
    return pd.DataFrame(rows)

def run_systemic_precision(seeds=300):
    rows=[]
    for seed in range(seeds):
        for policy in POLICIES:
            pool=100.0 if policy in ("liquidity_pool","adaptive_synergy") else 0.0
            reserve=100.0 if policy=="adaptive_synergy" else 0.0
            result=simulate(79000+seed,"systemic",policy,pool,reserve)
            rows.append({"seed":seed,"policy":policy,**result})
    return pd.DataFrame(rows)

def run_capital_sensitivity(seeds=100):
    rows=[]
    for capital in (0,50,100,200,400,800,1200):
        for seed in range(seeds):
            if capital==0:
                policy="isolated"; pool=reserve=0.0
            else:
                policy="adaptive_synergy"
                pool=capital*0.5
                reserve=capital*0.5
            result=simulate(89000+seed,"systemic",policy,pool,reserve)
            rows.append({"capital":capital,"seed":seed,**result})
    return pd.DataFrame(rows)

if __name__=="__main__":
    main=run_main_grid()
    sys=run_systemic_precision()
    cap=run_capital_sensitivity()
    main.to_csv("v654_main_raw.csv",index=False)
    sys.to_csv("v654_systemic_raw.csv",index=False)
    cap.to_csv("v654_capital_raw.csv",index=False)
    print("main paths",len(main),"systemic precision paths",len(sys),"capital paths",len(cap))
