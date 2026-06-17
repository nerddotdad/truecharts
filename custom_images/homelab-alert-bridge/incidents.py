"""Incident funnel: ingest alerts, merge, enrich, and export for Hermes/ntfy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from db import IncidentStore
from message_format import enrich_incident, hermes_message, operator_message

SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_id(value: str) -> str:
    cleaned = SAFE_ID_RE.sub("_", value.strip())[:128]
    return cleaned or "unknown"


def fingerprint(alert: dict[str, Any]) -> str:
    fp = str(alert.get("fingerprint") or "").strip()
    if fp:
        return safe_id(fp)
    labels = alert.get("labels") or {}
    return safe_id(f"{labels.get('alertname', 'alert')}-{labels.get('namespace', 'ns')}")


def alert_title(alert: dict[str, Any]) -> str:
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    return str(
        annotations.get("summary")
        or labels.get("alertname")
        or "Alert"
    )


def alert_severity(alert: dict[str, Any]) -> str | None:
    labels = alert.get("labels") or {}
    value = labels.get("severity")
    return str(value) if value else None


def severity_rank(severity: str | None) -> int:
    order = {"critical": 0, "warning": 1, "info": 2}
    return order.get(str(severity or "").lower(), 3)


class IncidentService:
    def __init__(self, store: IncidentStore, legacy_dir: Path) -> None:
        self.store = store
        self.legacy_dir = legacy_dir

    def migrate_legacy_json(self) -> int:
        if not self.legacy_dir.is_dir():
            return 0
        imported = 0
        for path in sorted(self.legacy_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            alert = raw.get("alert") or {}
            fp = fingerprint(alert)
            if self.store.get_incident_by_fingerprint(fp):
                continue
            labels = alert.get("labels") or {}
            incident = self.store.create_incident(
                title=alert_title(alert),
                severity=alert_severity(alert),
                summary=(alert.get("annotations") or {}).get("description"),
                incident_id=safe_id(str(raw.get("id") or fp)),
            )
            self.store.upsert_alert(
                incident_id=incident["id"],
                fingerprint=fp,
                status=str(alert.get("status") or raw.get("status") or "firing"),
                payload=alert,
            )
            imported += 1
        return imported

    def ingest_alertmanager_payload(self, payload: dict[str, Any]) -> list[str]:
        touched: list[str] = []
        for alert in payload.get("alerts") or []:
            if not isinstance(alert, dict):
                continue
            incident_id = self._ingest_alert(alert, receiver=payload.get("receiver"))
            if incident_id:
                touched.append(incident_id)
        return list(dict.fromkeys(touched))

    def _ingest_alert(self, alert: dict[str, Any], *, receiver: str | None = None) -> str | None:
        fp = fingerprint(alert)
        labels = alert.get("labels") or {}
        alertname = str(labels.get("alertname") or "alert")
        namespace = str(labels.get("namespace") or "")
        status = str(alert.get("status") or "firing")
        severity = alert_severity(alert)

        existing = self.store.get_incident_by_fingerprint(fp)
        if existing and existing.get("status") == "merged" and existing.get("merged_into_id"):
            existing = self.store.get_incident(existing["merged_into_id"])

        incident: dict[str, Any] | None = existing
        if incident is None:
            incident = self.store.find_open_incident(alertname, namespace)
        if incident is None:
            incident = self.store.create_incident(
                title=alert_title(alert),
                severity=severity,
                summary=(alert.get("annotations") or {}).get("description"),
            )
        elif severity and severity_rank(severity) < severity_rank(incident.get("severity")):
            self.store.update_incident(incident["id"], severity=severity)

        self.store.upsert_alert(
            incident_id=incident["id"],
            fingerprint=fp,
            status=status,
            payload=alert,
        )

        if status == "resolved":
            self._maybe_auto_resolve(incident["id"])
        elif incident.get("status") == "resolved":
            self.store.update_incident(
                incident["id"],
                status="open",
                event_type="reopened",
                event_detail={"reason": "firing alert received"},
            )

        enrichment = dict(incident.get("enrichment") or {})
        if receiver and not enrichment.get("receiver"):
            enrichment["receiver"] = receiver
            self.store.update_incident(incident["id"], enrichment=enrichment)

        return incident["id"]

    def _maybe_auto_resolve(self, incident_id: str) -> None:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return
        alerts = incident.get("alerts") or []
        if alerts and all(str(a.get("status")) == "resolved" for a in alerts):
            if incident.get("status") in ("open", "acknowledged"):
                self.store.update_incident(
                    incident_id,
                    status="resolved",
                    resolved_by="alertmanager",
                    event_type="resolved",
                    event_detail={"reason": "all alerts resolved"},
                )

    def acknowledge(self, incident_id: str, actor: str | None = None) -> dict[str, Any] | None:
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            return None
        return self.store.update_incident(
            incident_id,
            status="acknowledged",
            actor=actor,
            event_type="acknowledged",
        )

    def resolve(self, incident_id: str, actor: str | None = None) -> dict[str, Any] | None:
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            return None
        return self.store.update_incident(
            incident_id,
            status="resolved",
            actor=actor,
            event_type="resolved",
        )

    def reopen(self, incident_id: str, actor: str | None = None) -> dict[str, Any] | None:
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            return None
        return self.store.update_incident(
            incident_id,
            status="open",
            actor=actor,
            event_type="reopened",
        )

    def enrich(
        self,
        incident_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        severity: str | None = None,
        tags: list[str] | None = None,
        actor: str | None = None,
    ) -> dict[str, Any] | None:
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            return None

        enrichment = dict(incident.get("enrichment") or {})
        if tags is not None:
            enrichment["tags"] = sorted({t.strip() for t in tags if t.strip()})

        detail: dict[str, Any] = {}
        if title is not None:
            detail["title"] = title
        if summary is not None:
            detail["summary"] = summary
        if severity is not None:
            detail["severity"] = severity
        if tags is not None:
            detail["tags"] = enrichment.get("tags")

        return self.store.update_incident(
            incident_id,
            title=title,
            summary=summary,
            severity=severity,
            enrichment=enrichment,
            actor=actor,
            event_type="enriched",
            event_detail=detail,
        )

    def add_note(self, incident_id: str, body: str, actor: str | None = None) -> dict[str, Any] | None:
        if not body.strip():
            return None
        return self.store.add_note(incident_id, body, actor=actor)

    def merge(self, target_id: str, source_ids: list[str], actor: str | None = None) -> dict[str, Any] | None:
        target = self.store.get_incident(target_id)
        if target is None or target.get("status") == "merged":
            return None

        merged_sources: list[str] = []
        for source_id in source_ids:
            if source_id == target_id:
                continue
            source = self.store.get_incident(source_id)
            if source is None or source.get("status") == "merged":
                continue
            moved = self.store.move_alerts(source_id, target_id)
            self.store.update_incident(
                source_id,
                status="merged",
                merged_into_id=target_id,
                actor=actor,
                event_type="merged",
                event_detail={"into": target_id, "alerts_moved": moved},
            )
            merged_sources.append(source_id)

        if not merged_sources:
            return target

        target = self.store.get_incident(target_id)
        assert target is not None
        alerts = target.get("alerts") or []
        severities = [alert_severity(a) for a in alerts]
        best = min(severities, key=severity_rank) if severities else target.get("severity")
        enrichment = dict(target.get("enrichment") or {})
        enrichment.setdefault("merged_from", [])
        enrichment["merged_from"] = sorted(
            set(enrichment.get("merged_from") or []) | set(merged_sources)
        )
        self.store.update_incident(
            target_id,
            severity=best,
            enrichment=enrichment,
            actor=actor,
            event_type="merge_received",
            event_detail={"sources": merged_sources},
        )
        return self.store.get_incident(target_id)

    def export_legacy(self, incident_id: str) -> dict[str, Any] | None:
        """Shape consumed by Hermes and /homelab/api/incidents/<id>."""
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return None

        alerts = incident.get("alerts") or []
        primary = alerts[0] if alerts else {}
        export = {
            "id": incident["id"],
            "status": incident["status"],
            "title": incident["title"],
            "summary": incident.get("summary"),
            "severity": incident.get("severity"),
            "created_at": incident.get("created_at"),
            "updated_at": incident.get("updated_at"),
            "acknowledged_at": incident.get("acknowledged_at"),
            "resolved_at": incident.get("resolved_at"),
            "enrichment": incident.get("enrichment") or {},
            "alerts": alerts,
            "events": incident.get("events") or [],
            "alert": primary,
            "receiver": (incident.get("enrichment") or {}).get("receiver"),
        }
        export["operator_message"] = self._operator_message(incident)
        export["hermes_message"] = hermes_message(
            enrich_incident(
                {
                    "id": incident["id"],
                    "status": incident["status"],
                    "alert": primary,
                }
            )
        )
        if incident.get("summary") and primary:
            export["hermes_message"] = (
                f"{export['hermes_message']}\n\n---\n\nIncident summary:\n{incident['summary']}"
            )
        notes = (incident.get("enrichment") or {}).get("notes") or []
        if notes:
            lines = [f"- {n.get('actor', 'operator')}: {n.get('body', '')}" for n in notes[-5:]]
            export["hermes_message"] += "\n\nRecent notes:\n" + "\n".join(lines)
        return export

    def _operator_message(self, incident: dict[str, Any]) -> str:
        alerts = incident.get("alerts") or []
        header = [
            incident.get("title") or "Incident",
            f"Status: {incident.get('status', 'open')} · Severity: {incident.get('severity') or 'unknown'}",
            f"Alerts: {len(alerts)}",
        ]
        if incident.get("summary"):
            header.extend(["", str(incident["summary"])])
        bodies = [operator_message(alert) for alert in alerts[:3]]
        if len(alerts) > 3:
            bodies.append(f"... and {len(alerts) - 3} more alert(s)")
        return "\n".join(header + [""] + bodies)
