"""Minimal server-rendered incident UI (no frontend build)."""

from __future__ import annotations

import html
import json
from typing import Any
from urllib.parse import quote


def _esc(value: Any) -> str:
    return html.escape(str(value) if value is not None else "")


def _status_badge(status: str) -> str:
    return f'<span class="badge status-{ _esc(status) }">{ _esc(status) }</span>'


def _severity_badge(severity: str | None) -> str:
    sev = severity or "unknown"
    return f'<span class="badge severity-{ _esc(sev) }">{ _esc(sev) }</span>'


PAGE_SIZE = 25


def render_incident_rows(incidents: list[dict[str, Any]]) -> str:
    if not incidents:
        return ""
    rows = []
    for incident in incidents:
        iid = incident["id"]
        rows.append(
            f"""
            <div class="incident-row">
              <input class="row-check" type="checkbox" name="incident_id" value="{_esc(iid)}">
              <div>
                <a class="row-title" href="/incidents/{_esc(iid)}">{_esc(incident.get('title') or iid)}</a>
                <div class="muted">{_esc(iid)}</div>
              </div>
              <div>{_status_badge(str(incident.get('status') or 'open'))}</div>
              <div>{_severity_badge(incident.get('severity'))}</div>
              <div class="muted">{_esc(incident.get('updated_at') or '')}</div>
              <div><a href="/incidents/{_esc(iid)}">view →</a></div>
            </div>
            """
        )
    return "\n".join(rows)


def render_alert_rows(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return ""
    rows = []
    for alert in alerts:
        fp = str(alert.get("fingerprint") or "")
        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}
        title = annotations.get("summary") or labels.get("alertname") or fp
        rows.append(
            f"""
            <div class="incident-row">
              <input class="row-check" type="checkbox" name="fingerprint" value="{_esc(fp)}">
              <div>
                <strong class="row-title">{_esc(title)}</strong>
                <div class="muted">{_esc(labels.get('alertname', ''))} · {_esc(labels.get('namespace', ''))}</div>
              </div>
              <div>{_status_badge(str(alert.get('status') or 'firing'))}</div>
              <div>{_severity_badge(labels.get('severity'))}</div>
              <div class="muted">{_esc(alert.get('_updated_at') or '')}</div>
              <div>
                <button formaction="/alerts/{_esc(fp)}/raise" formmethod="post" type="submit">Raise</button>
              </div>
            </div>
            """
        )
    return "\n".join(rows)


