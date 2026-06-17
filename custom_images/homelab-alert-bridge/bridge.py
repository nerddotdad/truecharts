#!/usr/bin/env python3
"""Homelab incident funnel: ingest alerts, organize, merge, enrich, notify."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from db import IncidentStore
from incidents import IncidentService, fingerprint, safe_id
from ntfy_publish import publish_alerts
from ui import incident_detail_page, incident_list_page, login_page

INCIDENT_DIR = Path(os.environ.get("INCIDENT_DIR", "/data/incidents"))
DB_PATH = Path(os.environ.get("INCIDENT_DB", str(INCIDENT_DIR / "incidents.db")))
PENDING_ID_FILE = INCIDENT_DIR / ".pending_incident"
HERMES_WEBHOOK_URL = os.environ.get(
    "HERMES_WEBHOOK_URL",
    "http://hermes-oncall-app-template.ai.svc.cluster.local:8644/webhooks/homelab-alerts",
)
HERMES_WEBHOOK_SECRET = os.environ.get("HERMES_WEBHOOK_SECRET", "")
TRIAGE_AUTH_TOKEN = os.environ.get("TRIAGE_AUTH_TOKEN", "")
INCIDENTS_AUTH_TOKEN = os.environ.get("INCIDENTS_AUTH_TOKEN", TRIAGE_AUTH_TOKEN)
HERMES_PUBLIC_BASE_URL = os.environ.get("HERMES_PUBLIC_BASE_URL", "").rstrip("/")
INCIDENTS_PUBLIC_BASE_URL = os.environ.get("INCIDENTS_PUBLIC_BASE_URL", "").rstrip("/")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8000"))
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", str(2 * 1024 * 1024)))
SESSION_COOKIE = "incidents_session"

STORE = IncidentStore(DB_PATH)
SERVICE = IncidentService(STORE, INCIDENT_DIR)


def _summarize_hook_payload(payload: dict) -> str:
    alerts = payload.get("alerts") or []
    parts: list[str] = []
    for alert in alerts[:12]:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") or {}
        parts.append(
            f"{alert.get('status', '?')}:{labels.get('alertname', '?')}@{labels.get('namespace', '?')}"
        )
    suffix = f" (+{len(alerts) - 12} more)" if len(alerts) > 12 else ""
    return f"status={payload.get('status')} count={len(alerts)} [{', '.join(parts)}{suffix}]"


def _handle_alertmanager_hook(payload: dict) -> tuple[int, bytes]:
    sys.stderr.write(f"hook received: {_summarize_hook_payload(payload)}\n")
    incident_ids = SERVICE.ingest_alertmanager_payload(payload)
    if incident_ids:
        sys.stderr.write(f"incidents touched: {', '.join(incident_ids)}\n")

    enriched_payload = dict(payload)
    enriched_alerts = []
    for alert in payload.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        copy = dict(alert)
        fp = fingerprint(alert)
        incident = STORE.get_incident_by_fingerprint(fp)
        if incident:
            copy["_incident_id"] = incident["id"]
        enriched_alerts.append(copy)
    enriched_payload["alerts"] = enriched_alerts

    status, resp_body = publish_alerts(enriched_payload)
    if status >= 400:
        sys.stderr.write(f"ntfy publish failed ({status}): {resp_body[:500]!r}\n")
    return status, resp_body


def _sign_webhook(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _check_auth_token(headers, query: str = "") -> bool:
    if not INCIDENTS_AUTH_TOKEN:
        return False
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:].strip() == INCIDENTS_AUTH_TOKEN:
        return True
    if headers.get("X-Homelab-Triage-Token") == INCIDENTS_AUTH_TOKEN:
        return True
    for part in query.split("&"):
        if part.startswith("token=") and part[6:] == INCIDENTS_AUTH_TOKEN:
            return True
    return False


def _parse_cookie(header_value: str) -> dict[str, str]:
    jar = cookies.SimpleCookie()
    jar.load(header_value)
    return {key: morsel.value for key, morsel in jar.items()}


def _has_ui_session(headers) -> bool:
    if not INCIDENTS_AUTH_TOKEN:
        return True
    raw = headers.get("Cookie", "")
    if not raw:
        return False
    return _parse_cookie(raw).get(SESSION_COOKIE) == INCIDENTS_AUTH_TOKEN


def _set_session_cookie(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header(
        "Set-Cookie",
        f"{SESSION_COOKIE}={INCIDENTS_AUTH_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800",
    )


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
        return 502, json.dumps(
            {"error": "hermes webhook unreachable", "detail": str(exc.reason)}
        ).encode("utf-8")


def _read_form(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}


class Handler(BaseHTTPRequestHandler):
    server_version = "homelab-alert-bridge/3.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, content: str) -> None:
        self._send_bytes(status, content.encode("utf-8"), "text/html; charset=utf-8")

    def _json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _redirect(self, location: str, *, set_session: bool = False) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if set_session:
            _set_session_cookie(self)
        self.send_header("Content-Length", "0")
        self.end_headers()

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
                    return safe_id(str(value))
        query = self.path.split("?", 1)
        if len(query) == 2:
            for part in query[1].split("&"):
                if part.startswith("incident_id="):
                    return safe_id(urllib.parse.unquote(part.split("=", 1)[1]))
        return ""

    def _require_ui_auth(self) -> bool:
        if _has_ui_session(self.headers):
            return True
        self._html(200, login_page())
        return False

    def _require_api_auth(self, query: str = "") -> bool:
        if _check_auth_token(self.headers, query) or _has_ui_session(self.headers):
            return True
        self._json(401, {"error": "unauthorized"})
        return False

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")

        if path in ("/health", "/healthz"):
            self._json(200, {"ok": True, "version": "3.0"})
            return

        if path == "/login":
            self._html(200, login_page())
            return

        if path == "/":
            if not self._require_ui_auth():
                return
            params = urllib.parse.parse_qs(query)
            status_filter = (params.get("status") or [""])[0]
            incidents = STORE.list_incidents(status=status_filter or None)
            self._html(
                200,
                incident_list_page(incidents, status_filter=status_filter, hermes_base=HERMES_PUBLIC_BASE_URL),
            )
            return

        if path.startswith("/incidents/"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") :].strip("/"))
            incident = STORE.get_incident(iid)
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._html(
                200,
                incident_detail_page(incident, hermes_base=HERMES_PUBLIC_BASE_URL),
            )
            return

        if path == "/homelab/triage":
            self._handle_triage()
            return

        if path.startswith("/homelab/api/incidents/"):
            iid = safe_id(path[len("/homelab/api/incidents/") :].split("?", 1)[0].strip("/"))
            incident = SERVICE.export_legacy(iid)
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return

        if path.startswith("/api/incidents/"):
            iid = safe_id(path[len("/api/incidents/") :].split("?", 1)[0].strip("/"))
            incident = STORE.get_incident(iid)
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return

        if path == "/api/incidents":
            params = urllib.parse.parse_qs(query)
            status_filter = (params.get("status") or [None])[0]
            incidents = STORE.list_incidents(status=status_filter)
            self._json(200, {"incidents": incidents})
            return

        if path == "/homelab/api/pending-incident":
            iid = self._take_pending_incident()
            self._json(200, {"incident_id": iid})
            return

        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path, _, query = self.path.partition("?")

        if path == "/login":
            form = _read_form(self)
            if form.get("token") == INCIDENTS_AUTH_TOKEN:
                self._redirect("/", set_session=True)
            else:
                self._html(401, login_page("Invalid token"))
            return

        if path.startswith("/incidents/") and path.endswith("/ack"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -4].strip("/"))
            incident = SERVICE.acknowledge(iid, actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path.startswith("/incidents/") and path.endswith("/resolve"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -8].strip("/"))
            incident = SERVICE.resolve(iid, actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path.startswith("/incidents/") and path.endswith("/reopen"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -7].strip("/"))
            incident = SERVICE.reopen(iid, actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path.startswith("/incidents/") and path.endswith("/notes"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -6].strip("/"))
            form = _read_form(self)
            incident = SERVICE.add_note(iid, form.get("body", ""), actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path.startswith("/incidents/") and path.endswith("/enrich"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -7].strip("/"))
            form = _read_form(self)
            tags = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
            incident = SERVICE.enrich(
                iid,
                title=form.get("title") or None,
                summary=form.get("summary") or None,
                severity=form.get("severity") or None,
                tags=tags,
                actor="ui",
            )
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path.startswith("/incidents/") and path.endswith("/merge"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -6].strip("/"))
            form = _read_form(self)
            source_ids = [safe_id(part) for part in re.split(r"[\s,]+", form.get("source_ids", "")) if part.strip()]
            incident = SERVICE.merge(iid, source_ids, actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            self._redirect(f"/incidents/{iid}")
            return

        if path == "/api/incidents/merge":
            if not self._require_api_auth(query):
                return
            payload, err = self._read_json_body()
            if err:
                self._json(err, {"error": "invalid request"})
                return
            target_id = safe_id(str(payload.get("target_id") or payload.get("into") or ""))
            source_ids = [safe_id(str(x)) for x in (payload.get("source_ids") or payload.get("sources") or [])]
            incident = SERVICE.merge(target_id, source_ids, actor="api")
            if incident is None:
                self._json(404, {"error": "incident not found", "id": target_id})
                return
            self._json(200, incident)
            return

        if path.startswith("/api/incidents/") and path.endswith("/ack"):
            if not self._require_api_auth(query):
                return
            iid = safe_id(path[len("/api/incidents/") : -4].strip("/"))
            incident = SERVICE.acknowledge(iid, actor="api")
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return

        if path.startswith("/api/incidents/") and path.endswith("/resolve"):
            if not self._require_api_auth(query):
                return
            iid = safe_id(path[len("/api/incidents/") : -8].strip("/"))
            incident = SERVICE.resolve(iid, actor="api")
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return

        if path.startswith("/api/incidents/") and path.endswith("/notes"):
            if not self._require_api_auth(query):
                return
            iid = safe_id(path[len("/api/incidents/") : -6].strip("/"))
            payload, err = self._read_json_body()
            if err:
                self._json(err, {"error": "invalid request"})
                return
            incident = SERVICE.add_note(iid, str(payload.get("body") or ""), actor="api")
            if incident is None:
                self._json(404, {"error": "incident not found", "id": iid})
                return
            self._json(200, incident)
            return

        if path == "/homelab/triage":
            self._handle_triage()
            return

        if path == "/homelab/api/pending-incident":
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
            if STORE.get_incident(incident_id) is None:
                self._json(404, {"error": "incident not found", "id": incident_id})
                return
            PENDING_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PENDING_ID_FILE.write_text(incident_id, encoding="utf-8")
            self._json(200, {"ok": True, "incident_id": incident_id})
            return

        if path not in ("/hook", "/"):
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            self._json(413, {"error": "payload too large"})
            return
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "invalid payload"})
            return
        try:
            status, resp_body = _handle_alertmanager_hook(payload)
        except Exception as exc:
            sys.stderr.write(f"hook handler error: {exc}\n")
            self._json(500, {"error": "hook handler failed", "detail": str(exc)})
            return
        self._send_bytes(status, resp_body, "application/json")

    def _handle_triage(self) -> None:
        _, _, query = self.path.partition("?")
        if not _check_auth_token(self.headers, query):
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
        incident = SERVICE.export_legacy(incident_id)
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
                self._redirect(f"{base}/?incident={incident_id}&autostart=1")
                return
        self._json(200, {"ok": True, "incident_id": incident_id, "hermes": detail})

    def _take_pending_incident(self) -> str:
        if not PENDING_ID_FILE.is_file():
            return ""
        iid = PENDING_ID_FILE.read_text(encoding="utf-8").strip()
        try:
            PENDING_ID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return iid


def main() -> None:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    imported = SERVICE.migrate_legacy_json()
    if imported:
        print(f"migrated {imported} legacy incident file(s)", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"homelab-alert-bridge 3.0 listening on :{HTTP_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
