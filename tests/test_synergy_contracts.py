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
