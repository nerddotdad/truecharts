"""Map documentation/ sources to MkDocs staging paths (public URLs unchanged)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLUSTERS_ROOT = REPO_ROOT / "clusters"
DOCS_ROOT = REPO_ROOT / "documentation"


def doc_staging_rel(doc_rel: Path) -> Path:
    """documentation/kubernetes/... → main/kubernetes/...; index.md stays at site root."""
    parts = list(doc_rel.parts)
    if not parts:
        return doc_rel
    if parts[0] == "kubernetes":
        return Path("main", *parts)
    return doc_rel


def clusters_rel_to_doc_dir(clusters_rel: Path) -> Path:
    """main/kubernetes/my-apps/foo → documentation/kubernetes/my-apps/foo."""
    parts = list(clusters_rel.parts)
    if parts and parts[0] == "main":
        parts = parts[1:]
    return DOCS_ROOT.joinpath(*parts)


def app_dir_to_doc_dir(app_dir: Path) -> Path:
    return clusters_rel_to_doc_dir(app_dir.relative_to(CLUSTERS_ROOT))


def supplemental_mk_dirs(app_dir: Path) -> list[Path]:
    """Directories under documentation/ that mirror app/ and workload mk_*.md locations."""
    dirs = [app_dir_to_doc_dir(app_dir)]
    if app_dir.name == "app":
        dirs.append(app_dir_to_doc_dir(app_dir.parent))
    return [d for d in dirs if d.is_dir()]


def discover_doc_mk_sources() -> list[Path]:
    if not DOCS_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in DOCS_ROOT.rglob("mk_*.md")
        if path.is_file()
    )
