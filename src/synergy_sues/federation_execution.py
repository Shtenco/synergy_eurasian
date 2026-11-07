"""One-time local execution boundary for authorized federation requests.

Authorization decisions are not bearer tokens. This executor consumes each
request ID exactly once and commits the receipt with handler-local SQL effects
in one SQLite transaction. External effects must be emitted through an outbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from contextlib import contextmanager
from hashlib import sha256
from typing import Any, Callable, Mapping

from .federation_authorization import AuthorizationDecision, FederationAuthorizationPolicy
from .federation_identity import SignedEventEnvelope, TrustedKeyRegistry, _canonical, _event_hash, _utc


@dataclass(frozen=True)
class ExecutionResult:
    executed: bool
    status: str
    decision: AuthorizationDecision
    result: Any = None


class AuthorizedActionExecutor:
    """Single-host, file-backed executor with one-time request consumption.

    The handler must use only the supplied SQLite connection. It must not call
    network services, send payments, write files, or trigger external effects.
    Enqueue external work transactionally in an outbox and dispatch after commit.
    """

    def __init__(self, database_path: str, busy_timeout_ms: int = 5000) -> None:
        if not isinstance(database_path, str) or not database_path.strip() or database_path == ":memory:":
            raise ValueError("authorized action executor requires a file-backed database")
        if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int) or busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be a non-negative integer")
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        with self._session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS execution_receipts (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    request_event_id TEXT NOT NULL UNIQUE,
                    request_event_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    requester_identity_id TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    receipt_version INTEGER NOT NULL DEFAULT 1,
                    request_envelope_json TEXT NOT NULL DEFAULT '{}',
                    approval_envelopes_json TEXT NOT NULL DEFAULT '[]',
                    previous_hash TEXT NOT NULL,
                    receipt_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS execution_outbox (
                    message_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK(status IN ('PENDING','DELIVERED','DEAD')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    last_error TEXT,
                    UNIQUE(idempotency_key, destination, topic)
                );
                CREATE TRIGGER IF NOT EXISTS execution_outbox_identity_no_update
                BEFORE UPDATE OF message_id,idempotency_key,destination,topic,payload_json,created_at
                ON execution_outbox
                BEGIN SELECT RAISE(ABORT, 'execution outbox identity is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS execution_outbox_no_delete
                BEFORE DELETE ON execution_outbox
                BEGIN SELECT RAISE(ABORT, 'execution outbox is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS execution_receipts_no_update
                BEFORE UPDATE ON execution_receipts
                BEGIN SELECT RAISE(ABORT, 'execution receipts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS execution_receipts_no_delete
                BEFORE DELETE ON execution_receipts
                BEGIN SELECT RAISE(ABORT, 'execution receipts are append-only'); END;
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(execution_receipts)").fetchall()}
            if "receipt_version" not in columns:
                db.execute("ALTER TABLE execution_receipts ADD COLUMN receipt_version INTEGER NOT NULL DEFAULT 1")
            if "request_envelope_json" not in columns:
                db.execute("ALTER TABLE execution_receipts ADD COLUMN request_envelope_json TEXT NOT NULL DEFAULT '{}'")
            if "approval_envelopes_json" not in columns:
                db.execute("ALTER TABLE execution_receipts ADD COLUMN approval_envelopes_json TEXT NOT NULL DEFAULT '[]'")
        if not self.verify():
            raise ValueError("execution receipt chain verification failed")

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
    def enqueue_outbox(
        db: sqlite3.Connection,
        idempotency_key: str,
        destination: str,
        topic: str,
        payload: Mapping[str, Any],
    ) -> str:
        """Insert external intent inside the handler transaction; never dispatch here."""
        if any(not isinstance(value, str) or not value.strip()
               for value in (idempotency_key, destination, topic)):
            raise ValueError("outbox idempotency_key, destination and topic are required")
        if not isinstance(payload, Mapping):
            raise ValueError("outbox payload must be a JSON object")
        payload_json = _canonical(dict(payload)).decode("utf-8")
        identity = {"idempotency_key": idempotency_key,
                    "destination": destination, "topic": topic}
        message_id = sha256(_canonical(identity)).hexdigest()
        existing = db.execute(
            "SELECT payload_json FROM execution_outbox WHERE message_id=?", (message_id,)
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != payload_json:
                raise ValueError("outbox idempotency key reused with different payload")
            return message_id
        created_at = datetime.now(timezone.utc).isoformat()
        db.execute("""INSERT INTO execution_outbox
            (message_id,idempotency_key,destination,topic,payload_json,created_at)
            VALUES(?,?,?,?,?,?)""",
            (message_id, idempotency_key, destination, topic, payload_json, created_at))
        return message_id

    @staticmethod
    def _receipt_hash(row: Mapping[str, Any]) -> str:
        fields = ("sequence", "request_id", "request_event_id", "request_event_hash",
                  "action", "resource_type", "resource_id", "requester_identity_id",
                  "executed_at", "result_json", "decision_json", "previous_hash")
        try:
            version = int(row["receipt_version"])
        except (KeyError, IndexError):
            version = 1
        if version >= 2:
            fields = fields + ("receipt_version", "request_envelope_json", "approval_envelopes_json")
        return sha256(_canonical({field: row[field] for field in fields})).hexdigest()

    def execute(
        self,
        request: SignedEventEnvelope,
        approvals: Any,
        policy: FederationAuthorizationPolicy,
        registry: TrustedKeyRegistry,
        handler: Callable[[sqlite3.Connection, SignedEventEnvelope, AuthorizationDecision], Any],
        received_at: datetime | str | None = None,
    ) -> ExecutionResult:
        if not callable(handler):
            raise ValueError("handler must be callable")
        if received_at is None:
            now = datetime.now(timezone.utc)
        elif isinstance(received_at, str):
            now = _utc(received_at, "received_at")
        elif isinstance(received_at, datetime) and received_at.tzinfo is not None and received_at.utcoffset() is not None:
            now = received_at.astimezone(timezone.utc)
        else:
            raise ValueError("received_at must be an ISO timestamp or timezone-aware datetime")
        received_stamp = now.isoformat()

        def snapshot(envelope: SignedEventEnvelope) -> SignedEventEnvelope:
            if not isinstance(envelope, SignedEventEnvelope):
                raise ValueError("request and approvals must be signed event envelopes")
            document = json.loads(_canonical(envelope.as_dict()))
            return SignedEventEnvelope(**document)

        # Separate immutable-by-convention snapshots isolate authorization,
        # handler execution and receipt evidence from caller-owned mutable dicts.
        receipt_request = snapshot(request)
        authorization_request = snapshot(request)
        approval_snapshots = tuple(snapshot(item) for item in approvals)
        request_snapshot_json = _canonical(receipt_request.as_dict())
        approval_snapshot_json = tuple(_canonical(item.as_dict()) for item in approval_snapshots)

        decision = policy.authorize(authorization_request, approval_snapshots, registry, received_stamp)
        if (_canonical(authorization_request.as_dict()) != request_snapshot_json
                or tuple(_canonical(item.as_dict()) for item in approval_snapshots) != approval_snapshot_json):
            raise ValueError("authorization mutated signed request or approval evidence")
        verified_requester = registry.verify(receipt_request, received_stamp)
        if _canonical(receipt_request.as_dict()) != request_snapshot_json:
            raise ValueError("identity verification mutated signed request evidence")
        if (verified_requester.identity_id != decision.requester_identity_id
                or verified_requester.tenant_id != receipt_request.tenant_id):
            raise ValueError("authorization decision requester does not match signed request identity")
        payload = receipt_request.event["payload"]
        request_id = payload["request_id"]
        action = payload["action"]
        resource_type = payload["resource_type"]
        resource_id = payload["resource_id"]
        if decision.request_id != request_id:
            raise ValueError("authorization decision request_id does not match signed request")
        request_event_id = receipt_request.event["event_id"]
        request_event_hash = receipt_request.event["event_hash"]
        if (
            decision.request_event_id != request_event_id
            or decision.request_event_hash != request_event_hash
            or decision.action != action
            or decision.resource_type != resource_type
            or decision.resource_id != resource_id
            or decision.tenant_id != receipt_request.tenant_id
        ):
            raise ValueError("authorization decision is not bound to this signed event and exact action/resource")
        requester = verified_requester.identity_id
        if not decision.allowed:
            return ExecutionResult(False, "DENIED", decision)
        handler_request = snapshot(receipt_request)
        executed_at = received_stamp

        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT request_event_hash FROM execution_receipts WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if existing is not None:
                    if existing["request_event_hash"] != request_event_hash:
                        raise ValueError("request_id reused with a different signed event hash")
                    db.rollback()
                    return ExecutionResult(False, "ALREADY_EXECUTED", decision)
                event_existing = db.execute(
                    "SELECT request_id FROM execution_receipts WHERE request_event_id=?",
                    (request_event_id,),
                ).fetchone()
                if event_existing is not None:
                    raise ValueError("signed request event ID has already been consumed")

                # A persisted policy decision is valid only for the exact snapshot
                # still current in this same SQLite database. BEGIN IMMEDIATE
                # prevents a policy mutation from racing this check and commit.
                if decision.policy_version is not None or decision.policy_hash is not None:
                    if decision.policy_version is None or not decision.policy_hash:
                        raise ValueError("incomplete versioned policy evidence")
                    if getattr(policy, "database_path", None) != self.database_path:
                        raise ValueError("versioned policy execution requires the policy store and executor to share one SQLite database")
                    policy_table = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='authorization_policy_changes'"
                    ).fetchone()
                    if policy_table is None:
                        raise ValueError("versioned policy execution requires the policy store in the same database")
                    current_policy = db.execute(
                        "SELECT version,policy_hash FROM authorization_policy_changes "
                        "WHERE tenant_id=? ORDER BY version DESC LIMIT 1",
                        (receipt_request.tenant_id,),
                    ).fetchone()
                    if current_policy is None:
                        current_version = 0
                        current_hash = sha256(_canonical({
                            "tenant_id": receipt_request.tenant_id,
                            "version": 0,
                            "rules": [],
                        })).hexdigest()
                    else:
                        current_version = int(current_policy["version"])
                        current_hash = str(current_policy["policy_hash"])
                    if (current_version != decision.policy_version
                            or current_hash != decision.policy_hash):
                        raise ValueError("authorization policy snapshot changed before execution")

                result = handler(db, handler_request, decision)
                result_json = _canonical(result).decode("utf-8")
                decision_document = {
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "request_id": decision.request_id,
                    "requester_identity_id": decision.requester_identity_id,
                    "request_event_id": decision.request_event_id,
                    "request_event_hash": decision.request_event_hash,
                    "action": decision.action,
                    "resource_type": decision.resource_type,
                    "resource_id": decision.resource_id,
                    "tenant_id": decision.tenant_id,
                    "matched_rule_ids": list(decision.matched_rule_ids),
                    "approval_identity_ids": list(decision.approval_identity_ids),
                    "approval_event_refs": [list(item) for item in decision.approval_event_refs],
                    "policy_version": decision.policy_version,
                    "policy_hash": decision.policy_hash,
                }
                decision_json = _canonical(decision_document).decode("utf-8")
                prior = db.execute(
                    "SELECT sequence, receipt_hash FROM execution_receipts ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                sequence = 1 if prior is None else int(prior["sequence"]) + 1
                previous_hash = "" if prior is None else str(prior["receipt_hash"])
                approved_refs = set(decision.approval_event_refs)
                approved_envelopes = {
                    (approval.event["event_id"], approval.event["event_hash"]): approval.as_dict()
                    for approval in approval_snapshots
                    if (approval.event["event_id"], approval.event["event_hash"]) in approved_refs
                }
                row = {
                    "sequence": sequence,
                    "request_id": request_id,
                    "request_event_id": request_event_id,
                    "request_event_hash": request_event_hash,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "requester_identity_id": requester,
                    "executed_at": executed_at,
                    "result_json": result_json,
                    "decision_json": decision_json,
                    "receipt_version": 2,
                    "request_envelope_json": request_snapshot_json.decode("utf-8"),
                    "approval_envelopes_json": _canonical([
                        approved_envelopes[key] for key in sorted(approved_envelopes)
                    ]).decode("utf-8"),
                    "previous_hash": previous_hash,
                }
                receipt_hash = self._receipt_hash(row)
                db.execute("""INSERT INTO execution_receipts
                    (sequence,request_id,request_event_id,request_event_hash,action,
                     resource_type,resource_id,requester_identity_id,executed_at,
                     result_json,decision_json,receipt_version,request_envelope_json,
                     approval_envelopes_json,previous_hash,receipt_hash)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sequence, request_id, request_event_id, request_event_hash, action,
                     resource_type, resource_id, requester, executed_at, result_json,
                     decision_json, 2, row["request_envelope_json"], row["approval_envelopes_json"],
                     previous_hash, receipt_hash))
                db.commit()
                return ExecutionResult(True, "EXECUTED", decision, result)
            except Exception:
                db.rollback()
                raise

    def receipts(self) -> tuple[dict[str, Any], ...]:
        with self._session() as db:
            rows = db.execute("SELECT * FROM execution_receipts ORDER BY sequence").fetchall()
        return tuple(dict(row) for row in rows)

    def verify(self) -> bool:
        rows = self.receipts()
        previous = ""
        for expected_sequence, row in enumerate(rows, start=1):
            if row["sequence"] != expected_sequence or row["previous_hash"] != previous:
                return False
            try:
                result = json.loads(row["result_json"])
                decision = json.loads(row["decision_json"])
                if (_canonical(result).decode("utf-8") != row["result_json"]
                        or _canonical(decision).decode("utf-8") != row["decision_json"]):
                    return False
            except (TypeError, ValueError):
                return False
            if int(row["receipt_version"]) >= 2:
                try:
                    request_document = json.loads(row["request_envelope_json"])
                    approvals_document = json.loads(row["approval_envelopes_json"])
                    if (_canonical(request_document).decode("utf-8") != row["request_envelope_json"]
                            or _canonical(approvals_document).decode("utf-8") != row["approval_envelopes_json"]
                            or not isinstance(approvals_document, list)):
                        return False
                    decision_document = json.loads(row["decision_json"])
                    signed_request = SignedEventEnvelope(**request_document)
                    if (
                        decision_document.get("request_event_id") != row["request_event_id"]
                        or decision_document.get("request_event_hash") != row["request_event_hash"]
                        or decision_document.get("action") != row["action"]
                        or decision_document.get("resource_type") != row["resource_type"]
                        or decision_document.get("resource_id") != row["resource_id"]
                        or decision_document.get("requester_identity_id") != row["requester_identity_id"]
                        or decision_document.get("tenant_id") != signed_request.tenant_id
                    ):
                        return False
                    if (_event_hash(signed_request.event) != row["request_event_hash"]
                            or signed_request.event["event_id"] != row["request_event_id"]
                            or signed_request.identity_id != row["requester_identity_id"]
                            or signed_request.event["payload"].get("request_id") != row["request_id"]
                            or signed_request.event["payload"].get("action") != row["action"]
                            or signed_request.event["payload"].get("resource_type") != row["resource_type"]
                            or signed_request.event["payload"].get("resource_id") != row["resource_id"]):
                        return False
                    approval_refs = sorted(
                        (item["event"]["event_id"], item["event"]["event_hash"])
                        for item in approvals_document
                    )
                    if approval_refs != sorted(tuple(x) for x in decision.get("approval_event_refs", [])):
                        return False
                    for item in approvals_document:
                        signed_approval = SignedEventEnvelope(**item)
                        if _event_hash(signed_approval.event) != signed_approval.event["event_hash"]:
                            return False
                except (KeyError, TypeError, ValueError):
                    return False
            digest = self._receipt_hash(row)
            if digest != row["receipt_hash"]:
                return False
            previous = digest
        return True
