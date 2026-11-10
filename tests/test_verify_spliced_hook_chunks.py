"""verify must find the chunk holding the spliced hook calls, not the sidebar helper that merely names them."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_patcher():
    spec = importlib.util.spec_from_file_location("patch_codex_0543", ROOT / "patchers" / "patch_codex-0.5.43.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SplicedHookChunkScan(unittest.TestCase):
    def test_helper_chunk_naming_the_hooks_is_not_taken_for_a_spliced_chunk(self):
        mod = _load_patcher()
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            # The sidebar IIFE is appended to the host chunk and names both hooks, but never calls them spliced-style.
            (assets / "host.js").write_text(mod.SIDEBAR_IIFE, encoding="utf-8")
            self.assertIsNone(mod._chunk_with(assets, mod.STATUS_HOOK_CALL))
            self.assertIsNone(mod._chunk_with(assets, mod.USAGE_ROWS_EVENT))

    def test_chunk_with_spliced_status_hook_call_is_found(self):
        mod = _load_patcher()
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "status.js").write_text("function f(e,r){x()" + mod.STATUS_HOOK_TAIL, encoding="utf-8")
            found = mod._chunk_with(assets, mod.STATUS_HOOK_CALL)
            self.assertIsNotNone(found)
            self.assertEqual(found.name, "status.js")


if __name__ == "__main__":
    unittest.main()
