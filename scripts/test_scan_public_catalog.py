import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scan_public_catalog import run_clamav, scan_catalog, verify_receipt


def identity(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class PublicCatalogTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()

        def payload(name, data):
            source = self.root / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
            return {"file": name, **identity(data)}

        self.single = payload("mods/simple/simple.dll", b"synthetic single DLL")
        self.part1 = payload("mods/split/parts/0000", b"part one ")
        self.part2 = payload("mods/split/parts/0001", b"part two")
        self.bundle_main = {**payload("mods/guide/payload/guide.dll", b"guide main"), "path": "guide.dll"}
        extra = {**payload("mods/guide/payload/assets/text.dll", b"guide text"), "path": "assets/text.dll"}
        preview = payload("mods/simple/preview.png", b"synthetic preview")
        self.single.update(preview=preview["file"], previewSha256=preview["sha256"])
        self.split = {"file": "mods/split/split.dll", **identity(b"part one part two"), "parts": [self.part1, self.part2]}
        self.bundle = {"file": "mods/guide/guide.dll", **identity(b"guide main"), "bundle": [self.bundle_main, extra]}
        self.items = [self.single, self.split, self.bundle]

    def scan(self, callback):
        (self.root / "catalog.json").write_text(json.dumps({"mods": self.items}), encoding="utf-8")
        return scan_catalog(self.root, self.scratch, callback)

    def test_real_catalog_forms_send_every_physical_file_and_the_joined_dll(self):
        received = []
        self.assertEqual(self.scan(received.extend), (6, 1))
        files = {p for p in (self.root / "mods").rglob("*") if p.is_file()}
        self.assertEqual(set(received) - files, {self.scratch / "assembled-0.dll"})
        self.assertEqual(set(received) & files, files)
        self.assertEqual((self.scratch / "assembled-0.dll").read_bytes(), b"part one part two")

    def test_invalid_declarations_stop_before_scanner(self):
        changes = [(self.single, "size", True), (self.single, "sha256", "f" * 64),
                   (self.single, "previewSha256", "0" * 64), (self.part1, "sha256", "1" * 64),
                   (self.split, "sha256", "2" * 64), (self.bundle, "sha256", "3" * 64),
                   (self.bundle_main, "size", 1), (self.bundle_main, "path", "not-main.dll"),
                   (self.bundle["bundle"][1], "path", "GUIDE.DLL"), (self.bundle["bundle"][1], "file", "absent")]
        for record, key, invalid in changes:
            with self.subTest(key=key, invalid=invalid):
                old = record[key]
                record[key] = invalid
                with self.assertRaises(ValueError):
                    self.scan(lambda _: self.fail("invalid inventory sent to scanner"))
                record[key] = old
                (self.scratch / "assembled-0.dll").unlink(missing_ok=True)

    def test_legacy_preview_without_digest_remains_in_scan_inventory(self):
        del self.single["previewSha256"]
        del self.split["file"]  # Split-only author updates can omit the logical whole-file path.
        self.bundle["file"] = self.bundle_main["file"]
        received = []
        self.assertEqual(self.scan(received.extend), (6, 1))
        self.assertIn(self.root / self.single["preview"], received)


class ClamReceiptTest(unittest.TestCase):
    def setUp(self):
        self.paths = [Path("/mods/a.dll"), Path("/mods/名 空格.png")]
        self.ok = "".join(f"{p}: OK\n" for p in self.paths)
        self.summary = "\n----------- SCAN SUMMARY -----------\nScanned files: 2\nInfected files: 0\n"

    def test_receipts_and_summary_must_agree_and_every_path_must_pass(self):
        verify_receipt(io.StringIO(self.ok + self.summary), self.paths)
        for output in [self.summary, self.ok, self.ok.replace(f"{self.paths[0]}: OK\n", "") + self.summary,
                       self.ok + self.ok + self.summary, self.ok.replace(": OK", ": Excluded", 1) + self.summary,
                       self.ok + self.summary.replace("files: 2", "files: 1"), self.ok + self.summary + "Total errors: 1\n",
                       self.ok + self.summary.replace("Infected files: 0", "Infected files: 1"),
                       self.ok + "LibClamAV Warning: synthetic warning\n" + self.summary]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                verify_receipt(io.StringIO(output), self.paths)

    def test_command_checks_engine_exit_status_and_combines_warnings_in_fixed_locale(self):
        with tempfile.TemporaryDirectory() as temp:
            def scanner(args, **kwargs):
                self.assertNotIn("--infected", args)
                self.assertEqual(kwargs["env"]["LC_ALL"], "C")
                self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
                kwargs["stdout"].write(self.ok + self.summary)
                return subprocess.CompletedProcess(args, 0)
            with patch("scan_public_catalog.subprocess.run", side_effect=scanner):
                run_clamav(self.paths, Path(temp))
            with patch("scan_public_catalog.subprocess.run", return_value=subprocess.CompletedProcess([], 2)):
                with self.assertRaisesRegex(ValueError, "exit 2"):
                    run_clamav(self.paths, Path(temp))


if __name__ == "__main__":
    unittest.main()
