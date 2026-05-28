#!/usr/bin/env python3
"""
Stage MkDocs content from the GitOps tree:

1. Auto-generate chart index pages from helm-release.yaml (helm-release.md.j2 → <workload>/index.md).
2. Copy hand-written mk_*.md from documentation/ (override generated chart page when helmrelease_doc: manual).
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
from doc_metadata import git_last_modified, inject_freshness_banner, site_build_info
from doc_paths import DOCS_ROOT, app_dir_to_doc_dir, clusters_rel_to_doc_dir, doc_staging_rel
from runbook_index import discover_alert_runbooks, get_alert_runbooks, parse_front_matter, runbook_targets_workload

RUNBOOK_INDEX_BEGIN = "<!-- runbook-index-begin -->"
RUNBOOK_INDEX_END = "<!-- runbook-index-end -->"

HOME_SOURCE_NAME = "index.md"

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
    "mk_runbook_template.md",
}
FRONT_MATTER_TITLE = re.compile(r"^title:\s*['\"]?(.*?)['\"]?\s*$", re.MULTILINE)
AREA_INDEX_NAME = "mk_index.md"
SITE_HOME_SOURCE = DOCS_ROOT / HOME_SOURCE_NAME
KUBERNETES_DOCS_ROOT = DOCS_ROOT / "kubernetes"
KUBERNETES_ROOT = CLUSTERS_ROOT / "main" / "kubernetes"
CLUSTER_TAB_TITLE = "Kubernetes"
KUBERNETES_CLUSTER_INDEX = Path("main/kubernetes/index.md")
DEFAULT_SITE_URL = "http://127.0.0.1:8000"
GIT_REVISION_PLUGIN = "git-revision-date-localized"


def has_git_history(repo_root: Path) -> bool:
    return (repo_root / ".git").is_dir()


def mkdocs_plugins_for_build(base: dict[str, Any], repo_root: Path) -> list[Any]:
    """Drop git-revision-date plugin when .git is absent (Docker / CI build context)."""
    plugins: list[Any] = list(base.get("plugins") or [])
    if has_git_history(repo_root):
        return plugins
    filtered: list[Any] = []
    for entry in plugins:
        if entry == GIT_REVISION_PLUGIN:
            continue
        if isinstance(entry, dict) and GIT_REVISION_PLUGIN in entry:
            continue
        filtered.append(entry)
    if len(filtered) != len(plugins):
        print(
            "No .git in build context; omitting git-revision-date-localized "
            "(per-page Git dates need local build; CI uses DOCS_BUILD_* + freshness banners)",
            file=sys.stderr,
        )
    return filtered


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


def is_kubernetes_root_doc(doc_rel: Path) -> bool:
    """mk_*.md directly under documentation/kubernetes/ (tab roots, not workload docs)."""
    return doc_rel.parent.as_posix() == "kubernetes"


def discover_kubernetes_root_mk() -> list[tuple[Path, Path]]:
    if not KUBERNETES_DOCS_ROOT.is_dir():
        return []
    found: list[tuple[Path, Path]] = []
    for path in sorted(KUBERNETES_DOCS_ROOT.glob("mk_*.md")):
        if path.name in SKIP_MK_FILES:
            continue
        doc_rel = path.relative_to(DOCS_ROOT)
        found.append((path, doc_staging_rel(doc_rel)))
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
    if not DOCS_ROOT.is_dir():
        return found
    for root, dirnames, filenames in DOCS_ROOT.walk():
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for name in filenames:
            if not MK_FILE.match(name) or name in SKIP_MK_FILES:
                continue
            if name == HOME_SOURCE_NAME and Path(root) == DOCS_ROOT:
                continue
            src = root / name
            doc_rel = src.relative_to(DOCS_ROOT)
            if is_kubernetes_root_doc(doc_rel):
                continue
            staging_rel = doc_staging_rel(doc_rel)
            if staging_rel in auto_generated_paths and name.lower() == AUTO_DOC_FILE.lower():
                continue
            found.append((src, staging_rel))
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
            custom = DOCS_ROOT / "kubernetes" / "my-apps" / prefix.parts[-1] / AREA_INDEX_NAME
        elif "_sections" in prefix.parts:
            custom = DOCS_ROOT / "kubernetes" / "_sections" / prefix.parts[-1] / AREA_INDEX_NAME
        else:
            custom = clusters_rel_to_doc_dir(prefix)
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
            custom = clusters_rel_to_doc_dir(Path(workload_key)) / AREA_INDEX_NAME
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
    nav: list = [
        {
            "Home": [
                "index.md",
                {"Site build info": "meta/site-build.md"},
            ]
        }
    ]
    for page in sorted(kubernetes_tab_pages, key=lambda p: p["title"].lower()):
        nav.append({page["title"]: page["href"]})
    cluster_nav: list = []
    if cluster_index_href:
        cluster_nav.append(cluster_index_href)
    cluster_nav.extend(tree_to_nav(nav_tree))
    if cluster_nav:
        nav.append({CLUSTER_TAB_TITLE: cluster_nav})
    return nav


def apply_freshness_to_file(
    staged_path: Path,
    git_source: Path,
    *,
    site_build: dict[str, str],
) -> None:
    rel = git_source.relative_to(REPO_ROOT)
    updated = git_last_modified(REPO_ROOT, rel)
    text = staged_path.read_text(encoding="utf-8")
    staged_path.write_text(
        inject_freshness_banner(
            text,
            last_updated=updated,
            source_rel=rel.as_posix(),
            site_built_at=site_build.get("built_at"),
            site_sha=site_build.get("sha"),
        ),
        encoding="utf-8",
    )


def write_site_build_page(staging_root: Path, site_build: dict[str, str]) -> str:
    """Published-site metadata (image build time, not per-page Git dates)."""
    rel = Path("meta/site-build.md")
    dest = staging_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"""---
