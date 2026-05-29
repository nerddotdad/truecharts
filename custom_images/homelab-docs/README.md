# homelab-docs

Static MkDocs Material site served in the cluster (not on GitHub Actions).

## How it works

```text
Git push (documentation/, helm-release.yaml, mkdocs/*)
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
- **Home → Site build info**: CI image build time, git SHA, and semver image tag.
- Footer: same build metadata on every page.

If ntfy **Runbook** links 404, confirm **Site build info** is newer than your runbook commit and roll `homelab-docs` if needed (`tag: latest` may require a pod restart to re-pull).

## CI loop breaker (Renovate)

**Build Homelab Docs** watches `clusters/**/helm-release.yaml`. Renovate PRs that **only** bump custom image `tag:` / digest lines would otherwise:

1. Merge pin PR → docs workflow runs → bump `homelab-docs` VERSION → new GHCR tag  
2. Renovate opens another `homelab-docs` pin PR → merge → repeat

The workflow **skips** rebuilds when the push contains only HelmRelease **image pin** diffs (same idea as `[skip ci]` on VERSION-only commits). Real doc or HelmRelease **values** changes still rebuild. After a pin-only merge, run **Build Homelab Docs** manually if you need the published site HTML to show the new image tag in generated chart pages.

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
| Git tags `x.y.z-homelab-docs` | Semver tracked by CI (PaulHatch/semantic-version) |
| `.github/workflows/build-homelab-docs.yml` | Build and push to GHCR (**repo root** Docker context) |
| `.github/workflows/build-custom-images.yml` | Does **not** build this image (wrong context) |
| `clusters/.../homelab-docs/app/helm-release.yaml` | app-template + ingress |
