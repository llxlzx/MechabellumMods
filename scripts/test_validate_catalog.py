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

    def test_usage_is_optional_and_limited(self):
        errors: list[str] = []
        v.check_usage({"id": "a"}, errors)
        v.check_usage({"id": "a", "usage": "Tournament"}, errors)
        v.check_usage({"id": "a", "usage": "Casual"}, errors)
        self.assertEqual(errors, [])
        v.check_usage({"id": "a", "usage": "Unrated"}, errors)
        v.check_usage({"id": "a", "usage": "tournament"}, errors)
        v.check_usage({"id": "a", "usage": 1}, errors)
        self.assertEqual(len(errors), 3)
        self.assertTrue(all("invalid usage" in e for e in errors))


class ValidateFeedbackTests(unittest.TestCase):
    def _demo(self, root: Path, feedback=None, *, include_feedback=False) -> dict:
        entry = mod(root)
        entry["name"] = "Demo"
        if include_feedback:
            entry["feedback"] = feedback
        return entry

    def test_missing_feedback_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, _output = run_main(root, [self._demo(root)])
            self.assertEqual(code, 0)

    def test_plain_email_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, _output = run_main(
                root, [self._demo(root, "author@example.com", include_feedback=True)]
            )
            self.assertEqual(code, 0)

    def test_blank_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = run_main(root, [self._demo(root, "  ", include_feedback=True)])
            self.assertNotEqual(code, 0)
            self.assertIn("feedback", output)

    def test_http_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = run_main(
                root, [self._demo(root, "http://example.com", include_feedback=True)]
            )
            self.assertNotEqual(code, 0)
            self.assertIn("feedback", output)

    def test_file_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = run_main(
                root, [self._demo(root, "file:///C:/x", include_feedback=True)]
            )
            self.assertNotEqual(code, 0)
            self.assertIn("feedback", output)

    def test_feedback_choices_are_optional(self):
        errors: list[str] = []
        v.check_feedback_choices({"id": "a"}, errors)
        self.assertEqual(errors, [])

    def test_feedback_choices_accept_https(self):
        errors: list[str] = []
        v.check_feedback_choices(
            {
                "id": "a",
                "feedbackChoices": [
                    {"label": "QQ 频道", "url": "https://pd.qq.com/s/mrm8s2di"},
                    {"label": "Discord", "url": "https://discord.com/users/1"},
                ],
            },
            errors,
        )
        self.assertEqual(errors, [])

    def test_feedback_choices_reject_http_userinfo_and_blank_label(self):
        errors: list[str] = []
        v.check_feedback_choices(
            {
                "id": "a",
                "feedbackChoices": [
                    {"label": " ", "url": "https://example.com"},
                    {"label": "web", "url": "http://example.com"},
                    {"label": "bad", "url": "https://user@evil.example/x"},
                ],
            },
            errors,
        )
        self.assertEqual(len(errors), 3)


if __name__ == "__main__":
    unittest.main()
