#!/usr/bin/env python3
"""Mirror the default Hermes profile into GitOps-named profiles (model overlay only)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/home/hermeswebui/.hermes"))
GITOPS_PROFILES_DIR = Path(
    os.environ.get("HERMES_GITOPS_PROFILES_DIR", "/opt/hermes-gitops-profiles")
)
GITOPS_AGENT_DIR = Path(os.environ.get("HOMELAB_GITOPS_AGENT_DIR", "/opt/hermes-gitops"))

PROFILE_DIRS = (
    "memories",
    "sessions",
    "skills",
    "skins",
    "logs",
    "plans",
    "workspace",
    "cron",
    "home",
)

# Gateway runs on the default profile; mirror status files for WebUI profile views.
GATEWAY_MIRROR_FILES = ("gateway_state.json", "webhook_subscriptions.json")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    return loaded if isinstance(loaded, dict) else {}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _bootstrap_profile_dirs(profile_home: Path) -> None:
    profile_home.mkdir(parents=True, exist_ok=True)
    for subdir in PROFILE_DIRS:
        (profile_home / subdir).mkdir(parents=True, exist_ok=True)


def _copy_skills_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _seed_user_memory(profile_home: Path) -> None:
    user_seed = GITOPS_AGENT_DIR / "USER.md"
    user_dest = profile_home / "memories" / "USER.md"
    if user_seed.is_file() and not user_dest.is_file():
        user_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(user_seed, user_dest)


def _mirror_gateway_artifacts(default_home: Path, profile_home: Path) -> None:
    for name in GATEWAY_MIRROR_FILES:
        source = default_home / name
        if source.is_file():
            shutil.copy2(source, profile_home / name)


def sync_gitops_profiles() -> None:
    """Clone default profile state into each GitOps profile dir with model overlay."""
    if not GITOPS_PROFILES_DIR.is_dir():
        return

    default_home = HERMES_HOME
    default_config = _load_yaml(default_home / "config.yaml")
    if not default_config:
        return

    default_soul = default_home / "SOUL.md"
    default_skills = default_home / "skills"

    for overlay_path in sorted(GITOPS_PROFILES_DIR.glob("*/config.yaml")):
        profile_name = overlay_path.parent.name.strip()
        if not profile_name or profile_name == "default":
            continue

        profile_home = default_home / "profiles" / profile_name
        _bootstrap_profile_dirs(profile_home)

        overlay = _load_yaml(overlay_path)
        merged = _deep_merge(default_config, overlay)
        with (profile_home / "config.yaml").open("w", encoding="utf-8") as fh:
            yaml.safe_dump(merged, fh, default_flow_style=False, sort_keys=False)

        if default_soul.is_file():
            shutil.copy2(default_soul, profile_home / "SOUL.md")

        _copy_skills_tree(default_skills, profile_home / "skills")
        _seed_user_memory(profile_home)
        _mirror_gateway_artifacts(default_home, profile_home)


if __name__ == "__main__":
    sync_gitops_profiles()
