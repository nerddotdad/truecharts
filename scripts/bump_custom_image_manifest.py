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


def bump_helm_tag(path: Path, registry: str, version: str) -> bool:
    text = path.read_text(encoding="utf-8")
    dep = re.escape(registry)
    pattern = re.compile(
        rf"(# renovate: datasource=\S+ depName={dep}\s*\n\s*tag:\s*)[\"']?[^\"'\s#]+[\"']?",
        re.MULTILINE,
    )
    new_text, n = pattern.subn(rf'\1"{version}"', text, count=1)
    if n == 0:
        pattern2 = re.compile(
            rf"(repository:\s*{dep}\s*\n(?:\s+pullPolicy:.*\n)?\s*tag:\s*)[\"']?[^\"'\s#]+[\"']?",
            re.MULTILINE,
        )
        new_text, n = pattern2.subn(rf'\1"{version}"', text, count=1)
    if n == 0:
        print(f"  skip {path}: no tag: line found for {registry}", file=sys.stderr)
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"  updated {path} -> tag {version}")
        return True
    return False


def bump_deployment_image(path: Path, registry: str, version: str) -> bool:
    text = path.read_text(encoding="utf-8")
    dep = re.escape(registry)
    pattern = re.compile(
        rf"(# renovate: datasource=\S+ depName={dep}\s*\n\s*image:\s*){dep}:[^\s#]+",
        re.MULTILINE,
    )
    new_text, n = pattern.subn(rf"\1{registry}:{version}", text, count=1)
    if n == 0:
        pattern2 = re.compile(rf"(image:\s*){dep}:[^\s#]+", re.MULTILINE)
        new_text, n = pattern2.subn(rf"\1{registry}:{version}", text, count=1)
    if n == 0:
        print(f"  skip {path}: no image: line found for {registry}", file=sys.stderr)
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"  updated {path} -> image {registry}:{version}")
        return True
    return False


def bump_image(image: str, version: str, image_map: dict) -> int:
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
            ok = bump_helm_tag(path, registry, version)
        elif kind == "deployment-image":
            ok = bump_deployment_image(path, registry, version)
        else:
            print(f"  skip unknown kind {kind!r}", file=sys.stderr)
        if ok:
            changed += 1
    return changed


def load_bumps_from_dir(directory: Path) -> list[tuple[str, str]]:
    bumps: list[tuple[str, str]] = []
    for json_file in sorted(directory.glob("**/*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for item in data:
                bumps.append((item["image"], item["version"]))
        else:
            bumps.append((data["image"], data["version"]))
    return bumps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", default=[], help="Image dir name")
    parser.add_argument("--version", action="append", default=[], help="Semver tag (pair with --image)")
    parser.add_argument(
        "--from-dir",
        type=Path,
        help="Directory of bump-*.json artifacts from CI",
    )
    args = parser.parse_args()
    image_map = load_map()

    bumps: list[tuple[str, str]] = []
    if args.from_dir:
        bumps = load_bumps_from_dir(args.from_dir)
    elif args.image:
        if len(args.image) != len(args.version):
            print("--image and --version counts must match", file=sys.stderr)
            return 1
        bumps = list(zip(args.image, args.version, strict=True))
    else:
        parser.error("use --from-dir or --image/--version")

    total = 0
    for image, version in bumps:
        print(f"{image} -> {version}")
        total += bump_image(image, version, image_map)
    print(f"Done ({total} manifest file(s) changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
