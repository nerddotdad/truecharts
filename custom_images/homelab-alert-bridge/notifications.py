"""Incident-centric ntfy notifications (incident → ntfy)."""

from __future__ import annotations

import sys
from typing import Any

from ntfy_publish import publish_incident as _publish_incident
from settings import SettingsStore


class NotificationService:
    def __init__(self, store: Any, settings_path) -> None:
        self.store = store
        self.settings_store = SettingsStore(settings_path)

    def settings(self) -> dict[str, Any]:
        return self.settings_store.load()

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self.settings_store.save(settings)

    def should_notify(self, event: str) -> bool:
        cfg = self.settings()
        if not cfg.get("enabled", True):
            return False
        events = cfg.get("events") or {}
        return bool(events.get(event, False))

    def notify(self, incident_id: str, event: str) -> tuple[int, bytes] | None:
        if not self.should_notify(event):
            return None
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            return None
        topic = str(self.settings().get("topic") or "").strip()
        try:
            status, body = _publish_incident(incident, event=event, topic=topic)
            if status >= 400:
                sys.stderr.write(
                    f"ntfy incident notify failed ({status}) incident={incident_id} event={event}\n"
                )
            else:
                sys.stderr.write(f"ntfy notified incident={incident_id} event={event} topic={topic}\n")
            return status, body
        except Exception as exc:
            sys.stderr.write(f"ntfy notify error incident={incident_id}: {exc}\n")
            return None

    def notify_many(self, items: list[tuple[str, str]]) -> None:
        """Dedupe by incident id; highest-priority event wins per incident."""
        priority = {
            "resolved": 0,
            "reopened": 1,
            "created": 2,
            "manual": 2,
            "merged": 3,
            "acknowledged": 4,
            "updated": 5,
        }
        chosen: dict[str, str] = {}
        for incident_id, event in items:
            current = chosen.get(incident_id)
            if current is None or priority.get(event, 99) < priority.get(current, 99):
                chosen[incident_id] = event
        for incident_id, event in chosen.items():
            self.notify(incident_id, event)
