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
