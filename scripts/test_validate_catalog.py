import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_catalog as v


def mod(root: Path, *, parts=True, whole=True, part_equals_file=False):
    dll = b"dll-bytes"
    rel = "mods/demo/Demo.dll"
    part_rel = rel if part_equals_file else "mods/demo/parts/0000"
    if whole:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dll)
    if parts:
        path = root / part_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dll)
    entry = {
        "id": "demo",
        "file": rel,
        "sha256": v.sha256_of(root / (part_rel if parts else rel)) if (parts or whole) else "ab" * 32,
        "size": len(dll),
    }
    if parts:
        entry["parts"] = [{"file": part_rel, "sha256": v.sha256_of(root / part_rel), "size": len(dll)}]
    return entry


def hosted_off_git_entry(root: Path, *, whole: bool, wrong_hash: bool = False) -> dict:
    rel = "mods/big/Big.dll"
    blob = b"local-bytes"
    if whole:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    return {
        "id": "big",
        "name": "Big",
        "file": rel,
        "sha256": "ff" * 32 if wrong_hash else hashlib.sha256(blob).hexdigest(),
        "size": v.LARGE_FILE_BYTES + 1,
        "originUrl": "https://example.com/releases/Big.dll",
    }


def run_main(root: Path, mods: list) -> tuple[int, str]:
    catalog_path = root / "catalog.json"
    catalog_path.write_text(json.dumps({"mods": mods}), encoding="utf-8")
    old_root, old_catalog = v.ROOT, v.CATALOG
    buf = io.StringIO()
    try:
        v.ROOT = root
        v.CATALOG = catalog_path
        with redirect_stderr(buf):
            code = v.main()
        return code, buf.getvalue()
    finally:
        v.ROOT = old_root
        v.CATALOG = old_catalog


class ValidatePartsTests(unittest.TestCase):
    def test_parts_alone_are_enough(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            errors: list[str] = []
            v.check_parts(mod(root, whole=False), errors, root)
            self.assertEqual(errors, [])

    def test_part_path_must_differ_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            errors: list[str] = []
            v.check_parts(mod(root, part_equals_file=True), errors, root)
            self.assertTrue(any("equals file" in e for e in errors))

    def test_whole_file_must_match_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = mod(root)
            (root / "mods/demo/Demo.dll").write_bytes(b"other")
            errors: list[str] = []
            v.check_whole_file(entry, errors, root)
            self.assertTrue(any("sha256 mismatch" in e for e in errors))

    def test_hosted_off_git_verifies_present_whole_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = run_main(root, [hosted_off_git_entry(root, whole=True, wrong_hash=True)])
            self.assertNotEqual(code, 0)
            self.assertIn("sha256 mismatch", output)

    def test_hosted_off_git_skips_missing_whole_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = run_main(root, [hosted_off_git_entry(root, whole=False)])
            self.assertNotIn("file not found", output)

    def test_min_manager_version_is_optional_and_strict(self):
        errors: list[str] = []
        v.check_min_manager_version({"id": "a"}, errors)
        v.check_min_manager_version({"id": "a", "minManagerVersion": None}, errors)
        v.check_min_manager_version({"id": "a", "minManagerVersion": "1.3.14"}, errors)
        self.assertEqual(errors, [])
        v.check_min_manager_version({"id": "a", "minManagerVersion": "1.03.14"}, errors)
        v.check_min_manager_version({"id": "a", "minManagerVersion": "v1.3.14"}, errors)
        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
