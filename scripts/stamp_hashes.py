#!/usr/bin/env python3
"""Stamp each mod's real sha256 into catalog.json.

Two consumers depend on this hash:

- The manager refuses to install a mod fetched from a domestic mirror unless the
  catalog declares a hash, because a mirror is not the signed-TLS GitHub origin.
- The manager tells an outdated local copy from a current one by comparing the
  catalog hash against the bytes on disk, which keeps working even when an
  author forgets to bump "version".

The rewrite is a line-level insert rather than a json.dump so the hand-kept
formatting (inline "tags" arrays, CRLF endings) survives untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"

FILE_LINE = re.compile(r'^(?P<indent>\s*)"file"\s*:\s*"(?P<rel>[^"]+)"\s*,\s*$')
SHA_LINE = re.compile(r'^\s*"sha256"\s*:\s*"[^"]*"\s*,?\s*$')


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not CATALOG.is_file():
        print(f"ERROR: missing {CATALOG}", file=sys.stderr)
        return 1

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    mods = data.get("mods")
    if not isinstance(mods, list):
        print("ERROR: catalog.json 'mods' must be an array", file=sys.stderr)
        return 1

    wanted: dict[str, str] = {}
    for mod in mods:
        rel = mod.get("file")
        if not isinstance(rel, str) or not rel.strip():
            print(f"ERROR: id={mod.get('id')!r} has no 'file'", file=sys.stderr)
            return 1
        path = ROOT / rel.replace("\\", "/")
        if not path.is_file():
            print(f"ERROR: id={mod.get('id')!r} file not found: {rel}", file=sys.stderr)
            return 1
        wanted[rel] = sha256_of(path)

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
        digest = wanted.get(rel)
        if digest is None:
            continue

        ending = line[len(line.rstrip("\r\n")):] or "\n"
        stamped = f'{match.group("indent")}"sha256": "{digest}",{ending}'

        if index < len(lines) and SHA_LINE.match(lines[index].rstrip("\r\n")):
            if lines[index] != stamped:
                changed += 1
            out.append(stamped)
            index += 1
        else:
            changed += 1
            out.append(stamped)

    text = "".join(out)

    verify = json.loads(text)
    for mod in verify.get("mods", []):
        rel = mod.get("file")
        if mod.get("sha256") != wanted.get(rel):
            print(
                f"ERROR: rewrite did not stamp id={mod.get('id')!r} correctly",
                file=sys.stderr,
            )
            return 1

    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)

    print(f"OK: stamped {len(wanted)} mods ({changed} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
