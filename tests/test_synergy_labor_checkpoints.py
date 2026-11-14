from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64, json, sys, threading
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from synergy_labor_checkpoints import CheckpointError, GENESIS_HASH, create_registry_checkpoint, verify_registry_checkpoints, _digest
from synergy_labor_award_registry import SLEAwardRegistry
from synergy_labor_checkpoint_http import HttpCheckpointAnchorStore

class AnchorService:
    def __init__(self):
        self.lock, self.records = threading.RLock(), {}
    def handler(self):
        service = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def send_json(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            def registry_id(self):
                parts = urlsplit(self.path).path.strip("/").split("/")
                return unquote(parts[2]) if len(parts) == 4 and parts[:2] == ["v1", "registries"] and parts[3] == "checkpoints" else None
            def do_GET(self):
                rid = self.registry_id()
                if rid is None: return self.send_json(404, {})
                with service.lock: rows = list(service.records.get(rid, []))
                cursor = parse_qs(urlsplit(self.path).query).get("cursor", [None])[0]
                start = int(cursor or 0); page = rows[start:start+2]
                nxt = str(start+2) if start+2 < len(rows) else None
                self.send_json(200, {"items": page, "next_cursor": nxt})
            def do_POST(self):
                rid = self.registry_id()
                if rid is None: return self.send_json(404, {})
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                record, expected = body["checkpoint"], body["expected_previous_checkpoint_digest"]
                with service.lock:
                    rows = service.records.setdefault(rid, [])
                    actual = _digest(rows[-1]) if rows else GENESIS_HASH
                    if expected != actual or record.get("previous_checkpoint_digest") != actual:
                        return self.send_json(409, {"error":"stale"})
                    digest = _digest(record)
                    if self.headers.get("Idempotency-Key") != digest:
                        return self.send_json(400, {"error":"idempotency"})
                    if rows and int(record["event_seq"]) <= int(rows[-1]["event_seq"]):
                        return self.send_json(409, {"error":"sequence"})
                    rows.append(record)
                self.send_json(201, {"checkpoint_digest":digest})
        return Handler

@pytest.fixture
def service_url():
    service = AnchorService()
    server = ThreadingHTTPServer(("127.0.0.1", 0), service.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield f"http://127.0.0.1:{server.server_port}", service
    finally: server.shutdown(); thread.join(timeout=2); server.server_close()

def setup_registry():
    registry = SLEAwardRegistry()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    keys = {"checkpoint-key":{"roles":["REGISTRY_CHECKPOINTER"],"public_key_b64":base64.b64encode(public).decode(),
        "valid_from":"2026-01-01T00:00:00Z","valid_until":"2028-01-01T00:00:00Z","revoked_at":None}}
    return registry, private, keys

def test_remote_anchor_round_trip_and_recovery_with_new_client(service_url):
    url, service = service_url
    registry, private, keys = setup_registry()
    anchor = HttpCheckpointAnchorStore(url, lambda:"test-token")
    checkpoint = create_registry_checkpoint(registry, anchor, private, registry_id="registry-a",
        signer_key_id="checkpoint-key", created_at=datetime(2026,11,14,12,0,tzinfo=timezone.utc))
    # Simulate retry after a lost HTTP response: the exact signed record is not duplicated.
    anchor.append_checkpoint({key:value for key,value in checkpoint.items() if key != "checkpoint_digest"})
    assert len(anchor.list_checkpoints("registry-a")) == 1
    recovered = HttpCheckpointAnchorStore(url, lambda:"test-token")
    result = verify_registry_checkpoints(registry, recovered, keys, registry_id="registry-a")
    assert result["valid"] is True and result["checkpoints_checked"] == 1
    assert checkpoint["checkpoint_digest"] == _digest(service.records["registry-a"][0])
    registry.close()

def test_remote_compare_and_append_rejects_stale_competing_writers(service_url):
    url, _ = service_url
    stores = [HttpCheckpointAnchorStore(url, lambda:"test-token") for _ in range(2)]
    record = {"schema":"sle.registry-checkpoint/v1","registry_id":"registry-race","event_seq":1,
        "event_hash":"a"*64,"created_at":"2026-11-14T12:00:00+00:00","signer_key_id":"key",
        "previous_checkpoint_digest":GENESIS_HASH,"signature":"c2ln"}
    def append(store):
        try: store.append_checkpoint(record); return "accepted"
        except CheckpointError: return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(append, stores))
    assert sorted(outcomes) == ["accepted","rejected"]
    assert len(stores[0].list_checkpoints("registry-race")) == 1

def test_remote_adapter_rejects_insecure_urls_and_missing_token():
    with pytest.raises(CheckpointError, match="HTTPS"):
        HttpCheckpointAnchorStore("http://example.com", lambda:"secret")
    with pytest.raises(CheckpointError, match="token"):
        HttpCheckpointAnchorStore("http://127.0.0.1:1234", lambda:"")
