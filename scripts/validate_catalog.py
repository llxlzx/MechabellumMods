#!/usr/bin/env python3
"""Validate MechabellumMods catalog.json: required fields, unique ids, file paths,
and that every entry carries the sha256 of the file it points at.

The hash is not cosmetic: the manager refuses mirror-served downloads for entries
without one, and uses it to detect that a player's local copy went stale. Run
scripts/stamp_hashes.py to fill or refresh it after changing any mod binary.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"
REQUIRED = ("id", "name", "file")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_CATEGORIES = {
    "OverlayUI", "QoL", "Camera", "CombatAssist",
    "Economy", "ReplayDebug", "Misc",
}


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

    errors: list[str] = []
    seen: set[str] = set()

    for i, mod in enumerate(mods):
        if not isinstance(mod, dict):
            errors.append(f"mods[{i}]: not an object")
            continue

        for key in REQUIRED:
            val = mod.get(key)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"mods[{i}]: missing/empty '{key}'")

        mod_id = mod.get("id")
        if isinstance(mod_id, str) and mod_id.strip():
            if mod_id in seen:
                errors.append(f"duplicate id: {mod_id}")
            seen.add(mod_id)

        rel = mod.get("file")
        declared = mod.get("sha256")
        if not isinstance(declared, str) or not SHA256_HEX.match(declared.strip().lower()):
            errors.append(
                f"id={mod.get('id')!r}: missing/invalid 'sha256' "
                f"(run scripts/stamp_hashes.py)"
            )
            declared = None

        if isinstance(rel, str) and rel.strip():
            path = ROOT / rel.replace("\\", "/")
            if not path.is_file():
                errors.append(f"id={mod.get('id')!r}: file not found: {rel}")
            elif declared is not None:
                actual = sha256_of(path)
                if actual != declared.strip().lower():
                    errors.append(
                        f"id={mod.get('id')!r}: sha256 mismatch for {rel} "
                        f"(catalog={declared.strip().lower()}, file={actual}; "
                        f"run scripts/stamp_hashes.py)"
                    )

        preview = mod.get("preview")
        if isinstance(preview, str) and preview.strip():
            ppath = ROOT / preview.replace("\\", "/")
            if not ppath.is_file():
                errors.append(f"id={mod.get('id')!r}: preview not found: {preview}")

        cat = mod.get("category")
        if cat is not None:
            if not isinstance(cat, str) or cat.strip() not in ALLOWED_CATEGORIES:
                errors.append(f"id={mod.get('id')!r}: invalid category: {cat!r}")

        tags = mod.get("tags")
        if tags is not None:
            if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
                errors.append(f"id={mod.get('id')!r}: tags must be a string array")

    if errors:
        print("catalog validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(mods)} mods, ids unique, files present, sha256 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
