"""Persisted notification settings (PVC-backed JSON)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "topic": os.environ.get("NTFY_TOPIC", "homelab-alerts"),
        "events": {
            "created": True,
            "updated": True,
            "resolved": True,
            "reopened": True,
            "manual": True,
            "acknowledged": False,
            "merged": False,
        },
        "show_noise": False,
    }


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        defaults = default_settings()
        if not self.path.is_file():
            return defaults
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return defaults
        if not isinstance(raw, dict):
            return defaults
        merged = dict(defaults)
        merged.update({k: v for k, v in raw.items() if k != "events"})
        events = dict(defaults.get("events") or {})
        if isinstance(raw.get("events"), dict):
            events.update({str(k): bool(v) for k, v in raw["events"].items()})
        merged["events"] = events
        if not str(merged.get("topic") or "").strip():
            merged["topic"] = defaults["topic"]
        merged["enabled"] = bool(merged.get("enabled", True))
        merged["show_noise"] = bool(raw.get("show_noise", defaults.get("show_noise", False)))
        return merged

    def save(self, settings: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        if "enabled" in settings:
            current["enabled"] = bool(settings["enabled"])
        if "topic" in settings and str(settings["topic"]).strip():
            current["topic"] = str(settings["topic"]).strip()
        if isinstance(settings.get("events"), dict):
            events = dict(current.get("events") or {})
            for key, value in settings["events"].items():
                events[str(key)] = bool(value)
            current["events"] = events
        if "show_noise" in settings:
            current["show_noise"] = bool(settings["show_noise"])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
