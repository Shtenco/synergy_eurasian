from interfaces.ai_contracts import nexus_economy_advisory

def test_nexus_cannot_authorize_eurasian_funding():
    r=nexus_economy_advisory({"task_type":"ECONOMY","model_id":"nexus-v18","proposal":{"sector":"agro"},"confidence":0.6,"limitations":["advisory"]})
    assert r["funding_authorization"] is False
    assert r["requires_capital_governance"] is True
