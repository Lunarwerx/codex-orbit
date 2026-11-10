"""Opening a task picks the native row with the exact title, not an earlier row that only partly matches it."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import extract, load, run_node  # noqa: E402


class OpenRowExactTitle(unittest.TestCase):
    def test_exact_title_beats_an_earlier_partial_title(self):
        src = load("stable/patch_codex.py").SIDEBAR_IIFE
        fns = extract(src, {"findNativeRow", "titleKey", "clean"})
        script = """
const A={row:"[row]",title:"title"};
const data=["Fix login bug","Fix login"];
const els=data.map((t)=>({getAttribute:(k)=>(k==="title"?t:null), textContent:t}));
const document={querySelectorAll:()=>els};
""" + fns + """
const el=findNativeRow({title:"Fix login"});
console.log(JSON.stringify({title:el?el.getAttribute("title"):null}));
"""
        got = run_node(script)
        self.assertEqual(got["title"], "Fix login")


if __name__ == "__main__":
    unittest.main()
