"""Index alert runbooks and match them to HelmRelease services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from doc_paths import DOCS_ROOT, doc_staging_rel

SKIP_RUNBOOK_NAMES = {
    "mk_runbook_template.md",
    "mk_runbook_index.md",
}
SCOPE_ALL_HELMRELEASES = "all-helmreleases"


def parse_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    data = yaml.safe_load(text[3:end])
    return data if isinstance(data, dict) else {}


def _normalize_release_ref(value: str) -> str:
    return value.strip().lower()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def workload_area(helm_path: Path) -> str:
    from doc_paths import CLUSTERS_ROOT

    rel = helm_path.relative_to(CLUSTERS_ROOT)
    parts = rel.parts
    if "my-apps" in parts:
        return parts[parts.index("my-apps") + 1]
    if "kubernetes" in parts:
        idx = parts.index("kubernetes")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def discover_alert_runbooks() -> list[dict[str, Any]]:
    books: list[dict[str, Any]] = []
    if not DOCS_ROOT.is_dir():
        return books
    for path in sorted(DOCS_ROOT.rglob("mk_runbook_*.md")):
        if path.name in SKIP_RUNBOOK_NAMES:
            continue
        meta = parse_front_matter(path)
        alertnames = _as_list(meta.get("alertnames"))
        primary = meta.get("alertname")
        if primary:
            names = [str(primary)] + [str(a) for a in alertnames if str(a) != str(primary)]
        else:
            names = [str(a) for a in alertnames]
        doc_rel = path.relative_to(DOCS_ROOT)
        books.append(
            {
                "path": path,
                "href": doc_staging_rel(doc_rel).as_posix(),
                "title": str(meta.get("title") or path.stem.replace("mk_runbook_", "").replace("-", " ").title()),
                "alertname": primary,
                "alertnames": names,
                "scope": meta.get("scope"),
                "releases": [_normalize_release_ref(r) for r in _as_list(meta.get("releases"))],
                "areas": [a.strip().lower() for a in _as_list(meta.get("areas"))],
                "charts": [c.strip().lower() for c in _as_list(meta.get("charts"))],
            }
        )
    return books


def _release_matches_pattern(target: str, pattern: str) -> bool:
    if pattern in ("*", "all"):
        return True
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        return target.startswith(prefix + "/") or target == prefix
    return target == pattern


def match_runbooks_for_release(
    books: list[dict[str, Any]],
    *,
    namespace: str,
    name: str,
    chart: str,
    area: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (service-specific runbooks, platform-wide runbooks)."""
    target = _normalize_release_ref(f"{namespace}/{name}")
    chart_key = (chart or "").strip().lower()
    area_key = area.strip().lower()

    service: list[dict[str, str]] = []
    platform: list[dict[str, str]] = []

    for book in books:
        entry = {"title": book["title"], "href": book["href"]}
        if book.get("scope") == SCOPE_ALL_HELMRELEASES:
            platform.append(entry)
            continue
        matched = False
        for pattern in book["releases"]:
            if _release_matches_pattern(target, pattern):
                matched = True
                break
        if not matched and area_key and area_key in book["areas"]:
            matched = True
        if not matched and chart_key and chart_key in book["charts"]:
            matched = True
        if matched:
            service.append(entry)

    return service, platform


# Cached at build time (one index per collect/build).
_RUNBOOK_INDEX: list[dict[str, Any]] | None = None


def get_alert_runbooks() -> list[dict[str, Any]]:
    global _RUNBOOK_INDEX
    if _RUNBOOK_INDEX is None:
        _RUNBOOK_INDEX = discover_alert_runbooks()
    return _RUNBOOK_INDEX


def runbook_targets_workload(book: dict[str, Any], release_to_workload: dict[str, str]) -> str | None:
    """Map alert runbook front matter to a workload key (parent folder of app/)."""
    if book.get("scope") == SCOPE_ALL_HELMRELEASES:
        return None
    for pattern in book.get("releases") or []:
        for release, workload_key in release_to_workload.items():
            if _release_matches_pattern(release, pattern):
                return workload_key
    return None
