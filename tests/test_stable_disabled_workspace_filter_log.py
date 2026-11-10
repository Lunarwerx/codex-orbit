"""With workspace-filter disabled, the stable patcher's log does not claim the sidebar shows every project."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import load  # noqa: E402


class StableWorkspaceFilterLog(unittest.TestCase):
    def test_disabled_workspace_filter_log_is_accurate(self):
        mod = load("stable/patch_codex.py")
        logs = []
        with tempfile.TemporaryDirectory() as d:
            ext = Path(d) / "ext"
            (ext / "webview" / "assets").mkdir(parents=True)
            (ext / "package.json").write_text('{"main": "out/extension.js"}', encoding="utf-8")
            (ext / "webview" / "assets" / "app-main-1.js").write_text("export const x=1;\n", encoding="utf-8")
            with mock.patch.object(mod, "ENABLED_FEATURES", {"status-dots"}), \
                 mock.patch.object(mod, "log", side_effect=logs.append), \
                 mock.patch.multiple(mod, expose_native_openers=mock.DEFAULT, expose_host_channel=mock.DEFAULT,
                                     expose_usage_status=mock.DEFAULT, expose_usage_rows=mock.DEFAULT,
                                     inject_workspace_meta=mock.DEFAULT, inject_agents_opener=mock.DEFAULT):
                mod.copy_patched_assets(ext, "test")
        msgs = [m for m in logs if "workspace-filter" in m]
        self.assertTrue(msgs, "expected a workspace-filter skip message")
        for m in msgs:
            self.assertNotIn("every project", m)
            self.assertIn("still filters", m)


if __name__ == "__main__":
    unittest.main()
