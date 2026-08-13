#!/usr/bin/env python3
"""Build an isolated GitHub Pages artifact from an explicit file allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
from urllib.parse import urlsplit


FORBIDDEN_TOP_LEVEL = {
    ".git",
    ".github",
    ".seo",
    "_site",
    "docs",
    "google-sheets-template",
    "node_modules",
    "scripts",
    "server",
    "tests",
}
FORBIDDEN_FILE_NAMES = {
    "bun.lock",
    "bun.lockb",
    "cargo.lock",
    "cargo.toml",
    "composer.json",
    "composer.lock",
    "gemfile",
    "gemfile.lock",
    "go.mod",
    "go.sum",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "railway.json",
    "uv.lock",
    "yarn.lock",
}
WILDCARD_CHARACTERS = set("*?[]{}")
WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class ArtifactError(RuntimeError):
    """A fail-closed manifest or filesystem validation error."""


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or _is_reparse_point(path)


def validate_manifest_path(raw_path: str) -> str:
    if raw_path != raw_path.strip():
        raise ArtifactError(f"manifest path has surrounding whitespace: {raw_path!r}")
    if not raw_path:
        raise ArtifactError("manifest contains an empty path")
    if "\\" in raw_path:
        raise ArtifactError(f"manifest path must use forward slashes: {raw_path}")
    if "//" in raw_path:
        raise ArtifactError(f"manifest path contains an empty component: {raw_path}")
    if any(character in raw_path for character in WILDCARD_CHARACTERS):
        raise ArtifactError(f"manifest path contains a wildcard: {raw_path}")
    if WINDOWS_DRIVE.match(raw_path) or PurePosixPath(raw_path).is_absolute():
        raise ArtifactError(f"manifest path must be repository-relative: {raw_path}")
    parsed = urlsplit(raw_path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or ":" in raw_path:
        raise ArtifactError(f"manifest path must not be a URL: {raw_path}")

    parts = PurePosixPath(raw_path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ArtifactError(f"manifest path contains traversal or dot components: {raw_path}")

    folded = tuple(part.casefold() for part in parts)
    if folded[0] in FORBIDDEN_TOP_LEVEL:
        raise ArtifactError(f"manifest path is internal or forbidden: {raw_path}")
    if any(part in {".git", ".github", ".seo", "node_modules"} for part in folded):
        raise ArtifactError(f"manifest path is internal or forbidden: {raw_path}")
    if any(part.startswith(".") for part in parts) and raw_path != ".nojekyll":
        raise ArtifactError(f"hidden paths are forbidden except .nojekyll: {raw_path}")
    name = folded[-1]
    suffix = PurePosixPath(name).suffix
    if name in FORBIDDEN_FILE_NAMES or name.startswith("requirements") and suffix == ".txt":
        raise ArtifactError(f"package, lock, or backend configuration is forbidden: {raw_path}")
    if suffix in {".key", ".lock", ".map", ".markdown", ".md", ".pem"}:
        raise ArtifactError(f"internal, credential, or generated file is forbidden: {raw_path}")
    if name == ".env" or name.startswith(".env."):
        raise ArtifactError(f"environment files are forbidden: {raw_path}")
    if name.endswith(("~", ".bak", ".backup", ".orig", ".rej", ".swp", ".swo", ".temp", ".tmp")):
        raise ArtifactError(f"backup, temporary, or editor files are forbidden: {raw_path}")
    if raw_path.casefold() == "pages-public-manifest.txt":
        raise ArtifactError("the public manifest cannot include itself")
    return PurePosixPath(*parts).as_posix()


def read_manifest(manifest_path: Path) -> tuple[list[str], bytes]:
    try:
        raw = manifest_path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ArtifactError(f"cannot read strict UTF-8 manifest {manifest_path}: {exc}") from exc
    if text.startswith("\ufeff"):
        raise ArtifactError("manifest must be UTF-8 without a BOM")

    entries: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        try:
            entries.append(validate_manifest_path(line))
        except ArtifactError as exc:
            raise ArtifactError(f"manifest line {line_number}: {exc}") from exc

    if not entries:
        raise ArtifactError("manifest has no effective file entries")
    if len(entries) != len(set(entries)) or len(entries) != len({entry.casefold() for entry in entries}):
        raise ArtifactError("manifest contains duplicate or case-colliding entries")
    if entries != sorted(entries):
        raise ArtifactError("manifest entries must be sorted")
    return entries, raw


def _assert_source_file(source_root: Path, relative_path: str) -> Path:
    candidate = source_root
    for part in PurePosixPath(relative_path).parts:
        candidate = candidate / part
        if not candidate.exists() and not candidate.is_symlink():
            raise ArtifactError(f"allowlisted source file is missing: {relative_path}")
        if _is_link(candidate):
            raise ArtifactError(f"symlink or reparse component is forbidden: {relative_path}")

    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(source_root)
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"source path escapes the source root: {relative_path}") from exc
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        kind = "directory" if stat.S_ISDIR(mode) else "special file"
        raise ArtifactError(f"allowlisted path is a {kind}, not a regular file: {relative_path}")
    return resolved


def _prepare_output(source_root: Path, output: Path) -> Path:
    absolute_output = output if output.is_absolute() else source_root / output
    absolute_output = absolute_output.absolute()
    if absolute_output == Path(absolute_output.anchor):
        raise ArtifactError("refusing to use a filesystem root as artifact output")
    if absolute_output == source_root:
        raise ArtifactError("refusing to use the source root as artifact output")
    try:
        absolute_output.relative_to(source_root)
    except ValueError as exc:
        raise ArtifactError("artifact output must be a child of the source root") from exc

    cursor = source_root
    for part in absolute_output.relative_to(source_root).parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _is_link(cursor):
                raise ArtifactError(f"artifact output contains a symlink or reparse point: {cursor}")
    if absolute_output.exists():
        if not absolute_output.is_dir():
            raise ArtifactError(f"artifact output exists and is not a directory: {absolute_output}")
        shutil.rmtree(absolute_output)
    absolute_output.mkdir(parents=True, exist_ok=False)
    return absolute_output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_artifact(source_root: Path, manifest_path: Path, output: Path) -> dict[str, object]:
    source_root = source_root.resolve(strict=True)
    if not source_root.is_dir() or _is_link(source_root):
        raise ArtifactError(f"source root must be a real directory: {source_root}")
    manifest_path = manifest_path if manifest_path.is_absolute() else source_root / manifest_path
    entries, manifest_bytes = read_manifest(manifest_path)
    source_files = {entry: _assert_source_file(source_root, entry) for entry in entries}
    output_root = _prepare_output(source_root, output)

    inventory: list[dict[str, object]] = []
    aggregate = hashlib.sha256()
    for entry in entries:
        source = source_files[entry]
        destination = output_root.joinpath(*PurePosixPath(entry).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
        file_hash = sha256_file(destination)
        size = destination.stat().st_size
        aggregate.update(entry.encode("utf-8") + b"\0" + file_hash.encode("ascii") + b"\n")
        inventory.append({"path": entry, "bytes": size, "sha256": file_hash})

    report = {
        "artifact_sha256": aggregate.hexdigest(),
        "file_count": len(inventory),
        "files": inventory,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "output": str(output_root),
        "total_bytes": sum(int(item["bytes"]) for item in inventory),
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--manifest", default="pages-public-manifest.txt")
    parser.add_argument("--output", default="_site")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_artifact(Path(args.source_root), Path(args.manifest), Path(args.output))
    except ArtifactError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
