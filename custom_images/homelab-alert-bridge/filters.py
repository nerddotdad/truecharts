"""Drop noise alerts from triage (ingest, ntfy, and dashboard)."""

from __future__ import annotations

import json
import os
from typing import Any

# Mirrors kube-prometheus-stack AlertmanagerConfig null routes.
_BUILTIN_RULES: tuple[dict[str, Any], ...] = (
    {"alertname": "InfoInhibitor"},
    {"alertname": "Watchdog"},
    {"alertname": "TargetDown", "namespace": "downloaders"},
    {"alertname": "KubeJobNotCompleted", "job_name": "ollama-model-pull-job"},
    {"alertname": "KubeJobFailed", "job_name": "ollama-model-pull-job"},
)


def _extra_alertnames() -> set[str]:
    raw = os.environ.get("IGNORED_ALERTNAMES", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def _extra_rules() -> list[dict[str, str]]:
    raw = os.environ.get("IGNORED_ALERT_RULES", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    rules: list[dict[str, str]] = []
    for item in parsed:
        if isinstance(item, dict):
            rules.append({str(k): str(v) for k, v in item.items()})
    return rules


def ignored_alertnames() -> list[str]:
    names = {rule["alertname"] for rule in _BUILTIN_RULES if "alertname" in rule}
    names.update(_extra_alertnames())
    return sorted(names)


def ignored_summary() -> str:
    parts = ignored_alertnames()
    extras = _extra_rules()
    if extras:
        parts.append(f"{len(extras)} custom rule(s)")
    return ", ".join(parts)


def _labels(alert: dict[str, Any]) -> dict[str, str]:
    labels = alert.get("labels") or {}
    return {str(k): str(v) for k, v in labels.items()}


def _annotations(alert: dict[str, Any]) -> dict[str, str]:
    annotations = alert.get("annotations") or {}
    return {str(k): str(v) for k, v in annotations.items()}


def _matches_rule(labels: dict[str, str], rule: dict[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in rule.items())


def is_ignored_alert(alert: dict[str, Any]) -> bool:
    """True when an alert should not create incidents or appear in the dashboard."""
    labels = _labels(alert)
    annotations = _annotations(alert)

    for key in ("homelab_triage", "triage"):
        value = (labels.get(key) or annotations.get(key) or "").strip().lower()
        if value in ("false", "no", "skip", "ignore", "0"):
            return True

    alertname = labels.get("alertname", "")
    if alertname in _extra_alertnames():
        return True

    for rule in _BUILTIN_RULES:
        if _matches_rule(labels, rule):
            return True
    for rule in _extra_rules():
        if _matches_rule(labels, rule):
            return True
    return False


def filter_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [alert for alert in alerts if not is_ignored_alert(alert)]


def incident_is_noise(incident: dict[str, Any]) -> bool:
    """Hide incidents whose alerts are entirely noise."""
    alerts = incident.get("alerts") or []
    if not alerts:
        enrichment = incident.get("enrichment") or {}
        primary = enrichment.get("primary_alertname")
        if primary:
            return is_ignored_alert({"labels": {"alertname": str(primary)}})
        return False
    return all(is_ignored_alert(alert) for alert in alerts)
