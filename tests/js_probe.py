"""Shared helpers for the codex-orbit regression tests (standard library only).

The sidebar JS lives in Python raw strings. These helpers pull named functions out of that
source and run them under node with small stubs, so a test exercises the real code rather
than a copy of it. CODEX_ORBIT_ROOT points the tests at another checkout; that is how a
test is shown to fail on the old code.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("CODEX_ORBIT_ROOT") or Path(__file__).resolve().parents[1])


def load(rel):
    """Import a patcher file by its path under ROOT."""
    name = "orbit_" + re.sub(r"\W", "_", rel)
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract(src, names):
    """Source of the 4-space-indented `function NAME(` and one-line `const NAME=` declarations named in `names`."""
    lines = src.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^    (?:function (\w+)\(|const (\w+)=)", line)
        if not m:
            continue
        name = m.group(1) or m.group(2)
        if name not in names:
            continue
        if m.group(2):
            out.append(line)
            continue
        depth, started, j, chunk = 0, False, i, []
        while True:
            chunk.append(lines[j])
            for ch in lines[j]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
            j += 1
            if started and depth <= 0:
                break
        out.append("\n".join(chunk))
    return "\n".join(out)


def run_node(script):
    """Run a probe script under node and return the JSON it prints on its last line."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    d = tempfile.mkdtemp(prefix="orbit-probe-")
    try:
        p = Path(d) / "probe.js"
        p.write_text(script, encoding="utf-8")
        r = subprocess.run([node, str(p)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if r.returncode != 0:
        raise AssertionError("node probe failed:\n" + r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])
