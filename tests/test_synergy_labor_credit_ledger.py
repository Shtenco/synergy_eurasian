from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_credit_ledger import LaborCreditLedger


DUE = "2030-01-01T00:00:00+00:00"
LATER = "2030-01-03T00:00:00+00:00"


def prepared_ledger(path=":memory:", *, max_outstanding="100", capacity_units="80"):
    ledger = LaborCreditLedger(path)
    ledger.register_issuer("coop-a", "repair-service", "service-hour", max_outstanding, "policy-1")
    ledger.add_capacity(
        "coop-a", "repair-service", "service-hour", "capacity-1", capacity_units,
        "a" * 64, "independent-verifier", "capacity-1",
    )
    return ledger


def issue(ledger, *, units="30", credit_id="credit-1", key="issue-1", due=DUE):
    return ledger.issue(
        "coop-a", "member-b", f"contribution-{credit_id}", f"award-{key}",
        "c" * 64, "repair-service", "service-hour",
        "capacity-1", units, due, credit_id, key,
    )


def test_issue_creates_claim_and_reserves_capacity_without_money():
    ledger = prepared_ledger()
    result = issue(ledger, units="30")
    credit = ledger.get_credit("credit-1")
    capacity = ledger.get_capacity("capacity-1")
    assert result["units_issued"] == "30"
    assert credit["remaining_units"] == "30"
    assert credit["status"] == "ACTIVE"
    assert capacity["reserved_units"] == "30"
    assert capacity["available_units"] == "50"
    assert "currency" not in result
    assert ledger.verify_event_chain()["valid"] is True
    ledger.close()


def test_issuer_outstanding_limit_is_enforced_atomically():
    ledger = prepared_ledger(max_outstanding="60", capacity_units="80")
    issue(ledger, units="50")
    before = len(ledger.list_events())
    with pytest.raises(ValueError, match="outstanding limit"):
        issue(ledger, units="11", credit_id="credit-2", key="issue-2")
    assert len(ledger.list_events()) == before
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "50"
    ledger.close()


def test_capacity_limit_is_enforced_even_when_issuer_limit_allows_it():
    ledger = prepared_ledger()
    issue(ledger, units="75")
    with pytest.raises(ValueError, match="unreserved, unfulfilled capacity"):
        issue(ledger, units="6", credit_id="credit-2", key="issue-2")
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "75"
    ledger.close()


def test_issue_is_idempotent_and_conflicting_replay_is_rejected():
    ledger = prepared_ledger()
    first = issue(ledger, units="10", key="same-key")
    replay = issue(ledger, units="10", key="same-key")
    assert first["credit_id"] == replay["credit_id"]
    assert replay["idempotent_replay"] is True
    assert len(ledger.list_events()) == 3
    with pytest.raises(ValueError, match="different request"):
        issue(ledger, units="11", key="same-key")
    ledger.close()


def test_partial_and_full_redemption_consume_reserved_capacity_once():
    ledger = prepared_ledger()
    issue(ledger, units="20")
    partial = ledger.redeem("credit-1", "member-b", "7", 0, "redeem-1")
    assert partial["units_outstanding"] == "13"
    assert partial["status"] == "ACTIVE"
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "13"
    final = ledger.redeem("credit-1", "member-b", "13", 1, "redeem-2")
    assert final["status"] == "SETTLED"
    cap = ledger.get_capacity("capacity-1")
    assert cap["reserved_units"] == "0"
    assert cap["fulfilled_units"] == "20"
    assert cap["available_units"] == "60"
    ledger.close()


def test_wrong_holder_cannot_redeem_or_transfer():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    with pytest.raises(ValueError, match="current holder"):
        ledger.redeem("credit-1", "attacker", "1", 0, "bad-redeem")
    with pytest.raises(ValueError, match="current holder"):
        ledger.transfer("credit-1", "attacker", "member-c", 0, "bad-transfer")
    ledger.close()


def test_transfer_uses_optimistic_version_and_prevents_stale_spend():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    moved = ledger.transfer("credit-1", "member-b", "member-c", 0, "transfer-1")
    assert moved["version"] == 1
    with pytest.raises(ValueError, match="stale credit version"):
        ledger.redeem("credit-1", "member-c", "1", 0, "stale-redeem")
    redeemed = ledger.redeem("credit-1", "member-c", "1", 1, "redeem-1")
    assert redeemed["units_outstanding"] == "9"
    ledger.close()


def test_overdue_then_default_preserves_liability_and_freezes_issuer():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    overdue = ledger.mark_overdue("credit-1", LATER, "overdue-1")
    assert overdue["status"] == "OVERDUE"
    defaulted = ledger.mark_default("credit-1", LATER, "default-1")
    assert defaulted["status"] == "DEFAULTED"
    assert defaulted["units_outstanding"] == "10"
    with pytest.raises(ValueError, match="frozen"):
        issue(ledger, units="1", credit_id="credit-2", key="issue-2")
    with pytest.raises(ValueError, match="not redeemable"):
        ledger.redeem("credit-1", "member-b", "1", 2, "redeem-defaulted")
    ledger.close()


def test_cannot_mark_overdue_before_due_date():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    with pytest.raises(ValueError, match="not yet due"):
        ledger.mark_overdue("credit-1", "2029-12-31T00:00:00Z", "early")
    ledger.close()


def test_bilateral_cancellation_releases_only_unfulfilled_capacity():
    ledger = prepared_ledger()
    issue(ledger, units="20")
    ledger.redeem("credit-1", "member-b", "5", 0, "redeem-1")
    cancelled = ledger.cancel("credit-1", "sig:issuer-consent", "sig:holder-consent", 1, "cancel-1")
    assert cancelled["cancelled_units"] == "15"
    assert ledger.get_credit("credit-1")["status"] == "CANCELLED"
    cap = ledger.get_capacity("capacity-1")
    assert cap["reserved_units"] == "0"
    assert cap["fulfilled_units"] == "5"
    assert cap["available_units"] == "75"
    ledger.close()


