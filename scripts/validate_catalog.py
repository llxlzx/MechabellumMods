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
MANAGER_FLOOR = re.compile(r"^(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})$")
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


def check_preview_hash(mod: dict, label: str, preview, declared, errors: list[str]) -> None:
    """A preview path must exist. When previewSha256 is set, it must match those bytes."""
    if not isinstance(preview, str) or not preview.strip():
        return
    path = ROOT / preview.replace("\\", "/")
    if not path.is_file():
        errors.append(f"id={mod.get('id')!r}: {label} not found: {preview}")
        return
    if not isinstance(declared, str) or not declared.strip():
        return
    actual = sha256_of(path)
    if declared.strip().lower() != actual:
        errors.append(
            f"id={mod.get('id')!r}: {label} sha256 mismatch for {preview} "
            f"(catalog={declared!r}, file={actual}; run scripts/stamp_hashes.py)"
        )


def check_whole_file(
    mod: dict, errors: list[str], root: Path | None = None, *, allow_missing: bool = False
) -> None:
    if root is None:
        root = ROOT
    rel = mod.get("file")
    if not isinstance(rel, str) or not rel.strip():
        return
    path = root / rel.replace("\\", "/")
    has_parts = isinstance(mod.get("parts"), list) and len(mod.get("parts")) > 0
    if not path.is_file():
        if not has_parts and not allow_missing:
            errors.append(f"id={mod.get('id')!r}: file not found: {rel}")
        return
    declared = mod.get("sha256")
    size = mod.get("size")
    if isinstance(declared, str) and sha256_of(path) != declared.strip().lower():
        errors.append(
            f"id={mod.get('id')!r}: sha256 mismatch for {rel} "
            f"(catalog={declared.strip().lower()}, file={sha256_of(path)})"
        )
    if isinstance(size, int) and not isinstance(size, bool) and path.stat().st_size != size:
        errors.append(
            f"id={mod.get('id')!r}: size mismatch for {rel} "
            f"(catalog={size}, file={path.stat().st_size})"
        )


def check_parts(mod: dict, errors: list[str], root: Path | None = None) -> None:
    """Slices must exist, stay under GitHub's per-file limit, and rebuild the whole file."""
    if root is None:
        root = ROOT
    slices = mod.get("parts")
    if slices is None:
        return
    if not isinstance(slices, list) or not slices:
        errors.append(f"id={mod.get('id')!r}: 'parts' must be a non-empty array")
        return

    file_rel = mod.get("file")
    file_norm = file_rel.replace("\\", "/") if isinstance(file_rel, str) else None

    whole = bytearray()
    declared_sum = 0
    for index, part in enumerate(slices):
        label = f"id={mod.get('id')!r} parts[{index}]"
        if not isinstance(part, dict):
            errors.append(f"{label}: must be an object")
            continue
        rel = part.get("file")
        declared = part.get("sha256")
        size = part.get("size")
        if not isinstance(rel, str) or not rel.strip():
            errors.append(f"{label}: missing file")
            continue
        part_norm = rel.replace("\\", "/")
        if file_norm is not None and part_norm == file_norm:
            errors.append(f"id={mod.get('id')!r}: parts[{index}] equals file")
        if not isinstance(declared, str) or not SHA256_HEX.match(declared.strip().lower()):
            errors.append(f"{label}: missing/invalid sha256")
            declared = None
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0 or size >= LARGE_FILE_BYTES:
            errors.append(f"{label}: size must be between 1 and {LARGE_FILE_BYTES - 1} bytes")
            size = None
        path = root / part_norm
        if not path.is_file():
            errors.append(f"{label}: file not found: {rel}")
            continue
        actual_size = path.stat().st_size
        if size is not None and actual_size != size:
            errors.append(f"{label}: size mismatch (catalog={size}, file={actual_size})")
        actual = sha256_of(path)
        if declared is not None and actual != declared.strip().lower():
            errors.append(f"{label}: sha256 mismatch (catalog={declared}, file={actual})")
        if size is not None:
            declared_sum += size
        whole.extend(path.read_bytes())

    whole_hash = hashlib.sha256(whole).hexdigest()
    declared_whole = mod.get("sha256")
    if isinstance(declared_whole, str) and declared_whole.strip().lower() != whole_hash:
        errors.append(
            f"id={mod.get('id')!r}: parts do not reassemble to sha256 "
            f"(catalog={declared_whole}, joined={whole_hash})"
        )
    whole_size = mod.get("size")
    if isinstance(whole_size, int) and not isinstance(whole_size, bool) and declared_sum != whole_size:
        errors.append(
            f"id={mod.get('id')!r}: parts sizes sum to {declared_sum}, catalog size is {whole_size}"
        )


def check_min_manager_version(mod: dict, errors: list[str]) -> None:
    if "minManagerVersion" not in mod or mod.get("minManagerVersion") is None:
        return
    raw = mod.get("minManagerVersion")
    label = f"id={mod.get('id')!r}: minManagerVersion"
    if not isinstance(raw, str) or MANAGER_FLOOR.match(raw) is None:
        errors.append(f"{label} must be major.minor.patch with no leading zeros")
        return
    if any(int(part) > 65535 for part in raw.split(".")):
        errors.append(f"{label} segment must be at most 65535")


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

        check_min_manager_version(mod, errors)

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
        has_parts = isinstance(mod.get("parts"), list) and len(mod.get("parts")) > 0
        hosted_off_git = (
            not has_parts
            and isinstance(origin, str)
            and origin.strip().startswith("https://")
            and isinstance(size, int)
            and not isinstance(size, bool)
            and size > LARGE_FILE_BYTES
        )
        check_whole_file(mod, errors, allow_missing=hosted_off_git)

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

        check_parts(mod, errors)
        check_preview_hash(mod, "preview", mod.get("preview"), mod.get("previewSha256"), errors)

        locales = mod.get("locales")
        if isinstance(locales, dict):
            for lang, loc in locales.items():
                if not isinstance(loc, dict):
                    continue
                loc_preview = loc.get("preview")
                if isinstance(loc_preview, str) and loc_preview.strip():
                    check_preview_hash(
                        mod,
                        f"{lang} preview",
                        loc_preview,
                        loc.get("previewSha256"),
                        errors,
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
