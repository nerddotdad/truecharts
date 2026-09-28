# Renovate + GHCR (`ghcr.io/nerddotdad/*`)

Custom images publish **bare semver** tags only (`6.1.1`). Cluster pins match that shape — no `@sha256` digests.

| Pin shape | Where | Who updates it |
|-----------|--------|----------------|
| `tag: 1.2.8` | HelmRelease | TrueCharts YAML `# renovate:` comment + flux |
| `image: ghcr.io/nerddotdad/…:6.1.1` | Deployment | Tiny `customManagers` regex in `renovate.json5` |

`packageRules` set `versioning: semver` so leftover `latest` / `main-*` / calver tags are ignored.

## Verify tags

```bash
img=hearth
token=$(curl -s "https://ghcr.io/token?service=ghcr.io&scope=repository:nerddotdad/${img}:pull" | jq -r .token)
curl -s -H "Authorization: Bearer $token" "https://ghcr.io/v2/nerddotdad/${img}/tags/list" \
  | jq '.tags | map(select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")))'
```

## If Renovate misses a new tag

1. Confirm CI published the semver tag on GHCR.
2. Dependency Dashboard → `renovate:reset-cache` or `renovate:retry` (package cache can lag right after a push).
3. Do **not** add digest pins or `versionCompatibility` regexes — those caused the previous config sprawl.

## Private packages (`ghcr.io/nerddotdad/larpos`)

Anonymous tag listing returns 401. `renovate.json5` authenticates every `ghcr.io` lookup with Mend secret `GHCR_PULL_TOKEN` (same classic PAT the cluster uses: `read:packages` and `repo`).

1. [Mend Developer Portal](https://developer.mend.io) → this repository → Secrets.
2. Add `GHCR_PULL_TOKEN`. The `hostRules` entry reads it as **`password`**, not `token`.
3. Dependency Dashboard → `renovate:retry`.

The HelmRelease pin must be bare semver (`tag: 0.1.0`). This image’s workflow only publishes `0.1.0` when a `v*` git tag is pushed; `sha-*` and `latest` are ignored by the semver package rule, so Renovate will not open a PR while the pin is `sha-…`.

## GHCR auth (public packages)

“Public” packages still need a registry pull token; Renovate handles that unless a broken `hostRules` entry is present. The `ghcr.io` `hostRules` entry above also covers public packages, so the Mend secret must stay valid or hearth and the other public GHCR lookups fail too.
