"""Regression: a patcher generated from tools/emit_patcher.py must carry the ORBIT_CHANNEL constant
that tools/ship.py stamps, so stamping does not abort."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAMP_RE = r'^ORBIT_CHANNEL:\s*str\s*=\s*"[^"]*"'


def _template() -> str:
    tree = ast.parse((ROOT / "tools" / "emit_patcher.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TEMPLATE" for t in node.targets
        ):
            return node.value.value
    raise AssertionError("TEMPLATE not found")


class EmittedPatcherOrbitChannel(unittest.TestCase):
    def test_template_channel_is_stampable_by_ship(self):
        _, n = re.subn(STAMP_RE, 'ORBIT_CHANNEL: str = "stable"', _template(), count=1, flags=re.M)
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
