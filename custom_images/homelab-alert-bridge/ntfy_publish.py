"""Publish Alertmanager alerts to ntfy (replaces alertmanager-ntfy to avoid label spam)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request

from message_format import ntfy_body, ntfy_priority, ntfy_tags_header, ntfy_title

NTFY_BASE_URL = os.environ.get(
    "NTFY_BASE_URL",
    "http://ntfy.observability.svc.cluster.local:10222",
).rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "homelab-alerts")
NTFY_PUBLIC_URL = os.environ.get("NTFY_PUBLIC_URL", "https://ntfy.example.com").rstrip("/")
HERMES_PUBLIC_BASE_URL = os.environ.get("HERMES_PUBLIC_BASE_URL", "").rstrip("/")
INCIDENTS_PUBLIC_BASE_URL = os.environ.get("INCIDENTS_PUBLIC_BASE_URL", "").rstrip("/")


def _ntfy_post_url() -> str:
    return f"{NTFY_BASE_URL}/{NTFY_TOPIC}"


def _headers_for_alert(alert: dict) -> dict[str, str]:
    labels = alert.get("labels") or {}
    fingerprint = str(alert.get("fingerprint") or "").strip()
    incident_id = str(alert.get("_incident_id") or "").strip()
    incident = incident_id or fingerprint or f"{labels.get('alertname', 'alert')}-{labels.get('namespace', 'ns')}"

    click_url = f"{NTFY_PUBLIC_URL}/{NTFY_TOPIC}"
    if INCIDENTS_PUBLIC_BASE_URL and incident_id:
        click_url = f"{INCIDENTS_PUBLIC_BASE_URL}/incidents/{incident_id}"

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "X-Title": ntfy_title(alert),
        "X-Priority": ntfy_priority(alert),
        "Markdown": "yes",
        "X-Click": click_url,
    }

    tags = ntfy_tags_header(alert)
    if tags:
        headers["X-Tags"] = tags

    if fingerprint:
        headers["X-Sequence-ID"] = fingerprint

    actions: list[str] = []
    if INCIDENTS_PUBLIC_BASE_URL and incident_id:
        view = f"{INCIDENTS_PUBLIC_BASE_URL}/incidents/{incident_id}"
        actions.append(f"view, Open incident, {view}, clear=true")
    if HERMES_PUBLIC_BASE_URL:
        hermes = f"{HERMES_PUBLIC_BASE_URL}/?incident={incident}&autostart=1"
        actions.append(f"view, Ask AI, {hermes}, clear=true")
    if actions:
        headers["X-Actions"] = "; ".join(actions)

    return headers


def publish_alert(alert: dict) -> tuple[int, bytes]:
    """POST one alert to ntfy. Returns HTTP status and response body."""
    body = ntfy_body(alert).encode("utf-8")
    req = urllib.request.Request(
        _ntfy_post_url(),
        data=body,
        method="POST",
        headers=_headers_for_alert(alert),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def publish_alerts(payload: dict) -> tuple[int, bytes]:
    """Publish each alert in the webhook payload; all must succeed."""
    alerts = payload.get("alerts") or []
    if not alerts:
        return 200, b"{}"

    last_status = 200
    last_body = b"{}"
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        status, body = publish_alert(alert)
        last_status, last_body = status, body
        if status >= 400:
            return status, body
    return last_status, last_body
