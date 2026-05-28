---
title: Home
---

# Homelab cluster documentation

This site is generated from **`mk_*.md`** files co-located in this GitOps repository.

## MkDocs site (`homelab-docs`)

**Already deployed in the cluster** via `app-template` + Ingress at **`https://docs.${DOMAIN_0}`**. GitHub Actions only builds the container image; the runner does not host the site.

| Item | Location |
|------|----------|
| Collector script | `scripts/collect_mkdocs.py` |
| MkDocs config | `mkdocs/mkdocs.base.yml` |
| Docker image | `custom_images/homelab-docs/` → `ghcr.io/nerddotdad/homelab-docs` |
| CI workflow | `.github/workflows/build-homelab-docs.yml` (build image) |
| HelmRelease (app-template + ingress) | `my-apps/dashboards/homelab-docs/app/helm-release.yaml` |

Set GitHub repo variable **`DOCS_SITE_URL`** to `https://docs.<your-domain>` before the first docs image build. See `custom_images/homelab-docs/README.md`.

Top navigation uses **tabs** (visible on wide screens, ≥1220px): this page is **Home**. All cluster services live under the **Kubernetes** tab. Add more top-level tabs by placing `mk_*.md` files in `clusters/main/kubernetes/` (same folder as this file).

Local preview needs a site URL for tab/instant navigation:

```bash
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/python scripts/collect_mkdocs.py
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/mkdocs serve -f mkdocs/mkdocs.generated.yml
```

## HelmRelease pages (automatic)

Every `helm-release.yaml` gets a generated **chart index** at build time (`<workload>/index.md` from `helm-release.md.j2`). Matching alert runbooks appear as sub-pages under that chart.

Override with a hand-written `mk_helmrelease.md` next to the manifest (`helmrelease_doc: manual`).

## Extra pages (hand-written)

| Pattern | Example | Use |
|---------|---------|-----|
| `mk_info.md` | Area overview | |
| `mk_runbook_*.md` | Alert runbooks | |
| `mk_observability.md` | Stack / namespace docs | |

## Navigation

- **Tabs** — `navigation.tabs` (Home + Kubernetes + any `mk_*.md` in this directory except `mk_index.md`).
- **Section indexes** — each area (Downloaders, Observability, …) has an overview; charts with runbooks nest under the HelmRelease page.

Optional: `my-apps/<area>/mk_index.md` replaces the auto-generated area overview.

## Workflow

1. Add or edit `mk_*.md` next to your manifests under `clusters/`.
2. Push to `main` — GitHub Actions rebuilds the docs image.
3. Flux deploys to `https://docs.${DOMAIN_0}`.

```yaml
---
title: My custom page title
---
```
