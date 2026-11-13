"""Auditable dispute and appeal workflow for SLE service-credit claims.

A dispute freezes transfer, redemption and bilateral cancellation in the underlying
LaborCreditLedger while OPEN or APPEALED. A signed resolver decision closes the
freeze but never writes off or cancels the underlying obligation.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "sle.dispute-decision/v1"
DOMAIN = b"SYNERGY_SLE_DISPUTE_DECISION_V1\x00"
OUTCOMES = frozenset({"CLAIM_UPHELD", "DISPUTE_UPHELD"})

PARTY_AUTH_SCHEMA = "sle.dispute-party-authorization/v1"
PARTY_AUTH_DOMAIN = b"SYNERGY_SLE_DISPUTE_PARTY_AUTHORIZATION_V1\x00"
PARTY_ROLE = "SLE_CREDIT_PARTY"


def canonical_party_authorization_payload(envelope: Mapping[str, Any]) -> bytes:
    body = dict(envelope)
    body.pop("signature", None)
    try:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise DisputeError("party authorization is not canonical-JSON compatible") from None
    return PARTY_AUTH_DOMAIN + raw


def _action_digest(action: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps({"action": action, "payload": dict(payload)},
                     sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_party_authorization(envelope, key_registry, *, action, case_id, credit_id,
                               action_digest, expected_version, now):
    required = {"schema", "action", "case_id", "credit_id", "principal_id",
                "expected_version", "action_digest", "signed_at", "key_id", "signature"}
    if not isinstance(envelope, Mapping) or set(envelope) != required:
        raise DisputeError("party authorization envelope fields mismatch")
    if envelope["schema"] != PARTY_AUTH_SCHEMA or envelope["action"] != action:
        raise DisputeError("party authorization schema or action mismatch")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DisputeError("party authorization verification time must be timezone-aware")
    principal, key_id = _text(envelope["principal_id"], "principal_id"), _text(envelope["key_id"], "key_id")
    if _text(envelope["case_id"], "case_id") != case_id or _text(envelope["credit_id"], "credit_id") != credit_id:
        raise DisputeError("party authorization is bound to another case or credit")
    if envelope["expected_version"] != expected_version or isinstance(envelope["expected_version"], bool):
        raise DisputeError("party authorization version mismatch")
    if _text(envelope["action_digest"], "action_digest") != action_digest:
        raise DisputeError("party authorization action digest mismatch")
    signed_at = _time(envelope["signed_at"], "signed_at")
    instant = now.astimezone(timezone.utc)
    if signed_at > instant:
        raise DisputeError("party authorization cannot be future-dated")
    record = key_registry.get(key_id)
    if not isinstance(record, Mapping) or _text(record.get("principal_id"), "principal_id") != principal:
        raise DisputeError("party authorization key does not match principal")
    roles = record.get("roles")
    if not isinstance(roles, (list, tuple, set, frozenset)) or PARTY_ROLE not in {str(x).upper() for x in roles}:
        raise DisputeError("trusted key lacks SLE_CREDIT_PARTY role")
    valid_from, valid_until = _time(record.get("valid_from"), "key valid_from"), _time(record.get("valid_until"), "key valid_until")
    if not (valid_from <= instant < valid_until) or signed_at < valid_from or signed_at >= valid_until:
        raise DisputeError("party authorization key is outside its validity interval")
    revoked_at = record.get("revoked_at")
    if revoked_at is not None and instant >= _time(revoked_at, "key revoked_at"):
        raise DisputeError("party authorization key is revoked")
    try:
        public = base64.b64decode(_text(record.get("public_key_b64"), "public_key_b64"), validate=True)
        signature = base64.b64decode(_text(envelope["signature"], "signature"), validate=True)
    except (binascii.Error, ValueError):
        raise DisputeError("invalid party authorization key or signature encoding") from None
    if len(public) != 32 or len(signature) != 64:
        raise DisputeError("invalid Ed25519 party authorization key or signature length")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, canonical_party_authorization_payload(envelope))
    except (InvalidSignature, ValueError):
        raise DisputeError("party authorization signature verification failed") from None
    return {"principal_id": principal, "key_id": key_id,
            "authorization_digest": hashlib.sha256(canonical_party_authorization_payload(envelope)).hexdigest(),
            "envelope": dict(envelope)}


class DisputeError(ValueError):
    """Invalid dispute command, authority, or signed decision."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DisputeError(f"{field} must be a non-empty string")
    result = value.strip()
    if len(result) > 256:
        raise DisputeError(f"{field} exceeds 256 characters")
    return result


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DisputeError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise DisputeError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DisputeError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def canonical_decision_payload(envelope: Mapping[str, Any]) -> bytes:
    body = dict(envelope)
    body.pop("signature", None)
    try:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise DisputeError("decision envelope is not canonical-JSON compatible") from None
    return DOMAIN + raw


