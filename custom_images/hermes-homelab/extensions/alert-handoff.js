/**
 * Homelab alert deep-link: ?incident=<id>&autostart=1
 * Fetches incident JSON from /homelab/api/incidents/<id>, then either:
 * - autostart: new session + send() so Hermes begins triage immediately
 * - review: prefill composer only
 *
 * Persists pending incident in sessionStorage so login redirects can resume.
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

  sessionStorage.setItem("homelab_pending_incident_id", incidentId);
  sessionStorage.setItem("homelab_pending_autostart", autostart ? "1" : "0");

  const apiUrl =
    "/homelab/api/incidents/" + encodeURIComponent(incidentId);

  function formatAlert(data) {
    const alert = (data && data.alert) || {};
    const labels = alert.labels || {};
    const ann = alert.annotations || {};
    const parts = [
      "Homelab on-call triage for alert `" + (labels.alertname || "unknown") + "`",
      "namespace: `" + (labels.namespace || "n/a") + "`",
      "severity: `" + (labels.severity || "n/a") + "`",
    ];
    if (labels.job_name) parts.push("job: `" + labels.job_name + "`");
    if (labels.pod) parts.push("pod: `" + labels.pod + "`");
    if (ann.summary) parts.push("\nSummary: " + ann.summary);
    if (ann.description) parts.push("\n" + ann.description);
    if (ann.runbook_url) parts.push("\nRunbook: " + ann.runbook_url);
    parts.push(
      "\n\nInvestigate with read-only kubectl/flux, cite the runbook, and propose a resolution plan.",
      "Do not apply cluster changes yourself."
    );
    return parts.join("\n");
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
    try {
      const clean = new URL(window.location.href);
      clean.searchParams.delete("incident");
      clean.searchParams.delete("autostart");
      window.history.replaceState({}, "", clean.toString());
    } catch (e) {
      /* ignore */
    }
  }

  function waitForWebUI(timeoutMs) {
    return new Promise(function (resolve, reject) {
      const deadline = Date.now() + timeoutMs;
      (function poll() {
        const msg = document.getElementById("msg");
        const ready =
          msg &&
          typeof window.send === "function" &&
          typeof window.newSession === "function";
        if (ready) {
          resolve();
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error("Hermes WebUI did not become ready"));
          return;
        }
        setTimeout(poll, 200);
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

  async function startTriage(text) {
    await window.newSession(false, {});
    if (typeof window.renderSessionList === "function") {
      await window.renderSessionList();
    }
    if (!setComposerText(text)) {
      throw new Error("composer input not found");
    }
    await window.send();
  }

  showBanner(
    autostart
      ? "Loading alert and starting Hermes triage…"
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

      if (autostart) {
        return waitForWebUI(120000)
          .then(function () {
            showBanner("Starting on-call triage…");
            return startTriage(text);
          })
          .then(function () {
            clearPending();
            showBanner(
              "On-call triage started — Hermes is investigating. Use Stop to cancel."
            );
          });
      }

      return waitForWebUI(120000)
        .then(function () {
          if (setComposerText(text)) {
            clearPending();
            showBanner("Alert context loaded — review and send.");
            return;
          }
          throw new Error("composer input not found");
        })
        .catch(function () {
          showBanner(
            "Alert loaded — log in if needed, open a new chat, and send when ready."
          );
        });
    })
    .catch(function (err) {
      showBanner("Could not load incident " + incidentId + ": " + err.message);
    });
})();
