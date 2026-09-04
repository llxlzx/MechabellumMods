#!/usr/bin/env python3
"""Validate MechabellumMods catalog.json: required fields, unique ids, file paths exist."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"
REQUIRED = ("id", "name", "file")
ALLOWED_CATEGORIES = {
    "OverlayUI", "QoL", "Camera", "CombatAssist",
    "Economy", "ReplayDebug", "Misc",
}


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
        if isinstance(rel, str) and rel.strip():
            path = ROOT / rel.replace("\\", "/")
            if not path.is_file():
                errors.append(f"id={mod.get('id')!r}: file not found: {rel}")

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

    print(f"OK: {len(mods)} mods, ids unique, files present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
