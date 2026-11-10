"""An append edit must not be re-appended when the patcher runs again on patched text."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_edit_helpers():
    # tools/emit_patcher.py is a generator whose module-level code reads .tmp/ files,
    # so import only the two pure helpers from its source.
    src = (ROOT / "tools" / "emit_patcher.py").read_text(encoding="utf-8")
    start = src.index("def apply_edits(")
    end = src.index("def patch_package_json(")
    ns = {"json": json, "Path": Path}
    exec(src[start:end], ns)
    return ns["apply_edits"], ns["_choose"]


class AppendEditIdempotence(unittest.TestCase):
    def test_second_run_does_not_reappend_the_inserted_text(self):
        apply_edits, _ = _load_edit_helpers()
        edits = [{"op": "append", "inserted": "\n//tail-marker"}]
        once, applied_first, _ = apply_edits("var a=1;", edits)
        twice, applied_second, _ = apply_edits(once, edits)
        self.assertEqual(applied_first, 1)
        self.assertEqual(twice, once)
        self.assertEqual(applied_second, 0)


if __name__ == "__main__":
    unittest.main()
