"""Regression: the workspace-filter-disabled log in patch_codex-0.5.40 must not claim the sidebar
shows every project, since the IIFE still scopes rows by open chat, saved workspace and roots."""
import ast
import unittest
from pathlib import Path

PATCHER = Path(__file__).resolve().parent.parent / "patchers" / "patch_codex-0.5.40.py"


class WorkspaceFilterDisabledLog0540(unittest.TestCase):
    def test_disabled_log_does_not_promise_every_project(self):
        source = PATCHER.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("sidebar shows every project", source)
        self.assertIn("sidebar still scopes by open chat, saved workspace and roots", source)


if __name__ == "__main__":
    unittest.main()
