from datetime import datetime, timezone
import base64
import hashlib
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_labor_credit_ledger import LaborCreditLedger
from synergy_labor_disputes import (
    DisputeError,
    LaborCreditDisputes,
    canonical_decision_payload,
)

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def setup():
    ledger = LaborCreditLedger()
    ledger.register_issuer("coop-a", "repair", "service-hour", "100", "policy")
    ledger.add_capacity("coop-a", "repair", "service-hour", "capacity-1", "80",
                        "a" * 64, "verifier", "capacity")
    ledger.issue("coop-a", "member-b", "contribution-1", "award-1", "c" * 64,
                 "repair", "service-hour", "capacity-1", "20",
                 "2030-01-01T00:00:00Z", "credit-1", "issue")
    keys = {}
    private = {}
    for resolver in ("resolver-a", "resolver-b"):
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        key_id = f"{resolver}-key"
        keys[key_id] = {
            "principal_id": resolver,
            "roles": ["DISPUTE_RESOLVER"],
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2028-01-01T00:00:00Z",
            "revoked_at": None,
        }
        private[resolver] = (key, key_id)
    return ledger, LaborCreditDisputes(ledger, keys), private


def signed_decision(private, *, case="case-1", credit="credit-1",
                    resolver="resolver-a", outcome="CLAIM_UPHELD", version=0):
    key, key_id = private[resolver]
    envelope = {
        "schema": "sle.dispute-decision/v1",
        "case_id": case,
        "credit_id": credit,
        "resolver_id": resolver,
        "outcome": outcome,
        "rationale_digest": hashlib.sha256(f"{outcome} rationale".encode()).hexdigest(),
        "decided_at": "2026-11-14T11:00:00Z",
        "expected_version": version,
        "key_id": key_id,
    }
    envelope["signature"] = base64.b64encode(
        key.sign(canonical_decision_payload(envelope))
    ).decode("ascii")
    return envelope


def open_case(ledger, disputes, *, case="case-1", actor="member-b"):
    return disputes.open_dispute(case, "credit-1", actor, "SERVICE_QUALITY",
                                 ["evidence://inspection/1"], f"open-{case}")


def test_open_dispute_freezes_transfer_redemption_and_cancellation():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    assert disputes.get_dispute("case-1")["status"] == "OPEN"
    with pytest.raises(ValueError, match="active dispute"):
        ledger.transfer("credit-1", "member-b", "member-c", 0, "blocked-transfer")
    with pytest.raises(ValueError, match="active dispute"):
        ledger.redeem("credit-1", "member-b", "1", 0, "blocked-redeem")
    with pytest.raises(ValueError, match="active dispute"):
        ledger.cancel("credit-1", "issuer-approval", "holder-approval", 0, "blocked-cancel")
    assert ledger.get_credit("credit-1")["remaining_units"] == "20"
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "20"
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger.close()


def test_signed_claim_upheld_decision_unfreezes_without_cancelling_obligation():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    result = disputes.decide(signed_decision(private), NOW, "decision-1")
    assert result["outcome"] == "CLAIM_UPHELD"
    assert result["frozen"] is False
    assert result["obligation_cancelled"] is False
    redeemed = ledger.redeem("credit-1", "member-b", "2", 0, "redeem-after-decision")
    assert redeemed["units_outstanding"] == "18"
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger.close()


def test_dispute_upheld_does_not_automatically_cancel_or_release_capacity():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    result = disputes.decide(
        signed_decision(private, outcome="DISPUTE_UPHELD"), NOW, "decision-1"
    )
    assert result["obligation_cancelled"] is False
    assert result["frozen"] is True
    assert ledger.get_credit("credit-1")["status"] == "ACTIVE"
    assert ledger.get_credit("credit-1")["remaining_units"] == "20"
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "20"
    with pytest.raises(ValueError, match="active dispute"):
        ledger.redeem("credit-1", "member-b", "1", 0, "blocked-after-upheld-dispute")
    with pytest.raises(DisputeError, match="already has an active dispute"):
        disputes.open_dispute("case-2", "credit-1", "coop-a", "SECOND",
                              ["evidence://second"], "second-open")
    released = disputes.acknowledge_remediation(
        "case-1", "remediation-agreement-1", "issuer-signed-ack-1",
        "holder-signed-ack-1", "remediation-ack",
    )
    assert released["frozen"] is False
    assert released["obligation_cancelled"] is False
    assert ledger.get_capacity("capacity-1")["reserved_units"] == "20"
    second = disputes.open_dispute("case-2", "credit-1", "coop-a", "FOLLOW_UP",
                                   ["evidence://follow-up"], "second-open-after-remediation")
    assert second["status"] == "OPEN"
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger.close()


def test_appeal_refreezes_and_requires_a_different_resolver():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    disputes.decide(signed_decision(private), NOW, "decision-1")
    appeal = disputes.appeal("case-1", "coop-a", "appeal-ref-1", "NEW_EVIDENCE",
                             ["evidence://appeal/1"], 1, "appeal-1")
    assert appeal["status"] == "APPEALED" and appeal["frozen"] is True
    case = disputes.get_dispute("case-1")
    assert case["appeal_ref"] == "appeal-ref-1"
    assert case["appeal_evidence_refs"] == ["evidence://appeal/1"]
    with pytest.raises(ValueError, match="active dispute"):
        ledger.redeem("credit-1", "member-b", "1", 0, "blocked-after-appeal")
    with pytest.raises(DisputeError, match="different resolver"):
        disputes.decide(signed_decision(private, version=2), NOW, "bad-appeal-decision")
    final = disputes.decide(
        signed_decision(private, resolver="resolver-b", outcome="DISPUTE_UPHELD", version=2),
        NOW, "appeal-decision",
    )
    assert final["status"] == "DECIDED" and final["frozen"] is True
    with pytest.raises(ValueError, match="active dispute"):
        ledger.redeem("credit-1", "member-b", "1", 0, "blocked-final-upheld")
    disputes.acknowledge_remediation(
        "case-1", "appeal-remediation-1", "issuer-ack-appeal",
        "holder-ack-appeal", "appeal-remediation",
    )
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger.close()


