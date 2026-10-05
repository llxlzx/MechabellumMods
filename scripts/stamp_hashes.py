#!/usr/bin/env python3
"""Stamp each mod's real sha256 and byte size into catalog.json.

Consumers of the hash:

- The manager verifies every download against it, whatever the source. A mod is
  a .NET assembly loaded into the game, and neither a mirror nor a release asset
  is self-authenticating.
- The manager tells an outdated local copy from a current one by comparing the
  catalog hash against the bytes on disk, which keeps working even when an
  author forgets to bump "version".

Consumers of the size:

- The download UI needs a total to show progress against, because a resumed or
  mirror-served response cannot be trusted to carry Content-Length.
- The downloader rejects a response whose length disagrees with the catalog
  before writing gigabytes to disk.

With --origin-base, 'originUrl' is stamped as well. That is used after
tools/publish-mods-release.ps1 uploads the binaries as Release assets, which is
how a mod larger than GitHub's 100 MB per-file push limit gets distributed.

The rewrite is a line-level insert rather than a json.dump so the hand-kept
formatting (inline "tags" arrays, CRLF endings) survives untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"

FILE_LINE = re.compile(r'^(?P<indent>\s*)"file"\s*:\s*"(?P<rel>[^"]+)"\s*,\s*$')
PREVIEW_LINE = re.compile(
    r'^(?P<indent>\s*)"preview"\s*:\s*"(?P<rel>[^"]+)"\s*,?\s*$'
)
PREVIEW_HASH_LINE = re.compile(
    r'^\s*"previewSha256"\s*:\s*"[0-9a-fA-F]{64}"\s*,?\s*$'
)
# The stamped keys are rewritten as one block, so the matcher covers all of them.
STAMP_LINE = re.compile(r'^\s*"(?:sha256|size|originUrl)"\s*:\s*(?:"[^"]*"|\d+)\s*,?\s*$')


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_name(rel: str) -> str:
    """Release asset name for a catalog path.

    Release assets share one flat namespace, so the directory has to survive in
    the name: two mods may both ship 'Mod.dll'. tools/publish-mods-release.ps1
    and validate_catalog.py both depend on this exact rule.
    """
    return rel.replace("\\", "/").replace("/", "__")


def joined_digest(root: Path, parts: list) -> tuple[str, int]:
    blob = bytearray()
    for part in parts:
        rel = part["file"].replace("\\", "/")
        blob.extend((root / rel).read_bytes())
    return hashlib.sha256(blob).hexdigest(), len(blob)


def origin_line(mod: dict, origin_base: str | None, indent: str, ending: str) -> str | None:
    parts = mod.get("parts")
    if isinstance(parts, list) and parts:
        return None
    if not origin_base:
        return None
    rel = mod.get("file")
    if not isinstance(rel, str):
        return None
    return f'{indent}"originUrl": "{origin_base}/{asset_name(rel)}",{ending}'


def stamp_preview_lines(lines: list[str]) -> list[str]:
    """Insert previewSha256 after each preview path, including locale overrides.

    The hash line takes the comma when another property follows. When preview was
    the last property, the hash line has no trailing comma so the object stays valid.
    """
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = PREVIEW_LINE.match(line.rstrip("\r\n"))
        if match is None:
            out.append(line)
            index += 1
            continue

        rel = match.group("rel")
        ending = line[len(line.rstrip("\r\n")) :] or "\n"
        indent = match.group("indent")
        index += 1
        if index < len(lines) and PREVIEW_HASH_LINE.match(lines[index].rstrip("\r\n")):
            index += 1

        path = ROOT / rel.replace("\\", "/")
        if not path.is_file():
            out.append(line)
            continue

        nxt = lines[index] if index < len(lines) else ""
        comma = "" if nxt.lstrip().startswith("}") else ","
        out.append(f'{indent}"preview": "{rel}",{ending}')
        out.append(f'{indent}"previewSha256": "{sha256_of(path)}"{comma}{ending}')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin-base",
        help="Release download base, e.g. "
             "https://github.com/OWNER/REPO/releases/download/TAG . "
             "Omit to leave any existing originUrl untouched.",
    )
    args = parser.parse_args()
    origin_base = args.origin_base.rstrip("/") if args.origin_base else None
    if not CATALOG.is_file():
        print(f"ERROR: missing {CATALOG}", file=sys.stderr)
        return 1

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    mods = data.get("mods")
    if not isinstance(mods, list):
        print("ERROR: catalog.json 'mods' must be an array", file=sys.stderr)
        return 1

    wanted: dict[str, tuple[str, int]] = {}
    mod_by_rel: dict[str, dict] = {}
    for mod in mods:
        rel = mod.get("file")
        if not isinstance(rel, str) or not rel.strip():
            print(f"ERROR: id={mod.get('id')!r} has no 'file'", file=sys.stderr)
            return 1
        mod_by_rel[rel] = mod
        parts = mod.get("parts")
        has_parts = isinstance(parts, list) and parts
        path = ROOT / rel.replace("\\", "/")
        if has_parts:
            joined, joined_size = joined_digest(ROOT, parts)
            if path.is_file():
                whole = sha256_of(path)
                if whole != joined:
                    print(
                        f"ERROR: id={mod.get('id')!r} whole file sha256 "
                        f"({whole}) != joined parts ({joined})",
                        file=sys.stderr,
                    )
                    return 1
            wanted[rel] = (joined, joined_size)
        else:
            if not path.is_file():
                print(f"ERROR: id={mod.get('id')!r} file not found: {rel}", file=sys.stderr)
                return 1
            wanted[rel] = (sha256_of(path), path.stat().st_size)

    with CATALOG.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()

    out: list[str] = []
    changed = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        index += 1

        match = FILE_LINE.match(line.rstrip("\r\n"))
        if match is None:
            continue

        rel = match.group("rel")
        entry = wanted.get(rel)
        if entry is None:
            continue

        digest, size = entry
        indent = match.group("indent")
        ending = line[len(line.rstrip("\r\n")):] or "\n"
        stamped = [
            f'{indent}"sha256": "{digest}",{ending}',
            f'{indent}"size": {size},{ending}',
        ]

        existing: list[str] = []
        while index < len(lines) and STAMP_LINE.match(lines[index].rstrip("\r\n")):
            existing.append(lines[index])
            index += 1

        mod = mod_by_rel[rel]
        has_parts = isinstance(mod.get("parts"), list) and mod.get("parts")
        origin = origin_line(mod, origin_base, indent, ending)
        if origin is not None:
            stamped.append(origin)
        elif not has_parts:
            # Not ours to manage on this run: carry any existing value through verbatim.
            stamped.extend(l for l in existing if '"originUrl"' in l)

        if existing != stamped:
            changed += 1
        out.extend(stamped)

    text = "".join(stamp_preview_lines(out))

    verify = json.loads(text)
    for mod in verify.get("mods", []):
        rel = mod.get("file")
        entry = wanted.get(rel)
        if entry is None or (mod.get("sha256"), mod.get("size")) != entry:
            print(
                f"ERROR: rewrite did not stamp id={mod.get('id')!r} correctly",
                file=sys.stderr,
            )
            return 1
        has_parts = isinstance(mod.get("parts"), list) and mod.get("parts")
        if origin_base and not has_parts:
            expected = f"{origin_base}/{asset_name(rel)}"
            if mod.get("originUrl") != expected:
                print(
                    f"ERROR: rewrite did not stamp originUrl for id={mod.get('id')!r}",
                    file=sys.stderr,
                )
                return 1

    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)

    fields = "sha256+size+originUrl" if origin_base else "sha256+size"
    print(f"OK: stamped {fields} for {len(wanted)} mods ({changed} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
