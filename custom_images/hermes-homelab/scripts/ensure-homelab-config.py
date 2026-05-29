#!/usr/bin/env python3
"""Merge homelab-specific Hermes config into ~/.hermes/config.yaml on every pod start."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/home/hermeswebui/.hermes"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
SECRET = os.environ.get("WEBHOOK_SECRET") or os.environ.get("HERMES_WEBHOOK_SECRET") or ""
PORT = int(os.environ.get("WEBHOOK_PORT", "8644"))

# Forward K8s/chart env into terminal + execute_code subprocesses (see Hermes terminal.env_passthrough).
ENV_PASSTHROUGH = [
    "JELLYFIN_API_TOKEN",
    "JELLYFIN_API_URL",
    "JELLYFIN_PUBLIC_URL",
    "HOMELAB_DOCS_BASE_URL",
    "HOMELAB_GRAFANA_URL",
    "SEARXNG_URL",
    "HERMES_HOME",
]


def main() -> None:
    cfg: dict = {}
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                cfg = loaded

    if SECRET:
        platforms = cfg.setdefault("platforms", {})
        if not isinstance(platforms, dict):
            platforms = {}
            cfg["platforms"] = platforms
        platforms["webhook"] = {
            "enabled": True,
            "extra": {"host": "0.0.0.0", "port": PORT, "secret": SECRET},
        }

    terminal = cfg.setdefault("terminal", {})
    if not isinstance(terminal, dict):
        terminal = {}
        cfg["terminal"] = terminal
    terminal["env_passthrough"] = ENV_PASSTHROUGH

    browser = cfg.setdefault("browser", {})
    if not isinstance(browser, dict):
        browser = {}
        cfg["browser"] = browser
    # Allow in-cluster Service URLs (jellyfin.media.svc, homelab-docs, etc.).
    browser["allow_private_urls"] = True

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
