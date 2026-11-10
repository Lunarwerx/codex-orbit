"""The AGENTS.md editor reads and writes only the workspace's AGENTS.md, never a path the webview names (patch_codex-0.5.45)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import load, run_node  # noqa: E402


class AgentsMdOnlyWorkspaceFile(unittest.TestCase):
    def test_webview_supplied_path_is_ignored(self):
        case = load("patchers/patch_codex-0.5.45.py").AGENTS_OPEN_CASE
        script = """
const out=[];
const nde={join:(...a)=>a.join("/").replace(/\\/+/g,"/"),dirname:(p)=>p.replace(/\\/[^/]*$/,"")};
const Oe={workspace:{workspaceFolders:[{uri:{fsPath:"/ws"}}]},commands:{executeCommand:async()=>{}},Uri:{file:(p)=>({fsPath:p})}};
const iC={promises:{
  mkdir:async()=>{},
  writeFile:async(p)=>{out.push(["write",p]);},
  readFile:async(p)=>{out.push(["read",p]);return "";},
  access:async()=>{}
}};
const At=()=>"/home/u/.codex", pr=()=>false;
const self={postMessageToWebview:()=>{}};
async function handle(type,r){ const e=0; switch(type){ """ + case + """ } }
(async()=>{
  await handle.call(self,"codex-orbit-save-agents",{path:"/etc/passwd",content:"x"});
  await handle.call(self,"codex-orbit-read-agents",{path:"/etc/hosts"});
  console.log(JSON.stringify(out));
})();
"""
        got = run_node(script)
        self.assertTrue(got, "the handler should have touched the workspace AGENTS.md")
        for kind, path in got:
            self.assertEqual(path, "/ws/AGENTS.md", f"{kind} touched {path}")


if __name__ == "__main__":
    unittest.main()
