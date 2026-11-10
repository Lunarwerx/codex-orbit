"""With a host workspace stamped, an open chat from another project does not replace the current workspace (patch_codex-0.5.45)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import extract, load, run_node  # noqa: E402


class HostWorkspaceWins(unittest.TestCase):
    def test_open_chat_from_workspace_b_keeps_host_workspace_a(self):
        src = load("patchers/patch_codex-0.5.45.py").SIDEBAR_IIFE
        fns = extract(src, {"currentRows", "hostWorkspace", "setCurrent", "openThreadId", "normPath", "lastSeg",
                            "clean", "titleKey", "threadMatchesId", "uuidOf", "inCurrent", "threadTitleKey"})
        script = """
const CUR_KEY="cur";
let curRoot="", curLabel="", activeRoots=[];
const localStorage={getItem:()=>null,setItem:()=>{}};
const location={pathname:"/local/chat-b",search:"",hash:""};
const document={
  querySelector:(sel)=>(sel.indexOf("codex-orbit-workspace")>=0?{getAttribute:()=>JSON.stringify({r:"/ws/A",l:"A"})}:null),
  querySelectorAll:()=>[]
};
const A={row:"[row]",title:"title"};
""" + fns + """
const rows=[{id:"chat-b",__id:"chat-b",cwd:"/ws/B",project:"B",title:"t"}];
currentRows(rows,[]);
console.log(JSON.stringify({curRoot,curLabel}));
"""
        got = run_node(script)
        self.assertEqual(got["curRoot"], "/ws/a")  # normPath lower-cases; the host's workspace A must win
        self.assertEqual(got["curLabel"], "a")


if __name__ == "__main__":
    unittest.main()
