"""Configurable auto-raise rules: alert inbox → incident."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from filters import is_ignored_alert

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "unknown": 3}


def default_raise_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "min_severity": "critical",
        "alertnames": [],
        "label_rules": [],
        "group_open": True,
    }


class RaiseSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        defaults = default_raise_settings()
        if not self.path.is_file():
            return defaults
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return defaults
        if not isinstance(raw, dict):
            return defaults
        merged = dict(defaults)
        merged.update({k: v for k, v in raw.items() if k not in ("alertnames", "label_rules")})
        if isinstance(raw.get("alertnames"), list):
            merged["alertnames"] = [str(x).strip() for x in raw["alertnames"] if str(x).strip()]
        if isinstance(raw.get("label_rules"), list):
            rules: list[dict[str, str]] = []
            for item in raw["label_rules"]:
                if isinstance(item, dict):
                    rules.append({str(k): str(v) for k, v in item.items()})
            merged["label_rules"] = rules
        merged["enabled"] = bool(merged.get("enabled", True))
        merged["group_open"] = bool(merged.get("group_open", True))
        if not str(merged.get("min_severity") or "").strip():
            merged["min_severity"] = defaults["min_severity"]
        return merged

    def save(self, settings: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        if "enabled" in settings:
            current["enabled"] = bool(settings["enabled"])
        if "group_open" in settings:
            current["group_open"] = bool(settings["group_open"])
        if "min_severity" in settings and str(settings["min_severity"]).strip():
            current["min_severity"] = str(settings["min_severity"]).strip()
        if "alertnames" in settings:
            raw = settings["alertnames"]
            if isinstance(raw, str):
                current["alertnames"] = [p.strip() for p in raw.split(",") if p.strip()]
            elif isinstance(raw, list):
                current["alertnames"] = [str(x).strip() for x in raw if str(x).strip()]
        if "label_rules" in settings:
            raw = settings["label_rules"]
            if isinstance(raw, str) and raw.strip():
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = []
            else:
                parsed = raw
            rules: list[dict[str, str]] = []
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        rules.append({str(k): str(v) for k, v in item.items()})
            current["label_rules"] = rules
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current


def _severity_rank(severity: str | None) -> int:
    return SEVERITY_ORDER.get(str(severity or "").lower(), 99)


def _matches_rule(labels: dict[str, str], rule: dict[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in rule.items())


def should_auto_raise(alert: dict[str, Any], settings: dict[str, Any]) -> bool:
    if not settings.get("enabled", True):
        return False
    if is_ignored_alert(alert):
        return False
    if str(alert.get("status") or "firing") == "resolved":
        return False

    labels = {str(k): str(v) for k, v in (alert.get("labels") or {}).items()}
    severity = labels.get("severity")
    min_severity = str(settings.get("min_severity") or "critical")
    if _severity_rank(severity) > _severity_rank(min_severity):
        return False

    alertnames = settings.get("alertnames") or []
    if alertnames and labels.get("alertname") not in alertnames:
        return False

    label_rules = settings.get("label_rules") or []
    if label_rules and not any(_matches_rule(labels, rule) for rule in label_rules):
        return False

    return True
