from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_economy import POLICY_VERSION, score_contributions


def contribution(**overrides):
    record = {
        "schema_version": "1.0",
        "contribution_id": "contrib-001",
        "contributor_id": "person-pseudo-001",
        "contributor_kind": "HUMAN",
        "project_id": "project-001",
        "benefit_stream_id": "benefit-001",
        "category": "TECHNICAL",
        "status": "ACCEPTED",
        "effort_units": 10,
        "effort_unit": "verified_work_package_unit",
        "complexity_factor": 1.5,
        "quality_factor": 0.8,
        "outcome_factor": 1.2,
        "reliability_factor": 0.9,
        "attribution_share": 1,
        "evidence": [{
            "evidence_id": "evidence-001",
            "sha256": "a" * 64,
            "source": "independent-review",
            "independent": True,
        }],
        "verification": {
            "verifier_id": "verifier-001",
            "independent_from_contributor": True,
            "conflict_disclosed": True,
            "signature_reference": "sig:review-001",
        },
    }
    record.update(overrides)
    return record


def test_score_is_deterministic_and_non_monetary():
    result = score_contributions([contribution()])
    assert result["policy_version"] == POLICY_VERSION
    assert result["total_labor_score"] == "12.96"
    assert result["status"] == "NON_MONETARY_SCORE_ONLY"
    assert result["money_issued"] is False
    assert "currency" not in result


def test_same_benefit_can_be_shared_but_attribution_must_not_exceed_one():
    first = contribution(contribution_id="a", attribution_share="0.4")
    second = contribution(contribution_id="b", contributor_id="person-002", attribution_share="0.6")
    result = score_contributions([second, first])
    assert result["attribution_totals"] == {"benefit-001": "1"}
    assert [row["contribution_id"] for row in result["contributions"]] == ["a", "b"]


def test_overallocated_benefit_stream_is_rejected():
    first = contribution(contribution_id="a", attribution_share="0.7")
    second = contribution(contribution_id="b", attribution_share="0.5")
    with pytest.raises(ValueError, match="attribution exceeds"):
        score_contributions([first, second])


def test_duplicate_contribution_ids_are_rejected():
    with pytest.raises(ValueError, match="must be unique"):
        score_contributions([contribution(), contribution()])


def test_unaccepted_work_cannot_be_scored():
    with pytest.raises(ValueError, match="only ACCEPTED"):
        score_contributions([contribution(status="SUBMITTED")])


def test_self_attestation_without_independent_evidence_is_rejected():
    evidence = [{"evidence_id": "e1", "sha256": "b" * 64, "source": "self", "independent": False}]
    with pytest.raises(ValueError, match="independent evidence"):
        score_contributions([contribution(evidence=evidence)])


def test_non_independent_reviewer_is_rejected():
    verification = contribution()["verification"]
    verification["independent_from_contributor"] = False
    with pytest.raises(ValueError, match="verifier must be independent"):
        score_contributions([contribution(verification=verification)])


@pytest.mark.parametrize("field,value", [
    ("effort_units", "0"),
    ("complexity_factor", "2.1"),
    ("quality_factor", "1.1"),
    ("outcome_factor", "0.4"),
    ("reliability_factor", "-0.1"),
    ("attribution_share", "1.01"),
])
def test_policy_bounds_are_enforced(field, value):
    with pytest.raises(ValueError):
        score_contributions([contribution(**{field: value})])


def test_zero_quality_is_a_valid_zero_score_not_a_negative_score():
    result = score_contributions([contribution(quality_factor="0")])
    assert result["total_labor_score"] == "0"


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError, match="unsupported contribution category"):
        score_contributions([contribution(category="UNKNOWN")])


def test_effort_unit_is_required():
    record = contribution()
    del record["effort_unit"]
    with pytest.raises(ValueError, match="effort_unit"):
        score_contributions([record])


def test_negative_observed_hours_are_rejected():
    with pytest.raises(ValueError, match="hours_observed cannot be negative"):
        score_contributions([contribution(hours_observed="-1")])


def test_json_schema_accepts_valid_contribution_and_rejects_invalid_bounds():
    import jsonschema

    schema_path = ROOT / "interfaces" / "labor_contribution.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=contribution(), schema=schema)

    invalid = contribution(attribution_share=1.01)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)