def _lazy_list_script(*, kind: str, api_path: str, status_filter: str, checkbox_name: str, empty_message: str) -> str:
    placeholder = (
        'status:open severity>=warning title~"flux"'
        if kind == "incidents"
        else 'status:firing alertname:Homelab* namespace:flux-system'
    )
    return f"""
    <script>
    (function() {{
      const pageSize = {PAGE_SIZE};
      const apiPath = {json.dumps(api_path)};
      const checkboxName = {json.dumps(checkbox_name)};
      const emptyMessage = {json.dumps(empty_message)};
      let offset = 0;
      let hasMore = true;
      let loading = false;
      let statusFilter = {json.dumps(status_filter)};
      let query = new URLSearchParams(window.location.search).get("q") || "";

      const rowsEl = document.getElementById("lazy-rows");
      const statusEl = document.getElementById("list-status");
      const searchEl = document.getElementById("list-search");
      let sentinelEl = document.getElementById("scroll-sentinel");
      const selectAllEl = document.getElementById("select-all");
      let scrollObserver = null;
      let scrollBound = false;

      function ensureSentinel() {{
        if (!rowsEl) return null;
        if (!sentinelEl) {{
          sentinelEl = document.createElement("div");
          sentinelEl.id = "scroll-sentinel";
          sentinelEl.className = "scroll-sentinel";
          sentinelEl.setAttribute("aria-hidden", "true");
        }}
        rowsEl.appendChild(sentinelEl);
        return sentinelEl;
      }}

      function tailInView() {{
        const sentinel = ensureSentinel();
        if (!sentinel) return false;
        const rect = sentinel.getBoundingClientRect();
        return rect.top <= window.innerHeight + 320;
      }}

      function maybeLoadMore() {{
        if (hasMore && !loading && tailInView()) {{
          loadRows(true);
        }}
      }}

      function bindInfiniteScroll() {{
        const sentinel = ensureSentinel();
        if (!sentinel || !hasMore) return;

        if ("IntersectionObserver" in window) {{
          if (scrollObserver) scrollObserver.disconnect();
          scrollObserver = new IntersectionObserver(
            (entries) => {{
              if (entries.some((entry) => entry.isIntersecting)) {{
                maybeLoadMore();
              }}
            }},
            {{ root: null, rootMargin: "320px 0px", threshold: 0 }}
          );
          scrollObserver.observe(sentinel);
        }}

        if (!scrollBound) {{
          window.addEventListener("scroll", maybeLoadMore, {{ passive: true }});
          window.addEventListener("resize", maybeLoadMore, {{ passive: true }});
          scrollBound = true;
        }}
      }}

      function stopInfiniteScroll() {{
        if (scrollObserver) {{
          scrollObserver.disconnect();
          scrollObserver = null;
        }}
      }}

      function scheduleTailCheck() {{
        requestAnimationFrame(() => requestAnimationFrame(maybeLoadMore));
      }}

      if (searchEl) {{
        searchEl.value = query;
        let debounce = null;
        searchEl.addEventListener("input", () => {{
          clearTimeout(debounce);
          debounce = setTimeout(() => {{
            query = searchEl.value.trim();
            const url = new URL(window.location.href);
            if (query) url.searchParams.set("q", query); else url.searchParams.delete("q");
            window.history.replaceState({{}}, "", url);
            offset = 0;
            loadRows(false);
          }}, 300);
        }});
      }}

      document.querySelectorAll("[data-status-filter]").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          statusFilter = btn.getAttribute("data-status-filter") || "";
          document.querySelectorAll("[data-status-filter]").forEach((b) => b.classList.remove("primary"));
          btn.classList.add("primary");
          offset = 0;
          loadRows(false);
        }});
      }});

      if (selectAllEl) {{
        selectAllEl.addEventListener("change", (e) => {{
          document.querySelectorAll(`input[name="${{checkboxName}}"]`).forEach((cb) => {{
            cb.checked = e.target.checked;
          }});
        }});
      }}

      function setupInfiniteScroll() {{
        if (hasMore) {{
          bindInfiniteScroll();
          scheduleTailCheck();
        }} else {{
          stopInfiniteScroll();
        }}
      }}

      async function loadRows(append) {{
        if (loading) return;
        loading = true;
        if (!append) {{
          offset = 0;
          hasMore = true;
          rowsEl.innerHTML = '<div class="panel muted">Loading…</div>';
        }} else {{
          ensureSentinel()?.classList.add("loading-more");
        }}
        if (!append) statusEl.textContent = "Loading…";
        try {{
          const params = new URLSearchParams({{
            offset: String(append ? offset : 0),
            limit: String(pageSize),
            status: statusFilter,
            q: query,
          }});
          const resp = await fetch(`${{apiPath}}?${{params}}`, {{ credentials: "same-origin" }});
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.error || "load failed");
          if (!append) rowsEl.innerHTML = "";
          if (data.html) {{
            const wrap = document.createElement("div");
            wrap.innerHTML = data.html;
            while (wrap.firstChild) rowsEl.appendChild(wrap.firstChild);
          }} else if (!append) {{
            rowsEl.innerHTML = `<div class="panel muted">${{emptyMessage}}</div>`;
          }}
          offset = data.next_offset || 0;
          hasMore = !!data.has_more;
          const loadedCount = rowsEl.querySelectorAll(".incident-row").length;
          statusEl.textContent = hasMore
            ? `Showing ${{loadedCount}} — scroll for more`
            : `Showing all ${{loadedCount}} matches`;
        }} catch (err) {{
          if (!append) rowsEl.innerHTML = `<div class="panel"><span class="badge severity-critical">${{err.message}}</span></div>`;
          statusEl.textContent = "";
          stopInfiniteScroll();
        }} finally {{
          ensureSentinel()?.classList.remove("loading-more");
          loading = false;
          setupInfiniteScroll();
        }}
      }}

      bindInfiniteScroll();
      loadRows(false);
    }})();
    </script>
    """


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
      grid-template-columns: auto 1.4fr 0.7fr 0.7fr 0.8fr auto;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel);
    }}
    .incident-row:hover {{ border-color: var(--accent); }}
    .incident-row-head {{
      display: grid;
      grid-template-columns: auto 1.4fr 0.7fr 0.7fr 0.8fr auto;
      gap: 12px;
      align-items: center;
      padding: 0 14px 8px;
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .bulk-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }}
    .search-box {{
      display: grid;
      gap: 6px;
      margin-bottom: 12px;
    }}
    .search-box input {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.92rem;
    }}
    .list-status {{ color: var(--muted); font-size: 0.9rem; margin: 8px 0; }}
    .scroll-sentinel {{
      min-height: 4px;
      width: 100%;
      pointer-events: none;
      grid-column: 1 / -1;
    }}
    .scroll-sentinel.loading-more::after {{
      content: "Loading more…";
      display: block;
      text-align: center;
      color: var(--muted);
      font-size: 0.9rem;
      padding: 12px 0 4px;
    }}
    .status-filter {{ cursor: pointer; }}
    .row-check {{ width: 18px; height: 18px; accent-color: var(--accent); }}
    .row-title {{ font-weight: 600; }}
    .flash {{ border-color: color-mix(in srgb, var(--accent) 50%, var(--border)); }}
    .agent-feed {{ display: grid; gap: 10px; max-height: 420px; overflow: auto; }}
    .agent-msg {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      background: var(--panel);
      white-space: pre-wrap;
      font-size: 0.92rem;
    }}
    .agent-msg.user {{ border-color: color-mix(in srgb, var(--accent) 40%, var(--border)); }}
    .agent-msg.assistant {{ border-color: color-mix(in srgb, var(--ok) 35%, var(--border)); }}
    .agent-msg .role {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .agent-status {{ color: var(--muted); font-size: 0.9rem; }}
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
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .actions form {{ margin: 0; display: inline-flex; }}
    .actions button, .actions .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
      min-height: 38px;
      line-height: 1.2;
    }}
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
      .incident-row, .incident-row-head {{ grid-template-columns: auto 1fr; }}
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


