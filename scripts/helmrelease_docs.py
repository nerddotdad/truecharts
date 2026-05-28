"""Generate HelmRelease chart pages from co-located helm-release.yaml manifests."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from doc_paths import DOCS_ROOT, app_dir_to_doc_dir, doc_staging_rel
from runbook_index import get_alert_runbooks, match_runbooks_for_release, workload_area

REPO_ROOT = Path(__file__).resolve().parents[1]
CLUSTERS_ROOT = REPO_ROOT / "clusters"
TEMPLATE_DIR = REPO_ROOT / "mkdocs" / "templates"

AUTO_DOC_FILE = "mk_helmrelease.md"
HELM_RELEASE_PREFIX = "helm-release"
MANUAL_MARKER = re.compile(r"helmrelease_doc:\s*manual", re.IGNORECASE)
MK_FILE = re.compile(r"^mk_.*\.md$", re.IGNORECASE)
EXCLUDE_PATH_PARTS = {".git", "node_modules", ".venv", "staging", "site", "__pycache__", "generated"}


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def is_manual_helm_doc(app_dir: Path, doc_name: str = AUTO_DOC_FILE) -> bool:
    manual = app_dir_to_doc_dir(app_dir) / doc_name
    if not manual.is_file():
        return False
    head = manual.read_text(encoding="utf-8", errors="replace")[:800]
    return bool(MANUAL_MARKER.search(head))


def workload_key_from_app_dir(app_dir: Path) -> str | None:
    """Parent folder of app/ (chart workload root in the GitOps tree)."""
    rel = app_dir.relative_to(CLUSTERS_ROOT)
    parts = list(rel.parts)
    if "app" in parts:
        return str(Path(*parts[: parts.index("app")]))
    return None


def helm_doc_staging_rel(helm_path: Path) -> Path:
    """
    Staging path for the chart page rendered from helm-release.md.j2.

    Single-release workloads use <workload>/index.md (MkDocs section index).
    Multiple releases in one app/ dir keep per-release mk_<name>.md under app/.
    """
    app_dir = helm_path.parent
    meta = _load_helm_release(helm_path) or {}
    release_name = str(_safe_get(meta, "metadata", "name") or app_dir.parent.name)
    doc_name = output_doc_name(helm_path, release_name)
    if doc_name != AUTO_DOC_FILE:
        return app_dir.relative_to(CLUSTERS_ROOT) / doc_name
    wk = workload_key_from_app_dir(app_dir)
    if wk:
        return Path(wk) / "index.md"
    return app_dir.relative_to(CLUSTERS_ROOT) / doc_name


def relative_doc_href(page_rel: Path, target_rel: Path) -> str:
    """MkDocs link from page_rel to target_rel (paths under clusters/)."""
    return Path(os.path.relpath(target_rel, page_rel.parent)).as_posix()


def list_supplemental_mk(app_dir: Path) -> list[dict[str, str]]:
    """mk_*.md under documentation/ mirroring app/ and workload directories."""
    from doc_paths import supplemental_mk_dirs

    docs: list[dict[str, str]] = []
    seen: set[str] = set()
    for directory in supplemental_mk_dirs(app_dir):
        for path in sorted(directory.glob("mk_*.md")):
            if path.name.lower() == AUTO_DOC_FILE.lower():
                continue
            doc_rel = path.relative_to(DOCS_ROOT)
            href = doc_staging_rel(doc_rel).as_posix()
            if href in seen:
                continue
            seen.add(href)
            title = path.stem[3:].replace("_", " ").replace("-", " ").title()
            docs.append({"title": title, "href": href})
    return docs


def _link_entries(page_rel: Path, entries: list[dict[str, str]]) -> list[dict[str, str]]:
    linked: list[dict[str, str]] = []
    for entry in entries:
        target = Path(entry["href"])
        linked.append({"title": entry["title"], "href": relative_doc_href(page_rel, target)})
    return linked


def parse_helm_release(helm_path: Path, page_rel: Path | None = None) -> dict[str, Any]:
    raw = yaml.safe_load(helm_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid HelmRelease YAML: {helm_path}")

    spec = raw.get("spec") or {}
    meta = raw.get("metadata") or {}
    chart_spec = _safe_get(spec, "chart", "spec", default={}) or {}
    chart_ref = spec.get("chartRef") or {}
    source_ref = chart_spec.get("sourceRef") or chart_ref or {}
    values = spec.get("values") or {}
    image = values.get("image") or {}

    chart_name = chart_spec.get("chart") or chart_ref.get("name") or "—"
    chart_version = chart_spec.get("version") or "—"
    if chart_ref and not chart_spec.get("chart"):
        chart_display = f"{chart_name} (chartRef)"
    else:
        chart_display = str(chart_name)

    source_kind = source_ref.get("kind") or "—"
    source_name = source_ref.get("name") or "—"
    source_ns = source_ref.get("namespace") or "flux-system"
    chart_source_display = f"{source_kind} `{source_name}` in `{source_ns}`"

    values_from: list[dict[str, str]] = []
    for entry in spec.get("valuesFrom") or []:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("ref") or entry
        values_from.append(
            {
                "kind": str(ref.get("kind") or entry.get("kind") or "?"),
                "name": str(ref.get("name") or entry.get("name") or "?"),
                "key": str(entry.get("valuesKey") or entry.get("targetPath") or "values.yaml"),
            }
        )

    app_dir = helm_path.parent
    if page_rel is None:
        page_rel = helm_doc_staging_rel(helm_path)
    git_path = helm_path.relative_to(REPO_ROOT).as_posix()
    helm_filename = helm_path.name
    name = str(meta.get("name") or app_dir.parent.name)
    namespace = str(meta.get("namespace") or "—")
    title = name.replace("-", " ").replace("_", " ").title()
    chart_slug = str(chart_name).lower() if chart_name != "—" else ""
    area = workload_area(helm_path)
    service_runbooks, platform_runbooks = match_runbooks_for_release(
        get_alert_runbooks(),
        namespace=namespace,
        name=name,
        chart=chart_slug,
        area=area,
    )

    return {
        "title": title,
        "name": name,
        "namespace": namespace,
        "api_version": str(raw.get("apiVersion") or "helm.toolkit.fluxcd.io/v2"),
        "chart_display": chart_display,
        "chart_version": chart_version if chart_version != "—" else "",
        "chart_source_kind": source_kind,
        "chart_source_name": source_name,
        "chart_source_namespace": source_ns,
        "chart_source_display": chart_source_display,
        "interval": spec.get("interval"),
        "timeout": spec.get("timeout"),
        "max_history": spec.get("maxHistory"),
        "drift_mode": _safe_get(spec, "driftDetection", "mode"),
        "suspend": spec.get("suspend"),
        "image_repository": image.get("repository"),
        "image_tag": image.get("tag"),
        "values_from": values_from,
        "git_path": git_path,
        "helm_filename": helm_filename,
        "supplemental_docs": _link_entries(page_rel, list_supplemental_mk(app_dir)),
        "service_runbooks": _link_entries(page_rel, service_runbooks),
        "platform_runbooks": _link_entries(page_rel, platform_runbooks),
        "workload_area": area,
        "notes_block": "",
    }


def is_helm_release_file(path: Path) -> bool:
    name = path.name
    return name.startswith(HELM_RELEASE_PREFIX) and name.endswith(".yaml")


def _load_helm_release(path: Path) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if isinstance(raw, dict) and raw.get("kind") == "HelmRelease":
        return raw
    return None


def discover_helm_release_paths() -> list[Path]:
    paths: list[Path] = []
    for root, dirnames, filenames in CLUSTERS_ROOT.walk():
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PATH_PARTS]
        for name in filenames:
            candidate = root / name
            if is_helm_release_file(candidate) and _load_helm_release(candidate):
                paths.append(candidate)
    return sorted(paths)


def output_doc_name(helm_path: Path, release_name: str) -> str:
    """One release per app dir → mk_helmrelease.md; multiple → mk_<release-name>.md."""
    app_dir = helm_path.parent
    releases = [
        p
        for p in app_dir.iterdir()
        if p.is_file() and is_helm_release_file(p) and _load_helm_release(p)
    ]
    if len(releases) <= 1:
        return AUTO_DOC_FILE
    safe = release_name.replace("_", "-").lower()
    return f"mk_{safe}.md"


def render_helm_release_page(helm_path: Path) -> str:
    page_rel = helm_doc_staging_rel(helm_path)
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("helm-release.md.j2")
    context = parse_helm_release(helm_path, page_rel)
    return template.render(**context) + "\n"


def generate_helm_release_docs(staging_root: Path) -> list[tuple[Path, str]]:
    """Return list of (staging relative path under clusters/, page title)."""
    generated: list[tuple[Path, str]] = []
    for helm_path in discover_helm_release_paths():
        app_dir = helm_path.parent
        meta = _load_helm_release(helm_path) or {}
        release_name = str(_safe_get(meta, "metadata", "name") or app_dir.parent.name)
        doc_name = output_doc_name(helm_path, release_name)
        if is_manual_helm_doc(app_dir, doc_name):
            continue
        rel = helm_doc_staging_rel(helm_path)
        dest = staging_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_helm_release_page(helm_path), encoding="utf-8")
        title = parse_helm_release(helm_path, rel)["title"]
        generated.append((rel, title))
    return generated
