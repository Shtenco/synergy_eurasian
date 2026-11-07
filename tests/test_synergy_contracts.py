import copy
import pytest
import json
from pathlib import Path

from interfaces.synergy_contracts import CONTRACT_ID, federation_project_proposal_payload


def test_existing_agro_proposal_maps_without_turning_gva_into_cash():
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/"examples"/"project_proposal_ai_agro.json").read_text(encoding="utf-8"))
    payload=federation_project_proposal_payload(project)
    assert CONTRACT_ID=="synergy.economy.project-proposal/v1"
    assert payload["country"]=="KZ"
    assert payload["capital_required"]=="250000000"
    assert payload["expected_external_cashflows"]==[]
    assert payload["authorization_status"]=="PROPOSED"


def test_project_lifecycle_never_self_promotes_to_capital_authorization():
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/"examples"/"project_proposal_ai_agro.json").read_text(encoding="utf-8"))
    for lifecycle in ("funded", "building", "commissioned", "operating", "closed"):
        candidate=copy.deepcopy(project)
        candidate["status"]=lifecycle
        payload=federation_project_proposal_payload(candidate)
        assert payload["lifecycle_status"] == lifecycle
        assert payload["authorization_status"] == "UNDER_REVIEW"


def test_project_dependency_secured_flag_must_be_boolean():
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/"examples"/"project_proposal_ai_agro.json").read_text(encoding="utf-8"))
    project["dependencies"]=[{"kind":"power","required_value":"1","unit":"MW","secured":"false"}]
    with pytest.raises(ValueError, match="explicit boolean"):
        federation_project_proposal_payload(project)


def test_project_capex_rejects_binary_float():
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/"examples"/"project_proposal_ai_agro.json").read_text(encoding="utf-8"))
    project["capex"]["amount"]=250000000.0
    with pytest.raises(ValueError, match="binary floating-point"):
        federation_project_proposal_payload(project)
