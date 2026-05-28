/**
 * Homelab alert deep-link: ?incident=<fingerprint>
 * Fetches incident JSON from /homelab/api/incidents/<id> and seeds the composer.
 */
(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const incidentId = params.get("incident");
  if (!incidentId) return;

  const apiUrl =
    "/homelab/api/incidents/" + encodeURIComponent(incidentId);

  function formatAlert(data) {
    const alert = (data && data.alert) || {};
    const labels = alert.labels || {};
    const ann = alert.annotations || {};
    const parts = [
      "On-call triage for alert `" + (labels.alertname || "unknown") + "`",
      "namespace: `" + (labels.namespace || "n/a") + "`",
      "severity: `" + (labels.severity || "n/a") + "`",
    ];
    if (ann.summary) parts.push("\nSummary: " + ann.summary);
    if (ann.description) parts.push("\n" + ann.description);
    if (ann.runbook_url) parts.push("\nRunbook: " + ann.runbook_url);
    parts.push(
      "\n\nInvestigate with read-only kubectl/flux and propose a resolution plan."
    );
    return parts.join("\n");
  }

  function fillComposer(text) {
    const area = document.querySelector("#composer-input, textarea.composer-input, textarea");
    if (!area) return false;
    area.value = text;
    area.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }

  function showBanner(text) {
    const bar = document.createElement("div");
    bar.id = "homelab-incident-banner";
    bar.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:9999;padding:10px 14px;" +
      "background:#3b2e5a;color:#f5f0ff;font:14px/1.4 system-ui,sans-serif;" +
      "border-bottom:1px solid #6b4fa0;max-height:40vh;overflow:auto;";
    bar.textContent = text;
    document.body.prepend(bar);
  }

  fetch(apiUrl)
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      const text = formatAlert(data);
      sessionStorage.setItem("homelab_incident_" + incidentId, text);
      if (!fillComposer(text)) {
        showBanner("Alert loaded — open a new chat and paste from sessionStorage if needed.");
      } else {
        showBanner("Alert context loaded into composer — review and send.");
      }
      try {
        const clean = new URL(window.location.href);
        clean.searchParams.delete("incident");
        window.history.replaceState({}, "", clean.toString());
      } catch (e) {
        /* ignore */
      }
    })
    .catch(function (err) {
      showBanner("Could not load incident " + incidentId + ": " + err.message);
    });
})();
