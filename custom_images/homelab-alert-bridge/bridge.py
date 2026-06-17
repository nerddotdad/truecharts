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
from filters import ignored_summary
from incidents import IncidentService, safe_id
from notifications import NotificationService
from ui import (
    PAGE_SIZE,
    alerts_list_page,
    create_incident_page,
    incident_detail_page,
    incident_list_page,
    login_page,
    render_alert_rows,
    render_incident_rows,
    settings_page,
)

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
NOTIFIER = NotificationService(STORE, INCIDENT_DIR / "notification_settings.json")


def _list_params(params: dict[str, list[str]]) -> tuple[int, int, str, str]:
    try:
        offset = max(0, int((params.get("offset") or ["0"])[0] or 0))
    except ValueError:
        offset = 0
    try:
        limit = min(100, max(1, int((params.get("limit") or [str(PAGE_SIZE)])[0] or PAGE_SIZE)))
    except ValueError:
        limit = PAGE_SIZE
    status_filter = (params.get("status") or [""])[0]
    search_query = (params.get("q") or [""])[0]
    return offset, limit, status_filter, search_query


def _incident_id_from_query(query: str) -> str:
    params = urllib.parse.parse_qs(query)
    for key in ("incident_id", "incident", "id"):
        values = params.get(key)
        if values and values[0]:
            return safe_id(str(values[0]))
    return ""


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
    events = SERVICE.ingest_alertmanager_payload(payload)
    if events:
        ids = ", ".join(sorted({iid for iid, _ in events}))
        sys.stderr.write(f"incidents touched: {ids}\n")
        NOTIFIER.notify_many(events)
    if not events:
        return 200, b'{"ok":true,"skipped":"ignored or empty alerts"}'
    return 200, json.dumps({"ok": True, "incidents": len(events)}).encode("utf-8")


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


def _read_form_multi(handler: BaseHTTPRequestHandler) -> dict[str, list[str]]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    return urllib.parse.parse_qs(raw)


def _alerts_redirect_url(*, status: str = "", message: str = "") -> str:
    params: list[str] = []
    if status:
        params.append(f"status={urllib.parse.quote(status)}")
    if message:
        params.append(f"msg={urllib.parse.quote(message)}")
    return "/alerts?" + "&".join(params) if params else "/alerts"


def _list_redirect_url(*, status: str = "", message: str = "") -> str:
    params: list[str] = []
    if status:
        params.append(f"status={urllib.parse.quote(status)}")
    if message:
        params.append(f"msg={urllib.parse.quote(message)}")
    return "/?" + "&".join(params) if params else "/"


