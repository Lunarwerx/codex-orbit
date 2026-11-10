"""Regression: once the host meta is present, open-chat, roots and active-flag signals must not call
setCurrent, so a chat with a subfolder or worktree cwd keeps the workspace root (patch_codex-0.5.48)."""
import ast
import unittest
from pathlib import Path

PATCHER = Path(__file__).resolve().parent.parent / "patchers" / "patch_codex-0.5.48.py"


def _sidebar_iife() -> str:
    tree = ast.parse(PATCHER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SIDEBAR_IIFE" for t in node.targets
        ):
            return node.value.value
    raise AssertionError("SIDEBAR_IIFE not found")


class HostMetaNotNarrowed(unittest.TestCase):
    def test_setcurrent_is_a_no_op_while_host_meta_is_present(self):
        src = _sidebar_iife()
        start = src.index("function setCurrent(root,label){")
        head = src[start:start + 400]
        self.assertLess(head.index("if(hostWorkspace()) return;"), head.index("const r=normPath(root"))


if __name__ == "__main__":
    unittest.main()
