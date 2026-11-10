"""Unpinning a task whose pinned flag comes from the host clears the pin; starring it then leaves it starred only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import extract, load, run_node  # noqa: E402


class PinStarNativeFlags(unittest.TestCase):
    def test_unpin_then_star_a_host_pinned_task(self):
        src = load("stable/patch_codex.py").SIDEBAR_IIFE
        fns = extract(src, {"isPinned", "isStarred", "setPinned", "setStarred"})
        script = """
const PIN_KEY="p",STAR_KEY="s",PIN_OFF_KEY="po",STAR_OFF_KEY="so";
let pins=new Set(), stars=new Set(), pinOff=new Set(), starOff=new Set();
const saveSet=()=>{};
""" + fns + """
const t={id:"x",pinned:true,starred:false};
const obs={pinnedBefore:isPinned(t)};
setPinned(t,false);
obs.pinnedAfterUnpin=isPinned(t);
setStarred(t,true);
obs.pinnedAfterStar=isPinned(t);
obs.starredAfterStar=isStarred(t);
console.log(JSON.stringify(obs));
"""
        got = run_node(script)
        self.assertEqual(got["pinnedBefore"], True)
        self.assertEqual(got["pinnedAfterUnpin"], False)
        self.assertEqual(got["pinnedAfterStar"], False)
        self.assertEqual(got["starredAfterStar"], True)


if __name__ == "__main__":
    unittest.main()
