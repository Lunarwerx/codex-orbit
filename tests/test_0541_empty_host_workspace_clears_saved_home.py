"""Regression: an empty host workspace must clear the saved home, and a root change must
take its own label (patch_codex-0.5.41 sidebar current-workspace priority chain)."""
import ast
import re
import unittest
from pathlib import Path

PATCHER = Path(__file__).resolve().parent.parent / "patchers" / "patch_codex-0.5.41.py"


def _sidebar_iife() -> str:
    tree = ast.parse(PATCHER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SIDEBAR_IIFE" for t in node.targets
        ):
            return node.value.value
    raise AssertionError("SIDEBAR_IIFE not found")


def _body(src: str, header: str) -> str:
    start = src.index(header)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"unterminated {header}")


class EmptyHostWorkspaceClearsSavedHome(unittest.TestCase):
    def setUp(self):
        self.iife = _sidebar_iife()

    def test_setcurrent_root_change_takes_its_own_label(self):
        body = _body(self.iife, "function setCurrent(root,label)")
        self.assertIn("if(r&&r!==curRoot){ curRoot=r; curLabel=l; ch=true; }", body)

    def test_empty_host_meta_clears_root_and_label(self):
        body = _body(self.iife, "function currentRows(rows,nativeRows)")
        self.assertRegex(
            body,
            r'else if\(document\.querySelector\(\'meta\[name="codex-orbit-workspace"\]\'\)'
            r'&&\(curRoot\|\|curLabel\)\)\{[^}]*curRoot="";\s*curLabel="";',
        )


if __name__ == "__main__":
    unittest.main()
