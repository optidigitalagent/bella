#!/usr/bin/env python3
"""Fail-closed verification for the isolated Bella GitHub Pages artifact."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib.parse import unquote, urlsplit


MAX_ARTIFACT_BYTES = 1_000_000_000
STATIC_EXTENSIONS = {
    ".aac", ".avif", ".css", ".csv", ".gif", ".html", ".ico", ".jpeg", ".jpg",
    ".js", ".json", ".m4a", ".mov", ".mp3", ".mp4", ".ogg", ".otf", ".pdf", ".png",
    ".svg", ".ttf", ".txt", ".wav", ".webm", ".webmanifest", ".webp", ".woff", ".woff2", ".xml",
}
IGNORED_PREFIXES = ("#", "//", "data:", "http:", "https:", "javascript:", "mailto:", "tel:")
CSS_REFERENCE = re.compile(
    r"(?:url\(\s*['\"]?|@import\s+['\"])([^'\")\s;]+)", re.IGNORECASE
)
JS_STATIC_REFERENCE = re.compile(
    r"['\"`]([^'\"`\r\n?#]+\.(?:aac|avif|css|csv|gif|html|ico|jpe?g|js|json|m4a|mov|mp3|mp4|ogg|otf|pdf|png|svg|ttf|txt|wav|webm|webmanifest|webp|woff2?|xml)(?:[?#][^'\"`]*)?)['\"`]",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(rb"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(rb"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(rb"(?<![0-9])[0-9]{6,12}:[A-Za-z0-9_-]{30,}"),
)
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _load_builder_module():
    path = Path(__file__).with_name("build-pages-artifact.py")
    spec = importlib.util.spec_from_file_location("bella_pages_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _load_builder_module()
ArtifactError = BUILDER.ArtifactError


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or _is_reparse_point(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_no_secret_content(relative_path: str, path: Path) -> None:
    if path.suffix.casefold() not in {"", ".css", ".csv", ".html", ".js", ".json", ".txt", ".xml"}:
        return
    content = path.read_bytes()
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        raise ArtifactError(f"probable credential or private key content in artifact: {relative_path}")


def _sensitive_name(relative_path: str) -> str | None:
    parts = PurePosixPath(relative_path).parts
    folded_parts = tuple(part.casefold() for part in parts)
    name = folded_parts[-1]
    suffix = PurePosixPath(name).suffix
    if relative_path != ".nojekyll" and any(part.startswith(".") for part in parts):
        return "hidden path"
    if name == ".env" or name.startswith(".env."):
        return "environment file"
    if any(token in name for token in ("credential", "private-key", "private_key", "secret")):
        return "credential or secret material"
    if name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock", "poetry.lock"} or name.endswith(".lock"):
        return "lockfile"
    if name == "railway.json":
        return "backend configuration"
    if suffix in {".md", ".markdown", ".map"}:
        return "internal documentation or source map"
    if name.endswith(("~", ".bak", ".backup", ".orig", ".rej", ".swp", ".swo", ".temp", ".tmp")):
        return "backup, temporary, or editor file"
    return None


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.inline_css: list[str] = []
        self.inline_js: list[str] = []
        self._in_style = False
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        for name, value in attrs:
            if value and (name in {"href", "poster", "src"} or name.startswith("data-")):
                self.references.append(value)
        srcset = attributes.get("srcset")
        if srcset:
            self.references.extend(item.strip().split()[0] for item in srcset.split(",") if item.strip())
        style = attributes.get("style")
        if style:
            self.inline_css.append(style)
        if tag == "meta" and attributes.get("content") and attributes.get("property", "").casefold() in {"og:image", "twitter:image"}:
            self.references.append(attributes["content"] or "")
        self._in_style = tag == "style"
        self._in_script = tag == "script" and not attributes.get("src")

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.inline_css.append(data)
        if self._in_script:
            self.inline_js.append(data)


def _resolve_reference(reference: str, source: str) -> str | None:
    reference = reference.strip()
    if not reference or reference.casefold().startswith(IGNORED_PREFIXES):
        return None
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    if "\\" in path:
        raise ArtifactError(f"dependency uses a backslash path in {source}: {reference}")
    suffix = PurePosixPath(path).suffix.casefold()
    if not suffix:
        return None
    if suffix not in STATIC_EXTENSIONS:
        return None
    if path.startswith("/"):
        combined = PurePosixPath(path.lstrip("/"))
    else:
        combined = PurePosixPath(source).parent / PurePosixPath(path)
    normalized: list[str] = []
    for part in combined.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not normalized:
                raise ArtifactError(f"dependency escapes artifact root in {source}: {reference}")
            normalized.pop()
        else:
            normalized.append(part)
    if not normalized:
        return None
    return PurePosixPath(*normalized).as_posix()


def _references_for(relative_path: str, artifact_file: Path) -> list[str]:
    suffix = artifact_file.suffix.casefold()
    if suffix not in {".css", ".html", ".js"}:
        return []
    text = artifact_file.read_text(encoding="utf-8", errors="strict")
    references: list[str] = []
    if suffix == ".html":
        parser = ReferenceParser()
        parser.feed(text)
        references.extend(parser.references)
        for css in parser.inline_css:
            references.extend(CSS_REFERENCE.findall(css))
        for javascript in parser.inline_js:
            references.extend(JS_STATIC_REFERENCE.findall(javascript))
    elif suffix == ".css":
        references.extend(CSS_REFERENCE.findall(text))
    else:
        references.extend(JS_STATIC_REFERENCE.findall(text))
    resolved: list[str] = []
    for reference in references:
        dependency = _resolve_reference(reference, relative_path)
        if dependency:
            resolved.append(dependency)
    return sorted(set(resolved))


def _artifact_inventory(output_root: Path) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    if _is_link(output_root) or not output_root.is_dir():
        raise ArtifactError(f"artifact root must be a real directory: {output_root}")
    for current, directory_names, file_names in os.walk(output_root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(directory_names):
            directory = current_path / name
            relative = directory.relative_to(output_root).as_posix()
            if _is_link(directory):
                raise ArtifactError(f"artifact contains a symlink or reparse directory: {relative}")
            if not stat.S_ISDIR(directory.lstat().st_mode):
                raise ArtifactError(f"artifact contains a non-directory entry: {relative}")
            directories.add(relative)
        for name in file_names:
            file_path = current_path / name
            relative = file_path.relative_to(output_root).as_posix()
            metadata = file_path.lstat()
            if _is_link(file_path):
                raise ArtifactError(f"artifact contains a symlink or reparse file: {relative}")
            if not stat.S_ISREG(metadata.st_mode):
                raise ArtifactError(f"artifact contains a special file: {relative}")
            if metadata.st_nlink != 1:
                raise ArtifactError(f"artifact file must have exactly one hard link: {relative}")
            files.add(relative)
    return files, directories


def verify_artifact(source_root: Path, manifest_path: Path, output: Path) -> dict[str, object]:
    source_root = source_root.resolve(strict=True)
    manifest_path = manifest_path if manifest_path.is_absolute() else source_root / manifest_path
    entries, manifest_bytes = BUILDER.read_manifest(manifest_path)
    expected = set(entries)
    source_files = {entry: BUILDER._assert_source_file(source_root, entry) for entry in entries}
    output_root = output if output.is_absolute() else source_root / output
    output_root = output_root.absolute()
    files, directories = _artifact_inventory(output_root)

    missing = sorted(expected - files)
    extra = sorted(files - expected)
    if missing or extra:
        raise ArtifactError(f"artifact inventory mismatch; missing={missing}, extra={extra}")
    expected_directories = {
        PurePosixPath(*PurePosixPath(entry).parts[:index]).as_posix()
        for entry in entries
        for index in range(1, len(PurePosixPath(entry).parts))
    }
    extra_directories = sorted(directories - expected_directories)
    if extra_directories:
        raise ArtifactError(f"artifact contains unnecessary directories: {extra_directories}")

    inventory: list[dict[str, object]] = []
    for entry in entries:
        reason = _sensitive_name(entry)
        if reason:
            raise ArtifactError(f"forbidden leak ({reason}): {entry}")
        artifact_file = output_root.joinpath(*PurePosixPath(entry).parts)
        source_hash = sha256_file(source_files[entry])
        artifact_hash = sha256_file(artifact_file)
        if source_hash != artifact_hash:
            raise ArtifactError(f"artifact differs from source: {entry}")
        _assert_no_secret_content(entry, artifact_file)
        inventory.append({"path": entry, "bytes": artifact_file.stat().st_size, "sha256": artifact_hash})

    if (source_root / "index.html").is_file() and "index.html" not in expected:
        raise ArtifactError("index.html is required as the artifact root entry point")
    for entry in entries:
        artifact_file = output_root.joinpath(*PurePosixPath(entry).parts)
        for dependency in _references_for(entry, artifact_file):
            if dependency not in expected:
                raise ArtifactError(f"unresolved local dependency in {entry}: {dependency}")
            if not output_root.joinpath(*PurePosixPath(dependency).parts).is_file():
                raise ArtifactError(f"dependency is missing from artifact in {entry}: {dependency}")

    total_bytes = sum(int(item["bytes"]) for item in inventory)
    if total_bytes >= MAX_ARTIFACT_BYTES:
        raise ArtifactError(f"artifact is not substantially below the size limit: {total_bytes} bytes")
    return {
        "file_count": len(entries),
        "files": inventory,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "status": "verified",
        "total_bytes": total_bytes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--manifest", default="pages-public-manifest.txt")
    parser.add_argument("--output", default="_site")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = verify_artifact(Path(args.source_root), Path(args.manifest), Path(args.output))
    except (ArtifactError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
