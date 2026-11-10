"""A task the host archived shows as Archived, and one toggle asks the host to unarchive it."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import extract, load, run_node  # noqa: E402


class UnarchiveHostArchivedTask(unittest.TestCase):
    def test_one_toggle_unarchives_a_host_archived_task(self):
        src = load("stable/patch_codex.py").SIDEBAR_IIFE
        fns = extract(src, {"isArchived", "archiveThread"})
        script = """
const ARCH_KEY="a";
const saveSet=()=>{}, render=()=>{};
const posts=[];
const coxPost=(type)=>{ posts.push(type); return true; };
let archived=new Set(), unarchived=new Set();
""" + fns + """
const t={id:"x",raw:{archived:true}};
const obs={archivedBefore:(typeof isArchived==="function")?isArchived(t):null};
archiveThread(t);
obs.firstPost=posts[0];
obs.archivedAfter=(typeof isArchived==="function")?isArchived(t):archived.has(t.id);
console.log(JSON.stringify(obs));
"""
        got = run_node(script)
        self.assertEqual(got["archivedBefore"], True)
        self.assertEqual(got["firstPost"], "unarchive-conversation")
        self.assertEqual(got["archivedAfter"], False)


if __name__ == "__main__":
    unittest.main()
