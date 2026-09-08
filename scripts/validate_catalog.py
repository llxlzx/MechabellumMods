#!/usr/bin/env python3
"""Validate MechabellumMods catalog.json: required fields, unique ids, file paths,
and that every entry carries the sha256 and byte size of the file it points at.

Neither is cosmetic. The manager verifies every download against the hash no
matter which source served it, and needs the size to show progress and to reject
an over-long response before it fills the disk. Run scripts/stamp_hashes.py to
fill or refresh both after changing any mod binary.

'originUrl' is optional and only needed once a mod is too large for the git repo
(GitHub blocks pushes over 100 MB per file). It points at wherever the full-size
copy actually lives, most likely a GitHub Release asset. Integrity does not
depend on the host, because the sha256 above is mandatory regardless.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

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


def asset_name(rel: str) -> str:
    """Must stay identical to stamp_hashes.asset_name and to publish-mods-release.ps1."""
    return rel.replace("\\", "/").replace("/", "__")


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

        size = mod.get("size")
        # bool is an int subclass, and "size": true would otherwise sail through.
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            errors.append(
                f"id={mod.get('id')!r}: missing/invalid 'size' "
                f"(run scripts/stamp_hashes.py)"
            )
            size = None

        if isinstance(rel, str) and rel.strip():
            path = ROOT / rel.replace("\\", "/")
            if not path.is_file():
                errors.append(f"id={mod.get('id')!r}: file not found: {rel}")
            else:
                if declared is not None:
                    actual = sha256_of(path)
                    if actual != declared.strip().lower():
                        errors.append(
                            f"id={mod.get('id')!r}: sha256 mismatch for {rel} "
                            f"(catalog={declared.strip().lower()}, file={actual}; "
                            f"run scripts/stamp_hashes.py)"
                        )
                if size is not None:
                    actual_size = path.stat().st_size
                    if actual_size != size:
                        errors.append(
                            f"id={mod.get('id')!r}: size mismatch for {rel} "
                            f"(catalog={size}, file={actual_size}; "
                            f"run scripts/stamp_hashes.py)"
                        )

        origin = mod.get("originUrl")
        if origin is not None:
            if not isinstance(origin, str) or not origin.strip():
                errors.append(f"id={mod.get('id')!r}: 'originUrl' must be a non-empty string")
            else:
                parts = urlsplit(origin.strip())
                if parts.scheme != "https":
                    errors.append(
                        f"id={mod.get('id')!r}: originUrl must be https, got {parts.scheme or 'no scheme'!r}"
                    )
                elif not parts.netloc or "@" in parts.netloc:
                    errors.append(
                        f"id={mod.get('id')!r}: originUrl host is missing or carries userinfo: {origin!r}"
                    )
                elif (parts.netloc == "github.com"
                      and "/releases/download/" in parts.path
                      and isinstance(rel, str) and rel.strip()):
                    # Our own Release convention, so the asset name is checkable. A pointer at
                    # some other host (an R2 bucket, say) is left alone on purpose.
                    expected = asset_name(rel)
                    if not parts.path.endswith("/" + expected):
                        errors.append(
                            f"id={mod.get('id')!r}: originUrl should end with {expected!r} "
                            f"to match 'file', got {parts.path.rsplit('/', 1)[-1]!r} "
                            f"(re-run scripts/stamp_hashes.py --origin-base ...)"
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

    print(f"OK: {len(mods)} mods, ids unique, files present, sha256 and size verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