def verify_resolver_decision(
    envelope: Mapping[str, Any],
    key_registry: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    required = {
        "schema", "case_id", "credit_id", "resolver_id", "outcome",
        "rationale_digest", "decided_at", "expected_version", "key_id", "signature",
    }
    if not isinstance(envelope, Mapping) or set(envelope) != required:
        raise DisputeError("decision envelope fields mismatch")
    if envelope["schema"] != SCHEMA:
        raise DisputeError("unsupported dispute decision schema")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DisputeError("now must be timezone-aware")
    if not isinstance(key_registry, Mapping):
        raise DisputeError("key_registry must be a mapping")
    values = {k: _text(envelope[k], k) for k in (
        "case_id", "credit_id", "resolver_id", "outcome", "rationale_digest",
        "key_id", "signature",
    )}
    if values["outcome"] not in OUTCOMES:
        raise DisputeError("unsupported dispute outcome")
    digest = values["rationale_digest"]
    if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise DisputeError("rationale_digest must be a SHA-256 hex digest")
    version = envelope["expected_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise DisputeError("expected_version must be a non-negative integer")
    decided = _time(envelope["decided_at"], "decided_at")
    instant = now.astimezone(timezone.utc)
    if decided > instant:
        raise DisputeError("decision cannot be future-dated")

    record = key_registry.get(values["key_id"])
    if not isinstance(record, Mapping):
        raise DisputeError("resolver key is not in trusted registry")
    if _text(record.get("principal_id"), "principal_id") != values["resolver_id"]:
        raise DisputeError("resolver identity does not match trusted key")
    roles = record.get("roles")
    if not isinstance(roles, (list, tuple, set, frozenset)) or "DISPUTE_RESOLVER" not in {str(x).upper() for x in roles}:
        raise DisputeError("trusted key lacks DISPUTE_RESOLVER role")
    valid_from = _time(record.get("valid_from"), "key valid_from")
    valid_until = _time(record.get("valid_until"), "key valid_until")
    if not (valid_from <= instant < valid_until) or decided < valid_from or decided >= valid_until:
        raise DisputeError("resolver key is outside its validity interval")
    revoked_at = record.get("revoked_at")
    if revoked_at is not None and instant >= _time(revoked_at, "key revoked_at"):
        raise DisputeError("resolver key is revoked")
    try:
        public = base64.b64decode(_text(record.get("public_key_b64"), "public_key_b64"), validate=True)
        signature = base64.b64decode(values["signature"], validate=True)
    except (binascii.Error, ValueError):
        raise DisputeError("invalid resolver key or signature encoding") from None
    if len(public) != 32 or len(signature) != 64:
        raise DisputeError("invalid Ed25519 key or signature length")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, canonical_decision_payload(envelope))
    except (InvalidSignature, ValueError):
        raise DisputeError("resolver decision signature verification failed") from None
    return {
        **values,
        "expected_version": version,
        "decided_at": decided.isoformat(),
        "decision_digest": hashlib.sha256(canonical_decision_payload(envelope)).hexdigest(),
    }


class LaborCreditDisputes:
    """Dispute state machine sharing the ledger transaction/event log."""

    def __init__(self, ledger: Any, trusted_resolver_keys: Mapping[str, Mapping[str, Any]],
                 trusted_party_keys: Mapping[str, Mapping[str, Any]] | None = None):
        if not isinstance(trusted_resolver_keys, Mapping):
            raise DisputeError("trusted_resolver_keys must be a mapping")
        if not isinstance(trusted_party_keys, Mapping):
            raise DisputeError("trusted_party_keys mapping is required; unsigned party actions are disabled")
        self.ledger = ledger
        self.trusted_resolver_keys = trusted_resolver_keys
        self.trusted_party_keys = trusted_party_keys

    def open_dispute(
        self, case_id: str, credit_id: str, opened_by: str, reason_code: str,
        evidence_refs: list[str], idempotency_key: str,
        authorization_envelope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        case, credit = _text(case_id, "case_id"), _text(credit_id, "credit_id")
        actor, reason = _text(opened_by, "opened_by"), _text(reason_code, "reason_code")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise DisputeError("at least one evidence reference is required")
        refs = [_text(x, "evidence_ref") for x in evidence_refs]
        if len(set(refs)) != len(refs):
            raise DisputeError("duplicate evidence references are not allowed")
        action_payload = {"opened_by": actor, "reason_code": reason, "evidence_refs": refs}
        digest = _action_digest("OPEN_DISPUTE", action_payload)
        verified_party = verify_party_authorization(
            authorization_envelope, self.trusted_party_keys, action="OPEN_DISPUTE",
            case_id=case, credit_id=credit, action_digest=digest,
            expected_version=0, now=datetime.now(timezone.utc))
        if verified_party["principal_id"] != actor:
            raise DisputeError("signed party principal does not match dispute opener")
        request = {"case_id": case, "credit_id": credit, "opened_by": actor,
                   "reason_code": reason, "evidence_refs": refs,
                   "party_authorization": verified_party["envelope"],
                   "party_authorization_digest": verified_party["authorization_digest"]}

        def apply():
            row = self.ledger._credit(credit)
            if actor not in {row["issuer_id"], row["holder_id"]}:
                raise DisputeError("only issuer or current holder may open a dispute")
            if row["status"] not in {"ACTIVE", "OVERDUE", "DEFAULTED"}:
                raise DisputeError("settled or cancelled claims cannot be disputed")
            if self.ledger._db.execute("SELECT 1 FROM disputes WHERE case_id=?", (case,)).fetchone():
                raise DisputeError("case_id already exists")
            if self.ledger._db.execute(
                """SELECT 1 FROM disputes WHERE credit_id=? AND
                   (status IN ('OPEN','APPEALED') OR
                    (status='DECIDED' AND outcome='DISPUTE_UPHELD' AND remediation_closed=0))""",
                (credit,),
            ).fetchone():
                raise DisputeError("credit already has an active dispute")
            self.ledger._db.execute(
                """INSERT INTO disputes
                (case_id,credit_id,opened_by,reason_code,evidence_refs_json,status,version,
                 resolver_id,outcome,decision_digest,appeal_count)
                VALUES (?,?,?,?,?,'OPEN',0,NULL,NULL,NULL,0)""",
                (case, credit, actor, reason, json.dumps(refs, separators=(",", ":"), ensure_ascii=False)),
            )
            return {"case_id": case, "credit_id": credit, "status": "OPEN",
                    "version": 0, "frozen": True, "evidence_count": len(refs)}
        return self.ledger._command("DISPUTE_OPENED", idempotency_key, request, apply)

    def decide(self, envelope: Mapping[str, Any], now: datetime, idempotency_key: str) -> dict[str, Any]:
        verified = verify_resolver_decision(envelope, self.trusted_resolver_keys, now=now)
        request = dict(verified)

        def apply():
            row = self._case(verified["case_id"])
            if row["credit_id"] != verified["credit_id"]:
                raise DisputeError("decision credit_id does not match case")
            if row["status"] not in {"OPEN", "APPEALED"}:
                raise DisputeError("only open or appealed disputes can be decided")
            if row["version"] != verified["expected_version"]:
                raise DisputeError("stale dispute version")
            credit = self.ledger._credit(row["credit_id"])
            if verified["resolver_id"] in {credit["issuer_id"], credit["holder_id"]}:
                raise DisputeError("a dispute party cannot resolve its own case")
            if row["resolver_id"] == verified["resolver_id"]:
                raise DisputeError("appeal must be decided by a different resolver")
            self.ledger._db.execute(
                """UPDATE disputes SET status='DECIDED',version=version+1,resolver_id=?,
                   outcome=?,decision_digest=? WHERE case_id=?""",
                (verified["resolver_id"], verified["outcome"], verified["decision_digest"], verified["case_id"]),
            )
            frozen = verified["outcome"] == "DISPUTE_UPHELD"
            return {"case_id": verified["case_id"], "status": "DECIDED",
                    "outcome": verified["outcome"], "resolver_id": verified["resolver_id"],
                    "decision_digest": verified["decision_digest"],
                    "version": verified["expected_version"] + 1, "frozen": frozen,
                    "obligation_cancelled": False}
        return self.ledger._command("DISPUTE_DECIDED", idempotency_key, request, apply)

    def appeal(
        self, case_id: str, appellant_id: str, appeal_ref: str, reason_code: str,
        evidence_refs: list[str], expected_version: int, idempotency_key: str,
        authorization_envelope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        case, appellant = _text(case_id, "case_id"), _text(appellant_id, "appellant_id")
        ref, reason = _text(appeal_ref, "appeal_ref"), _text(reason_code, "reason_code")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 0:
            raise DisputeError("expected_version must be a non-negative integer")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise DisputeError("appeal requires at least one evidence reference")
        refs = [_text(x, "appeal_evidence_ref") for x in evidence_refs]
        if len(set(refs)) != len(refs):
            raise DisputeError("duplicate appeal evidence references are not allowed")
        action_payload = {"appellant_id": appellant, "appeal_ref": ref,
                          "reason_code": reason, "evidence_refs": refs}
        digest = _action_digest("APPEAL_DISPUTE", action_payload)
        case_credit_id = _text(self._case(case)["credit_id"], "credit_id")
        verified_party = verify_party_authorization(
            authorization_envelope, self.trusted_party_keys, action="APPEAL_DISPUTE",
            case_id=case, credit_id=case_credit_id, action_digest=digest,
            expected_version=expected_version, now=datetime.now(timezone.utc))
        if verified_party["principal_id"] != appellant:
            raise DisputeError("signed party principal does not match appellant")
        request = {"case_id": case, "appellant_id": appellant, "appeal_ref": ref,
                   "reason_code": reason, "evidence_refs": refs, "expected_version": expected_version,
                   "party_authorization": verified_party["envelope"],
                   "party_authorization_digest": verified_party["authorization_digest"]}

        def apply():
            row = self._case(case)
            if row["status"] != "DECIDED" or row["version"] != expected_version:
                raise DisputeError("only the current decision may be appealed")
            if row["appeal_count"] != 0:
                raise DisputeError("only one appeal is permitted in this reference workflow")
            credit = self.ledger._credit(row["credit_id"])
            if appellant not in {credit["issuer_id"], credit["holder_id"]}:
                raise DisputeError("only issuer or current holder may appeal")
            if appellant == row["resolver_id"]:
                raise DisputeError("resolver cannot appeal own decision")
            self.ledger._db.execute(
                """UPDATE disputes SET status='APPEALED',version=version+1,appeal_count=1,
                   appeal_ref=?,appeal_reason_code=?,appeal_evidence_refs_json=? WHERE case_id=?""",
                (ref, reason, json.dumps(refs, separators=(",", ":"), ensure_ascii=False), case),
            )
            return {"case_id": case, "status": "APPEALED", "version": expected_version + 1,
                    "frozen": True, "appeal_ref": ref, "appeal_evidence_count": len(refs)}
        return self.ledger._command("DISPUTE_APPEALED", idempotency_key, request, apply)

    def acknowledge_remediation(
        self, case_id: str, remediation_ref: str, issuer_ack_ref: str,
        holder_ack_ref: str, idempotency_key: str,
        issuer_authorization: Mapping[str, Any] | None = None,
        holder_authorization: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        case = _text(case_id, "case_id")
        remediation = _text(remediation_ref, "remediation_ref")
        issuer_ack = _text(issuer_ack_ref, "issuer_ack_ref")
        holder_ack = _text(holder_ack_ref, "holder_ack_ref")
        if issuer_ack == holder_ack:
            raise DisputeError("issuer and holder acknowledgements must be distinct")
        row_snapshot = self._case(case)
        credit_snapshot = self.ledger._credit(row_snapshot["credit_id"])
        digest = _action_digest("ACKNOWLEDGE_REMEDIATION", {
            "remediation_ref": remediation,
            "issuer_ack_ref": issuer_ack,
            "holder_ack_ref": holder_ack,
        })
        expected_version = int(row_snapshot["version"])
        issuer_proof = verify_party_authorization(
            issuer_authorization, self.trusted_party_keys, action="ACKNOWLEDGE_REMEDIATION",
            case_id=case, credit_id=row_snapshot["credit_id"], action_digest=digest,
            expected_version=expected_version, now=datetime.now(timezone.utc))
        holder_proof = verify_party_authorization(
            holder_authorization, self.trusted_party_keys, action="ACKNOWLEDGE_REMEDIATION",
            case_id=case, credit_id=row_snapshot["credit_id"], action_digest=digest,
            expected_version=expected_version, now=datetime.now(timezone.utc))
        if issuer_proof["principal_id"] != credit_snapshot["issuer_id"]:
            raise DisputeError("issuer remediation signature is not from the credit issuer")
        if holder_proof["principal_id"] != credit_snapshot["holder_id"]:
            raise DisputeError("holder remediation signature is not from the current credit holder")
        if issuer_proof["principal_id"] == holder_proof["principal_id"] or issuer_proof["key_id"] == holder_proof["key_id"]:
            raise DisputeError("remediation requires distinct issuer and holder principals and keys")
        request = {"case_id": case, "remediation_ref": remediation,
                   "issuer_ack_ref": issuer_ack, "holder_ack_ref": holder_ack,
                   "expected_version": expected_version,
                   "issuer_authorization": issuer_proof["envelope"],
                   "holder_authorization": holder_proof["envelope"],
                   "issuer_authorization_digest": issuer_proof["authorization_digest"],
                   "holder_authorization_digest": holder_proof["authorization_digest"]}

        def apply():
            row = self._case(case)
            if row["version"] != expected_version:
                raise DisputeError("stale remediation authorization version")
            if row["status"] != "DECIDED" or row["outcome"] != "DISPUTE_UPHELD":
                raise DisputeError("bilateral remediation is only required after DISPUTE_UPHELD")
            if row["remediation_closed"]:
                raise DisputeError("dispute remediation was already acknowledged")
            self.ledger._db.execute(
                """UPDATE disputes SET remediation_closed=1,remediation_ref=?,
                   issuer_ack_ref=?,holder_ack_ref=? WHERE case_id=?""",
                (remediation, issuer_ack, holder_ack, case),
            )
            return {"case_id": case, "status": "DECIDED", "outcome": "DISPUTE_UPHELD",
                    "frozen": False, "remediation_ref": remediation,
                    "obligation_cancelled": False}
        return self.ledger._command("DISPUTE_REMEDIATION_ACKNOWLEDGED", idempotency_key, request, apply)

    def get_dispute(self, case_id: str) -> dict[str, Any]:
        row = self._case(_text(case_id, "case_id"))
        result = dict(row)
        result["evidence_refs"] = json.loads(result.pop("evidence_refs_json"))
        if result.get("appeal_evidence_refs_json") is not None:
            result["appeal_evidence_refs"] = json.loads(result["appeal_evidence_refs_json"])
        else:
            result["appeal_evidence_refs"] = []
        return result

    def _case(self, case_id: str):
        row = self.ledger._db.execute("SELECT * FROM disputes WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise DisputeError("dispute case not found")
        return row
