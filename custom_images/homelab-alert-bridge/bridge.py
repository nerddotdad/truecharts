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
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

INCIDENT_DIR = Path(os.environ.get("INCIDENT_DIR", "/data/incidents"))
GROUP_STATE_DIR = INCIDENT_DIR / "_groups"
PENDING_ID_FILE = INCIDENT_DIR / ".pending_incident"
NTFY_BRIDGE_URL = os.environ.get(
    "NTFY_BRIDGE_URL",
    "http://alertmanager-ntfy.observability.svc.cluster.local:8000/hook",
)
NTFY_BASE_URL = os.environ.get(
    "NTFY_BASE_URL",
    "http://ntfy.observability.svc.cluster.local:10222",
).rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "homelab-alerts")
PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL",
    "http://kube-prometheus-stack-prometheus.kube-prometheus-stack.svc.cluster.local:9090",
).rstrip("/")
GRAFANA_PUBLIC_URL = os.environ.get("GRAFANA_PUBLIC_URL", "").rstrip("/")
NTFY_CLICK_URL = os.environ.get("NTFY_CLICK_URL", "").rstrip("/")
JELLYFIN_DASHBOARD_URL = os.environ.get("JELLYFIN_DASHBOARD_URL", "").rstrip("/")
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


def _prometheus_query(expr: str) -> list[dict]:
    url = (
        f"{PROMETHEUS_URL}/api/v1/query?"
        + urllib.parse.urlencode({"query": expr})
    )
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"prometheus query failed: {exc}\n")
        return []
    if payload.get("status") != "success":
        return []
    return payload.get("data", {}).get("result") or []


def _ntfy_publish(body: str, headers: dict[str, str]) -> tuple[int, str | None, str]:
    url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return exc.code, None, detail
    except urllib.error.URLError as exc:
        return 502, None, str(exc.reason)
    message_id = None
    try:
        message_id = json.loads(raw).get("id")
    except json.JSONDecodeError:
        pass
    return 200, message_id, raw


def _ntfy_update(message_id: str, body: str, headers: dict[str, str]) -> tuple[int, str]:
    url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}/{urllib.parse.quote(message_id, safe='')}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return 502, str(exc.reason)


def _group_state_path(group_id: str) -> Path:
    GROUP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return GROUP_STATE_DIR / f"{_safe_id(group_id)}.json"


