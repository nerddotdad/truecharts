#!/usr/bin/env python3
"""Merge homelab-specific Hermes config into ~/.hermes/config.yaml on every pod start."""
from __future__ import annotations

import os
import subprocess
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

    bundled = os.environ.get("HERMES_BUNDLED_SKILLS", "/opt/hermes/skills").strip()
    if bundled:
        os.environ.setdefault("HERMES_BUNDLED_SKILLS", bundled)
    sync_bundled_skills()


def sync_bundled_skills() -> None:
    """Copy bundled agent skills into ~/.hermes/skills (avoids /app/venv/skills exclusion)."""
    try:
        from tools.skills_sync import sync_skills

        sync_skills(quiet=True)
        return
    except Exception:
        pass

    venv_python = Path("/app/venv/bin/python3")
    if venv_python.is_file():
        try:
            subprocess.run(
                [
                    str(venv_python),
                    "-c",
                    "from tools.skills_sync import sync_skills; sync_skills(quiet=True)",
                ],
                env=os.environ.copy(),
                check=False,
                timeout=120,
            )
            return
        except Exception:
            pass

    hermes_bin = Path("/app/venv/bin/hermes")
    if hermes_bin.is_file():
        try:
            subprocess.run(
                [str(hermes_bin), "skills", "sync"],
                env=os.environ.copy(),
                check=False,
                timeout=120,
            )
        except Exception:
            pass  # gateway/WebUI still usable; homelab GitOps skills remain on PVC


if __name__ == "__main__":
    main()
