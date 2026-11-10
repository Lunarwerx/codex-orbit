"""With no host bundle in the extension folder, the injectors log the miss and return False instead of raising."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import load  # noqa: E402


class InjectorsWithoutHostBundle(unittest.TestCase):
    def test_both_injectors_return_false_when_the_host_bundle_is_missing(self):
        mod = load("stable/patch_codex.py")
        logs = []
        with tempfile.TemporaryDirectory() as d:
            ext = Path(d) / "ext"
            ext.mkdir()
            (ext / "package.json").write_text('{"main": "out/extension.js"}', encoding="utf-8")
            with mock.patch.object(mod, "log", side_effect=logs.append):
                self.assertIs(mod.inject_workspace_meta(ext), False)
                self.assertIs(mod.inject_agents_opener(ext), False)
        self.assertEqual(sum("Host bundle not found" in m for m in logs), 2, logs)


if __name__ == "__main__":
    unittest.main()
