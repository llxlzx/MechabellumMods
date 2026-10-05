import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import stamp_hashes as s

PART_BYTES = b"part-data"
FILE_REL = "mods/demo/Demo.dll"
PART_REL = "mods/demo/parts/0000"
INDENT = "            "


def write_part(root: Path) -> Path:
    path = root / PART_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PART_BYTES)
    return path


def write_whole(root: Path, data: bytes) -> Path:
    path = root / FILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def joined_sha256() -> str:
    return hashlib.sha256(PART_BYTES).hexdigest()


def parts_catalog_text(*, sha256: str = "0" * 64, size: int = 0, origin_url: str | None = "https://example.com/old-asset") -> str:
    lines = [
        "{",
        '    "mods": [',
        "        {",
        f'{INDENT}"id": "demo",',
        f'{INDENT}"file": "{FILE_REL}",',
        f'{INDENT}"sha256": "{sha256}",',
        f'{INDENT}"size": {size},',
    ]
    if origin_url is not None:
        lines.append(f'{INDENT}"originUrl": "{origin_url}",')
    part_sha = "a" * 64
    lines.extend([
        f'{INDENT}"parts": [',
        f'                {{"file": "{PART_REL}", "sha256": "{part_sha}", "size": {len(PART_BYTES)}}}',
        f"            ]",
        "        }",
        "    ]",
        "}",
    ])
    return "\n".join(lines) + "\n"


def plain_catalog_text(*, sha256: str = "0" * 64, size: int = 0, origin_url: str = "https://example.com/keep-me") -> str:
    return (
        "{\n"
        '    "mods": [\n'
        "        {\n"
        f'{INDENT}"id": "demo",\n'
        f'{INDENT}"file": "{FILE_REL}",\n'
        f'{INDENT}"sha256": "{sha256}",\n'
        f'{INDENT}"size": {size},\n'
        f'{INDENT}"originUrl": "{origin_url}"\n'
        "        }\n"
        "    ]\n"
        "}\n"
    )


def run_stamp_main(root: Path, catalog_text: str, *, argv: list[str] | None = None) -> tuple[int, str, str]:
    catalog_path = root / "catalog.json"
    catalog_path.write_text(catalog_text, encoding="utf-8")
    old_root, old_catalog = s.ROOT, s.CATALOG
    old_argv = sys.argv
    buf = io.StringIO()
    try:
        s.ROOT = root
        s.CATALOG = catalog_path
        sys.argv = argv if argv is not None else ["stamp_hashes.py"]
        with redirect_stderr(buf):
            code = s.main()
        return code, buf.getvalue(), catalog_path.read_text(encoding="utf-8")
    finally:
        s.ROOT = old_root
        s.CATALOG = old_catalog
        sys.argv = old_argv


class StampPartsTests(unittest.TestCase):
    def test_joined_parts_match_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "mods/demo/parts/0000"
            a.parent.mkdir(parents=True)
            a.write_bytes(b"abc")
            digest, size = s.joined_digest(root, [{"file": "mods/demo/parts/0000"}])
            self.assertEqual(size, 3)
            self.assertEqual(digest, s.sha256_of(a))

    def test_parts_entry_never_emits_origin(self):
        mod = {"id": "demo", "parts": [{"file": "mods/demo/parts/0000"}]}
        self.assertIsNone(s.origin_line(mod, "https://github.com/x/y/releases/download/t", "  ", "\n"))

    def test_plain_entry_still_emits_origin(self):
        mod = {"id": "demo", "file": "mods/demo/Demo.dll"}
        line = s.origin_line(mod, "https://github.com/x/y/releases/download/t", "    ", "\n")
        self.assertIn("originUrl", line)
        self.assertIn("mods__demo__Demo.dll", line)


class StampMainTests(unittest.TestCase):
    def test_parts_with_origin_base_drops_origin_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_part(root)
            origin_base = "https://github.com/x/y/releases/download/t"
            code, err, text = run_stamp_main(
                root,
                parts_catalog_text(),
                argv=["stamp_hashes.py", "--origin-base", origin_base],
            )
            self.assertEqual(code, 0, err)
            mod = json.loads(text)["mods"][0]
            self.assertEqual(mod["sha256"], joined_sha256())
            self.assertEqual(mod["size"], len(PART_BYTES))
            self.assertNotIn("originUrl", mod)
            self.assertNotIn("originUrl", text)

    def test_parts_without_whole_file_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_part(root)
            code, err, _ = run_stamp_main(root, parts_catalog_text(origin_url=None))
            self.assertEqual(code, 0, err)
            self.assertNotIn("file not found", err)

    def test_parts_whole_mismatch_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_part(root)
            write_whole(root, b"wrong-whole")
            code, err, _ = run_stamp_main(root, parts_catalog_text(origin_url=None))
            self.assertEqual(code, 1)
            self.assertIn("!= joined parts", err)

    def test_plain_without_origin_base_keeps_origin_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain_bytes = b"plain-data"
            write_whole(root, plain_bytes)
            kept = "https://example.com/keep-me"
            code, err, text = run_stamp_main(root, plain_catalog_text(origin_url=kept))
            self.assertEqual(code, 0, err)
            mod = json.loads(text)["mods"][0]
            self.assertEqual(mod["originUrl"], kept)
            self.assertEqual(mod["sha256"], hashlib.sha256(plain_bytes).hexdigest())
            self.assertEqual(mod["size"], len(plain_bytes))


if __name__ == "__main__":
    unittest.main()
