"""A used_percent of 1 is one percent, not a fraction of 100 (stable sidebar usage parsing)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import extract, load, run_node, ROOT  # noqa: E402


class UsagePercentScale(unittest.TestCase):
    def test_used_percent_of_one_leaves_ninety_nine_remaining(self):
        src = load("stable/patch_codex.py").SIDEBAR_IIFE
        fns = extract(src, {"clampPct", "num", "val", "resetMs", "usageName", "clean", "windowText", "bucketsFromRows"})
        script = fns + """
const rows=[{snapshot:{primary:{used_percent:1,window_duration_mins:300}}}];
const b=bucketsFromRows(rows)[0];
console.log(JSON.stringify({used:b.used,remaining:b.remaining}));
"""
        got = run_node(script)
        self.assertEqual(got, {"used": 1, "remaining": 99})


if __name__ == "__main__":
    unittest.main()
