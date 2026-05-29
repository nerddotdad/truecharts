#!/usr/bin/env python3
"""Update HelmRelease / Deployment pins after custom image CI builds."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = Path(__file__).resolve().parent / "custom_image_manifest_map.yaml"


def load_map() -> dict:
    data = yaml.safe_load(MAP_FILE.read_text(encoding="utf-8")) or {}
    return data.get("images") or {}


def format_tag(version: str, digest: str | None = None) -> str:
    if digest:
        hex_part = digest.removeprefix("sha256:")
        return f"{version}@sha256:{hex_part}"
    return version


def _sub_first_group(pattern: re.Pattern[str], text: str, suffix: str) -> tuple[str, int]:
    """Replace match; use callable so \\1 is not parsed as group 11 when suffix starts with a digit."""

    def repl(match: re.Match[str]) -> str:
        return match.group(1) + suffix

    return pattern.subn(repl, text, count=1)


def bump_helm_tag(path: Path, registry: str, version: str, digest: str | None = None) -> bool:
    text = path.read_text(encoding="utf-8")
    tag_value = format_tag(version, digest)
    dep = re.escape(registry)
    pattern = re.compile(
        rf"(# renovate: datasource=\S+ depName={dep}\s*\n\s*tag:\s*)[\"']?[^\"'\s#]+[\"']?",
        re.MULTILINE,
    )
    new_text, n = _sub_first_group(pattern, text, tag_value)
    if n == 0:
        pattern2 = re.compile(
            rf"(repository:\s*{dep}\s*\n(?:\s+pullPolicy:.*\n)?\s*tag:\s*)[\"']?[^\"'\s#]+[\"']?",
            re.MULTILINE,
        )
        new_text, n = _sub_first_group(pattern2, text, tag_value)
    if n == 0:
        print(f"  skip {path}: no tag: line found for {registry}", file=sys.stderr)
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"  updated {path} -> tag {tag_value}")
        return True
    return False


def bump_deployment_image(path: Path, registry: str, version: str, digest: str | None = None) -> bool:
    text = path.read_text(encoding="utf-8")
    tag_value = format_tag(version, digest)
    dep = re.escape(registry)
    pattern = re.compile(
        rf"(# renovate: datasource=\S+ depName={dep}\s*\n\s*image:\s*){dep}:[^\s#]+",
        re.MULTILINE,
    )
    new_text, n = _sub_first_group(pattern, text, f"{registry}:{tag_value}")
    if n == 0:
        pattern2 = re.compile(rf"(image:\s*){dep}:[^\s#]+", re.MULTILINE)
        new_text, n = _sub_first_group(pattern2, text, f"{registry}:{tag_value}")
    if n == 0:
        print(f"  skip {path}: no image: line found for {registry}", file=sys.stderr)
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"  updated {path} -> image {registry}:{tag_value}")
        return True
    return False


def bump_image(image: str, version: str, image_map: dict, digest: str | None = None) -> int:
    entry = image_map.get(image)
    if not entry:
        print(f"unknown image {image!r} (not in {MAP_FILE.name})", file=sys.stderr)
        return 0
    registry = entry["registry"]
    changed = 0
    for manifest in entry.get("manifests") or []:
        path = REPO_ROOT / manifest["path"]
        kind = manifest["kind"]
        if not path.is_file():
            print(f"  skip missing {path}", file=sys.stderr)
            continue
        ok = False
        if kind == "helm-tag":
            ok = bump_helm_tag(path, registry, version, digest)
        elif kind == "deployment-image":
            ok = bump_deployment_image(path, registry, version, digest)
        else:
            print(f"  skip unknown kind {kind!r}", file=sys.stderr)
        if ok:
            changed += 1
    return changed


def load_bumps_from_dir(directory: Path) -> list[tuple[str, str, str | None]]:
    bumps: list[tuple[str, str, str | None]] = []
    for json_file in sorted(directory.glob("**/*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for item in items:
            bumps.append((item["image"], item["version"], item.get("digest")))
    return bumps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", default=[], help="Image dir name")
    parser.add_argument("--version", action="append", default=[], help="Semver tag (pair with --image)")
    parser.add_argument("--digest", action="append", default=[], help="Optional sha256 digest (pair with --image)")
    parser.add_argument(
        "--from-dir",
        type=Path,
        help="Directory of bump-*.json artifacts from CI",
    )
    args = parser.parse_args()
    image_map = load_map()

    bumps: list[tuple[str, str, str | None]] = []
    if args.from_dir:
        bumps = load_bumps_from_dir(args.from_dir)
    elif args.image:
        if len(args.image) != len(args.version):
            print("--image and --version counts must match", file=sys.stderr)
            return 1
        if args.digest and len(args.digest) not in (0, len(args.image)):
            print("--digest count must match --image when provided", file=sys.stderr)
            return 1
        digests = args.digest or [None] * len(args.image)
        bumps = [
            (image, version, digest)
            for image, version, digest in zip(args.image, args.version, digests, strict=True)
        ]
    else:
        parser.error("use --from-dir or --image/--version")

    total = 0
    for image, version, digest in bumps:
        label = format_tag(version, digest)
        print(f"{image} -> {label}")
        total += bump_image(image, version, image_map, digest)
    print(f"Done ({total} manifest file(s) changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
