"""Regression: the status-dots-disabled log in patch_codex-0.5.40 must not claim rows show relative
time only, since addRow still draws dots and status text from wire data."""
import ast
import unittest
from pathlib import Path

PATCHER = Path(__file__).resolve().parent.parent / "patchers" / "patch_codex-0.5.40.py"


class StatusDotsDisabledLog0540(unittest.TestCase):
    def test_disabled_log_does_not_promise_relative_time_only(self):
        source = PATCHER.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("rows show relative time only", source)
        self.assertIn("rows still show status dots from the wire data", source)


if __name__ == "__main__":
    unittest.main()
