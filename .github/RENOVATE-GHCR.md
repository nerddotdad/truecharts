# Renovate + GHCR (`ghcr.io/nerddotdad/*`)

## Symptom

```text
Found no results from datasource that look like a version
releases: []
```

## Common causes

### 1. Invalid `versionCompatibility` regex (fixed)

Renovate expects **named capture groups** (`(?<version>…)`, optional `(?<compatibility>…)`).
A bare pattern like `^\d+\.\d+\.\d+$` can filter out **every** tag from GHCR and yield empty `releases`.

Use `versioning: "semver"` in a `packageRules` entry instead; do not use `versionCompatibility` unless you split version + suffix (e.g. `1.2.3-alpine`).

### 2. GHCR API always uses a pull token

“Public” on GitHub still means the registry API needs a Bearer token from `https://ghcr.io/token?scope=repository:nerddotdad/<image>:pull`.
Renovate does this automatically when **no broken `hostRules`** are present.

Do **not** add `hostRules` with only `username` and no `password`, or with `token` instead of `password` — that breaks GHCR lookups (see [Renovate #22347](https://github.com/renovatebot/renovate/discussions/22347)).

If Mend still cannot list tags, add a classic PAT (`read:packages`) as **`password`** (not `token`):

```json5
hostRules: [
  {
    hostType: "docker",
    matchHost: "ghcr.io",
    username: "nerddotdad",
    encrypted: { password: "<Mend-encrypted PAT>" },
  },
],
```

### 3. Tag format on GHCR

CI should publish bare semver (`1.1.5`). Extra tags (`latest`, `main-<sha>`, `2026.05.28-*`) are ignored when `versioning: "semver"` and the manifest pin is already semver.

Verify tags:

```bash
img=hermes-homelab
token=$(curl -s "https://ghcr.io/token?service=ghcr.io&scope=repository:nerddotdad/${img}:pull" | jq -r .token)
curl -s -H "Authorization: Bearer $token" "https://ghcr.io/v2/nerddotdad/${img}/tags/list" | jq '.tags | map(select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")))'
```

## `update failure` on Renovate branches

Do **not** delete old GHCR image tags — Renovate picks the newest semver above your cluster pin; extra tags are fine.

1. Delete **stale Git branches** (not registry tags), e.g. `renovate/ghcr.io-nerddotdad-homelab-alert-bridge-1.0.0`.
2. Ensure `autoReplaceStringTemplate` includes the YAML prefix (`tag: ` / `image: …:`), not only `1.2.3@sha256:…`.
3. Re-run Renovate.

One-time manual bump in Git is OK if you are blocked (e.g. bridge `1.0.0` → `1.1.1`); Renovate should maintain pins after the template fix.
