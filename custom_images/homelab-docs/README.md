# homelab-docs

Static MkDocs Material site built from co-located `clusters/**/mk_*.md` files.

- **Build context:** repository root (see `Dockerfile`)
- **Registry:** `ghcr.io/nerddotdad/homelab-docs`
- **CI:** `.github/workflows/build-homelab-docs.yml`

After the first image push, Flux deploys the HelmRelease at `my-apps/dashboards/homelab-docs/`.
