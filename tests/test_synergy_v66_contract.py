"""Contract tests for the first SYNERGY V6.6 cell-state schema."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "interfaces" / "synergy_v66_cell_state.schema.json"
FIXTURE_PATH = ROOT / "examples" / "synergy_v6_6_cell_state_minimal.json"


def load_contract():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema, fixture


def test_minimal_cell_state_fixture_is_valid():
    schema, fixture = load_contract()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert list(validator.iter_errors(fixture)) == []


def test_cell_state_requires_bitemporal_timestamps():
    schema, fixture = load_contract()
    invalid = copy.deepcopy(fixture)
    del invalid["known_at"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(invalid))
    assert any(error.validator == "required" for error in errors)


def test_cell_state_rejects_non_iso_currency_code():
    schema, fixture = load_contract()
    invalid = copy.deepcopy(fixture)
    invalid["financial"]["cash_accounts"][0]["currency"] = "TENGE"
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(invalid))
    assert any("currency" in str(error.absolute_path) for error in errors)


def test_cell_state_rejects_untyped_evidence_class():
    schema, fixture = load_contract()
    invalid = copy.deepcopy(fixture)
    invalid["evidence"][0]["class"] = "verified_profit"
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(invalid))
    assert any(error.validator == "enum" for error in errors)
