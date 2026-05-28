# homelab-docs

Static MkDocs Material site served in the cluster (not on GitHub Actions).

## How it works

```text
Git push (mk_*.md, helm-release.yaml, mkdocs/*)
    → GitHub Actions builds Docker image (collect_mkdocs + mkdocs build + nginx)
    → ghcr.io/nerddotdad/homelab-docs
    → Flux HelmRelease (app-template) in namespace dashboards
    → Ingress https://docs.${DOMAIN_0}
```

GitHub Actions only **builds** the image. **Serving** is your cluster: `app-template` Deployment, port 8080, external Ingress with cert-manager.

## First-time deploy

1. Set GitHub repository variable **`DOCS_SITE_URL`** to your public URL (e.g. `https://docs.example.com`) so `navigation.instant` and tabs work in the built site.
2. Push to `main` (or run workflow **Build Homelab Docs** manually) so the image exists on GHCR.
3. Ensure Flux reconciles `homelab-docs` Kustomization (`clusters/main/kubernetes/my-apps/dashboards/homelab-docs/`).
4. Open **`https://docs.${DOMAIN_0}`** (same host as in the HelmRelease ingress).

## Document freshness

- Each page: **Last updated (Git)** (last commit for that `mk_*.md` or `helm-release.yaml`).
- **Home → Site build info**: CI image build time, git SHA, and `VERSION` tag.
- Footer: same build metadata on every page.

If ntfy **Runbook** links 404, confirm **Site build info** is newer than your runbook commit and roll `homelab-docs` if needed (`tag: latest` may require a pod restart to re-pull).

## Verify in cluster

```bash
flux get helmrelease homelab-docs -n dashboards
kubectl get pods,ingress -n dashboards -l app.kubernetes.io/instance=homelab-docs
```

## Local preview (no cluster)

```bash
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/python scripts/collect_mkdocs.py
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/mkdocs serve -f mkdocs/mkdocs.generated.yml
```

## Files

| Path | Role |
|------|------|
| `Dockerfile` | `collect_mkdocs` + `mkdocs build` → nginx (no `.git` in CI context; uses `DOCS_BUILD_*` args) |
| `VERSION` | Image tag bumped by CI |
| `.github/workflows/build-homelab-docs.yml` | Build and push to GHCR |
| `clusters/.../homelab-docs/app/helm-release.yaml` | app-template + ingress |
