"""Scan a checked-out public Mod catalog, including the assembled split DLLs."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile


MAX_FILE = 512 * 1024**2
MAX_TOTAL = 4 * 1024**3
MAX_COUNT = 10_000
CHUNK = 1024**2


def inventory_files(mods):
    def onerror(error):
        raise error

    files = {}
    total = 0
    for directory, subdirs, names in os.walk(mods, onerror=onerror):
        directory = Path(directory)
        if any((directory / name).is_symlink() for name in subdirs):
            raise ValueError("Linked catalog directory")
        for name in names:
            path = directory / name
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_FILE:
                raise ValueError("Invalid file type or size under mods/")
            relative = path.relative_to(mods.parent).as_posix()
            if not relative.isprintable() or "\\" in relative or ":" in relative:
                raise ValueError("Invalid catalog filename")
            files[relative] = path
            total += metadata.st_size
            if total > MAX_TOTAL or len(files) > MAX_COUNT:
                raise ValueError("Catalog exceeds scan budget")
    if not files:
        raise ValueError("Empty payload directory")
    return files, total


def matches_record(record, digest, size):
    return (isinstance(record, dict) and isinstance(record.get("sha256"), str)
            and record["sha256"].lower() == digest and type(record.get("size")) is int and record["size"] == size)


def scan_catalog(root, scratch, scan):
    mods = root / "mods"
    catalog = root / "catalog.json"
    if mods.is_symlink() or not mods.is_dir() or not stat.S_ISREG(catalog.lstat().st_mode) or catalog.stat().st_size > 8 * 1024**2:
        raise ValueError("Invalid catalog source")
    files, total = inventory_files(mods)
    digests = {}

    def contents(name):
        if not isinstance(name, str) or name not in files:
            raise ValueError("File absent from scan inventory")
        if name not in digests:
            path = files[name]
            with path.open("rb") as stream:
                digests[name] = hashlib.file_digest(stream, "sha256").hexdigest(), path.stat().st_size
        return digests[name]

    def check_file(entry):
        if not isinstance(entry, dict) or not matches_record(entry, *contents(entry.get("file"))):
            raise ValueError("Catalog file size or SHA-256 mismatch")

    data = json.loads(catalog.read_text(encoding="utf-8-sig"))
    if not isinstance(data.get("mods"), list) or not data["mods"]:
        raise ValueError("Empty catalog")
    paths = list(files.values())
    assembled = 0
    for item in data["mods"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid catalog item")
        if isinstance(item.get("file"), str) and item["file"] in files:
            check_file(item)
        if item.get("preview") or item.get("previewSha256"):
            digest, _ = contents(item.get("preview"))
            declared = item.get("previewSha256")
            if declared is not None and (not isinstance(declared, str) or declared.lower() != digest):
                raise ValueError("Preview SHA-256 mismatch")
        if "bundle" in item:
            bundle = item["bundle"]
            logical_main = item.get("file")
            if "parts" in item or not isinstance(bundle, list) or not bundle or not isinstance(logical_main, str):
                raise ValueError("Invalid bundle")
            destinations = set()
            main = []
            for entry in bundle:
                check_file(entry)
                dest = entry.get("path")
                if (not isinstance(dest, str) or not dest.isprintable() or any(c in dest for c in '\\:<>"|?*')
                        or any(not s or s in (".", "..") or s.endswith((".", " ")) for s in dest.split("/"))
                        or dest.casefold() in destinations):
                    raise ValueError("Invalid or duplicate bundle destination")
                destinations.add(dest.casefold())
                if entry["file"] == logical_main or dest.casefold() == logical_main.rsplit("/", 1)[-1].casefold():
                    main.append(entry)
            if len(main) != 1 or not matches_record(item, *contents(main[0]["file"])):
                raise ValueError("Bundle main file mismatch")
            continue
        if "parts" not in item:
            check_file(item)
            continue
        parts = item["parts"]
        if not isinstance(parts, list) or not 0 < len(parts) <= 1024:
            raise ValueError("Invalid parts list")
        target = scratch / f"assembled-{assembled}.dll"
        digest = hashlib.sha256()
        size = 0
        with target.open("xb") as output:
            for part in parts:
                check_file(part)
                source = files[part["file"]]
                size += source.stat().st_size
                if size > MAX_FILE or total + size > MAX_TOTAL:
                    raise ValueError("Split assembly exceeds scan budget")
                with source.open("rb") as stream:
                    while block := stream.read(CHUNK):
                        digest.update(block)
                        output.write(block)
        if not matches_record(item, digest.hexdigest(), size):
            raise ValueError("Reassembled DLL does not match catalog")
        total += size
        paths.append(target)
        assembled += 1
    scan(paths)
    return len(files), assembled


def verify_receipt(lines, paths):
    pending = {os.fspath(path) for path in paths}
    if len(pending) != len(paths) or not pending:
        raise ValueError("Invalid scan inventory")
    summary = False
    counts = {}
    for row in lines:
        line = row.rstrip("\r\n")
        if not line:
            continue
        if not summary and line.endswith(": OK") and line[:-4] in pending:
            pending.remove(line[:-4])
        elif not summary and re.fullmatch(r"-+ SCAN SUMMARY -+", line):
            summary = True
        elif summary and (count := re.fullmatch(r"(Scanned files|Infected files|Total errors): ([0-9]+)", line)):
            if count[1] in counts:
                raise ValueError("Duplicate ClamAV summary")
            counts[count[1]] = int(count[2])
        elif not (summary and re.fullmatch(r"(Known viruses|Engine version|Scanned directories|Data scanned|Data read|Time|Start Date|End Date): .+", line)):
            raise ValueError("Unexpected ClamAV output, warning or missing file receipt")
    if pending or counts.get("Scanned files") != len(paths) or counts.get("Infected files") != 0 or counts.get("Total errors", 0) != 0:
        raise ValueError("Incomplete ClamAV file receipts")


def run_clamav(paths, scratch):
    inventory = scratch / "files.txt"
    inventory.write_text("".join(f"{path}\n" for path in paths), encoding="utf-8")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as receipt:
        result = subprocess.run([
            "clamscan", "--stdout", "--official-db-only=yes", "--fail-if-cvd-older-than=7",
            "--alert-exceeds-max=yes", "--alert-encrypted=yes", "--max-filesize=512M",
            "--max-scansize=1024M", "--max-files=4096", "--max-recursion=20", f"--file-list={inventory}",
        ], stdout=receipt, stderr=subprocess.STDOUT, env={**os.environ, "LC_ALL":"C", "LANG":"C"}, timeout=1200)
        if result.returncode != 0:
            raise ValueError(f"ClamAV did not clear the inventory (exit {result.returncode})")
        receipt.seek(0)
        verify_receipt(receipt, paths)


def main():
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        count, joined = scan_catalog(Path.cwd(), scratch, lambda paths: run_clamav(paths, scratch))
        print(f"Public catalog scan passed for {count} files and {joined} reconstructed DLLs.")


if __name__ == "__main__":
    main()
