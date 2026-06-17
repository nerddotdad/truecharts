"""Incident funnel: ingest alerts, merge, enrich, and export for Hermes/ntfy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from db import IncidentStore
from filters import incident_is_noise, is_ignored_alert
from message_format import enrich_incident, hermes_message, operator_message
from query_parser import parse_query
from raise_rules import RaiseSettingsStore

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
    def __init__(self, store: IncidentStore, legacy_dir: Path, *, raise_settings_path: Path | None = None) -> None:
        self.store = store
        self.legacy_dir = legacy_dir
        self.raise_settings = RaiseSettingsStore(
            raise_settings_path or legacy_dir / "auto_raise_settings.json"
        )

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
            if is_ignored_alert(alert):
                continue
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

    def list_for_dashboard(
        self,
        *,
        status: str | None = None,
        include_noise: bool = False,
        query: str = "",
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[dict[str, Any]], bool, int]:
        parsed = parse_query(query, mode="incidents")
        if parsed.errors:
            raise ValueError("; ".join(parsed.errors))
        scan_offset = offset
        visible: list[dict[str, Any]] = []
        has_more = False
        while len(visible) < limit:
            batch, batch_more = self.store.search_incidents(
                parsed=parsed,
                tab_status=status,
                offset=scan_offset,
                limit=limit,
            )
            if not batch:
                break
            if include_noise:
                visible.extend(batch[: limit - len(visible)])
            else:
                incident_ids = [inc["id"] for inc in batch]
                alerts_by_id = self.store.alerts_by_incident_ids(incident_ids)
                for incident in batch:
                    probe = dict(incident)
                    probe["alerts"] = alerts_by_id.get(incident["id"], [])
                    if not incident_is_noise(probe):
                        visible.append(incident)
                    if len(visible) >= limit:
                        break
            scan_offset += len(batch)
            has_more = batch_more
            if not batch_more:
                break
            if include_noise and len(visible) >= limit:
                break
        if len(visible) >= limit and has_more:
            return visible[:limit], True, scan_offset
        if not has_more:
            return visible, False, scan_offset
        return visible, True, scan_offset

    def list_inbox(
        self,
        *,
        status: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[dict[str, Any]], bool, int]:
        parsed = parse_query(query, mode="alerts")
        if parsed.errors:
            raise ValueError("; ".join(parsed.errors))
        scan_offset = offset
        visible: list[dict[str, Any]] = []
        has_more = False
        while len(visible) < limit:
            batch, batch_more = self.store.search_inbox_alerts(
                parsed=parsed,
                tab_status=status,
                offset=scan_offset,
                limit=limit,
            )
            if not batch:
                break
            for alert in batch:
                if not is_ignored_alert(alert):
                    visible.append(alert)
                if len(visible) >= limit:
                    break
            scan_offset += len(batch)
            has_more = batch_more
            if not batch_more:
                break
        if len(visible) >= limit and has_more:
            return visible[:limit], True, scan_offset
        return visible, False, scan_offset

    def raise_settings_dict(self) -> dict[str, Any]:
        return self.raise_settings.load()

    def save_raise_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self.raise_settings.save(settings)

    def ingest_alertmanager_payload(self, payload: dict[str, Any]) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        rules = self.raise_settings.load()
        for alert in payload.get("alerts") or []:
            if not isinstance(alert, dict):
                continue
            result = self._ingest_alert(alert, receiver=payload.get("receiver"), rules=rules)
            if result:
                events.append(result)
        return events

    def _ingest_alert(
        self,
        alert: dict[str, Any],
        *,
        receiver: str | None = None,
        rules: dict[str, Any] | None = None,
    ) -> tuple[str, str] | None:
        if is_ignored_alert(alert):
            return None

        fp = fingerprint(alert)
        status = str(alert.get("status") or "firing")
        rules = rules or self.raise_settings.load()

        existing = self.store.get_alert(fp)
        if existing and existing.get("incident_id"):
            return self._update_attached_alert(
                fp,
                alert,
                status,
                str(existing["incident_id"]),
                receiver=receiver,
            )

        self.store.upsert_inbox_alert(fingerprint=fp, status=status, payload=alert)

        if status == "resolved":
            return None

        if not should_auto_raise(alert, rules):
            return None

        return self._raise_incident_for_alerts(
            [fp],
            actor="auto_raise",
            receiver=receiver,
            group_open=bool(rules.get("group_open", True)),
        )

    def _update_attached_alert(
        self,
        fp: str,
        alert: dict[str, Any],
        status: str,
        incident_id: str,
        *,
        receiver: str | None = None,
    ) -> tuple[str, str] | None:
        incident = self.store.get_incident(incident_id)
        if incident is None or incident.get("status") == "merged":
            if incident and incident.get("merged_into_id"):
                incident_id = str(incident["merged_into_id"])
                incident = self.store.get_incident(incident_id)
            else:
                self.store.upsert_inbox_alert(fingerprint=fp, status=status, payload=alert)
                return None

        incident_before = str(incident.get("status") or "open")
        reopened = False
        if incident_before == "resolved" and status != "resolved":
            self.store.update_incident(
                incident_id,
                status="open",
                event_type="reopened",
                event_detail={"reason": "firing alert received"},
            )
            reopened = True

        severity = alert_severity(alert)
        if severity and severity_rank(severity) < severity_rank(incident.get("severity")):
            self.store.update_incident(incident_id, severity=severity)

        self.store.upsert_alert(
            incident_id=incident_id,
            fingerprint=fp,
            status=status,
            payload=alert,
        )

        enrichment = dict(incident.get("enrichment") or {})
        if receiver and not enrichment.get("receiver"):
            enrichment["receiver"] = receiver
            self.store.update_incident(incident_id, enrichment=enrichment)

        status_before_resolve = str(
            (self.store.get_incident(incident_id) or {}).get("status") or "open"
        )
        self._maybe_auto_resolve(incident_id)
        after = self.store.get_incident(incident_id)
        if after is None:
            return None

        if after.get("status") == "resolved" and status_before_resolve in ("open", "acknowledged"):
            return (incident_id, "resolved")
        if reopened:
            return (incident_id, "reopened")
        return (incident_id, "updated")

    def raise_from_alerts(
        self,
        fingerprints: list[str],
        *,
        title: str | None = None,
        summary: str | None = None,
        actor: str | None = None,
        group_open: bool = False,
    ) -> tuple[dict[str, Any] | None, str]:
        fps = list(dict.fromkeys(safe_id(fp) for fp in fingerprints if fp.strip()))
        if not fps:
            return None, "error"

        alerts: list[dict[str, Any]] = []
        for fp in fps:
            row = self.store.get_alert(fp)
            if row is None:
                continue
            if row.get("incident_id"):
                incident = self.store.get_incident(str(row["incident_id"]))
                if incident:
                    return incident, "already_raised"
            alerts.append(row)

        if not alerts:
            return None, "error"

        event = self._raise_incident_for_alerts(
            [str(a["fingerprint"]) for a in alerts],
            title=title,
            summary=summary,
            actor=actor,
            group_open=group_open,
        )
        if event is None:
            return None, "error"
        incident = self.store.get_incident(event[0])
        return incident, event[1]

    def _raise_incident_for_alerts(
        self,
        fingerprints: list[str],
        *,
        title: str | None = None,
        summary: str | None = None,
        actor: str | None = None,
        receiver: str | None = None,
        group_open: bool = False,
    ) -> tuple[str, str] | None:
        fps = list(dict.fromkeys(fingerprints))
        alert_rows: list[dict[str, Any]] = []
        for fp in fps:
            row = self.store.get_alert(fp)
            if row is None:
                payload = {"fingerprint": fp, "labels": {}, "status": "firing"}
                self.store.upsert_inbox_alert(fingerprint=fp, status="firing", payload=payload)
                row = self.store.get_alert(fp)
            if row and not row.get("incident_id"):
                alert_rows.append(row)

        if not alert_rows:
            for fp in fps:
                row = self.store.get_alert(fp)
                if row and row.get("incident_id"):
                    return (str(row["incident_id"]), "updated")
            return None

        primary = alert_rows[0]
        labels = primary.get("labels") or {}
        alertname = str(labels.get("alertname") or "alert")
        namespace = str(labels.get("namespace") or "")

        incident: dict[str, Any] | None = None
        created = False
        if group_open and alertname:
            incident = self.store.find_open_incident(alertname, namespace)

        if incident is None:
            if len(alert_rows) == 1:
                inc_title = title or alert_title(primary)
                inc_summary = summary or (primary.get("annotations") or {}).get("description")
            else:
                inc_title = title or f"{alert_title(primary)} (+{len(alert_rows) - 1} alerts)"
                inc_summary = summary
            severities = [alert_severity(a) for a in alert_rows]
            best = min(severities, key=severity_rank) if severities else alert_severity(primary)
            enrichment: dict[str, Any] = {}
            if actor == "auto_raise":
                enrichment["auto_raised"] = True
            elif actor:
                enrichment["raised_by"] = actor
            incident = self.store.create_incident(
                title=inc_title,
                severity=best,
                summary=inc_summary,
                enrichment=enrichment,
            )
            created = True
            self.store.update_incident(
                incident["id"],
                event_type="raised" if actor != "auto_raise" else "auto_raised",
                actor=actor,
                event_detail={"fingerprints": fps},
            )
        elif title or summary:
            self.store.update_incident(
                incident["id"],
                title=title or None,
                summary=summary or None,
                actor=actor,
            )

        attached = self.store.attach_alerts(incident["id"], [str(a["fingerprint"]) for a in alert_rows], actor=actor)
        if attached == 0:
            return None

        for alert_row in alert_rows:
            self.store.upsert_alert(
                incident_id=incident["id"],
                fingerprint=str(alert_row["fingerprint"]),
                status=str(alert_row.get("status") or "firing"),
                payload=alert_row,
            )

        enrichment = dict(incident.get("enrichment") or {})
        if receiver and not enrichment.get("receiver"):
            enrichment["receiver"] = receiver
            self.store.update_incident(incident["id"], enrichment=enrichment)

        self._maybe_auto_resolve(incident["id"])
        return (incident["id"], "created" if created else "updated")

    def reconcile_resolved_incidents(self) -> int:
        """Close open/ack incidents whose alerts are all resolved (e.g. after legacy import)."""
        fixed = 0
        for incident in self.store.list_incidents(status=None, limit=5000, include_merged=False):
            if incident.get("status") not in ("open", "acknowledged"):
                continue
            full = self.store.get_incident(incident["id"])
            if full is None:
                continue
            alerts = full.get("alerts") or []
            if not alerts:
                continue
            before = full.get("status")
            self._maybe_auto_resolve(full["id"])
            after = self.store.get_incident(full["id"])
            if after and after.get("status") == "resolved" and before != "resolved":
                fixed += 1
        return fixed

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

    def create_manual(
        self,
        *,
        title: str,
        summary: str | None = None,
        severity: str | None = "warning",
        tags: list[str] | None = None,
        note: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any] | None:
        clean_title = title.strip()
        if not clean_title:
            return None
        enrichment: dict[str, Any] = {"manual": True}
        if tags:
            enrichment["tags"] = sorted({t.strip() for t in tags if t.strip()})
        incident = self.store.create_incident(
            title=clean_title,
            severity=severity or "warning",
            summary=(summary or "").strip() or None,
            enrichment=enrichment,
        )
        self.store.update_incident(
            incident["id"],
            event_type="manual_created",
            actor=actor,
            event_detail={"title": clean_title},
        )
        if note and note.strip():
            self.add_note(incident["id"], note.strip(), actor=actor)
        return self.store.get_incident(incident["id"])

    def bulk_apply(
        self,
        action: str,
        incident_ids: list[str],
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        ids = list(dict.fromkeys(safe_id(i) for i in incident_ids if i.strip()))
        if not ids:
            return {"error": "no incidents selected", "count": 0}

        if action == "merge":
            if len(ids) < 2:
                return {"error": "merge requires at least 2 incidents", "count": 0}
            target_id = ids[0]
            source_ids = ids[1:]
            merged = self.merge(target_id, source_ids, actor=actor)
            if merged is None:
                return {"error": "merge failed", "count": 0, "target_id": target_id}
            return {
                "action": action,
                "count": len(source_ids),
                "target_id": target_id,
                "message": f"Merged {len(source_ids)} incident(s) into {target_id}",
                "notify": [(target_id, "merged")],
            }

        handlers = {
            "ack": self.acknowledge,
            "resolve": self.resolve,
            "reopen": self.reopen,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"unknown action: {action}", "count": 0}

        applied = 0
        skipped = 0
        notify: list[tuple[str, str]] = []
        event_map = {"ack": "acknowledged", "resolve": "resolved", "reopen": "reopened"}
        for iid in ids:
            result = handler(iid, actor=actor)
            if result is None:
                skipped += 1
            else:
                applied += 1
                notify.append((iid, event_map[action]))
        label = action.capitalize()
        if action == "ack":
            label = "Acknowledged"
        elif action == "resolve":
            label = "Resolved"
        elif action == "reopen":
            label = "Reopened"
        msg = f"{label} {applied} incident(s)"
        if skipped:
            msg += f" ({skipped} skipped)"
        return {"action": action, "count": applied, "skipped": skipped, "message": msg, "notify": notify}

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