def _load_group_state(group_id: str) -> dict:
    path = _group_state_path(group_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_group_state(group_id: str, state: dict) -> None:
    path = _group_state_path(group_id)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _format_user_list(users: list[str]) -> str:
    if not users:
        return "(none)"
    return ", ".join(users)


def _jellyfin_locked_users(namespace: str, payload: dict) -> list[str]:
    expr = f'jellyfin_user_account{{namespace="{namespace}", admin="0"}} == 0'
    users: list[str] = []
    for sample in _prometheus_query(expr):
        metric = sample.get("metric") or {}
        username = str(metric.get("username") or "").strip()
        if username:
            users.append(username)
    if users:
        return sorted(set(users))
    # Fallback when Prometheus is briefly stale.
    for alert in payload.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") or {}
        if labels.get("alertname") != "jellyfin_user_locked":
            continue
        if labels.get("namespace") != namespace:
            continue
        if alert.get("status") != "firing":
            continue
        username = str(labels.get("username") or "").strip()
        if username:
            users.append(username)
    return sorted(set(users))


def _jellyfin_markdown_links(namespace: str) -> str:
    runbook = "https://runbooks.prometheus-operator.dev/"
    grafana_alert = (
        f"{GRAFANA_PUBLIC_URL}/alerting/list?search=jellyfin_user_locked"
        if GRAFANA_PUBLIC_URL
        else "https://runbooks.prometheus-operator.dev/"
    )
    dashboard = JELLYFIN_DASHBOARD_URL or (
        f"{GRAFANA_PUBLIC_URL}/d/603679cbda70a9fe/jellyfin"
        if GRAFANA_PUBLIC_URL
        else ""
    )
    links = f"[Runbook]({runbook})"
    if dashboard:
        links += f" · [Dashboard]({dashboard})"
    links += f" · [Alert in Grafana]({grafana_alert})"
    return links


def _jellyfin_ntfy_headers(
    *,
    title: str,
    group_incident_id: str,
    resolved: bool,
) -> dict[str, str]:
    hermes = f"{HERMES_PUBLIC_BASE_URL}/?incident={group_incident_id}&autostart=1"
    headers = {
        "Title": title,
        "Markdown": "yes",
        "Priority": "3" if resolved else "4",
        "Tags": "white_check_mark" if resolved else "warning,rotating_light",
        "X-Actions": f"view, Ask AI, {hermes}, clear=true",
    }
    if NTFY_CLICK_URL:
        headers["X-Click"] = NTFY_CLICK_URL
    return headers


def _store_group_incident(
    group_incident_id: str,
    *,
    status: str,
    namespace: str,
    users: list[str],
    body: str,
    receiver: str | None,
) -> None:
    summary = (
        f"Jellyfin: {len(users)} user(s) locked in {namespace}"
        if users
        else f"Resolved: Jellyfin user lockouts in {namespace}"
    )
    incident = {
        "id": group_incident_id,
        "status": status,
        "receiver": receiver,
        "alert": {
            "status": status,
            "labels": {
                "alertname": "jellyfin_user_locked",
                "namespace": namespace,
                "severity": "warning",
                "homelab_team": "media",
            },
            "annotations": {
                "summary": summary,
                "description": body,
                "dashboard_url": JELLYFIN_DASHBOARD_URL or None,
            },
            "fingerprint": group_incident_id,
        },
    }
    path = INCIDENT_DIR / f"{group_incident_id}.json"
    path.write_text(json.dumps(incident, indent=2), encoding="utf-8")


def _sync_jellyfin_user_locked_group(namespace: str, payload: dict) -> tuple[str, int | None]:
    group_id = f"jellyfin_user_locked/{namespace}"
    group_incident_id = _safe_id(f"group-jellyfin_user_locked-{namespace}")
    state = _load_group_state(group_id)
    users = _jellyfin_locked_users(namespace, payload)
    receiver = payload.get("receiver")

    if users:
        user_line = f"Locked users: {_format_user_list(users)}"
        active_episode = (
            state.get("phase") == "active" and bool(state.get("ntfy_message_id"))
        )
        if not active_episode:
            body = user_line
            phase = "new"
        elif state.get("last_users") == users:
            return "unchanged", None
        else:
            body = f"{state['body']}\n\n— Update —\n{user_line}"
            phase = "updated"
        title = f"Jellyfin: {len(users)} user(s) locked in {namespace}"
        body_with_links = f"{body}\n\n---\n\n**Links:** {_jellyfin_markdown_links(namespace)}"
        headers = _jellyfin_ntfy_headers(
            title=f"🔥 {title}",
            group_incident_id=group_incident_id,
            resolved=False,
        )
        if phase == "new":
            status, message_id, detail = _ntfy_publish(body_with_links, headers)
            if status >= 400 or not message_id:
                sys.stderr.write(f"ntfy publish failed ({status}): {detail}\n")
                return "error", status or 502
        else:
            message_id = state["ntfy_message_id"]
            status, detail = _ntfy_update(message_id, body_with_links, headers)
            if status >= 400:
                sys.stderr.write(f"ntfy update failed ({status}): {detail}\n")
                return "error", status
        _save_group_state(
            group_id,
            {
                "group_id": group_id,
                "group_incident_id": group_incident_id,
                "namespace": namespace,
                "alertname": "jellyfin_user_locked",
                "ntfy_message_id": message_id,
                "body": body,
                "last_users": users,
                "phase": "active",
            },
        )
        _store_group_incident(
            group_incident_id,
            status="firing",
            namespace=namespace,
            users=users,
            body=body_with_links,
            receiver=receiver,
        )
        return phase, 200

    if state.get("phase") != "active" or not state.get("ntfy_message_id"):
        return "unchanged", None

    body = f"{state.get('body', '')}\n\n— Resolved —\nAll Jellyfin user lockouts cleared."
    body_with_links = f"{body}\n\n---\n\n**Links:** {_jellyfin_markdown_links(namespace)}"
    headers = _jellyfin_ntfy_headers(
        title=f"✅ Resolved: Jellyfin user lockouts ({namespace})",
        group_incident_id=group_incident_id,
        resolved=True,
    )
    status, detail = _ntfy_update(state["ntfy_message_id"], body_with_links, headers)
    if status >= 400:
        sys.stderr.write(f"ntfy resolve update failed ({status}): {detail}\n")
        return "error", status
    _save_group_state(
        group_id,
        {
            "group_id": group_id,
            "group_incident_id": group_incident_id,
            "namespace": namespace,
            "alertname": "jellyfin_user_locked",
            "ntfy_message_id": state["ntfy_message_id"],
            "body": body,
            "last_users": [],
            "phase": "resolved",
        },
    )
    _store_group_incident(
        group_incident_id,
        status="resolved",
        namespace=namespace,
        users=[],
        body=body_with_links,
        receiver=receiver,
    )
    return "resolved", 200


GROUPED_ALERT_HANDLERS: dict[str, Callable[[str, dict], tuple[str, int | None]]] = {
    "jellyfin_user_locked": _sync_jellyfin_user_locked_group,
}


def _process_grouped_alerts(payload: dict) -> tuple[set[str], int | None]:
    alerts = payload.get("alerts") or []
    namespaces_by_alert: dict[str, set[str]] = {}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") or {}
        alertname = labels.get("alertname")
        namespace = labels.get("namespace")
        if alertname in GROUPED_ALERT_HANDLERS and namespace:
            namespaces_by_alert.setdefault(alertname, set()).add(namespace)

    handled: set[str] = set()
    worst_status: int | None = None
    for alertname, namespaces in namespaces_by_alert.items():
        handler = GROUPED_ALERT_HANDLERS[alertname]
        handled.add(alertname)
        for namespace in sorted(namespaces):
            phase, status = handler(namespace, payload)
            sys.stderr.write(
                f"grouped alert {alertname}/{namespace}: phase={phase} status={status}\n"
            )
            if status and (worst_status is None or status >= worst_status):
                worst_status = status
    return handled, worst_status


def _handle_alertmanager_hook(payload: dict) -> tuple[int, bytes]:
    _store_incidents(payload)
    handled_names, grouped_status = _process_grouped_alerts(payload)

    remaining = [
        alert
        for alert in (payload.get("alerts") or [])
        if isinstance(alert, dict)
        and (alert.get("labels") or {}).get("alertname") not in handled_names
    ]
    if not remaining:
        body = json.dumps(
            {"ok": True, "grouped": sorted(handled_names), "proxied": False}
        ).encode("utf-8")
        status = grouped_status if grouped_status and grouped_status >= 400 else 200
        return status, body

    filtered = dict(payload)
    filtered["alerts"] = remaining
    proxy_body = json.dumps(filtered).encode("utf-8")
    status, resp_body = _proxy_to_ntfy(proxy_body, "application/json")
    if grouped_status and grouped_status >= 400 and status < 400:
        return grouped_status, json.dumps(
            {"ok": False, "grouped_error": grouped_status, "proxy": resp_body.decode("utf-8", errors="replace")[:500]}
        ).encode("utf-8")
    return status, resp_body


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
    for part in query.split("&"):
        if part.startswith("token=") and part[6:] == TRIAGE_AUTH_TOKEN:
            return True
    return False


def _load_incident(incident_id: str) -> dict | None:
    path = INCIDENT_DIR / f"{incident_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _set_pending_incident(incident_id: str) -> bool:
    if not _load_incident(incident_id):
        return False
    PENDING_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_ID_FILE.write_text(incident_id, encoding="utf-8")
    return True


def _take_pending_incident() -> str:
    if not PENDING_ID_FILE.is_file():
        return ""
    iid = PENDING_ID_FILE.read_text(encoding="utf-8").strip()
    try:
        PENDING_ID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return iid


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
    server_version = "homelab-alert-bridge/1.2"

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
        if self.path.split("?", 1)[0] == "/homelab/api/pending-incident":
            iid = _take_pending_incident()
            self._json(200, {"incident_id": iid})
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
        if self.path.split("?", 1)[0] == "/homelab/api/pending-incident":
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
            if not _set_pending_incident(incident_id):
                self._json(404, {"error": "incident not found", "id": incident_id})
                return
            self._json(200, {"ok": True, "incident_id": incident_id})
            return
        if self.path not in ("/hook", "/"):
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
        status, resp_body = _handle_alertmanager_hook(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)


def main() -> None:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    GROUP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"homelab-alert-bridge listening on :{HTTP_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
