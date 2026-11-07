"""Durable SQLite event log and transactional outbox/inbox primitives.

The module is transport infrastructure, not an accounting or payment authority.
Outbox delivery is at-least-once. Consumers obtain idempotent local effects by
committing their inbox receipt and handler writes in the same SQLite transaction.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from hashlib import sha256
import json
import sqlite3
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


_EVENT_FIELDS = (
    "event_id", "aggregate_type", "aggregate_id", "sequence", "event_type",
    "effective_at", "recorded_at", "payload", "source_ref", "evidence_ids",
    "idempotency_key", "previous_hash", "event_hash",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _row(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("Event must be a dataclass or mapping")


def _aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed


def _now(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return result.astimezone(timezone.utc)


def _unsigned(row: Mapping[str, Any], previous_hash: str) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "aggregate_type": row["aggregate_type"],
        "aggregate_id": row["aggregate_id"],
        "sequence": row["sequence"],
        "event_type": row["event_type"],
        "effective_at": row["effective_at"],
        "recorded_at": row["recorded_at"],
        "payload": row["payload"],
        "source_ref": row["source_ref"],
        "evidence_ids": tuple(row.get("evidence_ids") or ()),
        "idempotency_key": row.get("idempotency_key") or "",
        "previous_hash": previous_hash,
    }


def _validate_event(row: Mapping[str, Any]) -> None:
    missing = [name for name in _EVENT_FIELDS[:10] if name not in row]
    if missing:
        raise ValueError(f"Event missing required fields: {', '.join(missing)}")
    for name in ("event_id", "aggregate_type", "aggregate_id", "event_type", "source_ref"):
        if not isinstance(row[name], str) or not row[name].strip():
            raise ValueError(f"{name} must be a non-empty string")
    sequence = row["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence must be an integer >= 1")
    if not isinstance(row["payload"], dict):
        raise ValueError("payload must be a JSON object")
    _canonical(row["payload"])
    _aware(row["effective_at"], "effective_at")
    _aware(row["recorded_at"], "recorded_at")
    idem = row.get("idempotency_key") or ""
    previous = row.get("previous_hash") or ""
    if not isinstance(idem, str) or not isinstance(previous, str):
        raise ValueError("idempotency_key and previous_hash must be strings")
    evidence = tuple(row.get("evidence_ids") or ())
    if any(not isinstance(item, str) or not item for item in evidence):
        raise ValueError("evidence_ids must contain non-empty strings")
    if len(evidence) != len(set(evidence)):
        raise ValueError("evidence_ids must be unique within an event")
    _canonical(_unsigned(row, str(row.get("previous_hash") or "")))


@dataclass(frozen=True)
class DurableEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: str
    recorded_at: str
    payload: dict[str, Any]
    source_ref: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    previous_hash: str
    event_hash: str

    def unsigned(self) -> dict[str, Any]:
        return _unsigned(_row(self), self.previous_hash)


@dataclass(frozen=True)
class OutboxMessage:
    message_id: str
    event_id: str
    event_hash: str
    destination: str
    topic: str
    payload_json: str
    attempts: int
    lease_token: str
    lease_until: datetime


class DurableEventStore:
    """Append-only SQLite event log; event append and outbox enqueue are atomic.

    Use a file-backed database path. Each operation opens its own connection and
    obtains BEGIN IMMEDIATE, allowing independent processes to serialize writers.
    """

    def __init__(self, database_path: str, busy_timeout_ms: int = 5000):
        if not isinstance(database_path, str) or not database_path.strip() or database_path == ":memory:":
            raise ValueError("A persistent SQLite database file path is required")
        if isinstance(busy_timeout_ms, bool) or busy_timeout_ms < 1:
            raise ValueError("busy_timeout_ms must be a positive integer")
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        self._initialize()
        if not self.verify():
            raise ValueError("Durable event store integrity verification failed")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path, timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _session(self):
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._session() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS event_log (
                    event_row INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence >= 1),
                    event_type TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    event_json TEXT NOT NULL,
                    UNIQUE(aggregate_type, aggregate_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS aggregate_heads (
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY(aggregate_type, aggregate_id)
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    message_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES event_log(event_id),
                    event_hash TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PENDING','INFLIGHT','DELIVERED','DEAD')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    available_at TEXT NOT NULL,
                    lease_until TEXT,
                    lease_token TEXT,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT,
                    last_error TEXT NOT NULL DEFAULT '',
                    UNIQUE(event_id, destination)
                );
                CREATE INDEX IF NOT EXISTS outbox_ready
                    ON outbox(status, available_at, lease_until, created_at);
                CREATE TABLE IF NOT EXISTS inbox (
                    consumer TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    PRIMARY KEY(consumer, message_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS inbox_consumer_event_unique
                    ON inbox(consumer, event_id);
                CREATE TRIGGER IF NOT EXISTS inbox_no_update
                BEFORE UPDATE ON inbox
                BEGIN SELECT RAISE(ABORT, 'inbox receipts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS inbox_no_delete
                BEFORE DELETE ON inbox
                BEGIN SELECT RAISE(ABORT, 'inbox receipts are append-only'); END;
            """)

    @property
    def events(self) -> tuple[DurableEvent, ...]:
        with self._session() as db:
            rows = db.execute("SELECT event_json FROM event_log ORDER BY event_row").fetchall()
        result = []
        for item in rows:
            row = json.loads(item["event_json"])
            row["evidence_ids"] = tuple(row.get("evidence_ids") or ())
            result.append(DurableEvent(**row))
        return tuple(result)

    def append(
        self,
        event: Any,
        destination: str = "synergy.sues",
        topic: str | None = None,
        enqueue: bool = True,
        now: datetime | None = None,
    ) -> DurableEvent:
        row = _row(event)
        _validate_event(row)
        destination = destination.strip() if isinstance(destination, str) else ""
        if enqueue and not destination:
            raise ValueError("A non-empty outbox destination is required")
        topic_value = topic or str(row["event_type"])
        if enqueue and (not isinstance(topic_value, str) or not topic_value.strip()):
            raise ValueError("Outbox topic must be a non-empty string")
        timestamp = _now(now).isoformat()
        key = (row["aggregate_type"], row["aggregate_id"])
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                head = db.execute(
                    "SELECT sequence, event_hash FROM aggregate_heads WHERE aggregate_type=? AND aggregate_id=?",
                    key,
                ).fetchone()
                expected_sequence = (head["sequence"] if head else 0) + 1
                if row["sequence"] != expected_sequence:
                    raise ValueError(
                        f"Expected aggregate sequence {expected_sequence}, got {row['sequence']}"
                    )
                previous_hash = head["event_hash"] if head else ""
                supplied_previous = row.get("previous_hash") or ""
                if supplied_previous and supplied_previous != previous_hash:
                    raise ValueError("previous_hash does not match durable aggregate head")
                unsigned = _unsigned(row, previous_hash)
                digest = sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
                sealed = {
                    **unsigned,
                    "evidence_ids": list(unsigned["evidence_ids"]),
                    "event_hash": digest,
                }
                event_json = _canonical(sealed)
                db.execute(
                    """INSERT INTO event_log
                    (event_id,aggregate_type,aggregate_id,sequence,event_type,event_hash,
                     previous_hash,idempotency_key,event_json)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (row["event_id"], key[0], key[1], row["sequence"], row["event_type"],
                     digest, previous_hash, row.get("idempotency_key") or None, event_json),
                )
                db.execute(
                    """INSERT INTO aggregate_heads(aggregate_type,aggregate_id,sequence,event_hash)
                    VALUES(?,?,?,?)
                    ON CONFLICT(aggregate_type,aggregate_id)
                    DO UPDATE SET sequence=excluded.sequence,event_hash=excluded.event_hash""",
                    (key[0], key[1], row["sequence"], digest),
                )
                if enqueue:
                    message_id = sha256(
                        _canonical({"event_id": row["event_id"], "destination": destination}).encode()
                    ).hexdigest()
                    db.execute(
                        """INSERT INTO outbox
                        (message_id,event_id,event_hash,destination,topic,payload_json,status,
                         attempts,available_at,created_at)
                        VALUES(?,?,?,?,?,?,'PENDING',0,?,?)""",
                        (message_id, row["event_id"], digest, destination, topic_value,
                         event_json, timestamp, timestamp),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return DurableEvent(
            row["event_id"], key[0], key[1], row["sequence"], row["event_type"],
            row["effective_at"], row["recorded_at"], dict(row["payload"]), row["source_ref"],
            tuple(row.get("evidence_ids") or ()), row.get("idempotency_key") or "",
            previous_hash, digest,
        )

    def claim_outbox(
        self,
        limit: int = 50,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> tuple[OutboxMessage, ...]:
        if (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
                or isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1):
            raise ValueError("limit and lease_seconds must be positive integers")
        instant = _now(now)
        stamp = instant.isoformat()
        lease_end = (instant + timedelta(seconds=lease_seconds)).isoformat()
        claimed: list[OutboxMessage] = []
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                rows = db.execute(
                    """SELECT * FROM outbox
                    WHERE (status='PENDING' AND available_at<=?)
                       OR (status='INFLIGHT' AND lease_until<=?)
                    ORDER BY created_at,message_id LIMIT ?""",
                    (stamp, stamp, limit),
                ).fetchall()
                for row in rows:
                    token = uuid4().hex
                    db.execute(
                        """UPDATE outbox SET status='INFLIGHT',attempts=attempts+1,
                           lease_until=?,lease_token=? WHERE message_id=?""",
                        (lease_end, token, row["message_id"]),
                    )
                    claimed.append(OutboxMessage(
                        row["message_id"], row["event_id"], row["event_hash"],
                        row["destination"], row["topic"], row["payload_json"],
                        row["attempts"] + 1, token, datetime.fromisoformat(lease_end),
                    ))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return tuple(claimed)

    def ack_outbox(
        self, message_id: str, lease_token: str, now: datetime | None = None
    ) -> None:
        stamp = _now(now).isoformat()
        with self._session() as db:
            cursor = db.execute(
                """UPDATE outbox SET status='DELIVERED',delivered_at=?,
                   lease_until=NULL,lease_token=NULL
                   WHERE message_id=? AND status='INFLIGHT' AND lease_token=? AND lease_until>?""",
                (stamp, message_id, lease_token, stamp),
            )
            if cursor.rowcount != 1:
                raise ValueError("Outbox acknowledgement rejected: stale lease or unknown message")

    def fail_outbox(
        self,
        message_id: str,
        lease_token: str,
        error: str,
        retry_delay_seconds: int = 5,
        max_attempts: int = 10,
        now: datetime | None = None,
    ) -> str:
        if (isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, int)
                or retry_delay_seconds < 0 or isinstance(max_attempts, bool)
                or not isinstance(max_attempts, int) or max_attempts < 1):
            raise ValueError("retry_delay_seconds must be >= 0 and max_attempts >= 1")
        instant = _now(now)
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT attempts FROM outbox WHERE message_id=? AND status='INFLIGHT' AND lease_token=? AND lease_until>?",
                    (message_id, lease_token, instant.isoformat()),
                ).fetchone()
                if row is None:
                    raise ValueError("Outbox failure rejected: stale lease or unknown message")
                status = "DEAD" if row["attempts"] >= max_attempts else "PENDING"
                available = (instant + timedelta(seconds=retry_delay_seconds)).isoformat()
                db.execute(
                    """UPDATE outbox SET status=?,available_at=?,lease_until=NULL,
                       lease_token=NULL,last_error=? WHERE message_id=?""",
                    (status, available, str(error)[:2000], message_id),
                )
                db.commit()
                return status
            except Exception:
                db.rollback()
                raise

    def consume_inbox(
        self,
        consumer: str,
        message: Mapping[str, Any],
        handler: Callable[[sqlite3.Connection, Mapping[str, Any]], None],
        received_at: datetime | None = None,
    ) -> bool:
        """Apply local DB effects and record inbox receipt in one transaction.

        Handler must use only the supplied connection and must not perform network,
        payment, filesystem or other external side effects. Return False for an
        exact duplicate; reject message-ID reuse with a different event hash.
        """
        if not isinstance(consumer, str) or not consumer.strip():
            raise ValueError("consumer must be a non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")
        message_snapshot = json.loads(_canonical(dict(message)))
        required = ("message_id", "event_id", "event_hash", "payload_json")
        if any(not isinstance(message_snapshot.get(key), str) or not message_snapshot.get(key) for key in required):
            raise ValueError("Inbox message is missing required string fields")
        payload = json.loads(message_snapshot["payload_json"])
        if not isinstance(payload, dict):
            raise ValueError("Inbox payload_json must contain an event object")
        if _canonical(payload) != message_snapshot["payload_json"]:
            raise ValueError("Inbox payload_json must use canonical JSON encoding")
        if payload.get("event_id") != message_snapshot["event_id"] or payload.get("event_hash") != message_snapshot["event_hash"]:
            raise ValueError("Inbox envelope identity does not match its event payload")
        digest_row = dict(payload)
        supplied_hash = digest_row.pop("event_hash", None)
        unsigned = _unsigned(digest_row, str(digest_row.get("previous_hash") or ""))
        digest = sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
        if supplied_hash != digest or message_snapshot["event_hash"] != digest:
            raise ValueError("Inbox event hash verification failed")
        _validate_event(digest_row)
        stamp = _now(received_at).isoformat()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT event_hash FROM inbox WHERE consumer=? AND message_id=?",
                    (consumer, message_snapshot["message_id"]),
                ).fetchone()
                if existing is not None:
                    if existing["event_hash"] != digest:
                        raise ValueError("Inbox message ID reused with a different event hash")
                    db.rollback()
                    return False
                existing_event = db.execute(
                    "SELECT message_id,event_hash FROM inbox WHERE consumer=? AND event_id=?",
                    (consumer, message_snapshot["event_id"]),
                ).fetchone()
                if existing_event is not None:
                    if existing_event["event_hash"] != digest:
                        raise ValueError("Inbox event ID reused with a different event hash")
                    db.rollback()
                    return False
                handler_message = json.loads(_canonical(message_snapshot))
                handler(db, handler_message)
                db.execute(
                    """INSERT INTO inbox(consumer,message_id,event_id,event_hash,received_at)
                    VALUES(?,?,?,?,?)""",
                    (consumer, message_snapshot["message_id"], message_snapshot["event_id"], digest, stamp),
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise

    def inbox_contains(self, consumer: str, message_id: str) -> bool:
        with self._session() as db:
            row = db.execute(
                "SELECT 1 FROM inbox WHERE consumer=? AND message_id=?",
                (consumer, message_id),
            ).fetchone()
        return row is not None

    def outbox_status(self, message_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM outbox WHERE message_id=?", (message_id,)).fetchone()
        return dict(row) if row is not None else None

    def verify(self) -> bool:
        with self._session() as db:
            rows = db.execute("SELECT * FROM event_log ORDER BY event_row").fetchall()
            heads: dict[tuple[str, str], tuple[int, str]] = {}
            event_ids: set[str] = set()
            idempotency: set[str] = set()
            for stored in rows:
                row = json.loads(stored["event_json"])
                _validate_event(row)
                key = (row["aggregate_type"], row["aggregate_id"])
                prior_sequence, prior_hash = heads.get(key, (0, ""))
                if row["sequence"] != prior_sequence + 1:
                    return False
                if row.get("previous_hash", "") != prior_hash:
                    return False
                digest = sha256(_canonical(_unsigned(row, prior_hash)).encode("utf-8")).hexdigest()
                if digest != row.get("event_hash") or digest != stored["event_hash"]:
                    return False
                if row["event_id"] in event_ids:
                    return False
                idem = row.get("idempotency_key") or ""
                if idem and idem in idempotency:
                    return False
                event_ids.add(row["event_id"])
                if idem:
                    idempotency.add(idem)
                heads[key] = (row["sequence"], digest)

            persisted_heads = {
                (row["aggregate_type"], row["aggregate_id"]): (row["sequence"], row["event_hash"])
                for row in db.execute("SELECT * FROM aggregate_heads").fetchall()
            }
            if persisted_heads != heads:
                return False
            event_json_by_id = {row["event_id"]: row["event_json"] for row in rows}
            for item in db.execute("SELECT * FROM outbox").fetchall():
                row = json.loads(item["payload_json"])
                if row.get("event_id") != item["event_id"] or row.get("event_hash") != item["event_hash"]:
                    return False
                if item["event_id"] not in event_ids:
                    return False
                if _canonical(row) != event_json_by_id[item["event_id"]]:
                    return False
                expected_message_id = sha256(_canonical({"event_id": item["event_id"], "destination": item["destination"]}).encode()).hexdigest()
                if item["message_id"] != expected_message_id or not item["destination"] or not item["topic"]:
                    return False
        return True
