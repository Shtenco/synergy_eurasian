"""Transactional, issuer-specific service-credit ledger for SLE.

This is a local reference kernel, not a currency, deposit, loan, or payment rail.
Amounts are quantities of a named deliverable unit (e.g. kg, service-hour).
Financial OS remains the authority for any accounting recognition.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Callable


ZERO = Decimal("0")
GENESIS_HASH = "0" * 64
ACTIVE = "ACTIVE"
OVERDUE = "OVERDUE"
DEFAULTED = "DEFAULTED"
SETTLED = "SETTLED"
CANCELLED = "CANCELLED"


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a finite decimal") from None
    if not result.is_finite() or (result <= ZERO if positive else result < ZERO):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field} must be finite and {qualifier}")
    return result


def _fmt(value: Decimal) -> str:
    return "0" if value == ZERO else format(value.normalize(), "f")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _timestamp(value: str, field: str) -> str:
    raw = _text(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class LaborCreditLedger:
    """SQLite-backed service-obligation ledger with atomic, idempotent commands.

    The event chain detects accidental or partial tampering. It is not a
    cryptographic identity system or externally anchored proof of history.
    """

    def __init__(self, database: str | Path = ":memory:", *, timeout: float = 10.0):
        self.database = str(database)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.database, timeout=timeout, isolation_level=None,
            check_same_thread=False,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 10000")
        if self.database != ":memory:":
            self._db.execute("PRAGMA journal_mode = WAL")
            self._db.execute("PRAGMA synchronous = FULL")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _initialize(self) -> None:
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS issuer_policies (
            issuer_id TEXT NOT NULL,
            service_code TEXT NOT NULL,
            unit TEXT NOT NULL,
            max_outstanding TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
            frozen INTEGER NOT NULL CHECK(frozen IN (0,1)),
            PRIMARY KEY (issuer_id, service_code, unit)
        );
        CREATE TABLE IF NOT EXISTS capacity (
            capacity_id TEXT PRIMARY KEY,
            issuer_id TEXT NOT NULL,
            service_code TEXT NOT NULL,
            unit TEXT NOT NULL,
            total_units TEXT NOT NULL,
            reserved_units TEXT NOT NULL,
            fulfilled_units TEXT NOT NULL,
            evidence_sha256 TEXT NOT NULL UNIQUE,
            verifier_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')),
            FOREIGN KEY (issuer_id, service_code, unit)
                REFERENCES issuer_policies(issuer_id, service_code, unit)
        );
        CREATE TABLE IF NOT EXISTS credits (
            credit_id TEXT PRIMARY KEY,
            issuer_id TEXT NOT NULL,
            holder_id TEXT NOT NULL,
            source_contribution_id TEXT NOT NULL UNIQUE,
            award_authorization_ref TEXT NOT NULL UNIQUE,
            result_digest TEXT NOT NULL,
            service_code TEXT NOT NULL,
            unit TEXT NOT NULL,
            capacity_id TEXT NOT NULL REFERENCES capacity(capacity_id),
            issued_units TEXT NOT NULL,
            remaining_units TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN
                ('ACTIVE','OVERDUE','DEFAULTED','SETTLED','CANCELLED')),
            version INTEGER NOT NULL,
            FOREIGN KEY (issuer_id, service_code, unit)
                REFERENCES issuer_policies(issuer_id, service_code, unit)
        );
        CREATE INDEX IF NOT EXISTS credits_issuer_status
            ON credits(issuer_id, service_code, unit, status);
        CREATE TABLE IF NOT EXISTS disputes (
            case_id TEXT PRIMARY KEY,
            credit_id TEXT NOT NULL REFERENCES credits(credit_id),
            opened_by TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN','DECIDED','APPEALED')),
            version INTEGER NOT NULL,
            resolver_id TEXT,
            outcome TEXT,
            decision_digest TEXT,
            appeal_count INTEGER NOT NULL DEFAULT 0,
            appeal_ref TEXT,
            appeal_reason_code TEXT,
            appeal_evidence_refs_json TEXT,
            remediation_closed INTEGER NOT NULL DEFAULT 0 CHECK(remediation_closed IN (0,1)),
            remediation_ref TEXT,
            issuer_ack_ref TEXT,
            holder_ack_ref TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            idempotency_key TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS events_no_update
        BEFORE UPDATE ON events BEGIN
            SELECT RAISE(ABORT, 'events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS events_no_delete
        BEFORE DELETE ON events BEGIN
            SELECT RAISE(ABORT, 'events are append-only');
        END;
        """)
        # Additive migration for databases created before appeal metadata existed.
        dispute_columns = {
            row["name"] for row in self._db.execute("PRAGMA table_info(disputes)").fetchall()
        }
        for column, declaration in (
            ("appeal_ref", "TEXT"),
            ("appeal_reason_code", "TEXT"),
            ("appeal_evidence_refs_json", "TEXT"),
            ("remediation_closed", "INTEGER NOT NULL DEFAULT 0"),
            ("remediation_ref", "TEXT"),
            ("issuer_ack_ref", "TEXT"),
            ("holder_ack_ref", "TEXT"),
        ):
            if column not in dispute_columns:
                self._db.execute(f"ALTER TABLE disputes ADD COLUMN {column} {declaration}")
        self._db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS disputes_one_active_per_credit_v2 ON disputes(credit_id)
            WHERE status IN ('OPEN','APPEALED')
               OR (status='DECIDED' AND outcome='DISPUTE_UPHELD' AND remediation_closed=0)"""
        )

    def _event_head(self) -> tuple[int, str]:
        row = self._db.execute(
            "SELECT seq, event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return (0, GENESIS_HASH) if row is None else (int(row["seq"]), row["event_hash"])

    def _command(
        self,
        event_type: str,
        idempotency_key: str,
        request: dict[str, Any],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        key = _text(idempotency_key, "idempotency_key")
        request_hash = hashlib.sha256(_canonical(request).encode("utf-8")).hexdigest()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                existing = self._db.execute(
                    "SELECT request_hash, payload_json, event_id, seq, event_hash "
                    "FROM events WHERE idempotency_key = ?", (key,)
                ).fetchone()
                if existing is not None:
                    if existing["request_hash"] != request_hash:
                        raise ValueError("idempotency_key was already used for a different request")
                    stored = json.loads(existing["payload_json"])
                    self._db.execute("COMMIT")
                    return {
                        **stored["result"],
                        "event_id": existing["event_id"],
                        "event_seq": existing["seq"],
                        "event_hash": existing["event_hash"],
                        "idempotent_replay": True,
                    }

                result = operation()
                previous_seq, previous_hash = self._event_head()
                event_id = str(uuid.uuid4())
                created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                payload_json = _canonical({"request": request, "result": result})
                event_body = {
                    "seq": previous_seq + 1,
                    "event_id": event_id,
                    "idempotency_key": key,
                    "event_type": event_type,
                    "request_hash": request_hash,
                    "payload_json": payload_json,
                    "previous_hash": previous_hash,
                    "created_at": created_at,
                }
                event_hash = hashlib.sha256(_canonical(event_body).encode("utf-8")).hexdigest()
                self._db.execute(
                    """INSERT INTO events
                    (event_id,idempotency_key,event_type,request_hash,payload_json,
                     previous_hash,event_hash,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (event_id, key, event_type, request_hash, payload_json,
                     previous_hash, event_hash, created_at),
                )
                seq = previous_seq + 1
                self._db.execute("COMMIT")
                return {
                    **result, "event_id": event_id, "event_seq": seq,
                    "event_hash": event_hash, "idempotent_replay": False,
                }
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def register_issuer(
        self, issuer_id: str, service_code: str, unit: str,
        max_outstanding: Any, idempotency_key: str,
    ) -> dict[str, Any]:
        issuer, service, measure = _text(issuer_id, "issuer_id"), _text(service_code, "service_code"), _text(unit, "unit")
        limit = _decimal(max_outstanding, "max_outstanding", positive=True)
        request = {"issuer_id": issuer, "service_code": service, "unit": measure, "max_outstanding": _fmt(limit)}

        def apply() -> dict[str, Any]:
            self._db.execute(
                "INSERT INTO issuer_policies VALUES (?,?,?,?,1,0)",
                (issuer, service, measure, _fmt(limit)),
            )
            return {"issuer_id": issuer, "service_code": service, "unit": measure, "max_outstanding": _fmt(limit)}
        return self._command("ISSUER_REGISTERED", idempotency_key, request, apply)

    def add_capacity(
        self, issuer_id: str, service_code: str, unit: str, capacity_id: str,
        total_units: Any, evidence_sha256: str, verifier_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        issuer, service, measure = _text(issuer_id, "issuer_id"), _text(service_code, "service_code"), _text(unit, "unit")
        cid, verifier = _text(capacity_id, "capacity_id"), _text(verifier_id, "verifier_id")
        amount = _decimal(total_units, "total_units", positive=True)
        digest = _text(evidence_sha256, "evidence_sha256").lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("evidence_sha256 must be a 64-character SHA-256 hex digest")
        request = {"issuer_id": issuer, "service_code": service, "unit": measure, "capacity_id": cid,
                   "total_units": _fmt(amount), "evidence_sha256": digest, "verifier_id": verifier}

        def apply() -> dict[str, Any]:
            policy = self._policy(issuer, service, measure)
            if policy["enabled"] != 1 or policy["frozen"] == 1:
                raise ValueError("issuer is disabled or frozen")
            self._db.execute(
                "INSERT INTO capacity VALUES (?,?,?,?,?,'0','0',?,?,'OPEN')",
                (cid, issuer, service, measure, _fmt(amount), digest, verifier),
            )
            return {"capacity_id": cid, "total_units": _fmt(amount), "available_units": _fmt(amount)}
        return self._command("CAPACITY_REGISTERED", idempotency_key, request, apply)

    def issue(
        self, issuer_id: str, holder_id: str, source_contribution_id: str,
        award_authorization_ref: str, result_digest: str, service_code: str,
        unit: str, capacity_id: str, units: Any, due_at: str, credit_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        issuer, holder = _text(issuer_id, "issuer_id"), _text(holder_id, "holder_id")
        contribution = _text(source_contribution_id, "source_contribution_id")
        award_ref = _text(award_authorization_ref, "award_authorization_ref")
        digest = _text(result_digest, "result_digest").lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("result_digest must be a 64-character SHA-256 hex digest")
        service, measure = _text(service_code, "service_code"), _text(unit, "unit")
        cid, credit = _text(capacity_id, "capacity_id"), _text(credit_id, "credit_id")
        if issuer == holder:
            raise ValueError("issuer cannot be the initial holder of its own claim")
        amount = _decimal(units, "units", positive=True)
        due = _timestamp(due_at, "due_at")
        if due <= datetime.now(timezone.utc).isoformat(timespec="microseconds"):
            raise ValueError("due_at must be in the future at issuance")
        request = {"issuer_id": issuer, "holder_id": holder, "source_contribution_id": contribution,
                   "award_authorization_ref": award_ref, "result_digest": digest,
                   "service_code": service, "unit": measure, "capacity_id": cid,
                   "units": _fmt(amount), "due_at": due, "credit_id": credit}

        def apply() -> dict[str, Any]:
            policy = self._policy(issuer, service, measure)
            if policy["enabled"] != 1 or policy["frozen"] == 1:
                raise ValueError("issuer is disabled or frozen")
            cap = self._capacity(cid)
            if (cap["issuer_id"], cap["service_code"], cap["unit"], cap["status"]) != (issuer, service, measure, "OPEN"):
                raise ValueError("capacity does not belong to issuer/service/unit or is closed")
            available = Decimal(cap["total_units"]) - Decimal(cap["reserved_units"]) - Decimal(cap["fulfilled_units"])
            if amount > available:
                raise ValueError("issue exceeds unreserved, unfulfilled capacity")
            outstanding = self._outstanding(issuer, service, measure)
            if outstanding + amount > Decimal(policy["max_outstanding"]):
                raise ValueError("issue exceeds issuer outstanding limit")
            self._db.execute(
                "UPDATE capacity SET reserved_units=? WHERE capacity_id=?",
                (_fmt(Decimal(cap["reserved_units"]) + amount), cid),
            )
            self._db.execute(
                "INSERT INTO credits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (credit, issuer, holder, contribution, award_ref, digest, service, measure,
                 cid, _fmt(amount), _fmt(amount), due, ACTIVE),
            )
            return {"credit_id": credit, "issuer_id": issuer, "holder_id": holder,
                    "source_contribution_id": contribution, "award_authorization_ref": award_ref,
                    "units_issued": _fmt(amount), "units_outstanding": _fmt(amount),
                    "status": ACTIVE, "capacity_id": cid}
        return self._command("CREDIT_ISSUED", idempotency_key, request, apply)

    def transfer(
        self, credit_id: str, from_holder: str, to_holder: str,
        expected_version: int, idempotency_key: str,
    ) -> dict[str, Any]:
        credit, sender, recipient = _text(credit_id, "credit_id"), _text(from_holder, "from_holder"), _text(to_holder, "to_holder")
        if sender == recipient:
            raise ValueError("transfer recipient must differ from current holder")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        request = {"credit_id": credit, "from_holder": sender, "to_holder": recipient, "expected_version": expected_version}

        def apply() -> dict[str, Any]:
            row = self._credit(credit)
            if row["holder_id"] != sender:
                raise ValueError("transfer sender is not current holder")
            if row["version"] != expected_version:
                raise ValueError("stale credit version")
            if self._has_active_dispute(credit):
                raise ValueError("credit is frozen by an active dispute")
            if row["status"] != ACTIVE:
                raise ValueError("only active credits may be transferred")
            self._db.execute("UPDATE credits SET holder_id=?,version=version+1 WHERE credit_id=?", (recipient, credit))
            return {"credit_id": credit, "holder_id": recipient, "version": expected_version + 1,
                    "units_outstanding": row["remaining_units"]}
        return self._command("CREDIT_TRANSFERRED", idempotency_key, request, apply)

    def redeem(
        self, credit_id: str, holder_id: str, units: Any,
        expected_version: int, idempotency_key: str,
    ) -> dict[str, Any]:
        credit, holder = _text(credit_id, "credit_id"), _text(holder_id, "holder_id")
        amount = _decimal(units, "units", positive=True)
        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        request = {"credit_id": credit, "holder_id": holder, "units": _fmt(amount), "expected_version": expected_version}

        def apply() -> dict[str, Any]:
            row = self._credit(credit)
            if row["holder_id"] != holder:
                raise ValueError("only current holder may redeem")
            if row["version"] != expected_version:
                raise ValueError("stale credit version")
            if self._has_active_dispute(credit):
                raise ValueError("credit is frozen by an active dispute")
            if row["status"] not in {ACTIVE, OVERDUE}:
                raise ValueError("credit is not redeemable in its current state")
            remaining = Decimal(row["remaining_units"])
            if amount > remaining:
                raise ValueError("redemption exceeds outstanding claim")
            cap = self._capacity(row["capacity_id"])
            reserved = Decimal(cap["reserved_units"])
            if amount > reserved:
                raise RuntimeError("capacity reservation is inconsistent with outstanding claim")
            next_remaining = remaining - amount
            next_status = SETTLED if next_remaining == ZERO else row["status"]
            self._db.execute(
                "UPDATE capacity SET reserved_units=?,fulfilled_units=? WHERE capacity_id=?",
                (_fmt(reserved - amount), _fmt(Decimal(cap["fulfilled_units"]) + amount), row["capacity_id"]),
            )
            self._db.execute(
                "UPDATE credits SET remaining_units=?,status=?,version=version+1 WHERE credit_id=?",
                (_fmt(next_remaining), next_status, credit),
            )
            return {"credit_id": credit, "redeemed_units": _fmt(amount),
                    "units_outstanding": _fmt(next_remaining), "status": next_status,
                    "version": expected_version + 1}
        return self._command("CREDIT_REDEEMED", idempotency_key, request, apply)

    def mark_overdue(self, credit_id: str, as_of: str, idempotency_key: str) -> dict[str, Any]:
        credit, instant = _text(credit_id, "credit_id"), _timestamp(as_of, "as_of")
        request = {"credit_id": credit, "as_of": instant}

        def apply() -> dict[str, Any]:
            row = self._credit(credit)
            if row["status"] != ACTIVE:
                raise ValueError("only active credit can become overdue")
            if instant < row["due_at"]:
                raise ValueError("credit is not yet due")
            self._db.execute("UPDATE credits SET status=?,version=version+1 WHERE credit_id=?", (OVERDUE, credit))
            return {"credit_id": credit, "status": OVERDUE, "units_outstanding": row["remaining_units"],
                    "version": row["version"] + 1}
        return self._command("CREDIT_OVERDUE", idempotency_key, request, apply)

    def mark_default(self, credit_id: str, as_of: str, idempotency_key: str) -> dict[str, Any]:
        credit, instant = _text(credit_id, "credit_id"), _timestamp(as_of, "as_of")
        request = {"credit_id": credit, "as_of": instant}

        def apply() -> dict[str, Any]:
            row = self._credit(credit)
            if row["status"] != OVERDUE:
                raise ValueError("only overdue credit can be declared defaulted")
            if instant < row["due_at"]:
                raise ValueError("credit cannot default before due date")
            self._db.execute("UPDATE credits SET status=?,version=version+1 WHERE credit_id=?", (DEFAULTED, credit))
            self._db.execute(
                "UPDATE issuer_policies SET frozen=1 WHERE issuer_id=?",
                (row["issuer_id"],),
            )
            return {"credit_id": credit, "status": DEFAULTED,
                    "units_outstanding": row["remaining_units"], "issuer_frozen": True,
                    "version": row["version"] + 1}
        return self._command("CREDIT_DEFAULTED_ISSUER_FROZEN", idempotency_key, request, apply)

    def cancel(
        self, credit_id: str, issuer_approval_ref: str, holder_approval_ref: str,
        expected_version: int, idempotency_key: str,
    ) -> dict[str, Any]:
        credit = _text(credit_id, "credit_id")
        issuer_ref = _text(issuer_approval_ref, "issuer_approval_ref")
        holder_ref = _text(holder_approval_ref, "holder_approval_ref")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        request = {"credit_id": credit, "issuer_approval_ref": issuer_ref, "holder_approval_ref": holder_ref,
                   "expected_version": expected_version}

        def apply() -> dict[str, Any]:
            row = self._credit(credit)
            if row["version"] != expected_version:
                raise ValueError("stale credit version")
            if self._has_active_dispute(credit):
                raise ValueError("credit is frozen by an active dispute")
            if row["status"] not in {ACTIVE, OVERDUE}:
                raise ValueError("credit cannot be cancelled in its current state")
            remaining = Decimal(row["remaining_units"])
            cap = self._capacity(row["capacity_id"])
            reserved = Decimal(cap["reserved_units"])
            if remaining > reserved:
                raise RuntimeError("capacity reservation is inconsistent with outstanding claim")
            self._db.execute(
                "UPDATE capacity SET reserved_units=? WHERE capacity_id=?",
                (_fmt(reserved - remaining), row["capacity_id"]),
            )
            self._db.execute(
                "UPDATE credits SET remaining_units='0',status=?,version=version+1 WHERE credit_id=?",
                (CANCELLED, credit),
            )
            return {"credit_id": credit, "cancelled_units": _fmt(remaining),
                    "units_outstanding": "0", "status": CANCELLED,
                    "version": expected_version + 1}
        return self._command("CREDIT_CANCELLED_BY_BOTH_PARTIES", idempotency_key, request, apply)

    def _has_active_dispute(self, credit_id: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM disputes WHERE credit_id=? AND (status IN ('OPEN','APPEALED') OR (status='DECIDED' AND outcome='DISPUTE_UPHELD' AND remediation_closed=0)) LIMIT 1",
            (credit_id,),
        ).fetchone()
        return row is not None

    def _policy(self, issuer: str, service: str, unit: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM issuer_policies WHERE issuer_id=? AND service_code=? AND unit=?",
            (issuer, service, unit),
        ).fetchone()
        if row is None:
            raise ValueError("issuer policy not found")
        return row

    def _capacity(self, capacity_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM capacity WHERE capacity_id=?", (capacity_id,)).fetchone()
        if row is None:
            raise ValueError("capacity reservation not found")
        return row

    def _credit(self, credit_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM credits WHERE credit_id=?", (credit_id,)).fetchone()
        if row is None:
            raise ValueError("credit not found")
        return row

    def _outstanding(self, issuer: str, service: str, unit: str) -> Decimal:
        rows = self._db.execute(
            """SELECT remaining_units FROM credits
            WHERE issuer_id=? AND service_code=? AND unit=?
            AND status IN ('ACTIVE','OVERDUE','DEFAULTED')""",
            (issuer, service, unit),
        ).fetchall()
        return sum((Decimal(row["remaining_units"]) for row in rows), ZERO)

    def get_credit(self, credit_id: str) -> dict[str, Any]:
        row = self._credit(_text(credit_id, "credit_id"))
        return {"schema_version": "1.0", **dict(row)}

    def get_capacity(self, capacity_id: str) -> dict[str, Any]:
        row = self._capacity(_text(capacity_id, "capacity_id"))
        result = dict(row)
        result["available_units"] = _fmt(
            Decimal(row["total_units"]) - Decimal(row["reserved_units"]) - Decimal(row["fulfilled_units"])
        )
        return result

    def verify_event_chain(self) -> dict[str, Any]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            previous_hash = GENESIS_HASH
            expected_seq = 1
            for row in rows:
                body = {
                    "seq": int(row["seq"]), "event_id": row["event_id"],
                    "idempotency_key": row["idempotency_key"], "event_type": row["event_type"],
                    "request_hash": row["request_hash"], "payload_json": row["payload_json"],
                    "previous_hash": row["previous_hash"], "created_at": row["created_at"],
                }
                actual = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
                if int(row["seq"]) != expected_seq or row["previous_hash"] != previous_hash or row["event_hash"] != actual:
                    return {"valid": False, "events_checked": expected_seq - 1, "failed_seq": int(row["seq"])}
                previous_hash = actual
                expected_seq += 1
            head = self._event_head()[1]
            if head != previous_hash:
                return {"valid": False, "events_checked": len(rows), "failed_seq": None}
            return {"valid": True, "events_checked": len(rows), "head_hash": head}

    def verify_projection_consistency(self) -> dict[str, Any]:
        """Replay the append-only event log and compare it with mutable projections."""
        with self._lock:
            chain = self.verify_event_chain()
            if not chain["valid"]:
                return {"valid": False, "issues": ["event hash chain is invalid"], "events_replayed": 0}

            policies: dict[tuple[str, str, str], dict[str, Any]] = {}
            capacities: dict[str, dict[str, Any]] = {}
            credits: dict[str, dict[str, Any]] = {}
            disputes: dict[str, dict[str, Any]] = {}
            issues: list[str] = []
            events_replayed = 0

            rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            for event in rows:
                try:
                    payload = json.loads(event["payload_json"])
                    request = payload["request"]
                    event_type = event["event_type"]

                    if event_type == "ISSUER_REGISTERED":
                        key = (request["issuer_id"], request["service_code"], request["unit"])
                        if key in policies:
                            raise ValueError("duplicate issuer policy event")
                        policies[key] = {
                            "issuer_id": key[0], "service_code": key[1], "unit": key[2],
                            "max_outstanding": request["max_outstanding"],
                            "enabled": 1, "frozen": 0,
                        }

                    elif event_type == "CAPACITY_REGISTERED":
                        cid = request["capacity_id"]
                        if cid in capacities:
                            raise ValueError("duplicate capacity registration event")
                        capacities[cid] = {
                            "capacity_id": cid, "issuer_id": request["issuer_id"],
                            "service_code": request["service_code"], "unit": request["unit"],
                            "total_units": request["total_units"], "reserved_units": "0",
                            "fulfilled_units": "0", "evidence_sha256": request["evidence_sha256"],
                            "verifier_id": request["verifier_id"], "status": "OPEN",
                        }

                    elif event_type == "CREDIT_ISSUED":
                        credit_id = request["credit_id"]
                        contribution_id = request["source_contribution_id"]
                        award_ref = request["award_authorization_ref"]
                        if credit_id in credits:
                            raise ValueError("duplicate credit issue event")
                        if any(x["source_contribution_id"] == contribution_id for x in credits.values()):
                            raise ValueError("source contribution replay in event log")
                        if any(x["award_authorization_ref"] == award_ref for x in credits.values()):
                            raise ValueError("award authorization replay in event log")
                        capacity = capacities[request["capacity_id"]]
                        amount = Decimal(request["units"])
                        available = Decimal(capacity["total_units"]) - Decimal(capacity["reserved_units"]) - Decimal(capacity["fulfilled_units"])
                        if amount > available:
                            raise ValueError("event log oversubscribes capacity")
                        policy_key = (request["issuer_id"], request["service_code"], request["unit"])
                        policy = policies[policy_key]
                        outstanding = sum((
                            Decimal(x["remaining_units"]) for x in credits.values()
                            if (x["issuer_id"], x["service_code"], x["unit"]) == policy_key
                            and x["status"] in {ACTIVE, OVERDUE, DEFAULTED}
                        ), ZERO)
                        if policy["frozen"] or outstanding + amount > Decimal(policy["max_outstanding"]):
                            raise ValueError("event log exceeds issuer policy")
                        capacity["reserved_units"] = _fmt(Decimal(capacity["reserved_units"]) + amount)
                        credits[credit_id] = {
                            "credit_id": credit_id, "issuer_id": request["issuer_id"],
                            "holder_id": request["holder_id"],
                            "source_contribution_id": contribution_id,
                            "award_authorization_ref": award_ref,
                            "result_digest": request["result_digest"],
                            "service_code": request["service_code"], "unit": request["unit"],
                            "capacity_id": request["capacity_id"],
                            "issued_units": _fmt(amount), "remaining_units": _fmt(amount),
                            "due_at": request["due_at"], "status": ACTIVE, "version": 0,
                        }

                    elif event_type == "DISPUTE_OPENED":
                        case_id = request["case_id"]
                        credit_id = request["credit_id"]
                        if case_id in disputes or credit_id not in credits:
                            raise ValueError("duplicate dispute or unknown credit in dispute event")
                        if any(x["credit_id"] == credit_id and x["status"] in {"OPEN", "APPEALED"} for x in disputes.values()):
                            raise ValueError("credit already has an active dispute")
                        if request["opened_by"] not in {credits[credit_id]["issuer_id"], credits[credit_id]["holder_id"]}:
                            raise ValueError("dispute opener is not a credit party")
                        refs = request["evidence_refs"]
                        if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs) or not request["reason_code"]:
                            raise ValueError("dispute evidence or reason is invalid")
                        disputes[case_id] = {
                            "case_id": case_id, "credit_id": credit_id,
                            "opened_by": request["opened_by"], "reason_code": request["reason_code"],
                            "evidence_refs_json": _canonical(request["evidence_refs"]),
                            "status": "OPEN", "version": 0, "resolver_id": None,
                            "outcome": None, "decision_digest": None, "appeal_count": 0,
                            "appeal_ref": None, "appeal_reason_code": None,
                            "appeal_evidence_refs_json": None,
                            "remediation_closed": 0, "remediation_ref": None,
                            "issuer_ack_ref": None, "holder_ack_ref": None,
                        }

                    elif event_type == "DISPUTE_DECIDED":
                        case = disputes[request["case_id"]]
                        if case["status"] not in {"OPEN", "APPEALED"} or case["version"] != request["expected_version"]:
                            raise ValueError("invalid dispute decision transition")
                        if request["resolver_id"] in {credits[case["credit_id"]]["issuer_id"], credits[case["credit_id"]]["holder_id"]}:
                            raise ValueError("dispute resolver is a party")
                        if request["outcome"] not in {"CLAIM_UPHELD", "DISPUTE_UPHELD"} or len(request["decision_digest"]) != 64:
                            raise ValueError("dispute decision outcome or digest is invalid")
                        if case["resolver_id"] == request["resolver_id"]:
                            raise ValueError("same resolver cannot decide an appeal")
                        case["status"] = "DECIDED"
                        case["version"] += 1
                        case["resolver_id"] = request["resolver_id"]
                        case["outcome"] = request["outcome"]
                        case["decision_digest"] = request["decision_digest"]

                    elif event_type == "DISPUTE_APPEALED":
                        case = disputes[request["case_id"]]
                        credit = credits[case["credit_id"]]
                        if case["status"] != "DECIDED" or case["version"] != request["expected_version"] or case["appeal_count"] != 0:
                            raise ValueError("invalid or repeated dispute appeal")
                        if request["appellant_id"] not in {credit["issuer_id"], credit["holder_id"]}:
                            raise ValueError("appeal actor is not a credit party")
                        refs = request["evidence_refs"]
                        if not request["appeal_ref"] or not request["reason_code"] or not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
                            raise ValueError("appeal reason or evidence is invalid")
                        if request["appellant_id"] == case["resolver_id"]:
                            raise ValueError("resolver cannot appeal own decision")
                        case["status"] = "APPEALED"
                        case["version"] += 1
                        case["appeal_count"] += 1
                        case["appeal_ref"] = request["appeal_ref"]
                        case["appeal_reason_code"] = request["reason_code"]
                        case["appeal_evidence_refs_json"] = _canonical(request["evidence_refs"])

                    elif event_type == "DISPUTE_REMEDIATION_ACKNOWLEDGED":
                        case = disputes[request["case_id"]]
                        if case["status"] != "DECIDED" or case["outcome"] != "DISPUTE_UPHELD" or case["remediation_closed"] != 0:
                            raise ValueError("invalid dispute remediation acknowledgement")
                        refs = [request["issuer_ack_ref"], request["holder_ack_ref"]]
                        if not all(refs) or refs[0] == refs[1] or not request["remediation_ref"]:
                            raise ValueError("bilateral remediation references are invalid")
                        case["remediation_closed"] = 1
                        case["remediation_ref"] = request["remediation_ref"]
                        case["issuer_ack_ref"] = request["issuer_ack_ref"]
                        case["holder_ack_ref"] = request["holder_ack_ref"]

                    elif event_type == "CREDIT_TRANSFERRED":
                        credit = credits[request["credit_id"]]
                        if credit["holder_id"] != request["from_holder"] or credit["version"] != request["expected_version"] or credit["status"] != ACTIVE:
                            raise ValueError("invalid transfer transition in event log")
                        credit["holder_id"] = request["to_holder"]
                        credit["version"] += 1

                    elif event_type == "CREDIT_REDEEMED":
                        credit = credits[request["credit_id"]]
                        amount = Decimal(request["units"])
                        if credit["holder_id"] != request["holder_id"] or credit["version"] != request["expected_version"] or credit["status"] not in {ACTIVE, OVERDUE}:
                            raise ValueError("invalid redemption transition in event log")
                        remaining = Decimal(credit["remaining_units"])
                        capacity = capacities[credit["capacity_id"]]
                        reserved = Decimal(capacity["reserved_units"])
                        if amount <= ZERO or amount > remaining or amount > reserved:
                            raise ValueError("invalid redemption quantity in event log")
                        next_remaining = remaining - amount
                        capacity["reserved_units"] = _fmt(reserved - amount)
                        capacity["fulfilled_units"] = _fmt(Decimal(capacity["fulfilled_units"]) + amount)
                        credit["remaining_units"] = _fmt(next_remaining)
                        if next_remaining == ZERO:
                            credit["status"] = SETTLED
                        credit["version"] += 1

                    elif event_type == "CREDIT_OVERDUE":
                        credit = credits[request["credit_id"]]
                        if credit["status"] != ACTIVE or request["as_of"] < credit["due_at"]:
                            raise ValueError("invalid overdue transition in event log")
                        credit["status"] = OVERDUE
                        credit["version"] += 1

                    elif event_type == "CREDIT_DEFAULTED_ISSUER_FROZEN":
                        credit = credits[request["credit_id"]]
                        if credit["status"] != OVERDUE or request["as_of"] < credit["due_at"]:
                            raise ValueError("invalid default transition in event log")
                        credit["status"] = DEFAULTED
                        credit["version"] += 1
                        policy_key = (credit["issuer_id"], credit["service_code"], credit["unit"])
                        policies[policy_key]["frozen"] = 1

                    elif event_type == "CREDIT_CANCELLED_BY_BOTH_PARTIES":
                        credit = credits[request["credit_id"]]
                        if credit["status"] not in {ACTIVE, OVERDUE} or credit["version"] != request["expected_version"]:
                            raise ValueError("invalid cancellation transition in event log")
                        remaining = Decimal(credit["remaining_units"])
                        capacity = capacities[credit["capacity_id"]]
                        reserved = Decimal(capacity["reserved_units"])
                        if remaining > reserved:
                            raise ValueError("cancellation exceeds reserved capacity in event log")
                        capacity["reserved_units"] = _fmt(reserved - remaining)
                        credit["remaining_units"] = "0"
                        credit["status"] = CANCELLED
                        credit["version"] += 1

                    else:
                        raise ValueError(f"unsupported event type: {event_type}")
                    events_replayed += 1

                except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                    issues.append(f"event seq {event['seq']}: replay failed: {exc}")
                    break

            if not issues:
                actual_policies = {
                    (row["issuer_id"], row["service_code"], row["unit"]): dict(row)
                    for row in self._db.execute("SELECT * FROM issuer_policies").fetchall()
                }
                actual_capacities = {
                    row["capacity_id"]: dict(row)
                    for row in self._db.execute("SELECT * FROM capacity").fetchall()
                }
                actual_credits = {
                    row["credit_id"]: dict(row)
                    for row in self._db.execute("SELECT * FROM credits").fetchall()
                }
                if policies != actual_policies:
                    issues.append("issuer policy projection differs from event replay")
                if capacities != actual_capacities:
                    issues.append("capacity projection differs from event replay")
                if credits != actual_credits:
                    issues.append("credit projection differs from event replay")
                actual_disputes = {
                    row["case_id"]: dict(row)
                    for row in self._db.execute("SELECT * FROM disputes").fetchall()
                }
                if disputes != actual_disputes:
                    issues.append("dispute projection differs from event replay")

            if not issues:
                for capacity_id, capacity in capacities.items():
                    expected_reserved = sum((
                        Decimal(credit["remaining_units"]) for credit in credits.values()
                        if credit["capacity_id"] == capacity_id
                        and credit["status"] in {ACTIVE, OVERDUE, DEFAULTED}
                    ), ZERO)
                    if Decimal(capacity["reserved_units"]) != expected_reserved:
                        issues.append(f"capacity {capacity_id}: reserved units do not equal outstanding claims")
                    if Decimal(capacity["reserved_units"]) + Decimal(capacity["fulfilled_units"]) > Decimal(capacity["total_units"]):
                        issues.append(f"capacity {capacity_id}: total capacity is over-allocated")
                for key, policy in policies.items():
                    outstanding = sum((
                        Decimal(credit["remaining_units"]) for credit in credits.values()
                        if (credit["issuer_id"], credit["service_code"], credit["unit"]) == key
                        and credit["status"] in {ACTIVE, OVERDUE, DEFAULTED}
                    ), ZERO)
                    if outstanding > Decimal(policy["max_outstanding"]):
                        issues.append(f"issuer {key[0]}: outstanding obligation exceeds policy limit")

            return {
                "valid": not issues,
                "issues": issues,
                "events_replayed": events_replayed,
            }

    def list_events(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            return [dict(row) for row in rows]
