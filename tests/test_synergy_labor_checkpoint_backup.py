import sys
from pathlib import Path
import sqlite3
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from synergy_labor_checkpoints import GENESIS_HASH, _digest
from synergy_labor_checkpoint_service import SQLiteCheckpointAnchorApplication
from synergy_labor_checkpoint_backup import (
    AnchorBackupError, backup_anchor_database, restore_anchor_database,
    validate_anchor_database,
)

TOKEN = "backup-test-token-" + "z" * 40
PRINCIPAL = "backup-writer"


def make_record(seq, previous, marker):
    import base64
    return {
        "schema":"sle.registry-checkpoint/v1", "registry_id":"backup-registry",
        "event_seq":seq, "event_hash":marker*64,
        "created_at":"2026-11-14T12:00:00+00:00",
        "signer_key_id":"key-1", "previous_checkpoint_digest":previous,
        "signature":base64.b64encode(b"k"*64).decode("ascii"),
    }


def append(app, record):
    from tests.test_synergy_labor_checkpoint_service import append as service_append
    return service_append(app, record)


def test_online_backup_restore_and_independent_tail_validation(tmp_path):
    source = tmp_path / "source" / "anchor.sqlite"
    source.parent.mkdir()
    app = SQLiteCheckpointAnchorApplication(source, bearer_tokens={PRINCIPAL:TOKEN})
    first = make_record(1, GENESIS_HASH, "a")
    second = make_record(2, _digest(first), "b")
    assert append(app, first)[0] == 201
    assert append(app, second)[0] == 201
    backup = tmp_path / "off-host" / "anchor.backup.sqlite"
    result = backup_anchor_database(source, backup, registry_id="backup-registry",
                                    expected_tail_digest=_digest(second))
    assert result["checkpoints_checked"] == 2
    restored = tmp_path / "recovery" / "restored.sqlite"
    restored_result = restore_anchor_database(
        backup, restored, registry_id="backup-registry",
        expected_tail_digest=_digest(second), expected_backup_sha256=result["backup_sha256"],
    )
    assert restored_result["tail_digest"] == _digest(second)
    assert validate_anchor_database(
        restored, registry_id="backup-registry", expected_tail_digest=_digest(second)
    )["checkpoints_checked"] == 2


def test_restore_rejects_stale_backup_and_modified_backup_bytes(tmp_path):
    source = tmp_path / "source.sqlite"
    app = SQLiteCheckpointAnchorApplication(source, bearer_tokens={PRINCIPAL:TOKEN})
    first = make_record(1, GENESIS_HASH, "a")
    second = make_record(2, _digest(first), "b")
    assert append(app, first)[0] == 201
    old_backup = tmp_path / "old.sqlite"
    old = backup_anchor_database(source, old_backup, registry_id="backup-registry",
                                 expected_tail_digest=_digest(first))
    assert append(app, second)[0] == 201
    with pytest.raises(AnchorBackupError, match="trusted digest"):
        restore_anchor_database(old_backup, tmp_path/"bad.sqlite",
            registry_id="backup-registry", expected_tail_digest=_digest(second),
            expected_backup_sha256=old["backup_sha256"])
    old_backup.write_bytes(old_backup.read_bytes()+b"tamper")
    with pytest.raises(AnchorBackupError, match="SHA-256"):
        restore_anchor_database(old_backup, tmp_path/"bad2.sqlite",
            registry_id="backup-registry", expected_tail_digest=_digest(first),
            expected_backup_sha256=old["backup_sha256"])


def test_backup_validation_detects_rewritten_checkpoint_projection(tmp_path):
    source = tmp_path / "anchor.sqlite"
    app = SQLiteCheckpointAnchorApplication(source, bearer_tokens={PRINCIPAL:TOKEN})
    first = make_record(1, GENESIS_HASH, "a")
    assert append(app, first)[0] == 201
    with sqlite3.connect(source) as db:
        db.execute("DROP TRIGGER anchor_no_update")
        db.execute("UPDATE anchor_checkpoints SET checkpoint_json='{}' WHERE registry_id='backup-registry'")
    with pytest.raises(AnchorBackupError, match="validation failed"):
        validate_anchor_database(source, registry_id="backup-registry",
                                 expected_tail_digest=_digest(first))
