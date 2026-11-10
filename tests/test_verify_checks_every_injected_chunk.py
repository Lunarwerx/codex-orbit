"""verify() syntax-checks the chunk that carries the injected status hook, even when the sidebar host also names the hook."""
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_probe import load  # noqa: E402

_real_glob = pathlib.Path.glob


class VerifyEveryChunk(unittest.TestCase):
    def test_broken_hook_chunk_is_reported_when_the_sidebar_host_sorts_first(self):
        mod = load("stable/patch_codex.py")
        with tempfile.TemporaryDirectory() as d:
            ext = Path(d)
            assets = ext / "webview" / "assets"
            assets.mkdir(parents=True)
            # The sidebar host: valid ES module that mentions the hook name (as the real sidebar does).
            (assets / "a_host.js").write_text(
                'export const s="__codexOrbitSidebarV4 window.__codexOrbitStatusHook=function(){}";\n', encoding="utf-8")
            # The injected hook chunk: calls the hook and is syntactically broken.
            (assets / "z_chunk.js").write_text(
                "export function f(e,r){ window.__codexOrbitStatusHook(e,r)\n", encoding="utf-8")
            # Deterministic order: the sidebar host is listed first.
            ordered = lambda self, pat: iter(sorted(_real_glob(self, pat)))
            with mock.patch.object(pathlib.Path, "glob", new=ordered):
                with self.assertRaises(RuntimeError) as cm:
                    mod.verify(ext)
        self.assertIn("z_chunk.js", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