def error_page(message: str) -> str:
    body = f"""
    <div class="panel" style="max-width:520px;margin:48px auto;">
      <h2 style="margin-top:0;">{_esc(message)}</h2>
      <p><a href="/">← Back to incidents</a></p>
    </div>
    """
    return layout("Error", body)


def incident_list_page(
    *,
    status_filter: str,
    hermes_base: str,
    include_noise: bool = False,
    hidden_summary: str = "",
    flash_message: str = "",
    search_query: str = "",
) -> str:
    filters = []
    for status in ("", "open", "acknowledged", "resolved"):
        label = status or "all"
        active = "primary" if status == status_filter else ""
        filters.append(
            f'<button type="button" class="btn status-filter {active}" data-status-filter="{_esc(status)}">{_esc(label)}</button>'
        )

    hidden_note = ""
    if hidden_summary and not include_noise:
        hidden_note = f'<p class="muted">Hidden noise alerts: {_esc(hidden_summary)}. Enable <strong>Show noise</strong> in <a href="/settings">Settings</a>.</p>'
    flash = f'<div class="panel flash">{_esc(flash_message)}</div>' if flash_message else ""
    return_hidden = f'<input type="hidden" name="return_status" value="{_esc(status_filter)}">'

    body = f"""
    <div class="filters">
      {''.join(filters)}
      <a class="btn" href="/alerts">Alerts inbox</a>
      <a class="btn primary" href="/incidents/new">+ New incident</a>
      <a class="btn" href="/settings">Settings</a>
    </div>
    {flash}
    {hidden_note}
    <div class="panel search-box">
      <label for="list-search"><strong>Search</strong> <span class="muted">JQL-style, e.g. <code>status:open severity>=warning title~"flux"</code></span></label>
      <input id="list-search" type="search" placeholder="status:open severity>=warning title~&quot;flux&quot;" value="{_esc(search_query)}" autocomplete="off">
      <div id="list-status" class="list-status"></div>
    </div>
    <form method="post" action="/incidents/bulk" class="grid">
      {return_hidden}
      <div class="panel bulk-bar">
        <label class="muted"><input class="row-check" type="checkbox" id="select-all"> Select all</label>
        <div class="actions">
          <button type="submit" name="action" value="ack">Acknowledge</button>
          <button type="submit" name="action" value="resolve">Resolve</button>
          <button type="submit" name="action" value="reopen">Reopen</button>
          <button type="submit" name="action" value="merge" title="Merges into the first selected incident">Merge into first</button>
        </div>
      </div>
      <div class="incident-row-head">
        <span></span><span>Incident</span><span>Status</span><span>Severity</span><span>Updated</span><span></span>
      </div>
      <div id="lazy-rows" class="grid"></div>
    </form>
    {_lazy_list_script(kind="incidents", api_path="/api/list/incidents", status_filter=status_filter, checkbox_name="incident_id", empty_message="No incidents match this search.")}
    """
    return layout("Incidents", body)