class Handler(BaseHTTPRequestHandler):
    server_version = "homelab-alert-bridge/4.1"

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

    def _incident_id_from_request(self, payload: dict | None, query: str = "") -> str:
        if payload:
            for key in ("incident_id", "id", "fingerprint"):
                value = payload.get(key)
                if value:
                    return safe_id(str(value))
        if not query and "?" in self.path:
            query = self.path.split("?", 1)[1]
        return _incident_id_from_query(query)

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
            self._json(200, {"ok": True, "version": "4.1.0"})
            return

        if path == "/login":
            self._html(200, login_page())
            return

        if path == "/":
            if not self._require_ui_auth():
                return
            params = urllib.parse.parse_qs(query)
            status_filter = (params.get("status") or [""])[0]
            search_query = (params.get("q") or [""])[0]
            include_noise = bool(NOTIFIER.settings().get("show_noise"))
            flash_message = (params.get("msg") or [""])[0]
            self._html(
                200,
                incident_list_page(
                    status_filter=status_filter,
                    hermes_base=HERMES_PUBLIC_BASE_URL,
                    include_noise=include_noise,
                    hidden_summary=ignored_summary(),
                    flash_message=flash_message,
                    search_query=search_query,
                ),
            )
            return

        if path == "/settings":
            if not self._require_ui_auth():
                return
            params = urllib.parse.parse_qs(query)
            flash_message = (params.get("msg") or [""])[0]
            self._html(
                200,
                settings_page(
                    NOTIFIER.settings(),
                    SERVICE.raise_settings_dict(),
                    flash_message=flash_message,
                ),
            )
            return

        if path == "/alerts":
            if not self._require_ui_auth():
                return
            params = urllib.parse.parse_qs(query)
            status_filter = (params.get("status") or [""])[0]
            search_query = (params.get("q") or [""])[0]
            flash_message = (params.get("msg") or [""])[0]
            self._html(
                200,
                alerts_list_page(
                    status_filter=status_filter,
                    flash_message=flash_message,
                    search_query=search_query,
                ),
            )
            return

        if path == "/incidents/new":
            if not self._require_ui_auth():
                return
            self._html(200, create_incident_page())
            return

        if path.startswith("/incidents/") and path.endswith("/ask-ai"):
            iid = safe_id(path[len("/incidents/") : -len("/ask-ai")].strip("/"))
            incident = STORE.get_incident(iid)
            if incident is None:
                self._html(
                    404,
                    f"<!doctype html><html><body><h1>Incident not found</h1><p>{iid}</p></body></html>",
                )
                return
            base = HERMES_PUBLIC_BASE_URL
            if not base:
                host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
                if host:
                    proto = self.headers.get("X-Forwarded-Proto", "https")
                    base = f"{proto}://{host.split(',')[0].strip()}"
            if not base:
                self._json(503, {"error": "HERMES_PUBLIC_BASE_URL not configured"})
                return
            self._redirect(
                f"{base}/?incident={urllib.parse.quote(iid)}&autostart=1"
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

        if path == "/api/list/incidents":
            if not self._require_api_auth(query):
                return
            params = urllib.parse.parse_qs(query)
            offset, limit, status_filter, search_query = _list_params(params)
            include_noise = bool(NOTIFIER.settings().get("show_noise"))
            try:
                incidents, has_more, next_offset = SERVICE.list_for_dashboard(
                    status=status_filter or None,
                    include_noise=include_noise,
                    query=search_query,
                    offset=offset,
                    limit=limit,
                )
            except ValueError as exc:
                self._json(
                    400,
                    {"error": str(exc), "html": "", "has_more": False, "next_offset": offset},
                )
                return
            self._json(
                200,
                {
                    "html": render_incident_rows(incidents),
                    "has_more": has_more,
                    "next_offset": next_offset,
                },
            )
            return

        if path == "/api/list/alerts":
            if not self._require_api_auth(query):
                return
            params = urllib.parse.parse_qs(query)
            offset, limit, status_filter, search_query = _list_params(params)
            try:
                alerts, has_more, next_offset = SERVICE.list_inbox(
                    status=status_filter or None,
                    query=search_query,
                    offset=offset,
                    limit=limit,
                )
            except ValueError as exc:
                self._json(
                    400,
                    {"error": str(exc), "html": "", "has_more": False, "next_offset": offset},
                )
                return
            self._json(
                200,
                {
                    "html": render_alert_rows(alerts),
                    "has_more": has_more,
                    "next_offset": next_offset,
                },
            )
            return

        if path == "/api/incidents":
            if not self._require_api_auth(query):
                return
            params = urllib.parse.parse_qs(query)
            offset, limit, status_filter, search_query = _list_params(params)
            include_noise = bool(NOTIFIER.settings().get("show_noise"))
            try:
                incidents, has_more, next_offset = SERVICE.list_for_dashboard(
                    status=status_filter or None,
                    include_noise=include_noise,
                    query=search_query,
                    offset=offset,
                    limit=limit,
                )
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(
                200,
                {
                    "incidents": incidents,
                    "has_more": has_more,
                    "next_offset": next_offset,
                    "hidden_alertnames": ignored_summary(),
                },
            )
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

        if path == "/incidents/bulk":
            if not self._require_ui_auth():
                return
            form = _read_form_multi(self)
            action = (form.get("action") or [""])[0]
            incident_ids = form.get("incident_id", [])
            return_status = (form.get("return_status") or [""])[0]
            result = SERVICE.bulk_apply(action, incident_ids, actor="ui")
            if result.get("error"):
                self._redirect(
                    _list_redirect_url(
                        status=return_status,
                        message=result["error"],
                    )
                )
                return
            NOTIFIER.notify_many(result.get("notify") or [])
            if action == "merge" and result.get("target_id"):
                self._redirect(f"/incidents/{result['target_id']}")
                return
            self._redirect(
                _list_redirect_url(
                    status=return_status,
                    message=str(result.get("message") or "Done"),
                )
            )
            return

        if path == "/incidents/new":
            if not self._require_ui_auth():
                return
            form = _read_form(self)
            tags = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
            incident = SERVICE.create_manual(
                title=form.get("title", ""),
                summary=form.get("summary") or None,
                severity=form.get("severity") or "warning",
                tags=tags,
                note=form.get("note") or None,
                actor="ui",
            )
            if incident is None:
                self._html(400, create_incident_page(error="Title is required"))
                return
            NOTIFIER.notify(incident["id"], "manual")
            self._redirect(f"/incidents/{incident['id']}")
            return

        if path == "/settings":
            if not self._require_ui_auth():
                return
            form = _read_form(self)
            events = {
                key: form.get(f"event_{key}") == "on"
                for key in ("created", "updated", "resolved", "reopened", "manual", "acknowledged", "merged")
            }
            NOTIFIER.save_settings(
                {
                    "enabled": form.get("enabled") == "on",
                    "topic": form.get("topic", ""),
                    "events": events,
                }
            )
            self._redirect("/settings?msg=Notification+settings+saved")
            return

        if path == "/settings/display":
            if not self._require_ui_auth():
                return
            form = _read_form(self)
            NOTIFIER.save_settings({"show_noise": form.get("show_noise") == "on"})
            self._redirect("/settings?msg=Display+settings+saved")
            return

        if path == "/settings/raise":
            if not self._require_ui_auth():
                return
            form = _read_form(self)
            SERVICE.save_raise_settings(
                {
                    "enabled": form.get("raise_enabled") == "on",
                    "group_open": form.get("group_open") == "on",
                    "min_severity": form.get("min_severity", "critical"),
                    "alertnames": form.get("alertnames", ""),
                    "label_rules": form.get("label_rules", ""),
                }
            )
            self._redirect("/settings?msg=Auto-raise+settings+saved")
            return

        if path == "/alerts/raise":
            if not self._require_ui_auth():
                return
            form = _read_form_multi(self)
            fingerprints = form.get("fingerprint", [])
            title = (form.get("title") or [""])[0].strip() or None
            return_status = (form.get("return_status") or [""])[0]
            incident, kind = SERVICE.raise_from_alerts(
                fingerprints,
                title=title,
                actor="ui",
                group_open=False,
            )
            if incident is None:
                self._redirect(_alerts_redirect_url(status=return_status, message="Could not raise incident"))
                return
            if kind == "already_raised":
                self._redirect(
                    _alerts_redirect_url(
                        status=return_status,
                        message=f"Alert already on incident {incident['id']}",
                    )
                )
                return
            NOTIFIER.notify(incident["id"], "created" if kind == "created" else "updated")
            self._redirect(f"/incidents/{incident['id']}")
            return

        if path.startswith("/alerts/") and path.endswith("/raise"):
            if not self._require_ui_auth():
                return
            fp = safe_id(path[len("/alerts/") : -6].strip("/"))
            incident, kind = SERVICE.raise_from_alerts([fp], actor="ui", group_open=False)
            if incident is None:
                self._redirect(_alerts_redirect_url(message="Could not raise incident"))
                return
            if kind == "already_raised":
                self._redirect(f"/incidents/{incident['id']}")
                return
            NOTIFIER.notify(incident["id"], "created" if kind == "created" else "updated")
            self._redirect(f"/incidents/{incident['id']}")
            return

        if path.startswith("/incidents/") and path.endswith("/ack"):
            if not self._require_ui_auth():
                return
            iid = safe_id(path[len("/incidents/") : -4].strip("/"))
            incident = SERVICE.acknowledge(iid, actor="ui")
            if incident is None:
                self._html(404, login_page("Incident not found"))
                return
            NOTIFIER.notify(iid, "acknowledged")
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
            NOTIFIER.notify(iid, "resolved")
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
            NOTIFIER.notify(iid, "reopened")
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
            NOTIFIER.notify(iid, "merged")
            self._redirect(f"/incidents/{iid}")
            return

        if path == "/api/incidents/bulk":
            if not self._require_api_auth(query):
                return
            payload, err = self._read_json_body()
            if err:
                self._json(err, {"error": "invalid request"})
                return
            action = str(payload.get("action") or "")
            raw_ids = payload.get("incident_ids") or payload.get("ids") or []
            if not isinstance(raw_ids, list):
                raw_ids = []
            result = SERVICE.bulk_apply(action, [str(x) for x in raw_ids], actor="api")
            NOTIFIER.notify_many(result.get("notify") or [])
            status = 400 if result.get("error") else 200
            self._json(status, result)
            return

        if path == "/api/incidents":
            if not self._require_api_auth(query):
                return
            payload, err = self._read_json_body()
            if err:
                self._json(err, {"error": "invalid request"})
                return
            tags = payload.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            incident = SERVICE.create_manual(
                title=str(payload.get("title") or ""),
                summary=payload.get("summary"),
                severity=str(payload.get("severity") or "warning"),
                tags=[str(t) for t in tags] if isinstance(tags, list) else None,
                note=payload.get("note"),
                actor="api",
            )
            if incident is None:
                self._json(400, {"error": "title required"})
                return
            NOTIFIER.notify(incident["id"], "manual")
            self._json(201, incident)
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
            incident_id = self._incident_id_from_request(payload, query)
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
        incident_id = _incident_id_from_query(query)
        if not incident_id:
            payload, err = self._read_json_body()
            if err == 413:
                self._json(413, {"error": "payload too large"})
                return
            if err == 400:
                self._json(400, {"error": "invalid json"})
                return
            incident_id = self._incident_id_from_request(payload, query)
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
    fixed = SERVICE.reconcile_resolved_incidents()
    if fixed:
        print(f"reconciled {fixed} stale open incident(s) (all alerts already resolved)", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"homelab-alert-bridge 3.0 listening on :{HTTP_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
