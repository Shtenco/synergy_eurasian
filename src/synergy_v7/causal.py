"""Matched-pair difference-in-differences estimator for SYNERGY V7.3.1."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math
import numpy as np
from scipy.stats import t as student_t


@dataclass(frozen=True)
class CausalObservation:
    observation_id: str
    matched_pair_id: str
    unit_id: str
    group: str  # TREATED or CONTROL
    period: str # PRE or POST
    outcome: float
    evidence_id: str
    source_class: str="OBSERVED"
    def __post_init__(self):
        if not all((self.observation_id,self.matched_pair_id,self.unit_id,self.evidence_id)):
            raise ValueError("Causal observation identity and evidence are required")
        if self.group not in {"TREATED","CONTROL"}: raise ValueError("group must be TREATED or CONTROL")
        if self.period not in {"PRE","POST"}: raise ValueError("period must be PRE or POST")
        if not math.isfinite(self.outcome): raise ValueError("outcome must be finite")
        if self.source_class not in {"OBSERVED","VERIFIED","UNDERWRITTEN","SCENARIO"}:
            raise ValueError("Unsupported source_class")


def matched_pair_difference_in_differences(
    observations: Iterable[CausalObservation],
    confidence_level: float=0.95,
    outcome_direction: str="HIGHER_IS_BETTER",
) -> dict:
    """Estimate mean paired DiD and t interval across matched pairs.

    Each matched pair must contain exactly one treated and one control unit,
    each observed once pre and once post. This is a small-sample descriptive
    estimator; validity depends on matching, parallel trends and no spillovers.
    """
    rows=list(observations)
    if not 0<confidence_level<1: raise ValueError("confidence_level must be between 0 and 1")
    if outcome_direction not in {"HIGHER_IS_BETTER","LOWER_IS_BETTER"}:
        raise ValueError("Unsupported outcome_direction")
    if len({x.observation_id for x in rows})!=len(rows): raise ValueError("Duplicate observation_id")
    pairs={}
    for x in rows:
        slot=pairs.setdefault(x.matched_pair_id,{})
        key=(x.group,x.period)
        if key in slot: raise ValueError(f"Duplicate group-period observation in pair {x.matched_pair_id}")
        slot[key]=x
    required={("TREATED","PRE"),("TREATED","POST"),("CONTROL","PRE"),("CONTROL","POST")}
    effects=[]; classes={}
    for pair_id,slot in sorted(pairs.items()):
        if set(slot)!=required: raise ValueError(f"Incomplete matched pair: {pair_id}")
        treated_ids={slot[("TREATED","PRE")].unit_id,slot[("TREATED","POST")].unit_id}
        control_ids={slot[("CONTROL","PRE")].unit_id,slot[("CONTROL","POST")].unit_id}
        if len(treated_ids)!=1 or len(control_ids)!=1 or treated_ids==control_ids:
            raise ValueError(f"Unit identity/group assignment changes within pair: {pair_id}")
        treated_change=slot[("TREATED","POST")].outcome-slot[("TREATED","PRE")].outcome
        control_change=slot[("CONTROL","POST")].outcome-slot[("CONTROL","PRE")].outcome
        effect=treated_change-control_change
        effects.append(effect)
        for x in slot.values(): classes[x.source_class]=classes.get(x.source_class,0)+1
    if len(effects)<2: raise ValueError("At least two complete matched pairs are required for uncertainty estimates")
    arr=np.asarray(effects,dtype=float); n=len(arr)
    estimate=float(arr.mean()); se=float(arr.std(ddof=1)/math.sqrt(n))
    df=n-1; critical=float(student_t.ppf((1+confidence_level)/2,df))
    t_stat=estimate/se if se>0 else (math.copysign(math.inf,estimate) if estimate else 0.0)
    p_value=float(2*student_t.sf(abs(t_stat),df)) if se>0 else (0.0 if estimate else 1.0)
    lower=estimate-critical*se; upper=estimate+critical*se
    if outcome_direction=="LOWER_IS_BETTER":
        beneficial=-estimate; beneficial_ci=(-upper,-lower)
    else:
        beneficial=estimate; beneficial_ci=(lower,upper)
    return {"estimator":"MATCHED_PAIR_DIFFERENCE_IN_DIFFERENCES","matched_pair_count":n,
        "observation_count":len(rows),"effect_estimate":estimate,"standard_error":se,
        "degrees_of_freedom":df,"confidence_level":confidence_level,
        "confidence_interval":[lower,upper],"t_statistic":t_stat,"two_sided_p_value":p_value,
        "beneficial_effect_estimate":beneficial,"beneficial_effect_interval":list(beneficial_ci),
        "outcome_direction":outcome_direction,"pair_effects":arr.tolist(),
        "evidence_class_counts":classes,
        "causal_interpretation_requires_parallel_trends":True,
        "parallel_trends_testable_with_one_pre_period":False,
        "randomization_or_matching_quality_verified":False,
        "spillovers_and_time_varying_confounders_assessed":False,
        "not_a_causal_proof_without_design_review":True}
