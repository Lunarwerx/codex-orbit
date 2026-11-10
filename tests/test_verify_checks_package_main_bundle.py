"""verify() syntax-checks the host bundle that package.json main points at, the same file the injectors patch."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import load  # noqa: E402


class VerifyMainBundle(unittest.TestCase):
    def test_broken_custom_main_bundle_is_reported(self):
        mod = load("stable/patch_codex.py")
        with tempfile.TemporaryDirectory() as d:
            ext = Path(d)
            (ext / "package.json").write_text('{"main": "bundle/custom.js"}', encoding="utf-8")
            (ext / "bundle").mkdir()
            (ext / "bundle" / "custom.js").write_text("const = ;\n", encoding="utf-8")
            (ext / "out").mkdir()
            (ext / "out" / "extension.js").write_text("module.exports = {};\n", encoding="utf-8")
            with self.assertRaises(RuntimeError) as cm:
                mod.verify(ext)
        self.assertIn("custom.js", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