title: Site build info
---

# Site build info

Use this page to confirm the **homelab-docs** Deployment is serving a recent image.

| Field | Value |
|-------|-------|
| **Image built at** | {site_build["built_at"]} |
| **Git commit (build)** | `{site_build["sha"]}` |
| **Image version tag** | `{site_build["image_version"]}` |

## Why a runbook link shows 404

1. The runbook `mk_*.md` must exist under `documentation/` and be included by `collect_mkdocs.py`.
2. Push to **`main`** so the **Build Homelab Docs** workflow rebuilds `ghcr.io/nerddotdad/homelab-docs`.
3. Cluster pulls the new tag (`homelab-docs` HelmRelease). With `tag: latest`, restart the pod if the registry tag moved but Kubernetes did not pull again.
4. Confirm `runbook_url` matches the file: `python scripts/runbook_url.py YourAlertName`

Per-page **Last updated (Git)** on each doc reflects the last commit that touched that source file, not necessarily the published image date above.
""",
        encoding="utf-8",
    )
    return rel.as_posix()


def render_runbook_index_table(site_build: dict[str, str]) -> str:
    rows: list[tuple[str, str, str, str]] = []
    for book in discover_alert_runbooks():
        href = book["href"]
        slug = Path(href).stem
        link = f"[{book['title']}]({slug}/)"
        updated = git_last_modified(REPO_ROOT, Path(href)) or "—"
        names = list(book.get("alertnames") or [])
        if not names and book.get("alertname"):
            names = [str(book["alertname"])]
        for name in names:
            rows.append((f"`{name}`", link, updated, href))
    rows.sort(key=lambda r: r[0].lower())
    lines = [
        RUNBOOK_INDEX_BEGIN,
        "",
        "| Alert | Runbook | Last updated (Git) | Source |",
        "|-------|---------|-------------------|--------|",
    ]
    for alert, link, updated, src in rows:
        lines.append(f"| {alert} | {link} | {updated} | `{src}` |")
    lines.extend(
        [
            "",
            f"_Table generated at site build ({site_build['built_at']}). "
            "Add rows manually in git only if you disable auto-generation markers._",
            "",
            RUNBOOK_INDEX_END,
        ]
    )
    return "\n".join(lines)


def update_runbook_index_staged(staging_root: Path, site_build: dict[str, str]) -> None:
    index_rel = Path("main/kubernetes/my-apps/observability/runbooks/mk_runbook_index.md")
    staged = staging_root / index_rel
    if not staged.is_file():
        return
    text = staged.read_text(encoding="utf-8")
    table = render_runbook_index_table(site_build)
    if RUNBOOK_INDEX_BEGIN in text and RUNBOOK_INDEX_END in text:
        before, rest = text.split(RUNBOOK_INDEX_BEGIN, 1)
        _, after = rest.split(RUNBOOK_INDEX_END, 1)
        text = before + table + after
    else:
        text = text.rstrip() + "\n\n## Runbook index\n\n" + table + "\n"
    staged.write_text(text, encoding="utf-8")


def write_site_home(staged_index: Path, *, site_build: dict[str, str]) -> None:
    if SITE_HOME_SOURCE.is_file():
        shutil.copy2(SITE_HOME_SOURCE, staged_index)
        apply_freshness_to_file(staged_index, SITE_HOME_SOURCE, site_build=site_build)
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


def stage_kubernetes_tab_pages(site_build: dict[str, str]) -> list[dict[str, str]]:
    """Stage mk_*.md in documentation/kubernetes/ as extra top-level tabs."""
    tabs: list[dict[str, str]] = []
    for src, staging_rel in discover_kubernetes_root_mk():
        dest = STAGING_DIR / staging_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        apply_freshness_to_file(dest, src, site_build=site_build)
        tabs.append({"title": title_from_file(src), "href": staging_rel.as_posix()})
    return tabs


def stage_doc(
    nav_tree: dict,
    rel: Path,
    title: str,
    src: Path | None,
    *,
    release_to_workload: dict[str, str],
    site_build: dict[str, str],
    is_helm: bool = False,
    runbook_meta: dict[str, Any] | None = None,
    git_source: Path | None = None,
) -> None:
    dest = STAGING_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src is not None:
        shutil.copy2(src, dest)
        apply_freshness_to_file(dest, git_source or src, site_build=site_build)
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
    if not DOCS_ROOT.is_dir():
        print(f"documentation root not found: {DOCS_ROOT}", file=sys.stderr)
        return 1

    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)
    site_build = site_build_info(REPO_ROOT)
    write_site_build_page(STAGING_DIR, site_build)
    write_site_home(STAGING_DIR / "index.md", site_build=site_build)
    kubernetes_tab_pages = stage_kubernetes_tab_pages(site_build)

    nav_tree: dict = {}
    release_to_workload = build_release_to_workload_map()
    helm_count = 0
    manual_count = 0
    mk_count = 0

    helm_git_sources: dict[Path, Path] = {}
    for rel, title in generate_helm_release_docs(STAGING_DIR):
        stage_doc(
            nav_tree,
            rel,
            title,
            None,
            release_to_workload=release_to_workload,
            site_build=site_build,
            is_helm=True,
        )
        helm_count += 1

    for helm_path in discover_helm_release_paths():
        helm_git_sources[helm_doc_staging_rel(helm_path)] = helm_path

    for rel in list(helm_git_sources):
        staged = STAGING_DIR / rel
        if staged.is_file():
            apply_freshness_to_file(staged, helm_git_sources[rel], site_build=site_build)

    for src, rel in discover_mk_files():
        runbook_meta = None
        if RUNBOOK_FILE.match(src.name):
            runbook_meta = parse_front_matter(src)
        stage_doc(
            nav_tree,
            rel,
            title_from_file(src),
            src,
            release_to_workload=release_to_workload,
            site_build=site_build,
            runbook_meta=runbook_meta,
        )
        mk_count += 1

    for helm_path in discover_helm_release_paths():
        app_dir = helm_path.parent
        meta = yaml.safe_load(helm_path.read_text(encoding="utf-8")) or {}
        name = str((meta.get("metadata") or {}).get("name") or app_dir.parent.name)
        doc_name = output_doc_name(helm_path, name)
        if not is_manual_helm_doc(app_dir, doc_name):
            continue
        src = app_dir_to_doc_dir(app_dir) / doc_name
        rel = doc_staging_rel(src.relative_to(DOCS_ROOT))
        stage_doc(
            nav_tree,
            rel,
            title_from_file(src),
            src,
            release_to_workload=release_to_workload,
            site_build=site_build,
            is_helm=True,
        )
        manual_count += 1

    update_runbook_index_staged(STAGING_DIR, site_build)

    write_workload_indexes(nav_tree, STAGING_DIR)
    write_section_indexes(nav_tree, STAGING_DIR)
    cluster_index_href = write_kubernetes_cluster_index(nav_tree, STAGING_DIR)

    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    base["plugins"] = mkdocs_plugins_for_build(base, REPO_ROOT)
    base["docs_dir"] = "staging"
    base["site_dir"] = "site"
    base["site_url"] = os.environ.get("MKDOCS_SITE_URL", DEFAULT_SITE_URL).rstrip("/")
    base["copyright"] = (
        f"Site image built {site_build['built_at']} · "
        f"tag {site_build['image_version']} · git {site_build['sha'][:12]}"
    )
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
