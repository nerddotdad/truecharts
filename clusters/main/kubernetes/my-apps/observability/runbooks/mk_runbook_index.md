---
title: Alert runbooks
---

# Homelab alert runbooks

Runbooks live here as `mk_runbook_<alert-name-kebab>.md`. ntfy **tap links** use the `runbook_url` annotation on each PrometheusRule (see `mk_runbook_template.md`).

## Tie runbooks to services

Set front matter on the runbook so it appears on the right **HelmRelease** docs pages:

```yaml
releases:
  - downloaders/nzbget
  - observability/grafana
# or
areas:
  - downloaders
# or
scope: all-helmreleases   # platform-wide (e.g. HomelabFluxHelmReleaseNotReady)
```

Co-located **`app/mk_runbook.md`** is for steps that apply only to that chart (not tied to a Prometheus alert name).

## Create a new runbook

1. Copy `mk_runbook_template.md` → `mk_runbook_<your-alert-kebab>.md`
2. Set `releases` / `areas` / `scope` in front matter; fill in **What this means**; remove the template note.
3. Print the docs URL:

   ```bash
   python scripts/runbook_url.py YourAlertName
   ```

4. Add `runbook_url` to the alert in `prometheus-rules/app/*.yaml`
5. Commit — docs CI rebuilds; alert tap opens the runbook on your phone.

## Snippets (shared sections)

Reusable blocks in `mkdocs/snippets/runbook/` — include in any runbook with:

```markdown
--8<-- "runbook/triage-checklist.md"
```

## Runbook index

The table below is **regenerated at each docs build** from runbook front matter (`alertname`, `alertnames`) and Git last-commit dates.

<!-- runbook-index-begin -->
<!-- runbook-index-end -->

Add a new runbook file under this folder; set `alertname` / `alertnames` in front matter — no need to edit the table by hand.
