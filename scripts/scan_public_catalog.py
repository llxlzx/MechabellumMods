"""Scan a checked-out public Mod catalog, including the assembled split DLLs."""

import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile


MAX_FILE = 512 * 1024**2
MAX_TOTAL = 4 * 1024**3
MAX_COUNT = 10_000


def scan_catalog(root, scratch, scan):
    mods = root / "mods"
    catalog = root / "catalog.json"
    if mods.is_symlink() or not mods.is_dir() or catalog.is_symlink() or catalog.stat().st_size > 8 * 1024**2:
        raise ValueError("Invalid catalog source")
    files = {}
    total = 0
    for path in mods.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        size = path.lstat().st_size
        if not stat.S_ISREG(mode) or not 0 < size <= MAX_FILE:
            raise ValueError("Invalid file type or size under mods/")
        relative = path.relative_to(root).as_posix()
        if not relative.isprintable() or "\\" in relative or ":" in relative:
            raise ValueError("Invalid catalog filename")
        files[relative] = path
        total += size
        if total > MAX_TOTAL or len(files) > MAX_COUNT:
            raise ValueError("Catalog exceeds scan budget")
    if not files:
        raise ValueError("Empty payload directory")
    data = json.loads(catalog.read_text(encoding="utf-8-sig"))
    if not isinstance(data.get("mods"), list) or not data["mods"]:
        raise ValueError("Empty catalog")
    paths = list(files.values())
    assembled = 0
    for item in data["mods"]:
        if "bundle" in item:
            bundle = item["bundle"]
            if "parts" in item or not isinstance(bundle, list) or not bundle or any(entry["file"] not in files for entry in bundle):
                raise ValueError("Invalid bundle or bundle member absent from scan inventory")
            continue
        if "parts" not in item:
            if item.get("file") not in files:
                raise ValueError("Primary file absent from scan inventory")
            continue
        parts = item["parts"]
        if not isinstance(parts, list) or not 0 < len(parts) <= 1024:
            raise ValueError("Invalid parts list")
        target = scratch / f"assembled-{assembled}.dll"
        digest = hashlib.sha256()
        size = 0
        with target.open("xb") as output:
            for part in parts:
                source = files.get(part["file"])
                if not source:
                    raise ValueError("Split file absent from scan inventory")
                size += source.stat().st_size
                if size > MAX_FILE or total + size > MAX_TOTAL:
                    raise ValueError("Split assembly exceeds scan budget")
                with source.open("rb") as stream:
                    while block := stream.read(1024**2):
                        digest.update(block)
                        output.write(block)
        if digest.hexdigest() != item["sha256"].lower() or size != item["size"]:
            raise ValueError("Reassembled DLL does not match catalog")
        total += size
        paths.append(target)
        assembled += 1
    scan(paths)
    return len(files), assembled


def main():
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        def scan(paths):
            inventory = scratch / "files.txt"
            inventory.write_text("".join(f"{p}\n" for p in paths), encoding="utf-8")
            subprocess.run([
                "clamscan", "--infected", "--official-db-only=yes", "--fail-if-cvd-older-than=7",
                "--alert-exceeds-max=yes", "--alert-encrypted=yes", "--max-filesize=512M",
                "--max-scansize=1024M", "--max-files=4096", "--max-recursion=20",
                f"--file-list={inventory}",
            ], check=True, timeout=1200)
        count, joined = scan_catalog(Path.cwd(), scratch, scan)
        print(f"Public catalog scan passed for {count} files and {joined} reconstructed DLLs.")


if __name__ == "__main__":
    main()
