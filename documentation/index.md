---
title: Home
edit_url: https://github.com/nerddotdad/truecharts/edit/main/documentation/index.md
---

# Homelab cluster documentation

Hand-written pages live under **`documentation/`**. HelmRelease chart pages are still **auto-generated** from `helm-release.yaml` in `clusters/` at build time.

## MkDocs site (`homelab-docs`)

**Already deployed in the cluster** via `app-template` + Ingress at **`https://docs.${DOMAIN_0}`**. GitHub Actions only builds the container image; the runner does not host the site.

| Item | Location |
|------|----------|
| Hand-written docs | `documentation/` (mirrors cluster layout under `kubernetes/`) |
| Collector script | `scripts/collect_mkdocs.py` |
| MkDocs config | `mkdocs/mkdocs.base.yml` |
| Docker image | `custom_images/homelab-docs/` → `ghcr.io/nerddotdad/homelab-docs` |
| CI workflow | `.github/workflows/build-homelab-docs.yml` (build image) |
| HelmRelease (app-template + ingress) | `my-apps/dashboards/homelab-docs/app/helm-release.yaml` |

Set GitHub repo variable **`DOCS_SITE_URL`** to `https://docs.<your-domain>` before the first docs image build. See `custom_images/homelab-docs/README.md`.

Top navigation uses **tabs** (visible on wide screens, ≥1220px): this page is **Home**. All cluster services live under the **Kubernetes** tab. Add more top-level tabs with `mk_*.md` files in `documentation/kubernetes/`.

Local preview needs a site URL for tab/instant navigation:

```bash
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/python scripts/collect_mkdocs.py
MKDOCS_SITE_URL=http://127.0.0.1:8000 .venv-mkdocs/bin/mkdocs serve -f mkdocs/mkdocs.generated.yml
```

## HelmRelease pages (automatic)

Every `helm-release.yaml` gets a generated **chart index** at build time (`<workload>/index.md` from `helm-release.md.j2`). Matching alert runbooks appear as sub-pages under that chart.

Override with a hand-written `mk_helmrelease.md` under the mirrored path in `documentation/` (`helmrelease_doc: manual`).

## Extra pages (hand-written)

| Pattern | Example | Use |
|---------|---------|-----|
| `mk_info.md` | Area overview | |
| `mk_runbook_*.md` | Alert runbooks | `documentation/kubernetes/my-apps/observability/runbooks/` |
| `mk_observability.md` | Stack / namespace docs | |

## Navigation

- **Tabs** — `navigation.tabs` (Home + Kubernetes + any `mk_*.md` in `documentation/kubernetes/`).
- **Section indexes** — each area (Downloaders, Observability, …) has an overview; charts with runbooks nest under the HelmRelease page.

Optional: `documentation/kubernetes/my-apps/<area>/mk_index.md` replaces the auto-generated area overview.

## Document freshness

- **Page footer** (Material + `git-revision-date-localized`): last updated and created dates from Git for each source file.
- **Banner** on each page: last commit for that file plus link to **Site build info** (published image date).
- **Edit / View** (top of page): open the doc on GitHub (`repo_url` + `edit_uri` → `documentation/...`).

If a runbook link from ntfy returns 404, the Git file may exist but the cluster image is still old — rebuild and roll `homelab-docs`.

## Workflow

1. Add or edit `mk_*.md` under `documentation/` (keep runbooks out of `clusters/` so ClusterTool genconfig stays happy).
2. Push to `main` — GitHub Actions rebuilds the docs image.
3. Flux deploys to `https://docs.${DOMAIN_0}`.
4. Open **Site build info** and confirm the build date matches your push.

```yaml
---
title: My custom page title
---
```