def alerts_list_page(
    *,
    status_filter: str,
    flash_message: str = "",
    search_query: str = "",
) -> str:
    filters = []
    for status in ("", "firing", "resolved"):
        label = status or "all"
        active = "primary" if status == status_filter else ""
        filters.append(
            f'<button type="button" class="btn status-filter {active}" data-status-filter="{_esc(status)}">{_esc(label)}</button>'
        )

    flash = f'<div class="panel flash">{_esc(flash_message)}</div>' if flash_message else ""
    return_hidden = f'<input type="hidden" name="return_status" value="{_esc(status_filter)}">'

    body = f"""
    <p><a href="/">← Incidents</a></p>
    <div class="filters">
      {''.join(filters)}
      <a class="btn primary" href="/">Incidents</a>
      <a class="btn" href="/settings">Settings</a>
    </div>
    {flash}
    <p class="muted">Alertmanager → <strong>alerts inbox</strong> → raise incident (manual or auto-raise rules in Settings).</p>
    <div class="panel search-box">
      <label for="list-search"><strong>Search</strong> <span class="muted">JQL-style, e.g. <code>status:firing alertname:Homelab* namespace:flux-system</code></span></label>
      <input id="list-search" type="search" placeholder="status:firing alertname:Homelab* text~&quot;disk&quot;" value="{_esc(search_query)}" autocomplete="off">
      <div id="list-status" class="list-status"></div>
    </div>
    <form method="post" action="/alerts/raise" class="grid">
      {return_hidden}
      <div class="panel bulk-bar">
        <label class="muted"><input class="row-check" type="checkbox" id="select-all"> Select all</label>
        <input name="title" placeholder="Incident title (optional)" style="max-width:280px;">
        <div class="actions">
          <button class="primary" type="submit">Raise incident</button>
        </div>
      </div>
      <div class="incident-row-head">
        <span></span><span>Alert</span><span>Status</span><span>Severity</span><span>Updated</span><span></span>
      </div>
      <div id="lazy-rows" class="grid"></div>
    </form>
    {_lazy_list_script(kind="alerts", api_path="/api/list/alerts", status_filter=status_filter, checkbox_name="fingerprint", empty_message="No alerts match this search.")}
    """
    return layout("Alerts", body)


