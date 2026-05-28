## Resolve (GitOps)

Homelab changes must go through Git — do not `kubectl apply` or patch live resources.

1. Identify the manifest under `clusters/main/kubernetes/`.
2. Fix chart version, values, dependencies, or suspend/resume as appropriate.
3. Commit, push, and watch Flux:

```bash
flux get helmrelease -A | rg -i 'false|unknown'
flux logs -n flux-system --tail=30
```

4. Wait for `Ready=True` and confirm the alert clears (allow `for:` duration + scrape interval).
