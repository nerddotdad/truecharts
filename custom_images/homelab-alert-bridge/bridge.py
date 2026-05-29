#!/usr/bin/env python3
"""Store Alertmanager payloads, proxy to alertmanager-ntfy, forward triage to Hermes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INCIDENT_DIR = Path(os.environ.get("INCIDENT_DIR", "/data/incidents"))
NTFY_BRIDGE_URL = os.environ.get(
    "NTFY_BRIDGE_URL",
    "http://alertmanager-ntfy.observability.svc.cluster.local:8000/hook",
)
HERMES_WEBHOOK_URL = os.environ.get(
    "HERMES_WEBHOOK_URL",
    "http://hermes-oncall-app-template.ai.svc.cluster.local:8644/webhooks/homelab-alerts",
)
HERMES_WEBHOOK_SECRET = os.environ.get("HERMES_WEBHOOK_SECRET", "")
TRIAGE_AUTH_TOKEN = os.environ.get("TRIAGE_AUTH_TOKEN", "")
HERMES_PUBLIC_BASE_URL = os.environ.get("HERMES_PUBLIC_BASE_URL", "").rstrip("/")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8000"))
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", str(2 * 1024 * 1024)))


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())[:128]
    return cleaned or "unknown"


def _fingerprint(alert: dict) -> str:
    fp = str(alert.get("fingerprint") or "").strip()
    if fp:
        return _safe_id(fp)
    labels = alert.get("labels") or {}
    return _safe_id(
        f"{labels.get('alertname', 'alert')}-{labels.get('namespace', 'ns')}"
    )


def _store_incidents(payload: dict) -> list[str]:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    ids: list[str] = []
    for alert in payload.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        iid = _fingerprint(alert)
        path = INCIDENT_DIR / f"{iid}.json"
        path.write_text(
            json.dumps(
                {
                    "id": iid,
                    "status": payload.get("status"),
                    "receiver": payload.get("receiver"),
                    "alert": alert,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        ids.append(iid)
    return ids


def _proxy_to_ntfy(body: bytes, content_type: str) -> tuple[int, bytes]:
    req = urllib.request.Request(
        NTFY_BRIDGE_URL,
        data=body,
        method="POST",
        headers={"Content-Type": content_type or "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _sign_webhook(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _check_triage_auth(headers, query: str = "") -> bool:
    if not TRIAGE_AUTH_TOKEN:
        return False
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:].strip() == TRIAGE_AUTH_TOKEN:
        return True
    if headers.get("X-Homelab-Triage-Token") == TRIAGE_AUTH_TOKEN:
        return True
    # ntfy iOS often omits custom headers on http actions; allow token in query (ingress logs).
    for part in query.split("&"):
        if part.startswith("token=") and part[6:] == TRIAGE_AUTH_TOKEN:
            return True
    return False


def _load_incident(incident_id: str) -> dict | None:
    path = INCIDENT_DIR / f"{incident_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _forward_to_hermes(incident: dict) -> tuple[int, bytes]:
    if not HERMES_WEBHOOK_SECRET:
        return 503, b'{"error":"webhook secret not configured"}'
    body = json.dumps(incident).encode("utf-8")
    req = urllib.request.Request(
        HERMES_WEBHOOK_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": _sign_webhook(body, HERMES_WEBHOOK_SECRET),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        return 502, json.dumps({"error": "hermes webhook unreachable", "detail": str(exc.reason)}).encode(
            "utf-8"
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "homelab-alert-bridge/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> tuple[dict | None, int | None]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            return None, 413
        if length == 0:
            return {}, None
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None, 400
        if not isinstance(payload, dict):
            return None, 400
        return payload, None

    def _incident_id_from_request(self, payload: dict | None) -> str:
        if payload:
            for key in ("incident_id", "id", "fingerprint"):
                value = payload.get(key)
                if value:
                    return _safe_id(str(value))
        query = self.path.split("?", 1)
        if len(query) == 2:
            for part in query[1].split("&"):
                if part.startswith("incident_id="):
                    return _safe_id(part.split("=", 1)[1])
        return ""

    def do_GET(self) -> None:
        if self.path in ("/health", "/healthz"):
            self._json(200, {"ok": True})
            return
        if self.path.split("?", 1)[0] == "/homelab/triage":
            self._handle_triage()
            return
        prefix = "/homelab/api/incidents/"
        if self.path.startswith(prefix):
            iid = _safe_id(self.path[len(prefix) :].split("?", 1)[0].strip("/"))
            incident = _load_incident(iid)
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return
        self._json(404, {"error": "not found"})

    def _handle_triage(self) -> None:
        path, _, query = self.path.partition("?")
        if not _check_triage_auth(self.headers, query):
            self._json(401, {"error": "unauthorized"})
            return
        payload, err = self._read_json_body()
        if err == 413:
            self._json(413, {"error": "payload too large"})
            return
        if err == 400:
            self._json(400, {"error": "invalid json"})
            return
        incident_id = self._incident_id_from_request(payload)
        if not incident_id:
            self._json(400, {"error": "incident_id required"})
            return
        incident = _load_incident(incident_id)
        if incident is None:
            self._json(404, {"error": "incident not found", "id": incident_id})
            return
        status, resp_body = _forward_to_hermes(incident)
        try:
            detail = json.loads(resp_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = {"raw": resp_body.decode("utf-8", errors="replace")[:500]}
        if status >= 400:
            self._json(status if status != 502 else 502, {"error": "hermes webhook failed", "detail": detail})
            return
        if self.command == "GET":
            base = HERMES_PUBLIC_BASE_URL
            if not base:
                host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
                if host:
                    proto = self.headers.get("X-Forwarded-Proto", "https")
                    base = f"{proto}://{host.split(',')[0].strip()}"
            if base:
                location = f"{base}/?incident={incident_id}&autostart=1"
                self.send_response(302)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        self._json(200, {"ok": True, "incident_id": incident_id, "hermes": detail})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] == "/homelab/triage":
            self._handle_triage()
            return
        if self.path not in ("/hook", "/"):
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            self._json(413, {"error": "payload too large"})
            return
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "application/json")
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        if isinstance(payload, dict):
            _store_incidents(payload)
        status, resp_body = _proxy_to_ntfy(body, content_type)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)


def main() -> None:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"homelab-alert-bridge listening on :{HTTP_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
