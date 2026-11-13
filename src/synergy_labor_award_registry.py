"""Shared SQLite reservation registry for globally unique SLE labor awards.

The registry is a separate shared coordination database. It reserves contribution and
award identifiers before local credit issuance, then consumes the reservation only
after independently checking the local ledger's event chain and issuance projection.
Reservations are never auto-expired or silently released: crash recovery favors safety
(no duplicate award) over liveness (a reservation may need reconciliation).
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Mapping

from synergy_labor_award_authorization import (
    AwardAuthorizationError,
    verify_award_authorization,
)


GENESIS_HASH = "0" * 64


class AwardRegistryError(ValueError):
    """Global award reservation, consumption, or audit failure."""


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise AwardRegistryError("value is not canonical-JSON compatible") from None


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AwardRegistryError(f"{field} must be a non-empty string")
    return value.strip()


class SLEAwardRegistry:
    """One shared uniqueness authority for all participating award producers."""

    def __init__(self, database: str | Path = ":memory:", *, timeout: float = 10.0):
        self.database = str(database)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.database, timeout=timeout, isolation_level=None,
            check_same_thread=False,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=10000")
        if self.database != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS awards (
            award_id TEXT PRIMARY KEY,
            source_contribution_id TEXT NOT NULL UNIQUE,
            result_digest TEXT NOT NULL,
            authorization_digest TEXT NOT NULL UNIQUE,
            authorization_json TEXT NOT NULL,
            beneficiary_id TEXT NOT NULL,
            issuer_id TEXT NOT NULL,
            service_code TEXT NOT NULL,
            unit TEXT NOT NULL,
            quantity TEXT NOT NULL,
            capacity_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('RESERVED','CONSUMED')),
            credit_id TEXT UNIQUE,
            ledger_event_id TEXT UNIQUE,
            ledger_event_hash TEXT,
            reserved_at TEXT NOT NULL,
            consumed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS award_events_no_update
        BEFORE UPDATE ON events BEGIN
            SELECT RAISE(ABORT, 'award registry events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS award_events_no_delete
        BEFORE DELETE ON events BEGIN
            SELECT RAISE(ABORT, 'award registry events are append-only');
        END;
        """)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _head(self) -> tuple[int, str]:
        row = self._db.execute(
            "SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return (0, GENESIS_HASH) if row is None else (int(row["seq"]), row["event_hash"])

    def _append_event(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        seq, previous = self._head()
        event_id = hashlib.sha256(
            f"{seq + 1}:{event_type}:{_canonical(payload)}:{previous}".encode("utf-8")
        ).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        payload_json = _canonical(payload)
        body = {
            "seq": seq + 1, "event_id": event_id, "event_type": event_type,
            "payload_json": payload_json, "previous_hash": previous,
            "created_at": created_at,
        }
        event_hash = _sha(_canonical(body))
        self._db.execute(
            """INSERT INTO events(event_id,event_type,payload_json,previous_hash,event_hash,created_at)
               VALUES(?,?,?,?,?,?)""",
            (event_id, event_type, payload_json, previous, event_hash, created_at),
        )
        return {"event_id": event_id, "event_seq": seq + 1, "event_hash": event_hash}

    def reserve(
        self, envelope: Mapping[str, Any], key_registry: Mapping[str, Mapping[str, Any]],
        *, now: datetime,
    ) -> dict[str, Any]:
        try:
            verified = verify_award_authorization(envelope, key_registry, now=now)
        except AwardAuthorizationError as exc:
            raise AwardRegistryError(str(exc)) from None
        authorization_json = _canonical(dict(envelope))
        request = {
            "award_id": verified["award_id"],
            "source_contribution_id": verified["source_contribution_id"],
            "result_digest": verified["result_digest"],
            "authorization_digest": verified["authorization_digest"],
            "beneficiary_id": verified["beneficiary_id"],
            "issuer_id": verified["issuer_id"],
            "service_code": verified["service_code"],
            "unit": verified["unit"],
            "quantity": verified["quantity"],
            "capacity_id": verified["capacity_id"],
        }
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                by_award = self._db.execute(
                    "SELECT * FROM awards WHERE award_id=?", (verified["award_id"],)
                ).fetchone()
                by_contribution = self._db.execute(
                    "SELECT * FROM awards WHERE source_contribution_id=?",
                    (verified["source_contribution_id"],),
                ).fetchone()
                existing = by_award or by_contribution
                if existing is not None:
                    if (existing["award_id"] == verified["award_id"]
                        and existing["source_contribution_id"] == verified["source_contribution_id"]
                        and existing["authorization_digest"] == verified["authorization_digest"]
                        and existing["authorization_json"] == authorization_json):
                        self._db.execute("COMMIT")
                        return {**dict(existing), "idempotent_replay": True}
                    raise AwardRegistryError(
                        "source contribution or award ID is already reserved by a different authorization"
                    )
                reserved_at = now.astimezone(timezone.utc).isoformat(timespec="microseconds")
                self._db.execute(
                    """INSERT INTO awards(
                        award_id,source_contribution_id,result_digest,authorization_digest,
                        authorization_json,beneficiary_id,issuer_id,service_code,unit,quantity,
                        capacity_id,status,reserved_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'RESERVED',?)""",
                    (verified["award_id"], verified["source_contribution_id"],
                     verified["result_digest"], verified["authorization_digest"],
                     authorization_json, verified["beneficiary_id"], verified["issuer_id"],
                     verified["service_code"], verified["unit"], verified["quantity"],
                     verified["capacity_id"], reserved_at),
                )
                event = self._append_event("AWARD_RESERVED", request)
                self._db.execute("COMMIT")
                return {
                    **request, "status": "RESERVED", "reservation_id": verified["award_id"],
                    "reserved_at": reserved_at, **event, "idempotent_replay": False,
                }
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def get_award(self, award_id: str) -> dict[str, Any]:
        key = _text(award_id, "award_id")
        with self._lock:
            row = self._db.execute("SELECT * FROM awards WHERE award_id=?", (key,)).fetchone()
            if row is None:
                raise AwardRegistryError("award reservation not found")
            return dict(row)

    def consume_from_ledger(
        self, award_id: str, ledger: Any, credit_id: str,
    ) -> dict[str, Any]:
        """Consume only after the local SQLite ledger proves the matching issue event."""
        award = self.get_award(award_id)
        credit = ledger.get_credit(credit_id)
        expected = {
            "issuer_id": award["issuer_id"],
            "source_contribution_id": award["source_contribution_id"],
            "award_authorization_ref": award["award_id"],
            "result_digest": award["result_digest"],
            "service_code": award["service_code"],
            "unit": award["unit"],
            "capacity_id": award["capacity_id"],
            "issued_units": award["quantity"],
        }
        for field, value in expected.items():
            if str(credit[field]) != str(value):
                raise AwardRegistryError(f"local credit {field} does not match reserved award")
        chain = ledger.verify_event_chain()
        if not chain.get("valid"):
            raise AwardRegistryError("local ledger event chain is invalid")
        projection = ledger.verify_projection_consistency()
        if not projection.get("valid"):
            raise AwardRegistryError("local ledger projection is inconsistent")
        issue_events = []
        for event in ledger._db.execute(
            "SELECT event_id,event_hash,event_type,payload_json FROM events WHERE event_type='CREDIT_ISSUED'"
        ).fetchall():
            payload = json.loads(event["payload_json"])
            if payload.get("request", {}).get("credit_id") == credit_id:
                issue_events.append((event, payload.get("request", {})))
        if len(issue_events) != 1:
            raise AwardRegistryError("exactly one local CREDIT_ISSUED event is required")
        event, request = issue_events[0]
        for field, value in (
            ("issuer_id", award["issuer_id"]),
            ("holder_id", award["beneficiary_id"]),
            ("source_contribution_id", award["source_contribution_id"]),
            ("award_authorization_ref", award["award_id"]),
            ("result_digest", award["result_digest"]),
            ("service_code", award["service_code"]),
            ("unit", award["unit"]),
            ("capacity_id", award["capacity_id"]),
            ("units", award["quantity"]),
        ):
            if str(request.get(field)) != str(value):
                raise AwardRegistryError(f"local issue event {field} does not match reserved award")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                current = self._db.execute(
                    "SELECT * FROM awards WHERE award_id=?", (award_id,)
                ).fetchone()
                if current["status"] == "CONSUMED":
                    if (current["credit_id"] == credit_id
                        and current["ledger_event_id"] == event["event_id"]
                        and current["ledger_event_hash"] == event["event_hash"]):
                        self._db.execute("COMMIT")
                        return {**dict(current), "idempotent_replay": True}
                    raise AwardRegistryError("award reservation was already consumed by another ledger event")
                consumed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                self._db.execute(
                    """UPDATE awards SET status='CONSUMED',credit_id=?,ledger_event_id=?,
                       ledger_event_hash=?,consumed_at=? WHERE award_id=? AND status='RESERVED'""",
                    (credit_id, event["event_id"], event["event_hash"], consumed_at, award_id),
                )
                if self._db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise AwardRegistryError("award reservation changed concurrently")
                registry_event = self._append_event(
                    "AWARD_CONSUMED",
                    {"award_id": award_id, "credit_id": credit_id,
                     "ledger_event_id": event["event_id"],
                     "ledger_event_hash": event["event_hash"]},
                )
                self._db.execute("COMMIT")
                return {
                    **dict(self._db.execute("SELECT * FROM awards WHERE award_id=?", (award_id,)).fetchone()),
                    **registry_event, "idempotent_replay": False,
                }
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def verify_event_chain(self) -> dict[str, Any]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            previous = GENESIS_HASH
            expected_seq = 1
            for row in rows:
                body = {
                    "seq": int(row["seq"]), "event_id": row["event_id"],
                    "event_type": row["event_type"], "payload_json": row["payload_json"],
                    "previous_hash": row["previous_hash"], "created_at": row["created_at"],
                }
                actual = _sha(_canonical(body))
                if (int(row["seq"]) != expected_seq or row["previous_hash"] != previous
                    or row["event_hash"] != actual):
                    return {"valid": False, "failed_seq": int(row["seq"])}
                previous = actual
                expected_seq += 1
            head = self._head()[1]
            if head != previous:
                return {"valid": False, "failed_seq": None}
            return {"valid": True, "events_checked": len(rows), "head_hash": head}

    def verify_projection_consistency(self) -> dict[str, Any]:
        """Replay reservation/consumption events and compare the mutable award projection."""
        with self._lock:
            chain = self.verify_event_chain()
            if not chain["valid"]:
                return {"valid": False, "issues": ["award registry event chain is invalid"]}
            replay: dict[str, dict[str, Any]] = {}
            issues = []
            for row in self._db.execute("SELECT * FROM events ORDER BY seq").fetchall():
                try:
                    payload = json.loads(row["payload_json"])
                    if row["event_type"] == "AWARD_RESERVED":
                        award_id = payload["award_id"]
                        if award_id in replay or any(
                            x["source_contribution_id"] == payload["source_contribution_id"]
                            for x in replay.values()
                        ):
                            raise ValueError("duplicate global award or source contribution")
                        replay[award_id] = {
                            "award_id": award_id,
                            "source_contribution_id": payload["source_contribution_id"],
                            "result_digest": payload["result_digest"],
                            "authorization_digest": payload["authorization_digest"],
                            "beneficiary_id": payload["beneficiary_id"],
                            "issuer_id": payload["issuer_id"],
                            "service_code": payload["service_code"],
                            "unit": payload["unit"],
                            "quantity": payload["quantity"],
                            "capacity_id": payload["capacity_id"],
                            "status": "RESERVED", "credit_id": None,
                            "ledger_event_id": None, "ledger_event_hash": None,
                        }
                    elif row["event_type"] == "AWARD_CONSUMED":
                        award = replay[payload["award_id"]]
                        if award["status"] != "RESERVED":
                            raise ValueError("award reservation consumed more than once")
                        award.update({
                            "status": "CONSUMED", "credit_id": payload["credit_id"],
                            "ledger_event_id": payload["ledger_event_id"],
                            "ledger_event_hash": payload["ledger_event_hash"],
                        })
                    else:
                        raise ValueError("unsupported award registry event")
                except (KeyError, TypeError, ValueError) as exc:
                    issues.append(f"event seq {row['seq']}: {exc}")
                    break
            if not issues:
                actual = {
                    row["award_id"]: {
                        key: row[key] for key in (
                            "award_id", "source_contribution_id", "result_digest",
                            "authorization_digest", "beneficiary_id", "issuer_id",
                            "service_code", "unit", "quantity", "capacity_id", "status",
                            "credit_id", "ledger_event_id", "ledger_event_hash",
                        )
                    }
                    for row in self._db.execute("SELECT * FROM awards").fetchall()
                }
                if replay != actual:
                    issues.append("award registry projection differs from event replay")
            return {
                "valid": not issues, "events_replayed": len(replay) + sum(
                    1 for row in self._db.execute("SELECT event_type FROM events")
                    if row["event_type"] == "AWARD_CONSUMED"
                ), "issues": issues,
            }


def issue_authorized_credit(
    ledger: Any, registry: SLEAwardRegistry,
    envelope: Mapping[str, Any], key_registry: Mapping[str, Mapping[str, Any]],
    *, now: datetime, due_at: str, credit_id: str, idempotency_key: str,
) -> dict[str, Any]:
    """Reserve globally, issue locally, then consume the reservation with ledger proof.

    If the process crashes after local issuance but before registry consumption, a retry
    with the same credit/idempotency identifiers completes reconciliation without
    issuing a second credit. If local issuance never happened, the reservation remains
    locked and the same authorized request can be retried while its authorization is valid.
    """
    award_id = _text(envelope.get("award_id") if isinstance(envelope, Mapping) else None, "award_id")
    try:
        existing = registry.get_award(award_id)
    except AwardRegistryError:
        existing = None

    if existing is not None and existing["status"] == "RESERVED":
        try:
            ledger.get_credit(credit_id)
        except (KeyError, ValueError):
            pass
        else:
            consumed = registry.consume_from_ledger(award_id, ledger, credit_id)
            return {"credit_id": credit_id, "award_id": award_id,
                    "registry_status": consumed["status"],
                    "reconciled_after_local_issue": True}

    reservation = registry.reserve(envelope, key_registry, now=now)
    result = ledger.issue(
        reservation["issuer_id"], reservation["beneficiary_id"],
        reservation["source_contribution_id"], reservation["award_id"],
        reservation["result_digest"], reservation["service_code"],
        reservation["unit"], reservation["capacity_id"], reservation["quantity"],
        due_at, credit_id, idempotency_key,
    )
    consumed = registry.consume_from_ledger(reservation["award_id"], ledger, credit_id)
    return {**result, "award_id": award_id, "registry_status": consumed["status"],
            "reservation_id": award_id, "reconciled_after_local_issue": False}
