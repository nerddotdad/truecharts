# Operator context

- **Cluster**: Talos + Flux GitOps TrueCharts homelab (`truecharts` git repo).
- **Alerts**: Prometheus → Alertmanager → homelab-alert-bridge → ntfy; **Ask AI** opens Hermes WebUI with stored incident JSON.
- **Docs site**: `HOMELAB_DOCS_BASE_URL` (MkDocs). **Grafana**: `HOMELAB_GRAFANA_URL`.
- **Changes**: edit manifests in Git, commit, push; Flux reconciles — do not mutate the live cluster.
- **Alert skills**: Prometheus rules may set `annotations.recommended_ai_skills` (comma-separated Hermes skill names, e.g. `homelab-k8s-flux-triage,jellyfin-api`). Prefer those skills for the firing alert.
