#!/usr/bin/env python3
"""
Stage MkDocs content from the GitOps tree:

1. Auto-generate chart index pages from helm-release.yaml (helm-release.md.j2 → <workload>/index.md).
2. Copy hand-written mk_*.md (override generated chart page when helmrelease_doc: manual).
3. Emit mkdocs.generated.yml navigation (section indexes + chart/workload groups).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from helmrelease_docs import (
    AUTO_DOC_FILE,
    discover_helm_release_paths,
    generate_helm_release_docs,
    helm_doc_staging_rel,
    is_manual_helm_doc,
    output_doc_name,
    relative_doc_href,
)
from runbook_index import get_alert_runbooks, parse_front_matter, runbook_targets_workload

HOME_SOURCE_NAME = "mk_index.md"

REPO_ROOT = Path(__file__).resolve().parents[1]
CLUSTERS_ROOT = REPO_ROOT / "clusters"
MKDOCS_DIR = REPO_ROOT / "mkdocs"
STAGING_DIR = MKDOCS_DIR / "staging"
BASE_CONFIG = MKDOCS_DIR / "mkdocs.base.yml"
GENERATED_CONFIG = MKDOCS_DIR / "mkdocs.generated.yml"
EXCLUDE_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "staging",
    "site",
    "__pycache__",
    "generated",
}
MK_FILE = re.compile(r"^mk_.*\.md$", re.IGNORECASE)
RUNBOOK_FILE = re.compile(r"^mk_runbook_.*\.md$", re.IGNORECASE)
SKIP_MK_FILES = {
    HOME_SOURCE_NAME,
    "mk_runbook_template.md",
}
FRONT_MATTER_TITLE = re.compile(r"^title:\s*['\"]?(.*?)['\"]?\s*$", re.MULTILINE)
AREA_INDEX_NAME = "mk_index.md"
SITE_HOME_SOURCE = CLUSTERS_ROOT / "main" / "kubernetes" / AREA_INDEX_NAME
SITE_HOME_FALLBACK = CLUSTERS_ROOT / "main" / AREA_INDEX_NAME
KUBERNETES_ROOT = CLUSTERS_ROOT / "main" / "kubernetes"
CLUSTER_TAB_TITLE = "Kubernetes"
KUBERNETES_CLUSTER_INDEX = Path("main/kubernetes/index.md")
DEFAULT_SITE_URL = "http://127.0.0.1:8000"


def title_from_path(rel: Path) -> str:
    stem = rel.stem
    if stem.lower().startswith("mk_"):
        stem = stem[3:]
    return stem.replace("_", " ").replace("-", " ").strip().title() or "Page"


def title_from_file(src: Path) -> str:
    text = src.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            front = text[3:end]
            match = FRONT_MATTER_TITLE.search(front)
            if match and match.group(1).strip():
                return match.group(1).strip()
    return title_from_path(src)


def workload_key_from_rel(rel: Path) -> str | None:
    """Workload folder (parent of app/, or chart folder under my-apps)."""
    parts = list(rel.parts)
    if "app" in parts:
        return str(Path(*parts[: parts.index("app")]))
    if "my-apps" in parts:
        idx = parts.index("my-apps")
        # my-apps/<area>/<workload>/<file>.md
        if len(parts) >= idx + 4:
            return str(Path(*parts[:-1]))
    return None


def is_kubernetes_root_doc(rel: Path) -> bool:
    """mk_*.md directly under clusters/main/kubernetes/ (tab roots, not workload docs)."""
    return rel.parent.as_posix() == KUBERNETES_ROOT.relative_to(CLUSTERS_ROOT).as_posix()


def discover_kubernetes_root_mk() -> list[tuple[Path, Path]]:
    if not KUBERNETES_ROOT.is_dir():
        return []
    found: list[tuple[Path, Path]] = []
    for path in sorted(KUBERNETES_ROOT.glob("mk_*.md")):
        if path.name in SKIP_MK_FILES:
            continue
        found.append((path, path.relative_to(CLUSTERS_ROOT)))
    return found


def discover_mk_files() -> list[tuple[Path, Path]]:
    auto_generated_paths: set[Path] = set()
    for hr in discover_helm_release_paths():
        app_dir = hr.parent
        meta = yaml.safe_load(hr.read_text(encoding="utf-8")) or {}
        name = str((meta.get("metadata") or {}).get("name") or app_dir.parent.name)
        doc_name = output_doc_name(hr, name)
        if not is_manual_helm_doc(app_dir, doc_name):
            auto_generated_paths.add(helm_doc_staging_rel(hr))

    found: list[tuple[Path, Path]] = []
    for root, dirnames, filenames in CLUSTERS_ROOT.walk():
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for name in filenames:
            if not MK_FILE.match(name) or name in SKIP_MK_FILES:
                continue
            src = root / name
            rel = src.relative_to(CLUSTERS_ROOT)
            if is_kubernetes_root_doc(rel) or rel.as_posix() == "main/mk_index.md":
                continue
            if rel in auto_generated_paths and name.lower() == AUTO_DOC_FILE.lower():
                continue
            found.append((src, rel))
    return sorted(found, key=lambda item: str(item[1]).lower())


def _rel_parts(rel: Path) -> list[str]:
    parts = list(rel.parts)
    if parts and parts[0] == "main":
        parts = parts[1:]
    return parts


def nav_section_info(rel: Path) -> tuple[str, Path]:
    parts = _rel_parts(rel)
    if "my-apps" in parts:
        idx = parts.index("my-apps")
        section = parts[idx + 1]
        prefix = Path("main", "kubernetes", "my-apps", section)
    elif parts and parts[0] == "kubernetes":
        section = parts[1] if len(parts) > 1 else "cluster"
        display = "Cluster" if section == "cluster" else section.replace("_", " ").replace("-", " ").title()
        prefix = Path("main", "kubernetes", "_sections", section)
        return display, prefix
    else:
        section = parts[0] if parts else "cluster"
        prefix = Path("main", section)
    display = section.replace("_", " ").replace("-", " ").title()
    return display, prefix


def page_kind(rel: Path) -> str:
    name = rel.name.lower()
    if name == "mk_helmrelease.md" or name == "index.md":
        return "HelmRelease"
    if name.startswith("mk_runbook"):
        return "Alert runbook"
    return "Documentation"


def new_section_node(prefix: Path) -> dict[str, Any]:
    return {
        "__prefix__": prefix.as_posix(),
        "__leaves__": [],
        "__workloads__": {},
        "__index__": None,
    }


def ensure_section(nav_tree: dict, rel: Path) -> dict[str, Any]:
    section, prefix = nav_section_info(rel)
    return nav_tree.setdefault(section, new_section_node(prefix))


def ensure_workload(node: dict[str, Any], workload_key: str, title: str, helm_href: str) -> dict[str, Any]:
    workloads = node.setdefault("__workloads__", {})
    if workload_key not in workloads:
        workloads[workload_key] = {"title": title, "helm_href": helm_href, "children": []}
    else:
        workloads[workload_key]["title"] = title
        workloads[workload_key]["helm_href"] = helm_href
    return workloads[workload_key]


def build_release_to_workload_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for helm_path in discover_helm_release_paths():
        raw = yaml.safe_load(helm_path.read_text(encoding="utf-8")) or {}
        meta = raw.get("metadata") or {}
        ns = str(meta.get("namespace", "")).strip().lower()
        name = str(meta.get("name", "")).strip().lower()
        if not ns or not name:
            continue
        wk = workload_key_from_rel(helm_path.parent.relative_to(CLUSTERS_ROOT))
        if wk:
            mapping[f"{ns}/{name}"] = wk
    return mapping


def insert_nav_page(
    nav_tree: dict,
    rel: Path,
    title: str,
    doc_path: str,
    *,
    release_to_workload: dict[str, str],
    is_helm: bool = False,
    runbook_meta: dict[str, Any] | None = None,
) -> None:
    node = ensure_section(nav_tree, rel)
    page = {"title": title, "href": doc_path, "kind": page_kind(rel)}

    if is_helm:
        wk = workload_key_from_rel(rel)
        if wk:
            ensure_workload(node, wk, title, doc_path)
        else:
            node["__leaves__"].append(page)
        return

    if runbook_meta is not None:
        wk = runbook_targets_workload(runbook_meta, release_to_workload)
        if wk and wk in node.get("__workloads__", {}):
            node["__workloads__"][wk]["children"].append(page)
            return
        node["__leaves__"].append(page)
        return

    wk = workload_key_from_rel(rel)
    if wk and wk in node.get("__workloads__", {}):
        node["__workloads__"][wk]["children"].append(page)
        return

    node["__leaves__"].append(page)


def section_index_pages(data: dict[str, Any]) -> list[dict[str, str]]:
    pages = list(data.get("__leaves__", []))
    for workload in sorted(data.get("__workloads__", {}).values(), key=lambda w: w["title"].lower()):
        pages.append(
            {
                "title": workload["title"],
                "href": workload["helm_href"],
                "kind": "HelmRelease (chart)",
            }
        )
    return sorted(pages, key=lambda p: p["title"].lower())


def write_section_indexes(nav_tree: dict, staging_root: Path) -> None:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(MKDOCS_DIR / "templates"),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("section-index.md.j2")

    for section, data in sorted(nav_tree.items(), key=lambda x: x[0].lower()):
        prefix = Path(data["__prefix__"])
        index_rel = prefix / "index.md"
        index_staged = staging_root / index_rel
        index_staged.parent.mkdir(parents=True, exist_ok=True)

        if "my-apps" in prefix.parts:
            custom = CLUSTERS_ROOT / "main" / "kubernetes" / "my-apps" / prefix.parts[-1] / AREA_INDEX_NAME
        elif "_sections" in prefix.parts:
            custom = CLUSTERS_ROOT / "main" / "kubernetes" / "_sections" / prefix.parts[-1] / AREA_INDEX_NAME
        else:
            custom = CLUSTERS_ROOT / prefix / AREA_INDEX_NAME
        if custom.is_file():
            shutil.copy2(custom, index_staged)
            data["__index__"] = index_rel.as_posix()
            continue

        pages = [
            {
                **page,
                "href": relative_doc_href(index_rel, Path(page["href"])),
            }
            for page in section_index_pages(data)
        ]
        index_staged.write_text(
            template.render(title=section, description=None, pages=pages),
            encoding="utf-8",
        )
        data["__index__"] = index_rel.as_posix()


def write_kubernetes_cluster_index(nav_tree: dict, staging_root: Path) -> str | None:
    """Cluster-wide index.md — first page under the Kubernetes tab."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    if not nav_tree:
        return None

    env = Environment(
        loader=FileSystemLoader(MKDOCS_DIR / "templates"),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("section-index.md.j2")

    pages: list[dict[str, str]] = []
    for section in sorted(nav_tree.keys(), key=str.lower):
        data = nav_tree[section]
        href = data.get("__index__")
        if not href:
            continue
        pages.append(
            {
                "title": section,
                "href": relative_doc_href(KUBERNETES_CLUSTER_INDEX, Path(href)),
                "kind": "Area overview",
            }
        )

    index_staged = staging_root / KUBERNETES_CLUSTER_INDEX
    index_staged.parent.mkdir(parents=True, exist_ok=True)
    index_staged.write_text(
        template.render(
            title="Kubernetes cluster",
            description="Homelab workloads and platform components managed via GitOps.",
            pages=pages,
        ),
        encoding="utf-8",
    )
    return KUBERNETES_CLUSTER_INDEX.as_posix()


def write_workload_indexes(nav_tree: dict, staging_root: Path) -> None:
    """Optional chart mk_index.md replaces auto-generated workload/index.md."""
    for data in nav_tree.values():
        for workload_key, w in data.get("__workloads__", {}).items():
            custom = CLUSTERS_ROOT / workload_key / AREA_INDEX_NAME
            if not custom.is_file():
                continue
            index_rel = Path(workload_key) / "index.md"
            index_staged = staging_root / index_rel
            index_staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(custom, index_staged)
            w["helm_href"] = index_rel.as_posix()


def workload_nav_items(workloads: dict[str, dict[str, Any]]) -> list:
    """
    Single-page charts: flat link under the area.

    Charts with runbooks/extra docs: nested group; first entry is workload/index.md
    (helm-release.md.j2). Material navigation.indexes uses that as the section landing
    page; runbooks and other mk_*.md files are sub-pages beneath it.
    """
    items: list = []
    for _wk in sorted(workloads.keys(), key=lambda k: workloads[k]["title"].lower()):
        w = workloads[_wk]
        children = w.get("children") or []

        if not children:
            items.append({w["title"]: w["helm_href"]})
            continue

        group: list = [w["helm_href"]]
        for child in sorted(children, key=lambda c: c["title"].lower()):
            group.append({child["title"]: child["href"]})
        items.append({w["title"]: group})
    return items


def tree_to_nav(nav_tree: dict) -> list:
    """Sidebar sections inside the Kubernetes tab (areas, system, networking, …)."""
    nav: list = []
    for section in sorted(nav_tree.keys(), key=str.lower):
        data = nav_tree[section]
        items: list = []
        if data.get("__index__"):
            items.append(data["__index__"])
        for page in sorted(data["__leaves__"], key=lambda p: p["title"].lower()):
            items.append({page["title"]: page["href"]})
        items.extend(workload_nav_items(data.get("__workloads__", {})))
        nav.append({section: items})
    return nav


def build_top_level_nav(
    nav_tree: dict,
    kubernetes_tab_pages: list[dict[str, str]],
    *,
    cluster_index_href: str | None,
) -> list:
    """
    Material navigation.tabs: Home, optional mk_*.md siblings in kubernetes/, then Kubernetes tab.
    """
    nav: list = [{"Home": "index.md"}]
    for page in sorted(kubernetes_tab_pages, key=lambda p: p["title"].lower()):
        nav.append({page["title"]: page["href"]})
    cluster_nav: list = []
    if cluster_index_href:
        cluster_nav.append(cluster_index_href)
    cluster_nav.extend(tree_to_nav(nav_tree))
    if cluster_nav:
        nav.append({CLUSTER_TAB_TITLE: cluster_nav})
    return nav


def write_site_home(staged_index: Path) -> None:
    if SITE_HOME_SOURCE.is_file():
        shutil.copy2(SITE_HOME_SOURCE, staged_index)
        return
    if SITE_HOME_FALLBACK.is_file():
        shutil.copy2(SITE_HOME_FALLBACK, staged_index)
        return
    staged_index.write_text(
        """---
title: Home
---

# Homelab cluster documentation

HelmRelease pages are generated from `helm-release.yaml`. Alert runbooks nest under their chart in the sidebar when `releases:` matches.
""",
        encoding="utf-8",
    )


def stage_kubernetes_tab_pages() -> list[dict[str, str]]:
    """Stage mk_*.md in kubernetes/ (except mk_index.md) as extra top-level tabs."""
    tabs: list[dict[str, str]] = []
    for src, rel in discover_kubernetes_root_mk():
        if src.name == AREA_INDEX_NAME:
            continue
        dest = STAGING_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        tabs.append({"title": title_from_file(src), "href": rel.as_posix()})
    return tabs


def stage_doc(
    nav_tree: dict,
    rel: Path,
    title: str,
    src: Path | None,
    *,
    release_to_workload: dict[str, str],
    is_helm: bool = False,
    runbook_meta: dict[str, Any] | None = None,
) -> None:
    dest = STAGING_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src is not None:
        shutil.copy2(src, dest)
    insert_nav_page(
        nav_tree,
        rel,
        title,
        rel.as_posix(),
        release_to_workload=release_to_workload,
        is_helm=is_helm,
        runbook_meta=runbook_meta,
    )


def main() -> int:
    if not CLUSTERS_ROOT.is_dir():
        print(f"clusters root not found: {CLUSTERS_ROOT}", file=sys.stderr)
        return 1

    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)
    write_site_home(STAGING_DIR / "index.md")
    kubernetes_tab_pages = stage_kubernetes_tab_pages()

    nav_tree: dict = {}
    release_to_workload = build_release_to_workload_map()
    helm_count = 0
    manual_count = 0
    mk_count = 0

    for rel, title in generate_helm_release_docs(STAGING_DIR):
        stage_doc(nav_tree, rel, title, None, release_to_workload=release_to_workload, is_helm=True)
        helm_count += 1

    for helm_path in discover_helm_release_paths():
        app_dir = helm_path.parent
        meta = yaml.safe_load(helm_path.read_text(encoding="utf-8")) or {}
        name = str((meta.get("metadata") or {}).get("name") or app_dir.parent.name)
        doc_name = output_doc_name(helm_path, name)
        if not is_manual_helm_doc(app_dir, doc_name):
            continue
        src = app_dir / doc_name
        rel = src.relative_to(CLUSTERS_ROOT)
        stage_doc(
            nav_tree,
            rel,
            title_from_file(src),
            src,
            release_to_workload=release_to_workload,
            is_helm=True,
        )
        manual_count += 1

    for src, rel in discover_mk_files():
        runbook_meta = None
        if RUNBOOK_FILE.match(rel.name):
            runbook_meta = parse_front_matter(src)
        stage_doc(
            nav_tree,
            rel,
            title_from_file(src),
            src,
            release_to_workload=release_to_workload,
            runbook_meta=runbook_meta,
        )
        mk_count += 1

    write_workload_indexes(nav_tree, STAGING_DIR)
    write_section_indexes(nav_tree, STAGING_DIR)
    cluster_index_href = write_kubernetes_cluster_index(nav_tree, STAGING_DIR)

    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    base["docs_dir"] = "staging"
    base["site_dir"] = "site"
    base["site_url"] = os.environ.get("MKDOCS_SITE_URL", DEFAULT_SITE_URL).rstrip("/")
    base["nav"] = build_top_level_nav(
        nav_tree,
        kubernetes_tab_pages,
        cluster_index_href=cluster_index_href,
    )

    GENERATED_CONFIG.write_text(
        yaml.safe_dump(base, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    print(
        f"Staged {helm_count} generated HelmRelease page(s), "
        f"{manual_count} manual mk_helmrelease.md, {mk_count} other mk_*.md"
    )
    print(f"Wrote {GENERATED_CONFIG.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
