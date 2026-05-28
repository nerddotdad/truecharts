"""Git timestamps and MkDocs freshness banners for collect_mkdocs."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

METADATA_MARKER = "<!-- homelab-doc-metadata -->"
BANNER_PATTERN = re.compile(
    r"^!!! note \"Document freshness\".*?(?=\n(?:# |\Z))",
    re.MULTILINE | re.DOTALL,
)


def git_last_modified(repo_root: Path, rel_path: Path) -> str | None:
    """ISO date (UTC) of last Git commit touching rel_path, or None if unavailable."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "-1",
                "--format=%cI",
                "--",
                str(rel_path).replace("\\", "/"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    raw = proc.stdout.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else raw


def site_build_info(repo_root: Path) -> dict[str, str]:
    """Build metadata for the published docs image (CI / Docker ARGs)."""
    sha = (
        os.environ.get("DOCS_BUILD_SHA")
        or os.environ.get("GITHUB_SHA")
        or _git_head(repo_root)
        or "unknown"
    )[:12]
    built = os.environ.get("DOCS_BUILD_TIME") or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    version = os.environ.get("DOCS_IMAGE_VERSION", "").strip() or "local"
    return {
        "sha": sha,
        "built_at": built,
        "image_version": version,
    }


def _git_head(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def freshness_banner(
    *,
    last_updated: str | None,
    source_rel: str,
    site_built_at: str | None = None,
    site_sha: str | None = None,
) -> str:
    updated = last_updated or "_unknown (not in Git history)_"
    lines = [
        METADATA_MARKER,
        '!!! note "Document freshness"',
        "",
        f"- **Last updated (Git):** {updated}",
        f"- **Source file:** `{source_rel}`",
    ]
    if site_built_at:
        sha_bit = f" (`{site_sha[:12]}`)" if site_sha and site_sha != "unknown" else ""
        lines.append(
            f"- **Published site built:** {site_built_at}{sha_bit} — "
            "[Site build details](/meta/site-build/)"
        )
    lines.append(
        "- **When runbooks 404:** push `mk_*.md` to `main`, wait for "
        "[homelab-docs CI](https://github.com/nerddotdad/truecharts/actions), then confirm "
        "the cluster `homelab-docs` image tag matches the new build."
    )
    lines.append("")
    return "\n".join(lines)


def inject_freshness_banner(
    text: str,
    *,
    last_updated: str | None,
    source_rel: str,
    site_built_at: str | None = None,
    site_sha: str | None = None,
) -> str:
    banner = freshness_banner(
        last_updated=last_updated,
        source_rel=source_rel,
        site_built_at=site_built_at,
        site_sha=site_sha,
    )
    if METADATA_MARKER in text:
        if BANNER_PATTERN.search(text):
            return BANNER_PATTERN.sub(banner.rstrip() + "\n\n", text, count=1)
        return text
    body_start = 0
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            body_start = end + 3
            while body_start < len(text) and text[body_start] in "\r\n":
                body_start += 1
    return text[:body_start] + banner + "\n" + text[body_start:]
