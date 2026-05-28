#!/usr/bin/env python3
"""
Hermes WebUI prefill hook: load incident JSON when user opens ?incident=<id>.

Reads /data/incidents/<id>.json (same store as homelab-alert-bridge) or fetches
from the in-cluster bridge API when INCIDENT_API_BASE is set.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

INCIDENT_DIR = Path(os.environ.get("INCIDENT_DIR", "/data/incidents"))
INCIDENT_API_BASE = os.environ.get(
    "INCIDENT_API_BASE",
    "http://homelab-alert-bridge.observability.svc.cluster.local:8000/homelab/api/incidents",
)
PENDING_ID_FILE = Path(os.environ.get("PENDING_INCIDENT_FILE", "/data/incidents/.pending_incident"))


def _load_incident(incident_id: str) -> dict | None:
    local = INCIDENT_DIR / f"{incident_id}.json"
    if local.is_file():
        return json.loads(local.read_text(encoding="utf-8"))
    url = f"{INCIDENT_API_BASE.rstrip('/')}/{incident_id}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _format_incident(data: dict) -> str:
    alert = data.get("alert") or {}
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    lines = [
        "Homelab on-call triage session for a firing alert.",
        "",
        f"**Status:** {data.get('status', alert.get('status', 'unknown'))}",
        f"**Alert:** `{labels.get('alertname', 'unknown')}`",
        f"**Namespace:** `{labels.get('namespace', 'n/a')}`",
        f"**Severity:** `{labels.get('severity', 'n/a')}`",
    ]
    if labels.get("job_name"):
        lines.append(f"**Job:** `{labels['job_name']}`")
    if labels.get("pod"):
        lines.append(f"**Pod:** `{labels['pod']}`")
    if annotations.get("summary"):
        lines.append(f"\n**Summary:** {annotations['summary']}")
    if annotations.get("description"):
        lines.append(f"\n**Description:**\n{annotations['description']}")
    if annotations.get("runbook_url"):
        lines.append(f"\n**Runbook:** {annotations['runbook_url']}")
    lines.extend(
        [
            "",
            "Investigate with read-only kubectl/flux, cite the runbook, and propose a resolution plan.",
            "Do not apply cluster changes yourself.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    incident_id = os.environ.get("HERMES_INCIDENT_ID", "").strip()
    if not incident_id and PENDING_ID_FILE.is_file():
        incident_id = PENDING_ID_FILE.read_text(encoding="utf-8").strip()
    if not incident_id:
        return 0

    data = _load_incident(incident_id)
    if not data:
        print(
            json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Alert incident `{incident_id}` was not found in the incident store. "
                                "Ask the operator to paste alert details from ntfy."
                            ),
                        }
                    ]
                }
            )
        )
        return 0

    print(
        json.dumps(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the homelab on-call agent. Use skill homelab-k8s-flux-triage. "
                            "Read-only cluster access only."
                        ),
                    },
                    {"role": "user", "content": _format_incident(data)},
                ]
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
