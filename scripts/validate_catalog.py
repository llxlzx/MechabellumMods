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
# GitHub rejects a push that contains one file over 100 MB. A mod that large is
# served from originUrl; the git checkout, including CI, does not have the bytes.
LARGE_FILE_BYTES = 100 * 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_name(rel: str) -> str:
    """Must stay identical to stamp_hashes.asset_name and to publish-mods-release.ps1."""
    return rel.replace("\\", "/").replace("/", "__")


def conflict_errors(mod: dict, known_ids: set) -> list[str]:
    """Edges that point at self, at nothing, or are not objects with an id."""
    raw = mod.get("conflicts")
    if raw is None:
        return []
    mod_id = mod.get("id")
    if not isinstance(raw, list):
        return [f"id={mod_id!r}: conflicts must be an array"]

    errors: list[str] = []
    seen: set[str] = set()
    for index, edge in enumerate(raw):
        if not isinstance(edge, dict):
            errors.append(f"id={mod_id!r}: conflicts[{index}] must be an object")
            continue
        partner = edge.get("id")
        if not isinstance(partner, str) or not partner.strip():
            errors.append(f"id={mod_id!r}: conflicts[{index}].id must be a non-empty string")
            continue
        partner = partner.strip()
        key = partner.casefold()
        if isinstance(mod_id, str) and key == mod_id.strip().casefold():
            errors.append(f"id={mod_id!r}: conflicts[{index}] points at itself")
        elif key not in {str(item).strip().casefold() for item in known_ids if isinstance(item, str)}:
            errors.append(f"id={mod_id!r}: conflicts[{index}] unknown id {partner!r}")
        elif key in seen:
            errors.append(f"id={mod_id!r}: conflicts lists {partner!r} more than once")
        else:
            seen.add(key)
        reason = edge.get("reason")
        if reason is not None and not isinstance(reason, str):
            errors.append(f"id={mod_id!r}: conflicts[{index}].reason must be a string")
        locales = edge.get("locales")
        if locales is None:
            continue
        if not isinstance(locales, dict):
            errors.append(f"id={mod_id!r}: conflicts[{index}].locales must be an object")
            continue
        for lang, loc in locales.items():
            if not isinstance(loc, dict):
                errors.append(f"id={mod_id!r}: conflicts[{index}].locales[{lang!r}] must be an object")
                continue
            loc_reason = loc.get("reason")
            if loc_reason is not None and not isinstance(loc_reason, str):
                errors.append(
                    f"id={mod_id!r}: conflicts[{index}].locales[{lang!r}].reason must be a string"
                )
    return errors


def conflict_symmetry_errors(mods: list) -> list[str]:
    """If A lists B, B must list A. Runtime treats one side as enough; the catalog must not."""
    partners: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for mod in mods:
        if not isinstance(mod, dict):
            continue
        mod_id = mod.get("id")
        if not isinstance(mod_id, str) or not mod_id.strip():
            continue
        key = mod_id.strip().casefold()
        labels[key] = mod_id.strip()
        listed: set[str] = set()
        raw = mod.get("conflicts")
        if isinstance(raw, list):
            for edge in raw:
                if not isinstance(edge, dict):
                    continue
                partner = edge.get("id")
                if isinstance(partner, str) and partner.strip():
                    listed.add(partner.strip().casefold())
        partners[key] = listed

    errors: list[str] = []
    reported: set[tuple[str, str]] = set()
    for left, listed in partners.items():
        for right in listed:
            if right not in partners:
                continue
            if left in partners[right]:
                continue
            pair = tuple(sorted((left, right)))
            if pair in reported:
                continue
            reported.add(pair)
            errors.append(
                f"id={labels[left]!r} conflicts with {labels[right]!r}, "
                f"but {labels[right]!r} does not list it back"
            )
    return errors


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

        origin = mod.get("originUrl")
        if isinstance(rel, str) and rel.strip():
            path = ROOT / rel.replace("\\", "/")
            hosted_off_git = (
                isinstance(origin, str)
                and origin.strip().startswith("https://")
                and isinstance(size, int)
                and not isinstance(size, bool)
                and size > LARGE_FILE_BYTES
            )
            if not path.is_file():
                if not hosted_off_git:
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

        locales = mod.get("locales")
        if isinstance(locales, dict):
            for lang, loc in locales.items():
                if not isinstance(loc, dict):
                    continue
                loc_preview = loc.get("preview")
                if isinstance(loc_preview, str) and loc_preview.strip():
                    lpath = ROOT / loc_preview.replace("\\", "/")
                    if not lpath.is_file():
                        errors.append(
                            f"id={mod.get('id')!r}: {lang} preview not found: {loc_preview}"
                        )

        cat = mod.get("category")
        if cat is not None:
            if not isinstance(cat, str) or cat.strip() not in ALLOWED_CATEGORIES:
                errors.append(f"id={mod.get('id')!r}: invalid category: {cat!r}")

        tags = mod.get("tags")
        if tags is not None:
            if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
                errors.append(f"id={mod.get('id')!r}: tags must be a string array")

        errors.extend(conflict_errors(mod, {m.get("id") for m in mods if isinstance(m, dict)}))

    errors.extend(conflict_symmetry_errors(mods))

    if errors:
        print("catalog validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(mods)} mods, ids unique, files present, sha256 and size verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