def test_decision_tampering_and_untrusted_or_wrong_role_resolver_are_rejected():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    envelope = signed_decision(private)
    envelope["outcome"] = "DISPUTE_UPHELD"
    with pytest.raises(DisputeError, match="signature verification failed"):
        disputes.decide(envelope, NOW, "tampered")
    disputes.trusted_resolver_keys["resolver-a-key"]["roles"] = ["REWARD_AUTHORIZER"]
    with pytest.raises(DisputeError, match="DISPUTE_RESOLVER"):
        disputes.decide(signed_decision(private), NOW, "wrong-role")
    ledger.close()


def test_only_credit_parties_can_open_or_appeal_and_only_one_appeal_is_allowed():
    ledger, disputes, private = setup()
    with pytest.raises(DisputeError, match="only issuer or current holder"):
        open_case(ledger, disputes, actor="intruder")
    open_case(ledger, disputes)
    disputes.decide(signed_decision(private), NOW, "decision-1")
    disputes.appeal("case-1", "member-b", "appeal-ref-1", "NEW_EVIDENCE",
                     ["evidence://appeal/1"], 1, "appeal-1")
    disputes.decide(
        signed_decision(private, resolver="resolver-b", version=2), NOW, "appeal-decision"
    )
    with pytest.raises(DisputeError, match="only one appeal"):
        disputes.appeal("case-1", "member-b", "appeal-ref-2", "AGAIN",
                        ["evidence://appeal/2"], 3, "appeal-2")
    ledger.close()


def test_dispute_commands_are_idempotent_and_replay_detects_projection_tampering():
    ledger, disputes, private = setup()
    first = open_case(ledger, disputes)
    replay = open_case(ledger, disputes)
    assert replay["idempotent_replay"] is True
    assert first["case_id"] == replay["case_id"]
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger._db.execute("UPDATE disputes SET status='DECIDED' WHERE case_id='case-1'")
    audit = ledger.verify_projection_consistency()
    assert audit["valid"] is False
    assert any("dispute projection differs" in issue for issue in audit["issues"])
    ledger.close()


def test_dispute_evidence_references_must_be_nonempty_and_unique():
    ledger, disputes, private = setup()
    with pytest.raises(DisputeError, match="at least one evidence"):
        disputes.open_dispute("case-empty", "credit-1", "member-b", "QUALITY", [], "empty")
    with pytest.raises(DisputeError, match="duplicate evidence"):
        disputes.open_dispute("case-dup", "credit-1", "member-b", "QUALITY",
                              ["same", "same"], "dup")
    ledger.close()


def test_signed_decision_matches_strict_json_schema():
    import json
    import jsonschema

    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    envelope = signed_decision(private)
    schema = json.loads(
        (ROOT / "interfaces" / "sle_dispute_decision.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=envelope, schema=schema)
    invalid = dict(envelope)
    invalid["outcome"] = "WRITE_OFF"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)
    ledger.close()


def test_second_active_dispute_for_same_credit_is_rejected():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    with pytest.raises(DisputeError, match="already has an active dispute"):
        disputes.open_dispute("case-2", "credit-1", "coop-a", "OTHER",
                              ["evidence://other"], "open-case-2")
    assert ledger.verify_projection_consistency()["valid"] is True
    ledger.close()


def test_legacy_dispute_table_is_migrated_additively(tmp_path):
    import sqlite3

    db = tmp_path / "legacy-sle.sqlite"
    raw = sqlite3.connect(db)
    raw.execute("""
        CREATE TABLE disputes (
            case_id TEXT PRIMARY KEY,
            credit_id TEXT NOT NULL,
            opened_by TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN','DECIDED','APPEALED')),
            version INTEGER NOT NULL,
            resolver_id TEXT,
            outcome TEXT,
            decision_digest TEXT,
            appeal_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    raw.commit()
    raw.close()
    ledger = LaborCreditLedger(db)
    columns = {row["name"] for row in ledger._db.execute("PRAGMA table_info(disputes)")}
    assert {"appeal_ref", "appeal_reason_code", "appeal_evidence_refs_json",
            "remediation_closed", "remediation_ref", "issuer_ack_ref",
            "holder_ack_ref"} <= columns
    indexes = ledger._db.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='disputes_one_active_per_credit'"
    ).fetchone()
    assert "remediation_closed=0" in indexes["sql"]
    ledger.close()


def test_revoked_resolver_key_is_rejected():
    ledger, disputes, private = setup()
    open_case(ledger, disputes)
    disputes.trusted_resolver_keys["resolver-a-key"]["revoked_at"] = "2026-11-14T10:00:00Z"
    with pytest.raises(DisputeError, match="revoked"):
        disputes.decide(signed_decision(private), NOW, "revoked-decision")
    ledger.close()
