import numpy as np, math
N,DAYS,SECTORS,PER=80,120,4,20
POLICIES=("liquidity_first","network_greedy","rolling_horizon","cvar_robust")
def topology(seed):
    rng=np.random.default_rng(seed); sec=np.repeat(np.arange(SECTORS),PER); suppliers=np.zeros((N,2),int)
    for i in range(N):
        c=np.where(((sec==max(0,sec[i]-1))|(sec==sec[i]))&(np.arange(N)!=i))[0]
        suppliers[i]=rng.choice(c,2,replace=False)
    return sec,suppliers
def centrality(sec,suppliers):
    W=np.zeros((N,N))
    for b in range(N):
        for s in suppliers[b]: W[s,b]+=.5
    reach=np.eye(N); p=np.eye(N)
    for k in range(1,5): p=p@W; reach+=(.55**k)*p
    return np.maximum(0,reach.sum(axis=1)-1)
def run_path(seed,regime,policy,reserve=180.0):
    if regime not in ("severe","systemic") or policy not in POLICIES: raise ValueError("unknown regime/policy")
    sec,sup=topology(seed); sup=sup.copy()
    rng=np.random.default_rng(seed+(300001 if regime=="severe" else 600001))
    cash=np.full(N,38.); alive=np.ones(N,bool); impaired=np.zeros(N,bool)
    shock_day=35; count=18 if regime=="severe" else 25; duration=22 if regime=="severe" else 36
    imp=centrality(sec,sup); targets=np.argsort(imp+rng.normal(0,.04,N))[::-1][:count]
    end=np.zeros(N,int); end[targets]=shock_day+duration
    pool=float(reserve); repair_cost=support=0.; sales=output=lost=op=0.
    daily=[]; base=rng.normal(-.11 if regime=="severe" else -.21,.09 if regime=="severe" else .15)
    secbase=rng.normal(0,.08 if regime=="severe" else .15,SECTORS)
    for day in range(DAYS):
        impaired[impaired&(end<=day)]=False
        if day==shock_day: impaired[targets]=True
        demand=np.clip(1+base+rng.normal(0,.03)+secbase[sec]+rng.normal(0,.035,SECTORS)[sec]+rng.normal(0,.045,N),.04,1.15)
        if policy!="liquidity_first":
            load=np.bincount(sup.ravel(),minlength=N)
            for b in range(N):
                if not alive[b] or impaired[b]: continue
                for k in range(2):
                    old=sup[b,k]
                    if not alive[old] or impaired[old]:
                        c=np.where(alive&~impaired&(np.abs(sec-sec[b])<=1))[0]; c=c[c!=b]; c=c[load[c]<6]
                        if len(c):
                            new=c[np.argmin(np.abs(sec[c]-sec[b])+.025*load[c])]
                            load[old]=max(0,load[old]-1); load[new]+=1; sup[b,k]=new
        ok=alive[sup]&~impaired[sup]; ratio=ok.mean(axis=1)
        prod=np.where(alive&~impaired,demand*(.30+.70*ratio),0.)
        margin=10*prod-5.7*prod-1.65*alive
        cash+=margin; sales+=(10*prod).sum(); output+=prod.sum()
        lost+=np.maximum(0,demand-prod).sum(); op+=margin.sum(); daily.append(float(prod.sum()))
        cand=[]
        if day>=shock_day and pool>0:
            for i in np.where(alive&impaired)[0]:
                dep=np.where((sup==i).any(axis=1))[0]; live=dep[alive[dep]&~impaired[dep]]
                benefit=10*(.7+.45*len(live)+.10*imp[i])*max(.1,demand[i])+3*(len(live)+1)
                cand.append(("repair",int(i),18.,benefit))
            for i in np.where(alive&(cash<7))[0]:
                cost=min(8.,max(0.,7.-cash[i]))
                if cost:
                    value=4.+.30*imp[i]+.15*np.sum(alive&(sup==i).any(axis=1))
                    cand.append(("liquidity",int(i),cost,10.+value))
            if policy=="liquidity_first": cand.sort(key=lambda x:(0 if x[0]=="liquidity" else 1,cash[x[1]]))
            elif policy=="network_greedy": cand.sort(key=lambda x:x[3]/x[2],reverse=True)
            elif policy=="rolling_horizon": cand.sort(key=lambda x:(x[3]*(1-math.exp(-5/8))/x[2]),reverse=True)
            else:
                cand.sort(key=lambda x:(x[3]*(.72 if x[0]=="repair" else .90)/(1+.18*np.sum((sup==x[1]).any(axis=1)))/x[2]),reverse=True)
            used=set()
            for typ,i,cost,value in cand:
                if pool<cost or i in used: continue
                if typ=="repair":
                    if not impaired[i]: continue
                    impaired[i]=False; repair_cost+=cost
                else:
                    if not alive[i] or cash[i]>=7: continue
                    amount=min(cost,pool,max(0.,7.-cash[i])); cash[i]+=amount; cost=amount; support+=amount
                pool-=cost; used.add(i)
        alive[alive&(cash<0)]=False
    pre=np.mean(daily[15:35]); post=np.mean(daily[90:120]); ratio=post/pre if pre>0 else 0.
    days=85
    for d in range(shock_day+1,DAYS-4):
        if np.mean(daily[d:d+5])>=.9*pre: days=d-shock_day; break
    return {"seed":seed,"regime":regime,"policy":policy,"defaults":int((~alive).sum()),
      "survival_rate":float(alive.mean()),"external_gross_sales":float(sales),"production":float(output),
      "production_lost":float(lost),"operating_surplus":float(op),
      "net_after_intervention":float(op-repair_cost-support),"recovery_ratio":float(ratio),
      "recovery_days":int(days),"repair_cost":float(repair_cost),"liquidity_support":float(support),
      "reserve_remaining":float(pool)}