def test_cancellation_requires_both_approval_references():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    with pytest.raises(ValueError, match="holder_approval_ref"):
        ledger.cancel("credit-1", "sig:issuer", "", 0, "cancel-bad")
    assert ledger.get_credit("credit-1")["remaining_units"] == "10"
    ledger.close()


def test_same_capacity_evidence_cannot_be_registered_twice():
    ledger = prepared_ledger()
    with pytest.raises(Exception):
        ledger.add_capacity(
            "coop-a", "repair-service", "service-hour", "capacity-2", "80",
            "a" * 64, "another-verifier", "capacity-2",
        )
    assert len(ledger.list_events()) == 2
    ledger.close()


def test_persistent_database_reopens_with_valid_event_chain(tmp_path):
    path = tmp_path / "labor-credit.sqlite"
    first = prepared_ledger(str(path))
    issue(first, units="10")
    first.close()
    reopened = LaborCreditLedger(path)
    assert reopened.get_credit("credit-1")["remaining_units"] == "10"
    assert reopened.verify_event_chain()["valid"] is True
    reopened.close()


def test_event_rows_are_append_only_and_chain_detects_tampering():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    with pytest.raises(Exception):
        ledger._db.execute("UPDATE events SET event_type='TAMPERED' WHERE seq=1")
    ledger._db.execute("DROP TRIGGER events_no_update")
    ledger._db.execute("UPDATE events SET event_type='TAMPERED' WHERE seq=1")
    assert ledger.verify_event_chain()["valid"] is False
    ledger.close()


def test_concurrent_issuance_cannot_oversubscribe_capacity_or_issuer_limit(tmp_path):
    path = tmp_path / "concurrent.sqlite"
    setup = LaborCreditLedger(path)
    setup.register_issuer("coop-a", "repair-service", "service-hour", "10", "policy")
    setup.add_capacity(
        "coop-a", "repair-service", "service-hour", "capacity-1", "10",
        "b" * 64, "independent-verifier", "capacity",
    )
    setup.close()

    def attempt(index):
        ledger = LaborCreditLedger(path)
        try:
            return ledger.issue(
                "coop-a", f"member-{index}", f"contribution-{index}", f"award-parallel-{index}",
                "d" * 64, "repair-service", "service-hour",
                "capacity-1", "7", DUE, f"credit-{index}", f"parallel-{index}",
            )["credit_id"]
        except ValueError:
            return None
        finally:
            ledger.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [1, 2]))
    assert sum(item is not None for item in outcomes) == 1
    check = LaborCreditLedger(path)
    assert check.get_capacity("capacity-1")["reserved_units"] == "7"
    assert check.verify_event_chain()["valid"] is True
    check.close()


def test_event_chain_is_valid_after_all_lifecycle_events():
    ledger = prepared_ledger()
    issue(ledger, units="5")
    ledger.transfer("credit-1", "member-b", "member-c", 0, "transfer")
    ledger.redeem("credit-1", "member-c", "5", 1, "redeem")
    audit = ledger.verify_event_chain()
    assert audit["valid"] is True
    assert audit["events_checked"] == 5
    projection = ledger.verify_projection_consistency()
    assert projection["valid"] is True
    assert projection["events_replayed"] == 5
    ledger.close()


def test_one_contribution_cannot_back_two_credit_issues():
    ledger = prepared_ledger()
    issue(ledger, units="10", credit_id="credit-1", key="issue-1")
    with pytest.raises(Exception):
        ledger.issue(
            "coop-a", "member-c", "contribution-credit-1", "award-issue-2",
            "c" * 64, "repair-service", "service-hour", "capacity-1",
            "10", DUE, "credit-2", "issue-2",
        )
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "10"
    assert len(ledger.list_events()) == 3
    ledger.close()


def test_award_reference_cannot_be_reused_for_another_contribution():
    ledger = prepared_ledger()
    issue(ledger, units="10", credit_id="credit-1", key="issue-1")
    with pytest.raises(Exception):
        ledger.issue(
            "coop-a", "member-c", "contribution-credit-2", "award-issue-1",
            "e" * 64, "repair-service", "service-hour", "capacity-1",
            "10", DUE, "credit-2", "issue-2",
        )
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "10"
    ledger.close()


def test_credit_claim_schema_accepts_ledger_projection_and_rejects_missing_award_link():
    import jsonschema

    ledger = prepared_ledger()
    issue(ledger, units="4")
    claim = ledger.get_credit("credit-1")
    schema = json.loads((ROOT / "interfaces" / "labor_credit_claim.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=claim, schema=schema)
    invalid = dict(claim)
    del invalid["award_authorization_ref"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)
    ledger.close()


def test_projection_replay_detects_direct_database_mutation():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    ledger._db.execute("UPDATE credits SET remaining_units='9' WHERE credit_id='credit-1'")
    audit = ledger.verify_projection_consistency()
    assert audit["valid"] is False
    assert any("projection differs" in item for item in audit["issues"])
    ledger.close()


def test_projection_replay_detects_capacity_reservation_corruption():
    ledger = prepared_ledger()
    issue(ledger, units="10")
    ledger._db.execute("UPDATE capacity SET reserved_units='8' WHERE capacity_id='capacity-1'")
    audit = ledger.verify_projection_consistency()
    assert audit["valid"] is False
    assert any("capacity projection differs" in item for item in audit["issues"])
    ledger.close()
