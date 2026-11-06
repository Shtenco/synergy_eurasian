"""Signed, versioned, persistent federation authorization policies (V1).

Administrative trust is configured out-of-band. A policy mutation is accepted
only after an allowlisted administrator signs the exact change and a quorum of
other allowlisted administrators signs approvals bound to that exact event.
The SQLite implementation is a single-host research reference, not distributed
consensus or a production governance service.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Mapping

from .federation_authorization import (
    AuthorizationDecision,
    AuthorizationRule,
    FederationAuthorizationPolicy,
)
from .federation_identity import (
    SignedEventEnvelope,
    TrustedKeyRegistry,
    _canonical,
    _event_hash,
    _utc,
)


_RULE_FIELDS = (
    "rule_id", "tenant_id", "effect", "action", "resource_type",
    "subject_ids", "approver_ids", "min_approvals", "resource_id",
    "valid_from", "valid_until",
)


@dataclass(frozen=True)
class PolicySnapshot:
    tenant_id: str
    version: int
    policy_hash: str
    rules: tuple[AuthorizationRule, ...]


@dataclass(frozen=True)
class PolicyChangeResult:
    applied: bool
    status: str
    tenant_id: str
    change_id: str
    version: int
    policy_hash: str


class SQLiteAuthorizationPolicyStore:
    """File-backed CAS policy store with two-person signed administration.

    The admin allowlist is an explicit constructor input, deliberately not
    bootstrapped from an incoming event or from the policy being changed.
    Every change requires one allowlisted proposer and at least two distinct
    allowlisted approvers other than that proposer.
    """

    def __init__(
        self,
        database_path: str,
        administrators: Mapping[str, Iterable[str]],
        min_admin_approvals: int = 2,
        busy_timeout_ms: int = 5000,
    ) -> None:
        if not isinstance(database_path, str) or not database_path.strip() or database_path == ":memory:":
            raise ValueError("authorization policy store requires a file-backed database")
        if isinstance(min_admin_approvals, bool) or not isinstance(min_admin_approvals, int) or min_admin_approvals < 2:
            raise ValueError("min_admin_approvals must be an integer >= 2 for two-person control")
        if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int) or busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be a non-negative integer")
        if not isinstance(administrators, Mapping) or not administrators:
            raise ValueError("an out-of-band tenant administrator allowlist is required")
        normalized: dict[str, tuple[str, ...]] = {}
        for tenant_id, identities in administrators.items():
            if not isinstance(tenant_id, str) or not tenant_id.strip():
                raise ValueError("administrator tenant IDs must be non-empty strings")
            members = tuple(identities)
            if (len(members) != len(set(members))
                    or any(not isinstance(item, str) or not item.strip() for item in members)):
                raise ValueError("administrator identities must be unique non-empty strings")
            if len(members) < min_admin_approvals + 1:
                raise ValueError("each tenant needs at least one proposer plus the approval quorum")
            normalized[tenant_id] = tuple(sorted(members))
        self.database_path = database_path
        self.administrators = normalized
        self.min_admin_approvals = min_admin_approvals
        self.busy_timeout_ms = busy_timeout_ms
        with self._session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS authorization_policy_changes (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version >= 1),
                    change_id TEXT NOT NULL,
                    operation TEXT NOT NULL CHECK(operation IN ('UPSERT_RULE','REVOKE_RULE')),
                    rule_id TEXT NOT NULL,
                    request_event_id TEXT NOT NULL,
                    request_event_hash TEXT NOT NULL,
                    request_envelope_json TEXT NOT NULL,
                    approvals_json TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    policy_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    UNIQUE(tenant_id, version),
                    UNIQUE(tenant_id, change_id),
                    UNIQUE(request_event_id)
                );
                CREATE INDEX IF NOT EXISTS authorization_policy_changes_tenant_sequence
                    ON authorization_policy_changes(tenant_id, sequence);
                CREATE TRIGGER IF NOT EXISTS authorization_policy_changes_no_update
                BEFORE UPDATE ON authorization_policy_changes
                BEGIN SELECT RAISE(ABORT, 'authorization policy history is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS authorization_policy_changes_no_delete
                BEFORE DELETE ON authorization_policy_changes
                BEGIN SELECT RAISE(ABORT, 'authorization policy history is append-only'); END;
            """)
        if not self.verify():
            raise ValueError("authorization policy history or snapshot integrity verification failed")

    @contextmanager
    def _session(self):
        db = sqlite3.connect(self.database_path, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()

    @staticmethod
    def _rule_document(rule: AuthorizationRule) -> dict[str, Any]:
        return {
            "rule_id": rule.rule_id,
            "tenant_id": rule.tenant_id,
            "effect": rule.effect,
            "action": rule.action,
            "resource_type": rule.resource_type,
            "subject_ids": list(rule.subject_ids),
            "approver_ids": list(rule.approver_ids),
            "min_approvals": rule.min_approvals,
            "resource_id": rule.resource_id,
            "valid_from": rule.valid_from,
            "valid_until": rule.valid_until,
        }

    @classmethod
    def _rule_from_document(cls, document: Mapping[str, Any]) -> AuthorizationRule:
        if not isinstance(document, Mapping) or set(document) != set(_RULE_FIELDS):
            raise ValueError("policy rule document has missing or unsupported fields")
        if not isinstance(document["subject_ids"], list) or not isinstance(document["approver_ids"], list):
            raise ValueError("policy rule subject_ids and approver_ids must be arrays")
        return AuthorizationRule(
            rule_id=document["rule_id"],
            tenant_id=document["tenant_id"],
            effect=document["effect"],
            action=document["action"],
            resource_type=document["resource_type"],
            subject_ids=tuple(document["subject_ids"]),
            approver_ids=tuple(document["approver_ids"]),
            min_approvals=document["min_approvals"],
            resource_id=document["resource_id"],
            valid_from=document["valid_from"],
            valid_until=document["valid_until"],
        )

    @classmethod
    def _policy_hash(cls, tenant_id: str, version: int, rules: Mapping[str, AuthorizationRule]) -> str:
        document = {
            "tenant_id": tenant_id,
            "version": version,
            "rules": [cls._rule_document(rules[key]) for key in sorted(rules)],
        }
        return sha256(_canonical(document)).hexdigest()

    @staticmethod
    def _event_hash(row: Mapping[str, Any]) -> str:
        fields = (
            "tenant_id", "version", "change_id", "operation", "rule_id",
            "request_event_id", "request_event_hash", "request_envelope_json",
            "approvals_json", "policy_json", "policy_hash", "previous_hash",
        )
        return sha256(_canonical({field: row[field] for field in fields})).hexdigest()

    @staticmethod
    def _envelope_json(envelope: SignedEventEnvelope) -> str:
        return _canonical(envelope.as_dict()).decode("utf-8")

    @staticmethod
    def _decode_envelope(value: Mapping[str, Any]) -> SignedEventEnvelope:
        try:
            return SignedEventEnvelope(**dict(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("stored signed envelope has an invalid shape") from exc

    def _validate_change(
        self,
        request: SignedEventEnvelope,
        approvals: Iterable[SignedEventEnvelope],
        registry: TrustedKeyRegistry,
        received_at: datetime | str | None,
    ) -> tuple[str, str, int, str, str, dict[str, Any] | None, list[SignedEventEnvelope]]:
        proposer = registry.verify(request, received_at)
        if request.event.get("event_type") != "AUTHORIZATION_POLICY_CHANGE":
            raise ValueError("expected signed AUTHORIZATION_POLICY_CHANGE event")
        payload = request.event.get("payload")
        required = {"change_id", "tenant_id", "expected_version", "operation"}
        if not isinstance(payload, dict) or not required.issubset(payload):
            raise ValueError("policy change payload is missing required fields")
        tenant_id, change_id, operation = payload["tenant_id"], payload["change_id"], payload["operation"]
        expected_version = payload["expected_version"]
        if any(not isinstance(x, str) or not x.strip() for x in (tenant_id, change_id, operation)):
            raise ValueError("policy change tenant_id, change_id and operation are required")
        if proposer.tenant_id != tenant_id:
            raise ValueError("policy proposer tenant does not match the target tenant")
        admins = self.administrators.get(tenant_id, ())
        if proposer.identity_id not in admins:
            raise ValueError("policy proposer is not in the out-of-band administrator allowlist")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise ValueError("expected_version must be an integer >= 0")
        if operation == "UPSERT_RULE":
            if set(payload) != required | {"rule"}:
                raise ValueError("UPSERT_RULE requires exactly one rule document")
            rule_doc = payload["rule"]
            rule = self._rule_from_document(rule_doc)
            if rule.tenant_id != tenant_id:
                raise ValueError("policy rule tenant does not match the change tenant")
            # Reuse the evaluator's complete validation contract.
            validator = FederationAuthorizationPolicy()
            validator.register_rule(rule)
            rule_doc = self._rule_document(rule)
            rule_id = rule.rule_id
        elif operation == "REVOKE_RULE":
            if set(payload) != required | {"rule_id"}:
                raise ValueError("REVOKE_RULE requires exactly one rule_id")
            rule_id = payload["rule_id"]
            if not isinstance(rule_id, str) or not rule_id.strip():
                raise ValueError("REVOKE_RULE rule_id is required")
            rule_doc = None
        else:
            raise ValueError("unsupported policy operation")

        request_time = _utc(request.signed_at, "signed_at")
        now = _utc(received_at, "received_at") if isinstance(received_at, str) else (
            received_at or datetime.now(timezone.utc))
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        now = now.astimezone(timezone.utc)
        verified: dict[str, SignedEventEnvelope] = {}
        seen_event_ids: set[str] = set()
        veto = False
        for approval in approvals:
            approver = registry.verify(approval, received_at)
            if approval.event.get("event_type") != "AUTHORIZATION_POLICY_APPROVAL":
                raise ValueError("expected signed AUTHORIZATION_POLICY_APPROVAL event")
            approval_payload = approval.event.get("payload")
            if not isinstance(approval_payload, dict):
                raise ValueError("policy approval payload must be an object")
            approval_fields = {
                "change_id", "tenant_id", "expected_version",
                "policy_change_event_id", "policy_change_event_hash", "decision",
            }
            if set(approval_payload) != approval_fields:
                raise ValueError("policy approval payload has missing or unsupported fields")
            if approval.event["event_id"] in seen_event_ids:
                continue
            seen_event_ids.add(approval.event["event_id"])
            exact_binding = (
                approval_payload["change_id"] == change_id
                and approval_payload["tenant_id"] == tenant_id
                and approval_payload["expected_version"] == expected_version
                and approval_payload["policy_change_event_id"] == request.event["event_id"]
                and approval_payload["policy_change_event_hash"] == request.event["event_hash"]
                and approver.tenant_id == tenant_id
                and _utc(approval.signed_at, "signed_at") >= request_time
            )
            if not exact_binding or approver.identity_id not in admins or approver.identity_id == proposer.identity_id:
                continue
            if approval_payload["decision"] not in {"APPROVE", "REJECT"}:
                raise ValueError("policy approval decision must be APPROVE or REJECT")
            if approval_payload["decision"] == "REJECT":
                veto = True
            else:
                verified.setdefault(approver.identity_id, approval)
        if veto:
            raise ValueError("policy change vetoed by an authorized administrator")
        if len(verified) < self.min_admin_approvals:
            raise ValueError("policy change lacks the required distinct administrator quorum")
        approval_events = sorted(verified.values(), key=lambda item: item.event["event_id"])
        return tenant_id, change_id, expected_version, operation, rule_id, rule_doc, approval_events

    def apply_change(
        self,
        request: SignedEventEnvelope,
        approvals: Iterable[SignedEventEnvelope],
        registry: TrustedKeyRegistry,
        received_at: datetime | str | None = None,
    ) -> PolicyChangeResult:
        """Validate signatures/quorum and atomically apply one expected-version change."""
        if not self.verify():
            raise ValueError("authorization policy history integrity verification failed")
        approvals = tuple(approvals)
        tenant_id, change_id, expected_version, operation, rule_id, rule_doc, approval_events = (
            self._validate_change(request, approvals, registry, received_at)
        )
        request_json = self._envelope_json(request)
        approvals_json = _canonical([json.loads(self._envelope_json(item)) for item in approval_events]).decode("utf-8")
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT * FROM authorization_policy_changes WHERE tenant_id=? AND change_id=?",
                    (tenant_id, change_id),
                ).fetchone()
                if existing is not None:
                    if existing["request_event_hash"] != request.event["event_hash"]:
                        raise ValueError("change_id reused with a different signed change event")
                    db.rollback()
                    return PolicyChangeResult(False, "ALREADY_APPLIED", tenant_id, change_id,
                        int(existing["version"]), str(existing["policy_hash"]))

                latest = db.execute(
                    "SELECT version,policy_json,policy_hash,event_hash FROM authorization_policy_changes "
                    "WHERE tenant_id=? ORDER BY version DESC LIMIT 1", (tenant_id,)
                ).fetchone()
                current_version = 0 if latest is None else int(latest["version"])
                if current_version != expected_version:
                    raise ValueError(
                        f"stale policy version: expected {expected_version}, current {current_version}"
                    )
                rules: dict[str, AuthorizationRule] = {}
                if latest is not None:
                    stored_rules = json.loads(latest["policy_json"])
                    for document in stored_rules:
                        rule = self._rule_from_document(document)
                        rules[rule.rule_id] = rule
                if operation == "UPSERT_RULE":
                    rules[rule_id] = self._rule_from_document(rule_doc)
                else:
                    if rule_id not in rules:
                        raise ValueError("cannot revoke an unknown policy rule")
                    del rules[rule_id]

                next_version = current_version + 1
                policy_document = [self._rule_document(rules[key]) for key in sorted(rules)]
                policy_json = _canonical(policy_document).decode("utf-8")
                policy_hash = self._policy_hash(tenant_id, next_version, rules)
                previous_hash = "" if latest is None else str(latest["event_hash"])
                row = {
                    "tenant_id": tenant_id,
                    "version": next_version,
                    "change_id": change_id,
                    "operation": operation,
                    "rule_id": rule_id,
                    "request_event_id": request.event["event_id"],
                    "request_event_hash": request.event["event_hash"],
                    "request_envelope_json": request_json,
                    "approvals_json": approvals_json,
                    "policy_json": policy_json,
                    "policy_hash": policy_hash,
                    "previous_hash": previous_hash,
                }
                event_hash = self._event_hash(row)
                db.execute("""INSERT INTO authorization_policy_changes
                    (tenant_id,version,change_id,operation,rule_id,request_event_id,
                     request_event_hash,request_envelope_json,approvals_json,policy_json,
                     policy_hash,previous_hash,event_hash)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (tenant_id, next_version, change_id, operation, rule_id,
                     request.event["event_id"], request.event["event_hash"], request_json,
                     approvals_json, policy_json, policy_hash, previous_hash, event_hash))
                db.commit()
                return PolicyChangeResult(True, "APPLIED", tenant_id, change_id,
                    next_version, policy_hash)
            except Exception:
                db.rollback()
                raise

    def snapshot(self, tenant_id: str) -> PolicySnapshot:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.verify():
            raise ValueError("authorization policy history integrity verification failed")
        with self._session() as db:
            row = db.execute(
                "SELECT version,policy_json,policy_hash FROM authorization_policy_changes "
                "WHERE tenant_id=? ORDER BY version DESC LIMIT 1", (tenant_id,)
            ).fetchone()
        if row is None:
            return PolicySnapshot(tenant_id, 0, self._policy_hash(tenant_id, 0, {}), ())
        rules = tuple(self._rule_from_document(item) for item in json.loads(row["policy_json"]))
        return PolicySnapshot(tenant_id, int(row["version"]), str(row["policy_hash"]), rules)

    @staticmethod
    def _policy_from_snapshot(snapshot: PolicySnapshot) -> FederationAuthorizationPolicy:
        policy = FederationAuthorizationPolicy()
        for rule in snapshot.rules:
            policy.register_rule(rule)
        return policy

    def load_policy(self, tenant_id: str) -> FederationAuthorizationPolicy:
        return self._policy_from_snapshot(self.snapshot(tenant_id))

    def authorize(
        self,
        request: SignedEventEnvelope,
        approvals: Iterable[SignedEventEnvelope],
        registry: TrustedKeyRegistry,
        received_at: datetime | str | None = None,
    ) -> AuthorizationDecision:
        requester = registry.verify(request, received_at)
        snapshot = self.snapshot(requester.tenant_id)
        decision = self._policy_from_snapshot(snapshot).authorize(
            request, approvals, registry, received_at
        )
        return replace(decision, policy_version=snapshot.version, policy_hash=snapshot.policy_hash)

    def verify(self) -> bool:
        with self._session() as db:
            rows = db.execute(
                "SELECT * FROM authorization_policy_changes ORDER BY tenant_id,version"
            ).fetchall()
        previous_by_tenant: dict[str, str] = {}
        rules_by_tenant: dict[str, dict[str, AuthorizationRule]] = {}
        versions: dict[str, int] = {}
        for row in rows:
            tenant = row["tenant_id"]
            expected_version = versions.get(tenant, 0) + 1
            previous = previous_by_tenant.get(tenant, "")
            if row["version"] != expected_version or row["previous_hash"] != previous:
                return False
            try:
                request = json.loads(row["request_envelope_json"])
                approvals = json.loads(row["approvals_json"])
                policy_doc = json.loads(row["policy_json"])
                if (_canonical(request).decode("utf-8") != row["request_envelope_json"]
                        or _canonical(approvals).decode("utf-8") != row["approvals_json"]
                        or _canonical(policy_doc).decode("utf-8") != row["policy_json"]
                        or not isinstance(request, dict) or not isinstance(approvals, list)
                        or not isinstance(policy_doc, list)):
                    return False
                request_envelope = self._decode_envelope(request)
                change_event = request_envelope.event
                _event_hash(change_event)
                change_payload = change_event.get("payload")
                if (change_event.get("event_type") != "AUTHORIZATION_POLICY_CHANGE"
                        or change_event.get("event_id") != row["request_event_id"]
                        or change_event.get("event_hash") != row["request_event_hash"]
                        or request_envelope.tenant_id != tenant
                        or not isinstance(change_payload, dict)
                        or change_payload.get("tenant_id") != tenant
                        or change_payload.get("change_id") != row["change_id"]
                        or change_payload.get("expected_version") != expected_version - 1
                        or change_payload.get("operation") != row["operation"]
                        or request_envelope.identity_id not in self.administrators.get(tenant, ())):
                    return False
                request_signed_at = _utc(request_envelope.signed_at, "signed_at")
                if not approvals:
                    return False
                approval_identities: set[str] = set()
                approval_event_ids: set[str] = set()
                for approval_document in approvals:
                    approval_envelope = self._decode_envelope(approval_document)
                    approval_event = approval_envelope.event
                    _event_hash(approval_event)
                    approval_payload = approval_event.get("payload")
                    if (approval_event.get("event_id") in approval_event_ids
                            or approval_envelope.identity_id in approval_identities
                            or approval_event.get("event_type") != "AUTHORIZATION_POLICY_APPROVAL"
                            or approval_envelope.tenant_id != tenant
                            or approval_envelope.identity_id not in self.administrators.get(tenant, ())
                            or approval_envelope.identity_id == request_envelope.identity_id
                            or _utc(approval_envelope.signed_at, "signed_at") < request_signed_at
                            or not isinstance(approval_payload, dict)
                            or approval_payload.get("change_id") != row["change_id"]
                            or approval_payload.get("tenant_id") != tenant
                            or approval_payload.get("expected_version") != expected_version - 1
                            or approval_payload.get("policy_change_event_id") != row["request_event_id"]
                            or approval_payload.get("policy_change_event_hash") != row["request_event_hash"]
                            or approval_payload.get("decision") != "APPROVE"):
                        return False
                    approval_event_ids.add(approval_event["event_id"])
                    approval_identities.add(approval_envelope.identity_id)
                if len(approval_identities) < self.min_admin_approvals:
                    return False
                rules = rules_by_tenant.setdefault(tenant, {})
                operation = row["operation"]
                if operation == "UPSERT_RULE":
                    rule = self._rule_from_document(change_payload["rule"])
                    if rule.rule_id != row["rule_id"] or rule.tenant_id != tenant:
                        return False
                    rules[rule.rule_id] = rule
                elif operation == "REVOKE_RULE":
                    if (change_payload.get("rule_id") != row["rule_id"]
                            or row["rule_id"] not in rules):
                        return False
                    del rules[row["rule_id"]]
                else:
                    return False
                expected_policy_doc = [self._rule_document(rules[key]) for key in sorted(rules)]
                if expected_policy_doc != policy_doc:
                    return False
                expected_policy_hash = self._policy_hash(tenant, expected_version, rules)
                if expected_policy_hash != row["policy_hash"]:
                    return False
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return False
            digest = self._event_hash(row)
            if digest != row["event_hash"]:
                return False
            previous_by_tenant[tenant] = digest
            versions[tenant] = expected_version
        return True
