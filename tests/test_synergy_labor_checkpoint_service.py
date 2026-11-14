import base64
import io
import json
import sys
import sqlite3
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from synergy_labor_checkpoints import GENESIS_HASH, _digest
from synergy_labor_checkpoint_service import AnchorServiceError, SQLiteCheckpointAnchorApplication

TOKEN = "test-anchor-token-" + "x" * 40
AUDITOR_TOKEN = "test-anchor-auditor-" + "y" * 40
PRINCIPAL = "independent-checkpoint-writer"
AUDITOR = "independent-checkpoint-auditor"


def make_record(registry="r1", seq=1, previous=GENESIS_HASH, marker="a"):
    return {
        "schema": "sle.registry-checkpoint/v1",
        "registry_id": registry,
        "event_seq": seq,
        "event_hash": marker * 64,
        "created_at": "2026-11-14T12:00:00+00:00",
        "signer_key_id": "checkpoint-key",
        "previous_checkpoint_digest": previous,
        "signature": base64.b64encode(b"s" * 64).decode("ascii"),
    }


def call(app, method, path, *, payload=None, token=TOKEN, headers=None, query=""):
    body = b"" if payload is None else json.dumps(payload).encode()
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "HTTP_AUTHORIZATION": "Bearer " + token,
    }
    for key, value in (headers or {}).items():
        environ["HTTP_" + key.upper().replace("-", "_")] = value
    captured = {}

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    response = b"".join(app(environ, start_response))
    return int(captured["status"].split()[0]), json.loads(response), captured["headers"]


def make_app(path):
    return SQLiteCheckpointAnchorApplication(
        path,
        bearer_tokens={PRINCIPAL: TOKEN, AUDITOR: AUDITOR_TOKEN},
        reader_principals={PRINCIPAL, AUDITOR},
        writer_principals={PRINCIPAL},
        max_page_size=2,
        clock=lambda: 1794657600.0,
    )


def append(app, record):
    digest = _digest(record)
    return call(
        app,
        "POST",
        "/v1/registries/" + quote(record["registry_id"], safe="") + "/checkpoints",
        payload={
            "checkpoint": record,
            "expected_previous_checkpoint_digest": record["previous_checkpoint_digest"],
        },
        headers={
            "If-Match": record["previous_checkpoint_digest"],
            "Idempotency-Key": digest,
        },
    )


def test_atomic_append_idempotency_and_restart_recovery(tmp_path):
    db = tmp_path / "anchor.sqlite"
    app = make_app(db)
    first = make_record()
    status, body, _ = append(app, first)
    assert status == 201 and body["checkpoint_digest"] == _digest(first)
    status, replay, _ = append(app, first)
    assert status == 200 and replay["idempotent_replay"] is True

    restarted = make_app(db)
    status, page, _ = call(restarted, "GET", "/v1/registries/r1/checkpoints")
    assert status == 200 and page["items"] == [first]
    assert page["next_cursor"] is None


def test_compare_and_append_rejects_stale_writer_and_accepts_next_sequence(tmp_path):
    app = make_app(tmp_path / "anchor.sqlite")
    first = make_record()
    assert append(app, first)[0] == 201
    stale = make_record(seq=2, previous=GENESIS_HASH, marker="b")
    assert append(app, stale)[0] == 409
    second = make_record(seq=2, previous=_digest(first), marker="b")
    assert append(app, second)[0] == 201


def test_authentication_and_header_binding_fail_closed(tmp_path):
    app = make_app(tmp_path / "anchor.sqlite")
    record = make_record()
    status, _, _ = call(app, "GET", "/v1/registries/r1/checkpoints", token="wrong-token")
    assert status == 401
    digest = _digest(record)
    status, _, _ = call(
        app,
        "POST",
        "/v1/registries/r1/checkpoints",
        payload={
            "checkpoint": record,
            "expected_previous_checkpoint_digest": GENESIS_HASH,
        },
        headers={"If-Match": "f" * 64, "Idempotency-Key": digest},
    )
    assert status == 400


def test_pagination_and_append_only_storage(tmp_path):
    app = make_app(tmp_path / "anchor.sqlite")
    first = make_record(seq=1, marker="a")
    second = make_record(seq=2, previous=_digest(first), marker="b")
    third = make_record(seq=3, previous=_digest(second), marker="c")
    for record in (first, second, third):
        assert append(app, record)[0] == 201
    status, page1, _ = call(
        app, "GET", "/v1/registries/r1/checkpoints", query="limit=2"
    )
    status2, page2, _ = call(
        app, "GET", "/v1/registries/r1/checkpoints", query="limit=2&cursor=2"
    )
    assert status == status2 == 200
    assert page1["items"] == [first, second] and page1["next_cursor"] == "2"
    assert page2["items"] == [third] and page2["next_cursor"] is None
    with sqlite3.connect(tmp_path / "anchor.sqlite") as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(
                "UPDATE anchor_checkpoints SET checkpoint_json='{}' WHERE registry_id='r1'"
            )


def test_service_rejects_ephemeral_database_and_weak_credentials(tmp_path):
    with pytest.raises(AnchorServiceError, match="durable"):
        SQLiteCheckpointAnchorApplication(":memory:", bearer_tokens={PRINCIPAL: TOKEN})
    with pytest.raises(AnchorServiceError, match="32 characters"):
        SQLiteCheckpointAnchorApplication(
            tmp_path / "x.sqlite", bearer_tokens={PRINCIPAL: "weak"}
        )


def test_two_independent_service_instances_serialize_competing_writers(tmp_path):
    db = tmp_path / "shared-anchor.sqlite"
    apps = [make_app(db), make_app(db)]
    records = [
        make_record(seq=1, previous=GENESIS_HASH, marker="d"),
        make_record(seq=1, previous=GENESIS_HASH, marker="e"),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda pair: append(pair[0], pair[1])[0], zip(apps, records))
        )
    assert sorted(results) == [201, 409]
    status, page, _ = call(apps[0], "GET", "/v1/registries/r1/checkpoints")
    assert status == 200 and len(page["items"]) == 1


def test_auditor_is_read_only_and_cannot_publish(tmp_path):
    app = make_app(tmp_path / "anchor.sqlite")
    status, _, _ = call(
        app, "GET", "/v1/registries/r1/checkpoints", token=AUDITOR_TOKEN
    )
    assert status == 200
    record = make_record()
    digest = _digest(record)
    status, body, _ = call(
        app,
        "POST",
        "/v1/registries/r1/checkpoints",
        payload={
            "checkpoint": record,
            "expected_previous_checkpoint_digest": GENESIS_HASH,
        },
        token=AUDITOR_TOKEN,
        headers={"If-Match": GENESIS_HASH, "Idempotency-Key": digest},
    )
    assert status == 403 and body["error"] == "write_forbidden"
