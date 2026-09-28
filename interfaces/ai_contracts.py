from __future__ import annotations
from typing import Any

UPSTREAM_CONTRACT_ID="synergy.ai.proposal/v1"

def nexus_economy_advisory(payload:dict[str,Any])->dict[str,Any]:
    task=str(payload.get("task_type","")).upper()
    if task not in {"ECONOMY","GENERAL"}:
        raise ValueError(f"NEXUS proposal is not an economy advisory task: {task}")
    confidence=float(payload.get("confidence",-1))
    if not 0<=confidence<=1:
        raise ValueError("invalid confidence")
    limitations=payload.get("limitations")
    if not isinstance(limitations,list) or not limitations:
        raise ValueError("explicit limitations required")
    return {
        "source":"NEXUS_ADVISORY",
        "model_id":str(payload.get("model_id","")),
        "proposal":dict(payload.get("proposal") or {}),
        "confidence":confidence,
        "limitations":list(limitations),
        "funding_authorization":False,
        "requires_eiiom_validation":True,
        "requires_capital_governance":True,
    }
