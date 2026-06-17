"""Minimal server-rendered incident UI (no frontend build)."""

from __future__ import annotations

import html
from typing import Any
from urllib.parse import quote


def _esc(value: Any) -> str:
    return html.escape(str(value) if value is not None else "")


def _status_badge(status: str) -> str:
    return f'<span class="badge status-{ _esc(status) }">{ _esc(status) }</span>'


def _severity_badge(severity: str | None) -> str:
    sev = severity or "unknown"
    return f'<span class="badge severity-{ _esc(sev) }">{ _esc(sev) }</span>'


def layout(title: str, body: str, *, public_base: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)} · Homelab Incidents</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1419;
      --panel: #1a2332;
      --panel-2: #243044;
      --text: #e7edf5;
      --muted: #9fb0c3;
      --accent: #4da3ff;
      --ok: #3ecf8e;
      --warn: #f5c451;
      --crit: #ff6b6b;
      --border: #2d3b52;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.5 ui-sans-serif, system-ui, sans-serif;
      background: radial-gradient(circle at top, #172033, var(--bg));
      color: var(--text);
      min-height: 100vh;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }}
    header {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 16px; margin-bottom: 24px;
    }}
    header h1 {{ margin: 0; font-size: 1.35rem; letter-spacing: 0.02em; }}
    .panel {{
      background: color-mix(in srgb, var(--panel) 92%, transparent);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
      backdrop-filter: blur(8px);
    }}
    .grid {{ display: grid; gap: 12px; }}
    .incident-row {{
      display: grid;
      grid-template-columns: 1.4fr 0.7fr 0.7fr 0.8fr auto;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel);
    }}
    .incident-row:hover {{ border-color: var(--accent); }}
    .muted {{ color: var(--muted); font-size: 0.92rem; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      border: 1px solid var(--border);
      background: var(--panel-2);
    }}
    .status-open {{ color: var(--warn); border-color: color-mix(in srgb, var(--warn) 50%, var(--border)); }}
    .status-acknowledged {{ color: var(--accent); }}
    .status-resolved {{ color: var(--ok); border-color: color-mix(in srgb, var(--ok) 50%, var(--border)); }}
    .status-merged {{ color: var(--muted); }}
    .severity-critical {{ color: var(--crit); }}
    .severity-warning {{ color: var(--warn); }}
    .severity-info {{ color: var(--accent); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    button, .btn {{
      appearance: none;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 10px;
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
    }}
    button.primary, .btn.primary {{ background: color-mix(in srgb, var(--accent) 25%, var(--panel-2)); border-color: var(--accent); }}
    button.danger {{ border-color: color-mix(in srgb, var(--crit) 50%, var(--border)); }}
    input, textarea, select {{
      width: 100%;
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
    }}
    textarea {{ min-height: 96px; resize: vertical; }}
    .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
    .timeline {{ display: grid; gap: 10px; }}
    .event {{
      border-left: 2px solid var(--border);
      padding-left: 12px;
    }}
    .alert-card {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      background: var(--panel);
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.85rem;
    }}
    .two-col {{ display: grid; gap: 16px; }}
    @media (min-width: 900px) {{ .two-col {{ grid-template-columns: 1.2fr 0.8fr; }} }}
    @media (max-width: 800px) {{
      .incident-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Homelab Incidents</h1>
      <div class="muted">Alert funnel + ticketing</div>
    </header>
    {body}
  </div>
</body>
</html>"""


def login_page(error: str = "") -> str:
    err = f'<p class="badge severity-critical">{_esc(error)}</p>' if error else ""
    body = f"""
    <div class="panel" style="max-width:420px;margin:48px auto;">
      <h2 style="margin-top:0;">Sign in</h2>
      <p class="muted">Use your incidents API token.</p>
      {err}
      <form method="post" action="/login" class="grid">
        <input type="password" name="token" placeholder="Token" required autofocus>
        <button class="primary" type="submit">Continue</button>
      </form>
    </div>
    """
    return layout("Sign in", body)


def incident_list_page(
    incidents: list[dict[str, Any]],
    *,
    status_filter: str,
    hermes_base: str,
) -> str:
    filters = []
    for status in ("", "open", "acknowledged", "resolved"):
        label = status or "all"
        active = "primary" if status == status_filter else ""
        filters.append(f'<a class="btn {active}" href="/?status={quote(status)}">{_esc(label)}</a>')

    rows = []
    for incident in incidents:
        iid = incident["id"]
        rows.append(
            f"""
            <a class="incident-row" href="/incidents/{_esc(iid)}">
              <div>
                <strong>{_esc(incident.get('title') or iid)}</strong>
                <div class="muted">{_esc(iid)}</div>
              </div>
              <div>{_status_badge(str(incident.get('status') or 'open'))}</div>
              <div>{_severity_badge(incident.get('severity'))}</div>
              <div class="muted">{_esc(incident.get('updated_at') or '')}</div>
              <div class="muted">view →</div>
            </a>
            """
        )

    rows_html = "\n".join(rows) if rows else '<div class="panel muted">No incidents yet.</div>'
    body = f"""
    <div class="filters">{''.join(filters)}</div>
    <div class="grid">{rows_html}</div>
    """
    return layout("Incidents", body)


def incident_detail_page(
    incident: dict[str, Any],
    *,
    hermes_base: str,
    message: str = "",
) -> str:
    iid = incident["id"]
    status = str(incident.get("status") or "open")
    tags = (incident.get("enrichment") or {}).get("tags") or []
    notes = (incident.get("enrichment") or {}).get("notes") or []
    merged_into = incident.get("merged_into_id")

    action_buttons = []
    if status == "open":
        action_buttons.append(f'<form method="post" action="/incidents/{_esc(iid)}/ack"><button class="primary" type="submit">Acknowledge</button></form>')
    if status in ("open", "acknowledged"):
        action_buttons.append(f'<form method="post" action="/incidents/{_esc(iid)}/resolve"><button type="submit">Resolve</button></form>')
    if status == "resolved":
        action_buttons.append(f'<form method="post" action="/incidents/{_esc(iid)}/reopen"><button type="submit">Reopen</button></form>')

    hermes_link = ""
    if hermes_base:
        hermes_link = f'<a class="btn primary" href="{_esc(hermes_base)}/?incident={_esc(iid)}&autostart=1" target="_blank" rel="noopener">Ask AI</a>'

    alert_cards = []
    for alert in incident.get("alerts") or []:
        labels = alert.get("labels") or {}
        title = labels.get("alertname", "alert")
        alert_cards.append(
            f"""
            <div class="alert-card">
              <div><strong>{_esc(title)}</strong> · {_esc(alert.get('status'))}</div>
              <div class="muted">fingerprint: {_esc(alert.get('fingerprint'))}</div>
              <div>{_esc((alert.get('annotations') or {}).get('description') or (alert.get('annotations') or {}).get('summary') or '')}</div>
            </div>
            """
        )

    events = []
    for event in incident.get("events") or []:
        detail = event.get("detail") or {}
        extra = ""
        if event.get("event_type") == "note_added":
            extra = _esc(detail.get("body", ""))
        elif event.get("event_type") == "merged":
            extra = f"into {_esc(detail.get('into', ''))}"
        events.append(
            f"""
            <div class="event">
              <div><strong>{_esc(event.get('event_type'))}</strong> <span class="muted">{_esc(event.get('created_at'))}</span></div>
              <div class="muted">{_esc(event.get('actor') or 'system')} {extra}</div>
            </div>
            """
        )

    note_items = []
    for note in notes:
        note_items.append(
            f'<div class="event"><div>{_esc(note.get("body"))}</div><div class="muted">{_esc(note.get("actor"))} · {_esc(note.get("created_at"))}</div></div>'
        )

    msg = f'<div class="panel">{_esc(message)}</div>' if message else ""
    merged_banner = ""
    if merged_into:
        merged_banner = f'<div class="panel">Merged into <a href="/incidents/{_esc(merged_into)}">{_esc(merged_into)}</a></div>'

    tag_str = ", ".join(_esc(t) for t in tags)

    body = f"""
    <p><a href="/">← All incidents</a></p>
    {msg}
    {merged_banner}
    <div class="panel">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div>
          <h2 style="margin:0 0 8px;">{_esc(incident.get('title') or iid)}</h2>
          <div class="muted">{_esc(iid)} · updated {_esc(incident.get('updated_at'))}</div>
          <div style="margin-top:8px;">{_status_badge(status)} {_severity_badge(incident.get('severity'))}</div>
        </div>
        <div class="actions">
          {''.join(action_buttons)}
          {hermes_link}
        </div>
      </div>
      {f'<p>{_esc(incident.get("summary") or "")}</p>' if incident.get("summary") else ''}
      {f'<p class="muted">Tags: {tag_str}</p>' if tags else ''}
    </div>

    <div class="two-col">
      <div class="panel">
        <h3>Alerts ({len(incident.get('alerts') or [])})</h3>
        <div class="grid">{''.join(alert_cards) or '<div class="muted">No alerts attached.</div>'}</div>
      </div>
      <div class="grid">
        <div class="panel">
          <h3>Enrich</h3>
          <form method="post" action="/incidents/{_esc(iid)}/enrich" class="grid">
            <input name="title" placeholder="Title" value="{_esc(incident.get('title') or '')}">
            <textarea name="summary" placeholder="Summary">{_esc(incident.get('summary') or '')}</textarea>
            <select name="severity">
              {''.join(f'<option value="{_esc(s)}" {"selected" if incident.get("severity")==s else ""}>{_esc(s)}</option>' for s in ("critical", "warning", "info", "unknown"))}
            </select>
            <input name="tags" placeholder="Tags (comma-separated)" value="{_esc(", ".join(tags))}">
            <button class="primary" type="submit">Save</button>
          </form>
        </div>
        <div class="panel">
          <h3>Add note</h3>
          <form method="post" action="/incidents/{_esc(iid)}/notes" class="grid">
            <textarea name="body" placeholder="What did you try? What worked?" required></textarea>
            <button type="submit">Add note</button>
          </form>
        </div>
        <div class="panel">
          <h3>Merge into this incident</h3>
          <form method="post" action="/incidents/{_esc(iid)}/merge" class="grid">
            <input name="source_ids" placeholder="Source incident IDs (comma-separated)" required>
            <button type="submit">Merge</button>
          </form>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div class="panel">
        <h3>Timeline</h3>
        <div class="timeline">{''.join(events) or '<div class="muted">No events yet.</div>'}</div>
      </div>
      <div class="panel">
        <h3>Notes</h3>
        <div class="timeline">{''.join(note_items) or '<div class="muted">No notes yet.</div>'}</div>
      </div>
    </div>
    """
    return layout(incident.get("title") or iid, body)
