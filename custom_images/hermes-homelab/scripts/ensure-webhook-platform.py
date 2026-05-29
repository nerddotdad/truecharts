#!/usr/bin/env python3
"""Ensure platforms.webhook is enabled in ~/.hermes/config.yaml (secret from env)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/home/hermeswebui/.hermes"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
SECRET = os.environ.get("WEBHOOK_SECRET") or os.environ.get("HERMES_WEBHOOK_SECRET") or ""
PORT = int(os.environ.get("WEBHOOK_PORT", "8644"))


def main() -> None:
    if not SECRET:
        raise SystemExit("WEBHOOK_SECRET not set")
    cfg: dict = {}
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                cfg = loaded
    platforms = cfg.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
        cfg["platforms"] = platforms
    platforms["webhook"] = {
        "enabled": True,
        "extra": {"host": "0.0.0.0", "port": PORT, "secret": SECRET},
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