def create_incident_page(*, error: str = "") -> str:
    err = f'<div class="panel"><span class="badge severity-critical">{_esc(error)}</span></div>' if error else ""
    body = f"""
    <p><a href="/">← All incidents</a></p>
    {err}
    <div class="panel">
      <h2 style="margin-top:0;">New incident</h2>
      <p class="muted">Create a manual ticket — useful for tracking work that did not come from an alert.</p>
      <form method="post" action="/incidents/new" class="grid">
        <input name="title" placeholder="Title" required autofocus>
        <textarea name="summary" placeholder="What is going on?"></textarea>
        <select name="severity">
          <option value="critical">critical</option>
          <option value="warning" selected>warning</option>
          <option value="info">info</option>
          <option value="unknown">unknown</option>
        </select>
        <input name="tags" placeholder="Tags (comma-separated)">
        <textarea name="note" placeholder="Initial note (optional)"></textarea>
        <div class="actions">
          <button class="primary" type="submit">Create incident</button>
          <a class="btn" href="/">Cancel</a>
        </div>
      </form>
    </div>
    """
    return layout("New incident", body)


def _agent_panel_script(iid: str, hermes: dict[str, Any], *, auto_investigate: bool = False) -> str:
    session_id = str(hermes.get("session_id") or "")
    stream_id = str(hermes.get("stream_id") or "")
    status = str(hermes.get("status") or "")
    return f"""
    <script>
    (function() {{
      const incidentId = {json.dumps(iid)};
      const sessionId = {json.dumps(session_id)};
      const streamId = {json.dumps(stream_id)};
      const status = {json.dumps(status)};
      const autoInvestigate = {json.dumps(auto_investigate)};
      const feedEl = document.getElementById("agent-feed");
      const statusEl = document.getElementById("agent-status");
      let streamSource = null;

      function renderMessages(messages) {{
        if (!feedEl) return;
        feedEl.innerHTML = "";
        if (!messages || !messages.length) {{
          feedEl.innerHTML = '<div class="muted">No agent messages yet.</div>';
          return;
        }}
        for (const msg of messages) {{
          const role = msg.role || "message";
          const block = document.createElement("div");
          block.className = "agent-msg " + role;
          const roleEl = document.createElement("div");
          roleEl.className = "role";
          roleEl.textContent = role;
          const bodyEl = document.createElement("div");
          bodyEl.textContent = msg.content || "";
          block.appendChild(roleEl);
          block.appendChild(bodyEl);
          feedEl.appendChild(block);
        }}
        feedEl.scrollTop = feedEl.scrollHeight;
      }}

      async function refreshSession() {{
        try {{
          const resp = await fetch("/api/incidents/" + encodeURIComponent(incidentId) + "/agent/session", {{
            credentials: "same-origin",
          }});
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const data = await resp.json();
          renderMessages(data.messages || []);
          if (statusEl) {{
            statusEl.textContent = data.status === "running"
              ? "Agent is investigating…"
              : (data.messages && data.messages.length ? "Agent session ready" : "Waiting for agent output");
          }}
        }} catch (err) {{
          if (statusEl) statusEl.textContent = "Could not load agent feed: " + err.message;
        }}
      }}

      function connectStream() {{
        if (!streamId || status !== "running") return;
        if (streamSource) streamSource.close();
        streamSource = new EventSource(
          "/api/incidents/" + encodeURIComponent(incidentId) + "/agent/stream?stream_id=" + encodeURIComponent(streamId)
        );
        if (statusEl) statusEl.textContent = "Streaming agent response…";
        streamSource.onmessage = () => refreshSession();
        streamSource.addEventListener("end", () => {{
          streamSource.close();
          refreshSession();
        }});
        streamSource.onerror = () => {{
          streamSource.close();
          refreshSession();
        }};
      }}

      if (autoInvestigate && !sessionId) {{
        window.location.replace("/incidents/" + encodeURIComponent(incidentId) + "/investigate");
        return;
      }}

      if (sessionId) {{
        refreshSession();
        connectStream();
        if (status !== "running") {{
          window.setInterval(refreshSession, 5000);
        }}
      }}
    }})();
    </script>
    """


