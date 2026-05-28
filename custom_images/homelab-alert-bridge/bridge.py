#!/usr/bin/env python3
"""Store Alertmanager payloads and proxy to alertmanager-ntfy."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INCIDENT_DIR = Path(os.environ.get("INCIDENT_DIR", "/data/incidents"))
NTFY_BRIDGE_URL = os.environ.get(
    "NTFY_BRIDGE_URL",
    "http://alertmanager-ntfy.observability.svc.cluster.local:8000/hook",
)
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8000"))
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", str(2 * 1024 * 1024)))
INCIDENT_TTL_DAYS = int(os.environ.get("INCIDENT_TTL_DAYS", "14"))


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


class Handler(BaseHTTPRequestHandler):
    server_version = "homelab-alert-bridge/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/health", "/healthz"):
            self._json(200, {"ok": True})
            return
        prefix = "/homelab/api/incidents/"
        if self.path.startswith(prefix):
            iid = _safe_id(self.path[len(prefix) :].strip("/"))
            path = INCIDENT_DIR / f"{iid}.json"
            if not path.is_file():
                self._json(404, {"error": "incident not found", "id": iid})
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            self._json(200, data)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
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
