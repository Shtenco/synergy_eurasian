"""HTTPS client adapter for an independently operated SLE checkpoint service."""
from __future__ import annotations
import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from synergy_labor_checkpoints import CheckpointAnchorStore, CheckpointError, GENESIS_HASH, _canonical, _digest

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class HttpCheckpointAnchorStore(CheckpointAnchorStore):
    """Remote anchor client. The service must atomically compare-and-append."""
    def __init__(self, base_url: str, token_provider: Callable[[], str], *, timeout: float = 10.0, page_limit: int = 10000):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise CheckpointError("checkpoint service URL must use HTTPS")
        if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise CheckpointError("checkpoint service URL is malformed")
        if not callable(token_provider):
            raise CheckpointError("token_provider must be callable")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise CheckpointError("timeout must be a positive number")
        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or page_limit < 1:
            raise CheckpointError("page_limit must be a positive integer")
        self._base = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        self._token_provider, self._timeout, self._page_limit = token_provider, float(timeout), page_limit
        self._opener = build_opener(_NoRedirect)

    def _url(self, registry_id: str, cursor: str | None = None) -> str:
        path = f"{self._base}/v1/registries/{quote(registry_id, safe='')}/checkpoints"
        return path if cursor is None else f"{path}?{urlencode({'cursor': cursor})}"

    def _request(self, method: str, url: str, payload: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None):
        token = self._token_provider()
        if not isinstance(token, str) or not token.strip():
            raise CheckpointError("checkpoint service authentication token is unavailable")
        request_headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)
        data = None
        if payload is not None:
            data = _canonical(dict(payload))
            request_headers["Content-Type"] = "application/json"
        try:
            with self._opener.open(Request(url, data=data, headers=request_headers, method=method), timeout=self._timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise CheckpointError("checkpoint service response exceeds 8 MiB")
        except HTTPError as exc:
            if exc.code == 409:
                raise CheckpointError("checkpoint append conflict: remote head changed") from None
            if exc.code in (401, 403):
                raise CheckpointError("checkpoint service rejected authentication/authorization") from None
            if exc.code == 404:
                raise CheckpointError("checkpoint registry endpoint was not found") from None
            raise CheckpointError(f"checkpoint service HTTP error {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise CheckpointError(f"checkpoint service unavailable: {type(exc).__name__}") from None
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CheckpointError("checkpoint service returned invalid JSON") from None
        if not isinstance(result, dict):
            raise CheckpointError("checkpoint service response must be a JSON object")
        return result

    def list_checkpoints(self, registry_id: str):
        if (not isinstance(registry_id, str) or not registry_id.strip()
                or "/" in registry_id or chr(92) in registry_id):
            raise CheckpointError("registry_id must be a non-empty URL-safe path segment")
        items, cursor, seen = [], None, set()
        for _ in range(self._page_limit):
            result = self._request("GET", self._url(registry_id, cursor))
            page = result.get("items")
            if not isinstance(page, list) or any(not isinstance(x, dict) for x in page):
                raise CheckpointError("checkpoint service page must contain object items")
            items.extend(dict(x) for x in page)
            next_cursor = result.get("next_cursor")
            if next_cursor is None:
                return items
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen:
                raise CheckpointError("checkpoint service pagination cursor is invalid")
            seen.add(next_cursor)
            cursor = next_cursor
        raise CheckpointError("checkpoint service pagination exceeded configured page limit")

    def append_checkpoint(self, checkpoint: Mapping[str, Any]) -> None:
        record = dict(checkpoint)
        registry_id = record.get("registry_id")
        if not isinstance(registry_id, str) or not registry_id.strip():
            raise CheckpointError("registry_id is required")
        existing = self.list_checkpoints(registry_id)
        record_digest = _digest(record)
        # Recover an append whose HTTP response was lost after the service committed it.
        if any(_digest(item) == record_digest for item in existing):
            return
        previous = _digest(existing[-1]) if existing else GENESIS_HASH
        if record.get("previous_checkpoint_digest") != previous:
            raise CheckpointError("checkpoint does not extend the latest remote anchor")
        if existing and int(record.get("event_seq", -1)) <= int(existing[-1].get("event_seq", -1)):
            raise CheckpointError("checkpoint sequence must increase monotonically")
        self._request("POST", self._url(registry_id), {"checkpoint": record, "expected_previous_checkpoint_digest": previous},
                      {"If-Match": previous, "Idempotency-Key": record_digest})
