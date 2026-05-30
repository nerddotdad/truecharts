/**
 * Homelab alert deep-link: ?incident=<id>&autostart=1
 * Waits for Hermes WebUI boot to finish, then loads incident context and optionally
 * starts triage via newSession() + send().
 */
(function () {
  "use strict";

  if (window.__homelabAlertHandoffInit) return;
  window.__homelabAlertHandoffInit = true;

  const params = new URLSearchParams(window.location.search);
  let incidentId = params.get("incident");
  let autostart =
    params.get("autostart") === "1" || params.get("autostart") === "true";

  if (!incidentId) {
    incidentId = sessionStorage.getItem("homelab_pending_incident_id");
    autostart = sessionStorage.getItem("homelab_pending_autostart") === "1";
  }
  if (!incidentId) return;

  const handoffKey = "homelab_handoff_done_" + incidentId;
  if (sessionStorage.getItem(handoffKey) === "1") return;

  sessionStorage.setItem("homelab_pending_incident_id", incidentId);
  sessionStorage.setItem("homelab_pending_autostart", autostart ? "1" : "0");

  const apiUrl =
    "/homelab/api/incidents/" + encodeURIComponent(incidentId);

  function recommendedSkillsLine(ann) {
    const raw = (ann && (ann.recommended_ai_skills || ann.recommended_skills)) || "";
    const skills = String(raw)
      .split(",")
      .map(function (s) {
        return s.trim();
      })
      .filter(Boolean);
    if (!skills.length) return "";
    return "\nRecommended skills: " + skills.join(", ");
  }

  function formatAlert(data) {
    if (data && data.hermes_message) {
      return data.hermes_message;
    }
    if (data && data.operator_message) {
      return data.operator_message;
    }
    // Legacy incidents without bridge-rendered messages.
    const alert = (data && data.alert) || {};
    const labels = alert.labels || {};
    const ann = alert.annotations || {};
    const parts = [
      "Homelab alert `" + (labels.alertname || "unknown") + "`",
      "namespace: `" + (labels.namespace || "n/a") + "`",
      "severity: `" + (labels.severity || "n/a") + "`",
    ];
    if (labels.job_name) parts.push("job: `" + labels.job_name + "`");
    if (labels.pod) parts.push("pod: `" + labels.pod + "`");
    if (ann.summary) parts.push("\nSummary: " + ann.summary);
    if (ann.description) parts.push("\n" + ann.description);
    if (ann.runbook_url) parts.push("\nRunbook: " + ann.runbook_url);
    const skillsLine = recommendedSkillsLine(ann);
    if (skillsLine) parts.push(skillsLine);
    return parts.join("\n");
  }

  /** Sidebar title: prefer Prometheus summary, else alertname (+ namespace). */
  function sessionTitleFromIncident(data) {
    const alert = (data && data.alert) || {};
    const labels = alert.labels || {};
    const ann = alert.annotations || {};
    let title = String(ann.summary || "").replace(/\s+/g, " ").trim();
    if (!title) {
      const name = labels.alertname || "unknown alert";
      const ns = labels.namespace;
      title = ns ? name + " (" + ns + ")" : name;
    }
    if (title.length > 100) title = title.slice(0, 97) + "...";
    return title;
  }

  async function renameActiveSession(title) {
    const session =
      (window.S && window.S.session) ||
      (typeof S !== "undefined" && S && S.session) ||
      null;
    if (!session || !session.session_id) {
      throw new Error("no active session to rename");
    }
    const res = await fetch("/api/session/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ session_id: session.session_id, title: title }),
    });
    if (!res.ok) {
      throw new Error("session rename HTTP " + res.status);
    }
    session.title = title;
    if (window.S && window.S.session) window.S.session.title = title;
    if (typeof window.syncTopbar === "function") window.syncTopbar();
    if (typeof window.renderSessionList === "function") {
      await window.renderSessionList();
    }
  }

  function showBanner(text) {
    let bar = document.getElementById("homelab-incident-banner");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "homelab-incident-banner";
      bar.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:9999;padding:10px 14px;" +
        "background:#3b2e5a;color:#f5f0ff;font:14px/1.4 system-ui,sans-serif;" +
        "border-bottom:1px solid #6b4fa0;max-height:40vh;overflow:auto;";
      document.body.prepend(bar);
    }
    bar.textContent = text;
  }

  function clearPending() {
    sessionStorage.removeItem("homelab_pending_incident_id");
    sessionStorage.removeItem("homelab_pending_autostart");
    sessionStorage.setItem(handoffKey, "1");
    try {
      const clean = new URL(window.location.href);
      clean.searchParams.delete("incident");
      clean.searchParams.delete("autostart");
      window.history.replaceState({}, "", clean.toString());
    } catch (e) {
      /* ignore */
    }
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  /**
   * Hermes boot sets S._bootReady in ui.js, but S is not assigned to window — only
   * poll DOM side effects (model chip label, empty state, topbar) after APIs exist.
   */
  function isHermesBootReady() {
    const msg = document.getElementById("msg");
    if (
      !msg ||
      typeof window.newSession !== "function" ||
      typeof window.send !== "function"
    ) {
      return false;
    }
    const modelLabel = document.getElementById("composerModelLabel");
    if (modelLabel && modelLabel.textContent.trim()) return true;
    const empty = document.getElementById("emptyState");
    if (empty && empty.style.display !== "none") return true;
    const topbar = document.getElementById("topbarTitle");
    if (topbar && topbar.textContent.trim()) return true;
    return false;
  }

  function waitForBoot(timeoutMs) {
    return new Promise(function (resolve, reject) {
      const deadline = Date.now() + timeoutMs;
      (function poll() {
        if (isHermesBootReady()) {
          // Let loadSession / checkInflightOnBoot finish after _bootReady.
          setTimeout(resolve, 450);
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error("Hermes WebUI boot did not complete in time"));
          return;
        }
        setTimeout(poll, 150);
      })();
    });
  }

  function setComposerText(text) {
    const msg = document.getElementById("msg");
    if (!msg) return false;
    msg.value = text;
    msg.dispatchEvent(new Event("input", { bubbles: true }));
    if (typeof window.autoResize === "function") window.autoResize();
    return true;
  }

  async function registerPendingIncident(id) {
    const res = await fetch("/homelab/api/pending-incident", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ incident_id: id }),
    });
    if (!res.ok) {
      throw new Error("pending incident register HTTP " + res.status);
    }
  }

  async function waitForAgentReady(timeoutMs) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const res = await fetch("/api/gateway/status", {
          credentials: "same-origin",
        });
        if (res.ok) return;
      } catch (e) {
        /* retry */
      }
      await sleep(250);
    }
  }

  async function startTriage(text, incidentData) {
    await registerPendingIncident(incidentId);
    await window.newSession(true, {});
    if (typeof window.renderSessionList === "function") {
      await window.renderSessionList();
    }
    if (typeof window.renderMessages === "function") {
      window.renderMessages();
    }
    await renameActiveSession(sessionTitleFromIncident(incidentData));
    await waitForAgentReady(15000);
    await sleep(400);
    if (!setComposerText(text)) {
      throw new Error("composer input not found");
    }
    await sleep(50);
    await window.send();
  }

  showBanner(
    autostart
      ? "Loading alert — waiting for Hermes to finish starting…"
      : "Loading alert context…"
  );

  fetch(apiUrl)
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      const text = formatAlert(data);
      sessionStorage.setItem("homelab_incident_" + incidentId, text);

      return waitForBoot(120000).then(async function () {
        if (autostart) {
          showBanner("Starting on-call triage…");
          try {
            await startTriage(text, data);
            clearPending();
            showBanner(
              "On-call triage started — Hermes is investigating. Use Stop to cancel."
            );
          } catch (err) {
            setComposerText(text);
            showBanner(
              "Autostart failed: " +
                (err && err.message ? err.message : String(err)) +
                " — message restored in composer; tap Send to retry."
            );
          }
          return;
        }

        if (setComposerText(text)) {
          clearPending();
          showBanner("Alert context loaded — review and send.");
          return;
        }
        showBanner(
          "Alert loaded — open a new chat and paste if the composer is not visible."
        );
      });
    })
    .catch(function (err) {
      showBanner("Could not load incident " + incidentId + ": " + err.message);
    });
})();
