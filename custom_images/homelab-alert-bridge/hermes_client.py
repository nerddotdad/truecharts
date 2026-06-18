"""HTTP client for Hermes WebUI (in-cluster session + chat APIs)."""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator

HERMES_WEBUI_URL = os.environ.get(
    "HERMES_WEBUI_URL",
    "http://hermes-oncall-app-template.ai.svc.cluster.local:8787",
).rstrip("/")
HERMES_WEBUI_PASSWORD = os.environ.get("HERMES_WEBUI_PASSWORD", "")
HERMES_DEFAULT_WORKSPACE = os.environ.get("HERMES_WEBUI_DEFAULT_WORKSPACE", "/workspace")


class HermesError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class HermesClient:
    def __init__(self) -> None:
        self.base = HERMES_WEBUI_URL
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        if HERMES_WEBUI_PASSWORD:
            self._login()

    def _login(self) -> None:
        self._json_request(
            "POST",
            "/api/auth/login",
            {"password": HERMES_WEBUI_PASSWORD},
        )

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int = 120,
    ) -> dict[str, Any]:
        url = f"{self.base}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = body[:500]
            raise HermesError(f"Hermes API {method} {path} failed", status=exc.code, detail=detail) from exc
        except urllib.error.URLError as exc:
            raise HermesError(f"Hermes unreachable at {url}: {exc.reason}") from exc
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HermesError(f"Hermes returned invalid JSON from {path}") from exc
        if not isinstance(parsed, dict):
            raise HermesError(f"Hermes returned unexpected payload from {path}")
        return parsed

    def new_session(self, *, workspace: str | None = None) -> str:
        payload: dict[str, Any] = {}
        if workspace:
            payload["workspace"] = workspace
        data = self._json_request("POST", "/api/session/new", payload or None)
        session = data.get("session") or data
        session_id = str(session.get("session_id") or data.get("session_id") or "").strip()
        if not session_id:
            raise HermesError("Hermes session/new did not return session_id", detail=data)
        return session_id

    def rename_session(self, session_id: str, title: str) -> None:
        self._json_request(
            "POST",
            "/api/session/rename",
            {"session_id": session_id, "title": title[:80]},
        )

    def start_chat(self, session_id: str, message: str, *, workspace: str | None = None) -> str:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "message": message,
            "workspace": workspace or HERMES_DEFAULT_WORKSPACE,
        }
        data = self._json_request("POST", "/api/chat/start", payload, timeout=30)
        stream_id = str(data.get("stream_id") or "").strip()
        if not stream_id:
            raise HermesError("Hermes chat/start did not return stream_id", detail=data)
        return stream_id

    def get_session(self, session_id: str) -> dict[str, Any]:
        query = urllib.parse.quote(session_id, safe="")
        return self._json_request("GET", f"/api/session?session_id={query}")

    def iter_stream(self, stream_id: str) -> Iterator[bytes]:
        query = urllib.parse.quote(stream_id, safe="")
        url = f"{self.base}/api/chat/stream?stream_id={query}"
        req = urllib.request.Request(url, method="GET", headers={"Accept": "text/event-stream"})
        try:
            resp = self._opener.open(req, timeout=300)
        except urllib.error.HTTPError as exc:
            raise HermesError("Hermes stream failed", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise HermesError(f"Hermes stream unreachable: {exc.reason}") from exc
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()
