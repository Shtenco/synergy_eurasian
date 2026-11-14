"""Verified SQLite backup and restore for the independent SLE checkpoint anchor.

The expected tail digest must be obtained through a separate trusted channel and
retained outside the anchor host. A backup's own manifest is not a trust anchor.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.parse import quote

from synergy_labor_checkpoints import CheckpointError, GENESIS_HASH, _digest


class AnchorBackupError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly_connection(path: Path):
    uri = path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def validate_anchor_database(
    database_path: str | Path, *, registry_id: str, expected_tail_digest: str
) -> dict:
    path = Path(database_path)
    if not path.is_file():
        raise AnchorBackupError("anchor database file does not exist")
    if not isinstance(registry_id, str) or not registry_id.strip():
        raise AnchorBackupError("registry_id is required")
    if not isinstance(expected_tail_digest, str) or len(expected_tail_digest) != 64:
        raise AnchorBackupError("expected_tail_digest must be a SHA-256 digest")
    try:
        with _readonly_connection(path) as db:
            rows = db.execute(
                """SELECT event_seq,checkpoint_digest,previous_digest,checkpoint_json
                   FROM anchor_checkpoints WHERE registry_id=? ORDER BY event_seq""",
                (registry_id,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise AnchorBackupError(f"cannot read anchor database: {type(exc).__name__}") from None
    previous, previous_seq = GENESIS_HASH, -1
    for row in rows:
        try:
            record = json.loads(row[3])
            digest = _digest(record)
            seq = int(row[0])
            if record.get("registry_id") != registry_id:
                raise ValueError("registry identity mismatch")
            if seq != record.get("event_seq") or seq <= previous_seq:
                raise ValueError("event sequence is not strictly increasing")
            if row[1] != digest or row[2] != previous:
                raise ValueError("stored digest or previous-link mismatch")
            if record.get("previous_checkpoint_digest") != previous:
                raise ValueError("checkpoint previous digest mismatch")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError, CheckpointError) as exc:
            raise AnchorBackupError(f"anchor chain validation failed: {exc}") from None
        previous, previous_seq = digest, seq
    if previous != expected_tail_digest:
        raise AnchorBackupError("anchor tail does not match independently supplied trusted digest")
    return {
        "registry_id": registry_id,
        "checkpoints_checked": len(rows),
        "latest_event_seq": previous_seq if rows else None,
        "tail_digest": previous,
    }


def _sqlite_online_copy(source_path: Path, destination_path: Path) -> None:
    source = sqlite3.connect(str(source_path), timeout=30)
    destination = sqlite3.connect(str(destination_path), timeout=30)
    try:
        source.backup(destination)
        destination.execute("PRAGMA integrity_check")
        result = destination.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise AnchorBackupError("SQLite integrity_check failed on copied database")
    finally:
        destination.close()
        source.close()


def backup_anchor_database(
    source_database: str | Path,
    backup_path: str | Path,
    *,
    registry_id: str,
    expected_tail_digest: str,
) -> dict:
    source, target = Path(source_database).resolve(), Path(backup_path).resolve()
    if source == target:
        raise AnchorBackupError("backup destination must differ from source database")
    if not source.is_file():
        raise AnchorBackupError("source anchor database does not exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        _sqlite_online_copy(source, temp)
        validation = validate_anchor_database(
            temp, registry_id=registry_id, expected_tail_digest=expected_tail_digest
        )
        os.replace(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return {**validation, "backup_path": str(target), "backup_sha256": _file_sha256(target)}


def restore_anchor_database(
    backup_path: str | Path,
    destination_database: str | Path,
    *,
    registry_id: str,
    expected_tail_digest: str,
    expected_backup_sha256: str,
) -> dict:
    backup, target = Path(backup_path).resolve(), Path(destination_database).resolve()
    if backup == target:
        raise AnchorBackupError("restore destination must differ from backup")
    if not backup.is_file():
        raise AnchorBackupError("backup file does not exist")
    actual_sha = _file_sha256(backup)
    if actual_sha != expected_backup_sha256:
        raise AnchorBackupError("backup file SHA-256 does not match independently retained digest")
    validation = validate_anchor_database(
        backup, registry_id=registry_id, expected_tail_digest=expected_tail_digest
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".restore", dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        _sqlite_online_copy(backup, temp)
        validate_anchor_database(
            temp, registry_id=registry_id, expected_tail_digest=expected_tail_digest
        )
        os.replace(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return {**validation, "restored_path": str(target), "backup_sha256": actual_sha}
