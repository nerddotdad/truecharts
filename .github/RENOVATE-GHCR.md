# Renovate + GHCR (`ghcr.io/nerddotdad/*`)

Custom images publish **bare semver** tags only (`6.1.1`). Cluster pins match that shape — no `@sha256` digests.

| Pin shape | Where | Who updates it |
|-----------|--------|----------------|
| `tag: 1.2.8` | HelmRelease | TrueCharts YAML `# renovate:` comment + flux |
| `image: ghcr.io/nerddotdad/…:6.1.1` | Deployment | Tiny `customManagers` regex in `renovate.json5` |

`packageRules` set `versioning: semver` so leftover `latest` / `main-*` / calver tags are ignored.

## Verify tags

```bash
img=homelab-alert-bridge
token=$(curl -s "https://ghcr.io/token?service=ghcr.io&scope=repository:nerddotdad/${img}:pull" | jq -r .token)
curl -s -H "Authorization: Bearer $token" "https://ghcr.io/v2/nerddotdad/${img}/tags/list" \
  | jq '.tags | map(select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")))'
```

## If Renovate misses a new tag

1. Confirm CI published the semver tag on GHCR.
2. Dependency Dashboard → `renovate:reset-cache` or `renovate:retry` (package cache can lag right after a push).
3. Do **not** add digest pins or `versionCompatibility` regexes — those caused the previous config sprawl.

## GHCR auth (only if lookups fail)

“Public” packages still need a registry pull token; Renovate handles that unless a broken `hostRules` entry is present. Prefer no `hostRules` for `ghcr.io`. If Mend cannot list tags, add a classic PAT (`read:packages`) as **`password`** (not `token`).