def incident_detail_page(
    incident: dict[str, Any],
    *,
    hermes_base: str,
    message: str = "",
    auto_investigate: bool = False,
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

    hermes = (incident.get("enrichment") or {}).get("hermes") or {}
    hermes_session_id = str(hermes.get("session_id") or "")
    hermes_status = str(hermes.get("status") or "")

    investigate_btn = (
        f'<form method="post" action="/incidents/{_esc(iid)}/investigate">'
        f'<button class="primary" type="submit">Investigate</button></form>'
    )
    if hermes_session_id:
        investigate_btn += (
            f'<form method="post" action="/incidents/{_esc(iid)}/investigate">'
            f'<input type="hidden" name="force" value="1">'
            f'<button type="submit">New investigation</button></form>'
        )

    hermes_link = ""
    if hermes_base and hermes_session_id:
        hermes_url = f"{hermes_base.rstrip('/')}/?session_id={quote(hermes_session_id)}"
        hermes_link = f'<a class="btn" href="{_esc(hermes_url)}" target="_blank" rel="noopener">Open in Hermes</a>'

    agent_status = ""
    if hermes_session_id:
        agent_status = f'<div id="agent-status" class="agent-status">Status: {_esc(hermes_status or "unknown")}</div>'
    else:
        agent_status = '<div id="agent-status" class="agent-status">No agent session yet — start an investigation.</div>'

    agent_panel = f"""
    <div class="panel" id="agent">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;">
        <h3 style="margin:0;">Agent</h3>
        <div class="actions">
          {investigate_btn}
          {hermes_link}
        </div>
      </div>
      {agent_status}
      <div id="agent-feed" class="agent-feed" style="margin-top:12px;"></div>
    </div>
    {_agent_panel_script(iid, hermes, auto_investigate=auto_investigate)}
    """

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
    manual_badge = '<span class="badge">manual</span>' if (incident.get("enrichment") or {}).get("manual") else ""

    body = f"""
    <p><a href="/">← All incidents</a></p>
    {msg}
    {merged_banner}
    <div class="panel">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div>
          <h2 style="margin:0 0 8px;">{_esc(incident.get('title') or iid)}</h2>
          <div class="muted">{_esc(iid)} · updated {_esc(incident.get('updated_at'))}</div>
          <div style="margin-top:8px;">{_status_badge(status)} {_severity_badge(incident.get('severity'))} {manual_badge}</div>
        </div>
        <div class="actions">
          {''.join(action_buttons)}
        </div>
      </div>
      {f'<p>{_esc(incident.get("summary") or "")}</p>' if incident.get("summary") else ''}
      {f'<p class="muted">Tags: {tag_str}</p>' if tags else ''}
    </div>

    {agent_panel}

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


def settings_page(
    notifications: dict[str, Any],
    raise_settings: dict[str, Any],
    *,
    flash_message: str = "",
) -> str:
    events = notifications.get("events") or {}
    flash = f'<div class="panel flash">{_esc(flash_message)}</div>' if flash_message else ""
    alertnames = ", ".join(raise_settings.get("alertnames") or [])
    label_rules = json.dumps(raise_settings.get("label_rules") or [], indent=2)

    def event_checkbox(name: str, label: str, hint: str) -> str:
        checked = "checked" if events.get(name, False) else ""
        return f"""
        <label class="event-toggle">
          <input type="checkbox" name="event_{_esc(name)}" {checked}>
          <span><strong>{_esc(label)}</strong><br><span class="muted">{_esc(hint)}</span></span>
        </label>
        """

    body = f"""
    <p><a href="/">Incidents</a> · <a href="/alerts">Alerts inbox</a></p>
    {flash}
    <div class="panel">
      <h2 style="margin-top:0;">Display</h2>
      <form method="post" action="/settings/display" class="grid">
        <label class="event-toggle">
          <input type="checkbox" name="show_noise" {"checked" if notifications.get("show_noise") else ""}>
          <span><strong>Show noise on incident list</strong><br><span class="muted">Include Watchdog, InfoInhibitor, and other filtered alerts in the incidents view</span></span>
        </label>
        <div class="actions"><button class="primary" type="submit">Save display</button></div>
      </form>
    </div>
    <div class="panel">
      <h2 style="margin-top:0;">Auto-raise rules</h2>
      <p class="muted">
        Alertmanager webhooks land in the <strong>alerts inbox</strong> first.
        Matching rules automatically raise an incident and attach the alert.
      </p>
      <form method="post" action="/settings/raise" class="grid">
        <label class="event-toggle">
          <input type="checkbox" name="raise_enabled" {"checked" if raise_settings.get("enabled", True) else ""}>
          <span><strong>Auto-raise enabled</strong></span>
        </label>
        <label class="event-toggle">
          <input type="checkbox" name="group_open" {"checked" if raise_settings.get("group_open", True) else ""}>
          <span><strong>Group into open incidents</strong><br><span class="muted">Attach to an open incident with the same alertname + namespace</span></span>
        </label>
        <select name="min_severity">
          {''.join(f'<option value="{_esc(s)}" {"selected" if raise_settings.get("min_severity")==s else ""}>{_esc(s)} and above</option>' for s in ("critical", "warning", "info", "unknown"))}
        </select>
        <input name="alertnames" placeholder="Alertnames only (comma-separated, empty = all)" value="{_esc(alertnames)}">
        <textarea name="label_rules" placeholder='Label rules JSON e.g. [{{"alertname":"Foo","namespace":"bar"}}]'>{_esc(label_rules)}</textarea>
        <div class="actions"><button class="primary" type="submit">Save auto-raise</button></div>
      </form>
    </div>
    <div class="panel">
      <h2 style="margin-top:0;">Notification settings</h2>
      <p class="muted">When an incident is raised or updated, notifications flow <strong>incident → ntfy</strong>.</p>
      <form method="post" action="/settings" class="grid">
        <label class="event-toggle">
          <input type="checkbox" name="enabled" {"checked" if notifications.get("enabled", True) else ""}>
          <span><strong>Notifications enabled</strong><br><span class="muted">Master switch for all ntfy posts</span></span>
        </label>
        <input name="topic" placeholder="ntfy topic" value="{_esc(notifications.get('topic') or '')}" required>
        <div class="panel" style="margin:0;">
          <h3 style="margin-top:0;">Notify on</h3>
          <div class="grid">
            {event_checkbox("created", "New incident", "Incident raised from alert(s) or manual create")}
            {event_checkbox("updated", "Incident updated", "More alerts attached or severity changes")}
            {event_checkbox("resolved", "Resolved", "All alerts cleared or you resolve from UI")}
            {event_checkbox("reopened", "Reopened", "Firing alert returns after resolve")}
            {event_checkbox("manual", "Manual incident", "You create a ticket without alerts")}
            {event_checkbox("acknowledged", "Acknowledged", "Ack from UI or bulk actions")}
            {event_checkbox("merged", "Merged", "Incidents combined in UI")}
          </div>
        </div>
        <div class="actions">
          <button class="primary" type="submit">Save notifications</button>
        </div>
      </form>
    </div>
    <style>
      .event-toggle {{
        display: flex;
        gap: 12px;
        align-items: flex-start;
        padding: 10px 0;
        border-bottom: 1px solid var(--border);
      }}
      .event-toggle:last-child {{ border-bottom: 0; }}
      .event-toggle input {{ width: auto; margin-top: 4px; }}
    </style>
    """
    return layout("Settings", body)
