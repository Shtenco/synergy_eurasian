"""SYNERGY Q4.2: scalable network netting/reserve stress harness.
Standalone synthetic research only; not production CreditLedger.
Assumes full-cohort enforceable multilateral set-off, defaulted cash exhausted
before settlement, and no same-day receipt reuse.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
import csv, json, random

EPS=1e-8
SCALES=(20,50,100)
TOPOLOGIES=("ring","mesh","hub")
DEFAULT_MODES=("random","regional_cluster","largest_debtors")
RESERVE_RATIOS=(0.05,0.10,0.20)
SEEDS=(17,29,43)

@dataclass(frozen=True)
class Invoice:
    invoice_id:str
    buyer:str
    seller:str
    amount:float

def cell(i): return f"C{i:03d}"

def build_network(n, n_regions, topology, seed):
    if n<3 or not 1<=n_regions<=n: raise ValueError("invalid dimensions")
    if topology not in TOPOLOGIES: raise ValueError("invalid topology")
    rng=random.Random(seed); cells=[cell(i) for i in range(n)]
    regions={c:f"R{i%n_regions:02d}" for i,c in enumerate(cells)}
    raw=[]
    if topology=="ring":
        for i in range(n): raw.append((i,(i+1)%n,rng.uniform(80,120)))
        for i in range(0,n,3):
            j=(i+max(2,n//4))%n
            if i!=j: raw.append((i,j,rng.uniform(20,55)))
    elif topology=="mesh":
        for i in range(n):
            for step in range(1,min(4,n-1)+1):
                raw.append((i,(i+step)%n,rng.uniform(25,100)/step))
    else:
        hub=0
        for i in range(1,n):
            raw.append((i,hub,rng.uniform(60,130)))
            if i%2==0: raw.append((hub,i,rng.uniform(15,65)))
        for i in range(1,n):
            raw.append((i,(i%(n-1))+1,rng.uniform(10,35)))
    inv=[Invoice(f"{topology}-{seed}-{k:04d}",cells[b],cells[s],round(a,6))
         for k,(b,s,a) in enumerate(raw)]
    return inv,regions

def select_defaults(n,invoices,regions,mode,share,seed):
    if mode not in DEFAULT_MODES: raise ValueError("invalid default mode")
    k=max(1,min(n-1,round(n*share))); cells=sorted(regions); rng=random.Random(seed+991)
    if mode=="random": return set(rng.sample(cells,k))
    if mode=="regional_cluster":
        names=sorted(set(regions.values())); reg=names[seed%len(names)]
        members=[c for c in cells if regions[c]==reg]
        if len(members)<k:
            other=[c for c in cells if c not in members]
            members += rng.sample(other,min(k-len(members),len(other)))
        return set(rng.sample(members,min(k,len(members))))
    out=defaultdict(float)
    for x in invoices: out[x.buyer]+=x.amount
    return set(sorted(cells,key=lambda c:(-out[c],c))[:k])

def gini(values):
    xs=sorted(max(0,x) for x in values); total=sum(xs)
    if not xs or total<=EPS: return 0.0
    n=len(xs)
    return 2*sum((i+1)*x for i,x in enumerate(xs))/(n*total)-(n+1)/n

def hhi(values):
    total=sum(values)
    return sum((x/total)**2 for x in values if x>0) if total>EPS else 0.0

def settle(invoices,cells,opening_cash,reserve_open,method):
    gross_out=defaultdict(float); gross_in=defaultdict(float)
    for x in invoices: gross_out[x.buyer]+=x.amount; gross_in[x.seller]+=x.amount
    gross=sum(x.amount for x in invoices)
    if method=="gross_snapshot":
        due=dict(gross_out); weights=dict(gross_in); claim_base=gross; net_volume=gross
    elif method=="multilateral_netting":
        net={c:gross_out[c]-gross_in[c] for c in cells}
        due={c:max(0,net[c]) for c in cells}
        weights={c:max(0,-net[c]) for c in cells}
        net_volume=sum(due.values()); claim_base=net_volume
    else: raise ValueError("bad method")
    paid_by={c:min(opening_cash[c],due.get(c,0)) for c in cells}
    collected=sum(paid_by.values()); pre_reserve=max(0,claim_base-collected)
    reserve_paid=min(reserve_open,pre_reserve); uncovered=max(0,pre_reserve-reserve_paid)
    creditor_total=sum(weights.values())
    member_end=dict(opening_cash)
    for c,v in paid_by.items(): member_end[c]-=v
    payouts={c:0.0 for c in cells}
    if creditor_total>EPS:
        for c in cells:
            payouts[c]=(collected+reserve_paid)*weights.get(c,0)/creditor_total
            member_end[c]+=payouts[c]
    reserve_end=reserve_open-reserve_paid
    residual=sum(member_end.values())+reserve_end-(sum(opening_cash.values())+reserve_open)
    if min(member_end.values(),default=0)<-EPS or reserve_end<-EPS: raise AssertionError("negative balance")
    if abs(residual)>EPS: raise AssertionError("cash conservation")
    if abs(collected+reserve_paid+uncovered-claim_base)>EPS: raise AssertionError("claim reconciliation")
    return {"method":method,"gross_claims":gross,"net_debit_volume":net_volume,
      "legal_claim_base":claim_base,"cash_paid_by_members":collected,
      "reserve_paid":reserve_paid,"uncovered":uncovered,"reserve_open":reserve_open,
      "reserve_end":reserve_end,"reserve_utilization":reserve_paid/reserve_open if reserve_open>EPS else 0,
      "coverage":(collected+reserve_paid)/claim_base if claim_base>EPS else 1,
      "cash_conservation_residual":residual,"member_cash_end":sum(member_end.values()),
      "ending_member_cash_min":min(member_end.values(),default=0),
      "ending_member_cash_max":max(member_end.values(),default=0),
      "creditor_payout_gini":gini(list(payouts.values())),
      "creditor_payout_hhi":hhi(list(payouts.values()))}

def run_case(n,topology,default_mode,reserve_ratio,seed,default_share=0.20):
    n_regions={20:2,50:5,100:10}.get(n,min(10,max(2,n//10)))
    invoices,regions=build_network(n,n_regions,topology,seed)
    defaults=select_defaults(n,invoices,regions,default_mode,default_share,seed)
    cells=sorted(regions); gross=sum(x.amount for x in invoices)
    cash_before={c:1000+20*(int(c[1:])%7) for c in cells}
    external_burn=sum(cash_before[c] for c in defaults)
    cash={c:(0.0 if c in defaults else cash_before[c]) for c in cells}
    reserve=gross*reserve_ratio
    gross_result=settle(invoices,cells,cash,reserve,"gross_snapshot")
    net_result=settle(invoices,cells,cash,reserve,"multilateral_netting")
    net_eff=1-net_result["net_debit_volume"]/gross if gross>EPS else 0
    cross=sum(x.amount for x in invoices if regions[x.buyer]!=regions[x.seller])
    default_buyer=sum(x.amount for x in invoices if x.buyer in defaults)
    default_seller=sum(x.amount for x in invoices if x.seller in defaults)
    initial=sum(cash_before.values())+reserve
    expected=initial-external_burn
    for r in (gross_result,net_result):
        r["system_cash_end"]=r["member_cash_end"]+r["reserve_end"]
        r["system_cash_residual"]=r["system_cash_end"]-expected
        if abs(r["system_cash_residual"])>EPS: raise AssertionError("system cash identity")
    return {"n_cells":n,"n_regions":n_regions,"topology":topology,
      "default_mode":default_mode,"default_share_target":default_share,
      "default_count":len(defaults),"defaulted_cells":sorted(defaults),
      "reserve_ratio_of_gross":reserve_ratio,"seed":seed,"invoice_count":len(invoices),
      "gross_claims":gross,"cross_region_claim_share":cross/gross if gross else 0,
      "gross_claims_on_defaulted_buyers":default_buyer,
      "gross_receivables_to_defaulted_sellers":default_seller,
      "external_cash_burn":external_burn,"reserve_open":reserve,
      "net_debit_volume":net_result["net_debit_volume"],"netting_efficiency":net_eff,
      "gross_snapshot":gross_result,"multilateral_netting":net_result,
      "assumption":"full-cohort enforceable multilateral set-off; defaulted cash exhausted before settlement; same-day receipts not reusable"}

def run_grid():
    return [run_case(n,t,d,r,s) for n in SCALES for t in TOPOLOGIES
      for d in DEFAULT_MODES for r in RESERVE_RATIOS for s in SEEDS]

def summarize(rows):
    groups=defaultdict(list)
    for x in rows: groups[(x["n_cells"],x["topology"],x["default_mode"],x["reserve_ratio_of_gross"])].append(x)
    out=[]
    for (n,t,d,r),g in sorted(groups.items()):
        gross=[x["gross_snapshot"] for x in g]; net=[x["multilateral_netting"] for x in g]
        out.append({"n_cells":n,"topology":t,"default_mode":d,"reserve_ratio":r,"seeds":len(g),
          "mean_gross_claims":sum(x["gross_claims"] for x in g)/len(g),
          "mean_netting_efficiency":sum(x["netting_efficiency"] for x in g)/len(g),
          "mean_gross_uncovered":sum(x["uncovered"] for x in gross)/len(g),
          "mean_net_uncovered":sum(x["uncovered"] for x in net)/len(g),
          "mean_gross_reserve_paid":sum(x["reserve_paid"] for x in gross)/len(g),
          "mean_net_reserve_paid":sum(x["reserve_paid"] for x in net)/len(g),
          "mean_gross_coverage":sum(x["coverage"] for x in gross)/len(g),
          "mean_net_coverage":sum(x["coverage"] for x in net)/len(g),
          "mean_net_payout_gini":sum(x["creditor_payout_gini"] for x in net)/len(g),
          "max_abs_cash_residual":max(abs(x[m]["system_cash_residual"]) for x in g for m in ("gross_snapshot","multilateral_netting"))})
    return out

# pytest tests
def test_net_positions_sum_to_zero():
    inv,_=build_network(20,2,"mesh",17); out=defaultdict(float); inc=defaultdict(float)
    for x in inv: out[x.buyer]+=x.amount; inc[x.seller]+=x.amount
    assert abs(sum(out[c]-inc[c] for c in sorted(set(out)|set(inc))))<EPS

def test_equal_ring_zero_net_cash_need():
    n=12; cells=[cell(i) for i in range(n)]
    inv=[Invoice(str(i),cells[i],cells[(i+1)%n],100) for i in range(n)]
    r=settle(inv,cells,{c:0 for c in cells},0,"multilateral_netting")
    assert r["net_debit_volume"]==r["uncovered"]==r["cash_paid_by_members"]==0

def test_netting_volume_bounded_by_gross():
    for n in SCALES:
        for t in TOPOLOGIES:
            x=run_case(n,t,"random",.1,29)
            assert x["net_debit_volume"]<=x["gross_claims"]+EPS

def test_cash_conservation_all_scales():
    for n in SCALES:
        for t in TOPOLOGIES:
            x=run_case(n,t,"regional_cluster",.1,17)
            for m in ("gross_snapshot","multilateral_netting"):
                assert abs(x[m]["system_cash_residual"])<EPS
                assert abs(x[m]["cash_conservation_residual"])<EPS

def test_reserve_never_overdrawn():
    for ratio in RESERVE_RATIOS:
        x=run_case(50,"hub","largest_debtors",ratio,43)
        for m in ("gross_snapshot","multilateral_netting"):
            assert -EPS<=x[m]["reserve_end"]<=x[m]["reserve_open"]+EPS
            assert x[m]["reserve_paid"]<=x[m]["reserve_open"]+EPS

def test_member_balances_nonnegative():
    for t in TOPOLOGIES:
        x=run_case(100,t,"random",.2,29)
        for m in ("gross_snapshot","multilateral_netting"):
            assert x[m]["ending_member_cash_min"]>=-EPS

def test_deterministic_replay():
    assert run_case(50,"mesh","regional_cluster",.1,17)==run_case(50,"mesh","regional_cluster",.1,17)

def test_default_cash_burn_explicit():
    x=run_case(20,"ring","random",.05,17)
    expected=sum(1000+20*(int(c[1:])%7) for c in x["defaulted_cells"])
    assert abs(x["external_cash_burn"]-expected)<EPS and expected>0

def test_full_243_case_grid():
    rows=run_grid()
    assert len(rows)==243
    assert all(abs(x[m]["system_cash_residual"])<EPS for x in rows for m in ("gross_snapshot","multilateral_netting"))

def write_outputs(outdir):
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    rows=run_grid(); sums=summarize(rows)
    (outdir/"synergy_q4_2_results.json").write_text(json.dumps({"assumptions":{
      "scales":SCALES,"topologies":TOPOLOGIES,"default_modes":DEFAULT_MODES,
      "reserve_ratios":RESERVE_RATIOS,"seeds":SEEDS,"case_count":len(rows),
      "default_share_target":.2,"netting":"full-cohort enforceable multilateral set-off",
      "default_cash":"zero after explicit external cash burn","same_day_receipts_reusable":False},
      "cases":rows,"summary":sums},indent=2),encoding="utf-8")
    with (outdir/"synergy_q4_2_summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(sums[0])); w.writeheader(); w.writerows(sums)
    eff=[x["netting_efficiency"] for x in rows]
    delta=[x["gross_snapshot"]["uncovered"]-x["multilateral_netting"]["uncovered"] for x in rows]
    maxres=max(abs(x[m]["system_cash_residual"]) for x in rows for m in ("gross_snapshot","multilateral_netting"))
    lines=["# SYNERGY EURASIAN — Q4.2 scalable netting and reserve-capital experiment","",
      "**Status:** standalone local synthetic model; not production `CreditLedger`.","",
      "## Design","",
      "- 20, 50 and 100 cells; ring, mesh and hub topologies; random, regional-cluster and largest-debtor defaults.",
      "- Reserve ratios: 5%, 10%, 20% of gross invoices; seeds 17, 29, 43; 243 paired cases.",
      "- Paired comparison: gross snapshot settlement vs full-cohort multilateral netting.",
      "- Defaulted member cash is set to zero after an explicit external cash burn. Same-day receipts are not reused.",
      "- Assumes netting is legally enforceable for all cohort obligations, including defaulted members.","",
      "## Definitions","",
      "`Net position_i = gross payables_i - gross receivables_i`.",
      "`Net debit volume = sum(max(Net position_i, 0)) = sum(max(-Net position_i, 0))`.",
      "`Netting efficiency = 1 - net debit volume / gross invoice claims`.","",
      "## 27 aggregated configurations","",
      "| Cells | Topology | Default mode | Reserve | Netting efficiency | Gross uncovered | Net uncovered |",
      "|---:|---|---|---:|---:|---:|---:|"]
    for x in sums:
        lines.append(f"| {x['n_cells']} | {x['topology']} | {x['default_mode']} | {x['reserve_ratio']:.0%} | {x['mean_netting_efficiency']:.2%} | {x['mean_gross_uncovered']:.2f} | {x['mean_net_uncovered']:.2f} |")
    lines += ["","## Aggregate diagnostics","",
      f"- Cases: **{len(rows)}**.",
      f"- Mean theoretical netting efficiency: **{sum(eff)/len(eff):.2%}**.",
      f"- Range: **{min(eff):.2%}–{max(eff):.2%}**.",
      f"- Cases with lower uncovered amount under netting: **{sum(v>EPS for v in delta)}/{len(delta)}**.",
      f"- Mean gross-minus-net uncovered difference: **{sum(delta)/len(delta):.2f}**.",
      f"- Maximum absolute system cash residual: **{maxres:.3e}**.","",
      "## Limitations","",
      "1. Full-cohort netting is a strong legal/contractual assumption, not established for SYNERGY.",
      "2. No close-out valuation, disputed invoice, collateral, maturity mismatch, FX, tax or settlement-finality risk.",
      "3. Reserve is a single synthetic pool, not a regulatory or economic capital calibration.",
      "4. No member-funded replenishment, bank lines, physical assets, external receivables or external liabilities.",
      "5. Aggregate reduction in net debit does not guarantee every creditor is better off; payout concentration metrics are retained.",
      "6. Synthetic results are not empirical EAEU estimates or policy recommendations.","",
      "## Local tests","",
      "`pytest -q synergy_q4_2_network_netting.py` — 9 tests, including the full 243-case grid.","",
      "## Next","",
      "Test insolvency-safe set-off boundaries, maturities, bilateral vs multilateral eligibility, multi-level reserve waterfall and compare against production `CreditLedger`."]
    (outdir/"synergy_q4_2_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"case_count":len(rows),"summary_rows":len(sums),"max_cash_residual":maxres,
      "mean_netting_efficiency":sum(eff)/len(eff),"min_netting_efficiency":min(eff),
      "max_netting_efficiency":max(eff),"cases_netting_reduces_uncovered":sum(v>EPS for v in delta),
      "mean_uncovered_reduction":sum(delta)/len(delta)}

if __name__=="__main__":
    print(json.dumps(write_outputs(Path(__file__).resolve().parent),indent=2))