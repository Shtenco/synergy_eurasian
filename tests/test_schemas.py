import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_project_proposal_example_matches_schema():
    schema = load("interfaces/project_proposal.schema.json")
    example = load("examples/project_proposal_ai_agro.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
    assert errors == [], "\n".join(e.message for e in errors)


def test_evidence_schema_compiles():
    schema = load("interfaces/evidence_package.schema.json")
    Draft202012Validator.check_schema(schema)
