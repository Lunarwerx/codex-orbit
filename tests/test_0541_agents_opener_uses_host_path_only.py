"""Regression: the AGENTS.md read/save/open host cases must derive the project path host-side and
never take r.path from the webview message (patch_codex-0.5.41 inject_agents_opener)."""
import ast
import unittest
from pathlib import Path

PATCHER = Path(__file__).resolve().parent.parent / "patchers" / "patch_codex-0.5.41.py"


def _constant(name: str) -> str:
    tree = ast.parse(PATCHER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


class AgentsOpenerHostPathOnly(unittest.TestCase):
    def test_host_cases_never_read_webview_supplied_path(self):
        case = _constant("AGENTS_OPEN_CASE")
        self.assertNotIn("r.path", case)
        self.assertEqual(case.count('o=i&&i.uri?nde.join(i.uri.fsPath,"AGENTS.md"):""'), 3)


if __name__ == "__main__":
    unittest.main()
