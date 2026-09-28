from __future__ import annotations
from decimal import Decimal
from typing import Any


CONTRACT_ID = "synergy.economy.project-proposal/v1"
AUTHORITY = "productive_economy"

_STATUS={
    "model_candidate":"PROPOSED",
    "review":"UNDER_REVIEW",
    "rejected":"REJECTED",
    "approved_for_underwriting":"UNDER_REVIEW",
    "funded":"AUTHORIZED",
    "building":"AUTHORIZED",
    "commissioned":"AUTHORIZED",
    "operating":"AUTHORIZED",
    "closed":"AUTHORIZED",
}


def federation_project_proposal_payload(project: dict[str, Any]) -> dict[str, Any]:
    capex=project["capex"]
    economics=project["economics"]
    if economics.get("gva_equivalent_is_cash") is not False:
        raise ValueError("GVA equivalent must never be treated as cash")
    status=str(project["status"])
    if status not in _STATUS:
        raise ValueError("unsupported project status")
    cashflows=[]
    for key in ("expected_external_revenue","expected_operating_cashflow"):
        value=economics.get(key)
        if value is not None:
            cashflows.append(str(Decimal(str(value))))
    constraints=[]
    for dep in project.get("dependencies",[]):
        constraints.append(
            f"{dep.get('kind')}={dep.get('required_value')} {dep.get('unit')}; secured={bool(dep.get('secured'))}"
        )
    constraints.extend(project.get("risk",{}).get("stop_conditions",[]))
    evidence_ids=[
        str(x.get("milestone_id"))
        for x in project.get("evidence_plan",[])
        if x.get("milestone_id")
    ]
    return {
        "project_id": str(project["proposal_id"]),
        "country": str(project["country"]),
        "sector": str(project["sector"]),
        "capital_required": str(Decimal(str(capex["amount"]))),
        "currency": str(capex["currency"]).upper(),
        "expected_external_cashflows": cashflows,
        "constraints": constraints,
        "evidence_package_ids": evidence_ids,
        "authorization_status": _STATUS[status],
        "optimizer_scenario_id": str(project.get("model_run_id")) if project.get("model_run_id") else None,
    }
