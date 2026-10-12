# Catalog previews: friend-overlay & replay-reset

Approved scope **A** (community catalog only).

## Goal

Players browsing MechabellumMods in the manager see real UI screenshots and clearer summaries for the two maintainer mods.

## Changes

| Path | Action |
|------|--------|
| `mods/friend-overlay/preview.png` | Add (friend list overlay screenshot) |
| `mods/replay-reset/preview.png` | Add (replay list screenshot) |
| `catalog.json` | Set `preview` / `previewSha256`; rewrite zh + en/de/ja/ru summaries; bump `updatedAt` |

No DLL / version bump. No local source README changes. No manager code.

## Summary rules

Per `docs/ai-mod-standard.md`: what the player can do, hotkeys if relevant, Official/Beta; ≤400 chars; **no** manager version sentences; no changelog piles.

## Ship

`stamp_hashes.py` → `validate_catalog.py` → git push → `sync-mirror.ps1`.
