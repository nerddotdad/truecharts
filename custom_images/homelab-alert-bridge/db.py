"""SQLite persistence for homelab incidents."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class IncidentStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'open',
                    severity TEXT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    merged_into_id TEXT REFERENCES incidents(id),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    enrichment TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    fingerprint TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incident_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    actor TEXT,
                    detail TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
                CREATE INDEX IF NOT EXISTS idx_incidents_updated ON incidents(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_incident ON alerts(incident_id);
                CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events(incident_id, created_at);
                """
            )

    def _row_to_incident(self, row: sqlite3.Row, *, include_alerts: bool = True) -> dict[str, Any]:
        incident = {
            "id": row["id"],
            "status": row["status"],
            "severity": row["severity"],
            "title": row["title"],
            "summary": row["summary"],
            "merged_into_id": row["merged_into_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "acknowledged_at": row["acknowledged_at"],
            "acknowledged_by": row["acknowledged_by"],
            "resolved_at": row["resolved_at"],
            "resolved_by": row["resolved_by"],
            "enrichment": json.loads(row["enrichment"] or "{}"),
        }
        if include_alerts:
            incident["alerts"] = self.list_alerts(incident["id"])
            incident["events"] = self.list_events(incident["id"])
        return incident

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 200,
        include_merged: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if not include_merged:
            clauses.append("status != 'merged'")
        params.append(limit)
        query = f"""
            SELECT * FROM incidents
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_incident(row, include_alerts=False) for row in rows]

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_incident(row)

    def get_incident_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT i.* FROM incidents i
                JOIN alerts a ON a.incident_id = i.id
                WHERE a.fingerprint = ?
                """,
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_incident(row)

    def find_open_incident(self, alertname: str, namespace: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT i.* FROM incidents i
                WHERE i.status IN ('open', 'acknowledged')
                  AND i.merged_into_id IS NULL
                ORDER BY i.updated_at DESC
                LIMIT 100
                """
            ).fetchall()
        for row in rows:
            alerts = self.list_alerts(row["id"])
            for alert in alerts:
                labels = (alert.get("labels") or {})
                if labels.get("alertname") == alertname and labels.get("namespace") == namespace:
                    return self._row_to_incident(row)
        return None

    def create_incident(
        self,
        *,
        title: str,
        severity: str | None,
        summary: str | None = None,
        enrichment: dict[str, Any] | None = None,
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        iid = incident_id or new_id()
        now = utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    id, status, severity, title, summary, created_at, updated_at, enrichment
                ) VALUES (?, 'open', ?, ?, ?, ?, ?, ?)
                """,
                (
                    iid,
                    severity,
                    title,
                    summary,
                    now,
                    now,
                    json.dumps(enrichment or {}),
                ),
            )
            self._add_event(conn, iid, "created", None, {"title": title, "severity": severity})
        incident = self.get_incident(iid)
        assert incident is not None
        return incident

    def upsert_alert(
        self,
        *,
        incident_id: str,
        fingerprint: str,
        status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = utcnow()
        raw = json.dumps(payload)
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT fingerprint FROM alerts WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE alerts
                    SET incident_id = ?, status = ?, payload = ?, updated_at = ?
                    WHERE fingerprint = ?
                    """,
                    (incident_id, status, raw, now, fingerprint),
                )
                event_type = "alert_updated"
            else:
                conn.execute(
                    """
                    INSERT INTO alerts (fingerprint, incident_id, status, payload, received_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (fingerprint, incident_id, status, raw, now, now),
                )
                event_type = "alert_attached"
            conn.execute(
                "UPDATE incidents SET updated_at = ? WHERE id = ?",
                (now, incident_id),
            )
            self._add_event(
                conn,
                incident_id,
                event_type,
                None,
                {
                    "fingerprint": fingerprint,
                    "status": status,
                    "alertname": (payload.get("labels") or {}).get("alertname"),
                },
            )
        return payload

    def list_alerts(self, incident_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE incident_id = ? ORDER BY updated_at DESC",
                (incident_id,),
            ).fetchall()
        alerts: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload"])
            payload["fingerprint"] = row["fingerprint"]
            payload["status"] = row["status"]
            alerts.append(payload)
        return alerts

    def alerts_by_incident_ids(self, incident_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not incident_ids:
            return {}
        placeholders = ",".join("?" for _ in incident_ids)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM alerts
                WHERE incident_id IN ({placeholders})
                ORDER BY updated_at DESC
                """,
                incident_ids,
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {iid: [] for iid in incident_ids}
        for row in rows:
            payload = json.loads(row["payload"])
            payload["fingerprint"] = row["fingerprint"]
            payload["status"] = row["status"]
            grouped.setdefault(row["incident_id"], []).append(payload)
        return grouped

    def list_events(self, incident_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM incident_events
                WHERE incident_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (incident_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "detail": json.loads(row["detail"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def update_incident(
        self,
        incident_id: str,
        *,
        status: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        severity: str | None = None,
        enrichment: dict[str, Any] | None = None,
        acknowledged_by: str | None = None,
        resolved_by: str | None = None,
        merged_into_id: str | None = None,
        actor: str | None = None,
        event_type: str | None = None,
        event_detail: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = []
        now = utcnow()

        if status is not None:
            fields.append("status = ?")
            params.append(status)
            if status == "acknowledged":
                fields.extend(["acknowledged_at = ?", "acknowledged_by = ?"])
                params.extend([now, acknowledged_by or actor or "operator"])
            if status == "resolved":
                fields.extend(["resolved_at = ?", "resolved_by = ?"])
                params.extend([now, resolved_by or actor or "operator"])
            if status == "open":
                fields.extend(
                    [
                        "acknowledged_at = NULL",
                        "acknowledged_by = NULL",
                        "resolved_at = NULL",
                        "resolved_by = NULL",
                    ]
                )
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if summary is not None:
            fields.append("summary = ?")
            params.append(summary)
        if severity is not None:
            fields.append("severity = ?")
            params.append(severity)
        if enrichment is not None:
            fields.append("enrichment = ?")
            params.append(json.dumps(enrichment))
        if merged_into_id is not None:
            fields.append("merged_into_id = ?")
            params.append(merged_into_id)

        if not fields:
            return self.get_incident(incident_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(incident_id)

        with self._conn() as conn:
            conn.execute(
                f"UPDATE incidents SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            if event_type:
                self._add_event(conn, incident_id, event_type, actor, event_detail or {})
        return self.get_incident(incident_id)

    def move_alerts(self, source_id: str, target_id: str) -> int:
        now = utcnow()
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE alerts SET incident_id = ?, updated_at = ? WHERE incident_id = ?",
                (target_id, now, source_id),
            )
            conn.execute("UPDATE incidents SET updated_at = ? WHERE id = ?", (now, target_id))
        return result.rowcount if result.rowcount is not None else 0

    def add_note(self, incident_id: str, body: str, actor: str | None = None) -> dict[str, Any] | None:
        incident = self.get_incident(incident_id)
        if incident is None:
            return None
        enrichment = dict(incident.get("enrichment") or {})
        notes = list(enrichment.get("notes") or [])
        note = {"body": body.strip(), "actor": actor or "operator", "created_at": utcnow()}
        notes.append(note)
        enrichment["notes"] = notes
        return self.update_incident(
            incident_id,
            enrichment=enrichment,
            actor=actor,
            event_type="note_added",
            event_detail={"body": body.strip()},
        )

    def _add_event(
        self,
        conn: sqlite3.Connection,
        incident_id: str,
        event_type: str,
        actor: str | None,
        detail: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO incident_events (incident_id, event_type, actor, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (incident_id, event_type, actor, json.dumps(detail), utcnow()),
        )
