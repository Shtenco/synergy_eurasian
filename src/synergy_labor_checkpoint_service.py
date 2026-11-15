"""Durable SQLite WSGI service for independently hosted SLE checkpoints.

Deploy in a separate administrative/failure domain from the award registry.
Terminate TLS at a trusted reverse proxy; never expose this WSGI app over plain
network HTTP. The service stores signed checkpoint bytes but does not replace
independent Ed25519 verification by auditors.
"""
from __future__ import annotations

import base64
import hashlib
from contextlib import closing
import hmac
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, unquote

from synergy_labor_checkpoints import CheckpointError, GENESIS_HASH, _canonical, _digest


class AnchorServiceError(ValueError):
    pass


class SQLiteCheckpointAnchorApplication:
    """Small WSGI app with durable append-only records and atomic CAS publication."""

    def __init__(
        self,
        database: str | Path,
        *,
        bearer_tokens: Mapping[str, str],
        max_page_size: int = 500,
        reader_principals: set[str] | None = None,
        writer_principals: set[str] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if str(database) == ":memory:":
            raise AnchorServiceError("production anchor service requires a durable database path")
        if not bearer_tokens or any(
            not isinstance(principal, str) or not principal.strip()
            or not isinstance(token, str) or len(token) < 32
            for principal, token in bearer_tokens.items()
        ):
            raise AnchorServiceError("configure named principals with bearer tokens of at least 32 characters")
        if isinstance(max_page_size, bool) or not isinstance(max_page_size, int) or not 1 <= max_page_size <= 5000:
            raise AnchorServiceError("max_page_size must be between 1 and 5000")
        principals = set(bearer_tokens)
        self.reader_principals = principals if reader_principals is None else set(reader_principals)
        self.writer_principals = principals if writer_principals is None else set(writer_principals)
        if not self.reader_principals.issubset(principals) or not self.writer_principals.issubset(principals):
            raise AnchorServiceError("reader/writer principals must have configured credentials")
        if not self.reader_principals or not self.writer_principals:
            raise AnchorServiceError("at least one reader and one writer principal are required")
        self.database = str(database)
        self.max_page_size = max_page_size
        self.clock = clock
        self._tokens = {
            hashlib.sha256(token.encode("utf-8")).digest(): principal
            for principal, token in bearer_tokens.items()
        }
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self):
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS anchor_checkpoints (
                registry_id TEXT NOT NULL,
                event_seq INTEGER NOT NULL,
                checkpoint_digest TEXT NOT NULL,
                previous_digest TEXT NOT NULL,
                checkpoint_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                publisher_principal TEXT NOT NULL,
                stored_at REAL NOT NULL,
                PRIMARY KEY(registry_id, event_seq),
                UNIQUE(registry_id, checkpoint_digest),
                UNIQUE(registry_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS anchor_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                registry_id TEXT NOT NULL,
                action TEXT NOT NULL,
                checkpoint_digest TEXT,
                principal TEXT NOT NULL,
                occurred_at REAL NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS anchor_no_update
            BEFORE UPDATE ON anchor_checkpoints BEGIN
                SELECT RAISE(ABORT, 'anchor checkpoints are append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS anchor_no_delete
            BEFORE DELETE ON anchor_checkpoints BEGIN
                SELECT RAISE(ABORT, 'anchor checkpoints are append-only');
            END;
            """)

    def _principal(self, authorization: str | None):
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:]
        if not token or len(token) > 4096:
            return None
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        for expected, principal in self._tokens.items():
            if hmac.compare_digest(candidate, expected):
                return principal
        return None

    @staticmethod
    def _response(start_response, status: str, payload: Mapping[str, Any]):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        start_response(status, [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ])
        return [body]

    def __call__(self, environ, start_response):
        principal = self._principal(environ.get("HTTP_AUTHORIZATION"))
        if principal is None:
            return self._response(start_response, "401 Unauthorized", {"error": "unauthorized"})
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")
        match = re.fullmatch(r"/v1/registries/([^/]+)/checkpoints", path)
        if match is None:
            return self._response(start_response, "404 Not Found", {"error": "not_found"})
        registry_id = unquote(match.group(1))
        if not registry_id or len(registry_id) > 256 or "/" in registry_id or chr(92) in registry_id:
            return self._response(start_response, "400 Bad Request", {"error": "invalid_registry_id"})
        if method == "GET":
            if principal not in self.reader_principals:
                return self._response(start_response, "403 Forbidden", {"error": "read_forbidden"})
            return self._list(environ, start_response, registry_id, principal)
        if method == "POST":
            if principal not in self.writer_principals:
                return self._response(start_response, "403 Forbidden", {"error": "write_forbidden"})
            return self._append(environ, start_response, registry_id, principal)
        return self._response(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"})

    def _list(self, environ, start_response, registry_id, principal):
        try:
            query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
            cursor_text = query.get("cursor", ["0"])[0]
            limit_text = query.get("limit", [str(min(100, self.max_page_size))])[0]
            if not cursor_text.isdigit() or not limit_text.isdigit():
                raise ValueError
            offset, limit = int(cursor_text), int(limit_text)
            if offset < 0 or not 1 <= limit <= self.max_page_size:
                raise ValueError
        except (ValueError, TypeError):
            return self._response(start_response, "400 Bad Request", {"error": "invalid_pagination"})
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT checkpoint_json FROM anchor_checkpoints WHERE registry_id=? ORDER BY event_seq LIMIT ? OFFSET ?",
                (registry_id, limit + 1, offset),
            ).fetchall()
            db.execute(
                "INSERT INTO anchor_audit(registry_id,action,principal,occurred_at) VALUES(?,?,?,?)",
                (registry_id, "LIST", principal, self.clock()),
            )
        has_more = len(rows) > limit
        items = [json.loads(row["checkpoint_json"]) for row in rows[:limit]]
        next_cursor = str(offset + limit) if has_more else None
        return self._response(start_response, "200 OK", {"items": items, "next_cursor": next_cursor})

    def _append(self, environ, start_response, registry_id, principal):
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError:
            length = -1
        if length < 1 or length > 1024 * 1024:
            return self._response(start_response, "413 Payload Too Large", {"error": "invalid_content_length"})
        try:
            raw = environ["wsgi.input"].read(length)
            if len(raw) != length:
                raise ValueError
            payload = json.loads(raw.decode("utf-8"))
            record = payload["checkpoint"]
            expected = payload["expected_previous_checkpoint_digest"]
            if not isinstance(record, dict) or not isinstance(expected, str):
                raise ValueError
            required = {
                "schema", "registry_id", "event_seq", "event_hash", "created_at",
                "signer_key_id", "previous_checkpoint_digest", "signature",
            }
            if set(record) != required:
                raise ValueError
            if record.get("registry_id") != registry_id or record.get("schema") != "sle.registry-checkpoint/v1":
                raise ValueError
            seq = record.get("event_seq")
            if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
                raise ValueError
            if not re.fullmatch(r"[0-9a-f]{64}", record.get("event_hash", "")):
                raise ValueError
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError
            if record.get("previous_checkpoint_digest") != expected:
                raise ValueError
            if not isinstance(record.get("signer_key_id"), str) or not record["signer_key_id"].strip():
                raise ValueError
            created_at = record.get("created_at")
            if not isinstance(created_at, str):
                raise ValueError
            parsed_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if parsed_time.tzinfo is None:
                raise ValueError
            signature = record.get("signature")
            if not isinstance(signature, str):
                raise ValueError
            if len(base64.b64decode(signature, validate=True)) != 64:
                raise ValueError
            record_digest = _digest(record)
            idem = environ.get("HTTP_IDEMPOTENCY_KEY")
            if idem != record_digest:
                raise ValueError
            if environ.get("HTTP_IF_MATCH") != expected:
                raise ValueError
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError, CheckpointError):
            return self._response(start_response, "400 Bad Request", {"error": "invalid_checkpoint_request"})

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT checkpoint_digest,idempotency_key FROM anchor_checkpoints WHERE registry_id=? AND idempotency_key=?",
                (registry_id, idem),
            ).fetchone()
            if existing is not None:
                if existing["checkpoint_digest"] != record_digest:
                    db.execute("ROLLBACK")
                    return self._response(start_response, "409 Conflict", {"error": "idempotency_key_reused"})
                db.execute(
                    "INSERT INTO anchor_audit(registry_id,action,checkpoint_digest,principal,occurred_at) VALUES(?,?,?,?,?)",
                    (registry_id, "IDEMPOTENT_REPLAY", record_digest, principal, self.clock()),
                )
                db.execute("COMMIT")
                return self._response(start_response, "200 OK", {"checkpoint_digest": record_digest, "idempotent_replay": True})

            tail = db.execute(
                "SELECT event_seq,checkpoint_digest FROM anchor_checkpoints WHERE registry_id=? ORDER BY event_seq DESC LIMIT 1",
                (registry_id,),
            ).fetchone()
            actual_digest = GENESIS_HASH if tail is None else tail["checkpoint_digest"]
            previous_seq = -1 if tail is None else int(tail["event_seq"])
            if expected != actual_digest or record.get("previous_checkpoint_digest") != actual_digest or seq <= previous_seq:
                db.execute("ROLLBACK")
                return self._response(start_response, "409 Conflict", {"error": "stale_or_non_monotonic_checkpoint"})
            db.execute(
                """INSERT INTO anchor_checkpoints
                   (registry_id,event_seq,checkpoint_digest,previous_digest,checkpoint_json,idempotency_key,publisher_principal,stored_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (registry_id, seq, record_digest, expected, _canonical(record).decode("utf-8"), idem, principal, self.clock()),
            )
            db.execute(
                "INSERT INTO anchor_audit(registry_id,action,checkpoint_digest,principal,occurred_at) VALUES(?,?,?,?,?)",
                (registry_id, "APPEND", record_digest, principal, self.clock()),
            )
            db.execute("COMMIT")
            return self._response(start_response, "201 Created", {"checkpoint_digest": record_digest, "idempotent_replay": False})
        except sqlite3.IntegrityError:
            if db.in_transaction:
                db.execute("ROLLBACK")
            return self._response(start_response, "409 Conflict", {"error": "sequence_or_digest_conflict"})
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            return self._response(start_response, "500 Internal Server Error", {"error": "internal_error"})
        finally:
            db.close()


def create_app_from_environment():
    """Build a service from explicit deployment environment variables."""
    database = os.environ.get("SLE_ANCHOR_DATABASE")
    writer_principal = os.environ.get("SLE_ANCHOR_WRITER_PRINCIPAL")
    writer_token = os.environ.get("SLE_ANCHOR_WRITER_TOKEN")
    auditor_principal = os.environ.get("SLE_ANCHOR_AUDITOR_PRINCIPAL")
    auditor_token = os.environ.get("SLE_ANCHOR_AUDITOR_TOKEN")
    if not all((database, writer_principal, writer_token, auditor_principal, auditor_token)):
        raise AnchorServiceError("SLE_ANCHOR_DATABASE and separate writer/auditor principal+token variables are required")
    if writer_principal == auditor_principal:
        raise AnchorServiceError("writer and auditor must use distinct principals")
    return SQLiteCheckpointAnchorApplication(
        database,
        bearer_tokens={writer_principal: writer_token, auditor_principal: auditor_token},
        reader_principals={writer_principal, auditor_principal},
        writer_principals={writer_principal},
    )
