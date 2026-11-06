"""Non-duplicative benefit and portfolio accounting for SYNERGY V7."""
from dataclasses import dataclass
from typing import Iterable
import math


@dataclass(frozen=True)
class BenefitClaim:
    enterprise_id: str
    benefit_stream_id: str
    period: str
    gross_incremental_benefit: float
    incremental_opex: float
    replacement_obligation: float
    evidence_id: str
    source_class: str="SCENARIO"
    def __post_init__(self):
        if not all((self.enterprise_id,self.benefit_stream_id,self.period,self.evidence_id)): raise ValueError("Benefit claim identity and evidence are required")
        vals=(self.gross_incremental_benefit,self.incremental_opex,self.replacement_obligation)
        if any(not math.isfinite(v) or v<0 for v in vals): raise ValueError("Benefit amounts must be finite and non-negative")
        if self.source_class not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}: raise ValueError("Invalid evidence source_class")
    @property
    def net_reproducible_benefit(self):
        return self.gross_incremental_benefit-self.incremental_opex-self.replacement_obligation


class BenefitLedger:
    """One claim per enterprise × benefit stream × period."""
    def __init__(self): self._claims={}
    def add(self,claim: BenefitClaim):
        key=(claim.enterprise_id,claim.benefit_stream_id,claim.period)
        if key in self._claims: raise ValueError(f"Duplicate benefit claim: {key}")
        self._claims[key]=claim
    @property
    def claims(self): return tuple(self._claims.values())
    def consolidated(self):
        total=sum(c.net_reproducible_benefit for c in self._claims.values()); by_class={}
        for c in self._claims.values(): by_class[c.source_class]=by_class.get(c.source_class,0.0)+c.net_reproducible_benefit
        return {"net_reproducible_benefit":total,"claim_count":len(self._claims),"by_evidence_class":by_class,
                "scenario_values_are_not_observed_cash":True}


def cashflow_npv(cashflows: Iterable[float],discount_rate: float):
    flows=list(cashflows)
    if not math.isfinite(discount_rate) or discount_rate<=-1: raise ValueError("discount_rate must be finite and greater than -1")
    if any(not math.isfinite(x) for x in flows): raise ValueError("cashflows must be finite")
    return sum(v/((1+discount_rate)**t) for t,v in enumerate(flows))


def empirical_cvar(losses: Iterable[float],alpha: float=0.95):
    """Mean of the worst ceil((1-alpha)*N) observed losses; descriptive, not constrained optimization."""
    values=sorted(float(x) for x in losses)
    if not values or any(not math.isfinite(x) for x in values): raise ValueError("losses must be a non-empty finite sequence")
    if not 0<alpha<1: raise ValueError("alpha must be between 0 and 1")
    tail=max(1,math.ceil((1-alpha)*len(values)))
    return sum(values[-tail:])/tail


def pareto_frontier(rows: Iterable[dict],maximize: tuple[str,...],minimize: tuple[str,...]=()):
    data=list(rows); metrics=maximize+minimize
    if not metrics: raise ValueError("At least one objective is required")
    for row in data:
        for key in metrics:
            if key not in row or not math.isfinite(float(row[key])): raise ValueError(f"Missing or invalid Pareto metric: {key}")
    def dominates(a,b):
        av=[float(a[k])*(1 if k in maximize else -1) for k in metrics]
        bv=[float(b[k])*(1 if k in maximize else -1) for k in metrics]
        return all(x>=y for x,y in zip(av,bv)) and any(x>y for x,y in zip(av,bv))
    return [r for i,r in enumerate(data) if not any(dominates(o,r) for j,o in enumerate(data) if i!=j)]
