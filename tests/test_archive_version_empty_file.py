"""An empty version file must give the 'is empty' message, not an IndexError."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_archive_patcher():
    spec = importlib.util.spec_from_file_location("archive_patcher", ROOT / "tools" / "archive_patcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReadVersionEmptyFile(unittest.TestCase):
    def test_empty_version_file_reports_empty_not_index_error(self):
        mod = _load_archive_patcher()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "version.txt"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                mod.read_version(path, "patcher version")
        self.assertIn("is empty", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
