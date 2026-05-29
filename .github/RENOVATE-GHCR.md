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

## Dashboard shows branch names you never see on GitHub

That is normal for **`update failure`**: Renovate **plans** a branch name (e.g. `renovate/ghcr.io-nerddotdad-homelab-alert-bridge-1.0.0`), then fails while applying file edits (bad `autoReplaceStringTemplate`, digest mismatch, etc.) **before** it successfully pushes the branch. Logs often show `branchExists=false` → `Branch needs creating` → `update failure` — the branch was never on GitHub, so there is nothing to delete.

Each run retries the **same planned branch name** and records **Repository problems** until one run succeeds or the update is no longer needed.

## Dashboard still shows “Repository problems”

Renovate also keeps **repository / branch cache** (especially on Mend-hosted). The warning can linger after a failed run even when `git branch -r | grep renovate/ghcr.io-nerddotdad` prints nothing.

Check Git is clean:

```bash
git fetch origin
git branch -r | grep 'renovate/ghcr.io-nerddotdad'
```

If that prints nothing, then:

1. Confirm `.github/renovate.json5` on `main` has the fixed `autoReplaceStringTemplate` (with `tag: ` / `image:` prefixes).
2. Open the **Dependency Dashboard** issue and comment: `renovate:retry` (or use Mend → run Renovate manually).
3. After the next green run, **Repository problems** should disappear. Failed entries may show once more, then drop when Renovate opens fresh PRs or finds nothing to update.

You do **not** need to recreate deleted branches. Renovate will create new ones only when a new update is available (e.g. the next CI image build).
