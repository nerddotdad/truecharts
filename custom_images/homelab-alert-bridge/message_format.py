"""Render ntfy notification text (mirrors alertmanager-ntfy ConfigMap templates)."""

from __future__ import annotations

import os

GRAFANA_PUBLIC_URL = os.environ.get("GRAFANA_PUBLIC_URL", "https://grafana.example.com").rstrip("/")
DEFAULT_RUNBOOK_URL = os.environ.get(
    "DEFAULT_RUNBOOK_URL",
    "https://runbooks.prometheus-operator.dev/",
)


def ntfy_title(alert: dict) -> str:
    """Match clusters/.../alertmanager-ntfy/app/configmap.yaml title template."""
    status = str(alert.get("status") or "firing")
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    headline = (
        annotations.get("summary")
        or labels.get("alertname")
        or "Alert"
    )
    if status == "resolved":
        return f"✅ Resolved: {headline}"
    return f"🔥 {headline}"


def ntfy_body(alert: dict) -> str:
    """Match alertmanager-ntfy description template (without title)."""
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    status = str(alert.get("status") or "unknown")

    if annotations.get("description"):
        body = str(annotations["description"])
    elif annotations.get("message"):
        body = str(annotations["message"])
    elif annotations.get("summary"):
        body = str(annotations["summary"])
    else:
        body = f"Alert {labels.get('alertname', 'unknown')} is {status}."

    extras: list[str] = []
    if labels.get("exported_namespace"):
        extras.append(f"\nFlux namespace: {labels['exported_namespace']}")
    if labels.get("name"):
        extras.append(f"\nRelease: {labels['name']}")
    if labels.get("chart") or labels.get("chart_ref"):
        extras.append(f"\nChart: {labels.get('chart', '')}{labels.get('chart_ref', '')}")
    if labels.get("chart_version"):
        extras.append(f"\nChart version: {labels['chart_version']}")
    if labels.get("namespace"):
        extras.append(f"\nNamespace: {labels['namespace']}")
    if labels.get("job_name"):
        extras.append(f"\nJob: {labels['job_name']}")
    if labels.get("pod"):
        extras.append(f"\nPod: {labels['pod']}")
    if labels.get("severity"):
        extras.append(f"\nSeverity: {labels['severity']}")

    runbook = (
        annotations.get("runbook_url")
        or annotations.get("runbook")
        or DEFAULT_RUNBOOK_URL
    )
    grafana_alert = f"{GRAFANA_PUBLIC_URL}/alerting/list?search={labels.get('alertname', '')}"
    links = f"\n\n---\n\n**Links:** [Runbook]({runbook})"
    if annotations.get("dashboard_url"):
        links += f" · [Dashboard]({annotations['dashboard_url']})"
    links += f" · [Alert in Grafana]({grafana_alert})"

    return body + "".join(extras) + links


def ntfy_tags_line(labels: dict) -> str:
    """Approximate ntfy client tag line (Prometheus labels)."""
    if not labels:
        return ""
    parts = [f"{key} = {labels[key]}" for key in sorted(labels)]
    return "Tags: " + ", ".join(parts)


def operator_message(alert: dict) -> str:
    """Full text the operator sees in ntfy (title + body + label tags)."""
    labels = alert.get("labels") or {}
    parts = [ntfy_title(alert), "", ntfy_body(alert)]
    tags = ntfy_tags_line(labels)
    if tags:
        parts.extend(["", tags])
    return "\n".join(parts)


def agent_context(incident: dict) -> str:
    """Extra fields for Hermes (not shown in ntfy)."""
    alert = incident.get("alert") or {}
    annotations = alert.get("annotations") or {}
    lines: list[str] = []

    incident_id = incident.get("id")
    if incident_id:
        lines.append(f"Incident ID: {incident_id}")

    status = incident.get("status") or alert.get("status")
    if status:
        lines.append(f"Status: {status}")
    if alert.get("startsAt"):
        lines.append(f"Starts: {alert['startsAt']}")
    ends_at = alert.get("endsAt")
    if ends_at and ends_at != "0001-01-01T00:00:00Z":
        lines.append(f"Ends: {ends_at}")

    skills = str(
        annotations.get("recommended_ai_skills") or annotations.get("recommended_skills") or ""
    ).strip()
    if skills:
        lines.append(f"Recommended skills: {skills}")

    fingerprint = alert.get("fingerprint")
    if fingerprint and fingerprint != incident_id:
        lines.append(f"Fingerprint: {fingerprint}")

    if not lines:
        return ""
    return "---\n\nAgent context:\n" + "\n".join(lines)


def hermes_message(incident: dict) -> str:
    """Operator ntfy text plus agent-only context for Ask AI."""
    alert = incident.get("alert") or {}
    operator = operator_message(alert)
    agent = agent_context(incident)
    if agent:
        return f"{operator}\n\n{agent}"
    return operator


def enrich_incident(incident: dict) -> dict:
    """Ensure stored incidents expose operator_message and hermes_message."""
    if incident.get("hermes_message") and incident.get("operator_message"):
        return incident
    alert = incident.get("alert") or {}
    enriched = dict(incident)
    enriched["operator_message"] = operator_message(alert)
    enriched["hermes_message"] = hermes_message(enriched)
    return enriched
