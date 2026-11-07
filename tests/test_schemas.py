import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_all_interface_schemas_compile():
    schema_paths = sorted((ROOT / "interfaces").glob("*.schema.json"))
    assert schema_paths, "No interface schemas found"
    for path in schema_paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_project_proposal_example_matches_schema():
    schema = load("interfaces/project_proposal.schema.json")
    example = load("examples/project_proposal_ai_agro.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
    assert errors == [], "\n".join(e.message for e in errors)


def test_point_in_time_contracts_require_known_at():
    demand = load("interfaces/demand_signal.schema.json")
    resource = load("interfaces/resource_state.schema.json")
    assert "known_at" in demand["required"]
    assert "known_at" in resource["required"]


def test_technology_candidate_has_evidence_and_next_gate():
    schema = load("interfaces/technology_candidate.schema.json")
    assert "evidence" in schema["required"]
    assert "next_gate" in schema["required"]


def test_demand_price_requires_explicit_currency():
    schema = load("interfaces/demand_signal.schema.json")
    validator = Draft202012Validator(schema)
    sample = {
        "signal_id": "demand-001", "as_of": "2026-11-06T00:00:00Z",
        "known_at": "2026-11-06T00:00:00Z",
        "source": {"authority": "market", "reference": "feed:1", "source_class": "B"},
        "geography": {"country": "KZ"},
        "demand": {"commodity_or_service": "power", "quantity": 10, "unit": "MWh",
            "time_horizon": "month", "price": 50},
        "status": "OBSERVED", "confidence": 0.8,
    }
    assert list(validator.iter_errors(sample))
    sample["demand"]["currency"] = "USD"
    assert not list(validator.iter_errors(sample))


def test_resource_state_rejects_negative_capacity_and_untyped_cost():
    schema = load("interfaces/resource_state.schema.json")
    validator = Draft202012Validator(schema)
    sample = {
        "resource_state_id": "resource-001", "resource_type": "POWER", "node_id": "node-1",
        "effective_time": "2026-11-06T00:00:00Z", "known_at": "2026-11-06T00:00:00Z",
        "capacity": {"available": -1, "unit": "MW"},
        "source": {"publisher": "operator", "reference": "grid:1", "source_class": "A"},
        "status": "OBSERVED", "confidence": 0.9,
    }
    assert list(validator.iter_errors(sample))
    sample["capacity"]["available"] = 1
    sample["cost"] = {"value": 10, "per_unit": "MWh"}
    assert list(validator.iter_errors(sample))
    sample["cost"]["currency"] = "KZT"
    assert not list(validator.iter_errors(sample))


def test_replicated_technology_requires_replication_evidence_and_economic_currency():
    schema = load("interfaces/technology_candidate.schema.json")
    validator = Draft202012Validator(schema)
    sample = {
        "technology_id": "tech-001", "name": "Storage", "problem": "Long duration storage",
        "claimed_effect": {"metric": "efficiency", "baseline": 0.8, "target": 0.9,
            "unit": "ratio", "claim_status": "REPLICATED"},
        "trl": 6, "evidence": {"independent_replications": 0, "references": []},
        "next_gate": {"description": "pilot", "required_capex": 100, "currency": "USD",
            "success_criteria": ["measured"]},
        "economics": {"unrisked_project_value": 1000, "probability_science": 0.8,
            "probability_scale": 0.5, "probability_market": 0.5},
        "status": "PILOT",
    }
    assert list(validator.iter_errors(sample))
    sample["evidence"] = {"independent_replications": 1, "references": ["study:1"]}
    sample["economics"]["currency"] = "USD"
    assert not list(validator.iter_errors(sample))


def test_new_canonical_financial_schemas_accept_valid_records_and_reject_zero_amounts():
    samples = {
        "interfaces/capital_authorization.schema.json": {
            "authorization_id": "auth-001", "proposal_id": "proposal-001",
            "entity_id": "entity-001", "amount": "100.00", "currency": "USD",
            "approved_by": "identity:finance", "approved_at": "2026-11-06T10:00:00Z",
            "approval_event_id": "event-001", "approval_event_hash": "a" * 64,
            "evidence_package_id": "evidence-001", "status": "ACTIVE",
        },
        "interfaces/payment_intent.schema.json": {
            "payment_intent_id": "payment-001", "entity_id": "entity-001",
            "beneficiary_id": "supplier-001", "amount": "100.00", "currency": "USD",
            "purpose": "invoice settlement", "authorization_id": "auth-001",
            "source_event_id": "event-002", "created_at": "2026-11-06T10:00:00Z",
            "expires_at": "2026-11-07T10:00:00Z", "idempotency_key": "idem-key-001",
            "status": "APPROVED", "evidence_ids": ["invoice:001"],
        },
        "interfaces/settlement_receipt.schema.json": {
            "settlement_receipt_id": "settlement-001", "payment_intent_id": "payment-001",
            "provider": "bank", "provider_reference": "bank-ref-001",
            "payer_entity_id": "entity-001", "payee_id": "supplier-001",
            "amount": "100.00", "currency": "USD", "settled_at": "2026-11-06T11:00:00Z",
            "external_transaction_id": "bank-tx-001", "evidence_package_id": "evidence-002",
            "source_event_id": "event-003", "status": "CONFIRMED",
        },
        "interfaces/accounting_snapshot.schema.json": {
            "snapshot_id": "snapshot-001", "entity_id": "entity-001", "period_id": "2026-Q4",
            "as_of": "2026-11-06T23:59:00Z", "known_at": "2026-11-07T00:00:00Z",
            "functional_currency": "USD", "cash_balance": "100.00", "total_assets": "200.00",
            "total_liabilities": "50.00", "equity": "150.00", "period_revenue": "80.00",
            "period_expenses": "30.00", "journal_hash": "b" * 64,
            "reconciliation_status": "VERIFIED", "evidence_ids": ["bank-statement:001"],
        },
    }
    for schema_path, sample in samples.items():
        validator = Draft202012Validator(load(schema_path), format_checker=FormatChecker())
        assert not list(validator.iter_errors(sample)), schema_path
        if "amount" in sample:
            invalid = dict(sample)
            invalid["amount"] = "0.00"
            assert list(validator.iter_errors(invalid)), schema_path
