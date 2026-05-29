# Operator context

- **Cluster**: Talos + Flux GitOps TrueCharts homelab (`truecharts` git repo).
- **Alerts**: Prometheus → Alertmanager → homelab-alert-bridge → ntfy; **Ask AI** triggers Hermes webhook triage.
- **Docs site**: `HOMELAB_DOCS_BASE_URL` (MkDocs). **Grafana**: `HOMELAB_GRAFANA_URL`.
- **Changes**: edit manifests in Git, commit, push; Flux reconciles — do not mutate the live cluster.
