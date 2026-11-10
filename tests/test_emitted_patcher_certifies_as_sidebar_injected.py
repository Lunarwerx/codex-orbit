"""Regression: a patcher generated from tools/emit_patcher.py must log the success string that
tools/ship.py certifies on, so certification does not always abort."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _template() -> str:
    tree = ast.parse((ROOT / "tools" / "emit_patcher.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TEMPLATE" for t in node.targets
        ):
            return node.value.value
    raise AssertionError("TEMPLATE not found")


class EmittedPatcherCertifies(unittest.TestCase):
    def test_template_logs_the_string_ship_gates_on(self):
        gate = re.search(r'"(Overall status: [^"]+)" not in log', (ROOT / "tools" / "ship.py").read_text(encoding="utf-8"))
        self.assertIsNotNone(gate)
        self.assertIn(gate.group(1), _template())
        self.assertNotIn("dynamic patch complete", _template())


if __name__ == "__main__":
    unittest.main()
