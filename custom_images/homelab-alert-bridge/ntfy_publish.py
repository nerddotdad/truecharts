"""Publish incidents to ntfy — notifications always flow incident → ntfy."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from typing import Any

from message_format import incident_ntfy_body, incident_ntfy_priority, incident_ntfy_tags, incident_ntfy_title

NTFY_BASE_URL = os.environ.get(
    "NTFY_BASE_URL",
    "http://ntfy.observability.svc.cluster.local:10222",
).rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "homelab-alerts")
NTFY_PUBLIC_URL = os.environ.get("NTFY_PUBLIC_URL", "https://ntfy.example.com").rstrip("/")
HERMES_PUBLIC_BASE_URL = os.environ.get("HERMES_PUBLIC_BASE_URL", "").rstrip("/")
INCIDENTS_PUBLIC_BASE_URL = os.environ.get("INCIDENTS_PUBLIC_BASE_URL", "").rstrip("/")


def _ntfy_post_url(topic: str | None = None) -> str:
    return f"{NTFY_BASE_URL}/{topic or NTFY_TOPIC}"


def _headers_for_incident(incident: dict[str, Any], *, event: str, topic: str | None = None) -> dict[str, str]:
    incident_id = str(incident.get("id") or "").strip()

    click_url = f"{NTFY_PUBLIC_URL}/{topic or NTFY_TOPIC}"
    if INCIDENTS_PUBLIC_BASE_URL and incident_id:
        click_url = f"{INCIDENTS_PUBLIC_BASE_URL}/incidents/{incident_id}"

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "X-Title": incident_ntfy_title(incident, event=event),
        "X-Priority": incident_ntfy_priority(incident, event=event),
        "Markdown": "yes",
        "X-Click": click_url,
    }

    tags = incident_ntfy_tags(incident, event=event)
    if tags:
        headers["X-Tags"] = tags

    if incident_id:
        headers["X-Sequence-ID"] = incident_id

    actions: list[str] = []
    if INCIDENTS_PUBLIC_BASE_URL and incident_id:
        view = f"{INCIDENTS_PUBLIC_BASE_URL}/incidents/{incident_id}"
        actions.append(f"view, Open incident, {view}, clear=true")
    if incident_id:
        if INCIDENTS_PUBLIC_BASE_URL:
            investigate = f"{INCIDENTS_PUBLIC_BASE_URL.rstrip('/')}/incidents/{incident_id}/investigate"
            actions.append(f"view, Investigate, {investigate}, clear=true")
    if actions:
        headers["X-Actions"] = "; ".join(actions)

    return headers


def publish_incident(
    incident: dict[str, Any],
    *,
    event: str = "updated",
    topic: str | None = None,
) -> tuple[int, bytes]:
    """POST one incident notification to ntfy."""
    body = incident_ntfy_body(incident, event=event).encode("utf-8")
    req = urllib.request.Request(
        _ntfy_post_url(topic),
        data=body,
        method="POST",
        headers=_headers_for_incident(incident, event=event, topic=topic),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
