#!/usr/bin/env python3
"""Print docs site runbook URL for a Prometheus alert name."""

from __future__ import annotations

import argparse
import re
import sys


# PascalCase alerts need explicit slugs (HelmRelease → helmrelease, not helm-release).
SLUG_OVERRIDES: dict[str, str] = {
    "HomelabFluxHelmReleaseNotReady": "homelab-flux-helmrelease-not-ready",
    "HomelabFluxHelmReleaseTestFail": "homelab-flux-helmrelease-test-fail",
}


def alert_to_slug(alertname: str) -> str:
    if alertname in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[alertname]
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", alertname)
    return s.replace("_", "-").lower()


def runbook_path(alertname: str) -> str:
    return (
        "main/kubernetes/my-apps/observability/runbooks/"
        f"mk_runbook_{alert_to_slug(alertname)}.md"
    )


def runbook_url(alertname: str, domain_var: str = "docs.${DOMAIN_0}") -> str:
    path = runbook_path(alertname).removesuffix(".md") + "/"
    return f"https://{domain_var}/{path}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alertname", help="Prometheus alert name, e.g. HomelabFluxHelmReleaseNotReady")
    parser.add_argument(
        "--domain-var",
        default="docs.${DOMAIN_0}",
        help="Host for docs ingress (default: docs.${DOMAIN_0} for Flux substitution)",
    )
    parser.add_argument("--path-only", action="store_true", help="Print mkdocs path only")
    args = parser.parse_args()

    if args.path_only:
        print(runbook_path(args.alertname))
    else:
        print(runbook_url(args.alertname, args.domain_var))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
