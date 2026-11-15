from pathlib import Path
import sys
from datetime import datetime, timezone

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdu_ledger_checkpoints import (
    CheckpointError,
    create_checkpoint,
    verify_checkpoint,
    verify_checkpoint_progression,
)


KEY = b"checkpoint-signing-key-material-32-bytes!!"


def test_checkpoint_signature_and_digest_verify():
    checkpoint = create_checkpoint(
        12, "a" * 64, KEY,
        created_at=datetime(2026, 11, 15, 2, 0, tzinfo=timezone.utc),
    )
    assert verify_checkpoint(checkpoint, KEY)
    assert checkpoint.algorithm == "HMAC-SHA256"


def test_checkpoint_tampering_is_detected():
    checkpoint = create_checkpoint(12, "a" * 64, KEY)
    altered = type(checkpoint)(
        sequence=13, event_hash=checkpoint.event_hash,
        created_at=checkpoint.created_at, digest=checkpoint.digest,
        signature=checkpoint.signature,
    )
    assert not verify_checkpoint(altered, KEY)


def test_checkpoint_progression_requires_monotonic_sequence():
    first = create_checkpoint(10, "a" * 64, KEY)
    later = create_checkpoint(20, "b" * 64, KEY)
    older = create_checkpoint(9, "c" * 64, KEY)
    assert verify_checkpoint_progression(first, later, KEY)
    assert not verify_checkpoint_progression(first, older, KEY)


def test_wrong_key_and_short_key_rejected():
    checkpoint = create_checkpoint(1, "f" * 64, KEY)
    assert not verify_checkpoint(checkpoint, b"x" * 32)
    with pytest.raises(CheckpointError, match="32 bytes"):
        create_checkpoint(1, "f" * 64, b"short")


def test_invalid_hash_or_naive_timestamp_rejected():
    with pytest.raises(CheckpointError, match="event_hash"):
        create_checkpoint(1, "BAD", KEY)
    with pytest.raises(CheckpointError, match="timezone"):
        create_checkpoint(1, "a" * 64, KEY, created_at=datetime(2026, 1, 1))
