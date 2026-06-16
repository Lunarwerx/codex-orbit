#!/usr/bin/env python
"""ship.py — one command to cut a Codex Orbit release (mirrors claude-code-orbit's
ship.py, adapted for Codex).

    python tools/ship.py            # experimental (DEFAULT)
    python tools/ship.py --stable   # stable (ONLY when Jacob says "stable")
    python tools/ship.py --no-certify   # skip the newest-Codex re-certify (channel + build only)

What it does:
  1. Stamps the release channel INTO the patcher's ORBIT_CHANNEL constant
     (experimental by DEFAULT; stable ONLY with --stable). The tag then ships
     inside stable/patch_codex.py, gets embedded into the patched webview as
     ccPatchChannel, and is mirrored into patchers/manifest.json by archive_patcher.
     THE TAG IS INFALLIBLE: every release is tagged, default experimental.
  2. Re-certifies (unless --no-certify): runs the patcher against the NEWEST Codex
     from the Marketplace (no --version => newest). Aborts unless the patcher
     reports "Overall status: sidebar injected". Writes that version to
     stable_version.txt + stable/stable_version.txt — so we always certify against
     whatever Codex is newest at ship time, never a hand-typed version.
  3. Writes release_channel.txt (back-compat side file for already-installed wrappers).
  4. Runs build.py -> archives the patcher (stamped channel) into the rollback
     registry and builds latest/codex-orbit.vsix.
  5. Prints the exact git add/commit/push for the release.

This script never pushes by itself — it does the error-prone prep so a release is
just: run this, then commit + push the printed file list and confirm the raw CDN
serves the new patcher CODE before calling it live.

NOTE: the patcher only runs its strict JS syntax check when `node` is on PATH;
without node it SKIPS that check (and ship warns). Install node for a fully-
verified release. Channel bumping never touches patcher_version.txt — bump that
by hand (RELEASE_RULES.md) before shipping a new patcher.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATCHER = ROOT / "stable" / "patch_codex.py"
CHANNEL_FILE = ROOT / "release_channel.txt"
STABLE_VERSION = ROOT / "stable_version.txt"
STABLE_VERSION_NESTED = ROOT / "stable" / "stable_version.txt"
TARGET = "openai.chatgpt"


def stamp_channel(channel: str) -> None:
    """Write the channel INTO the patcher's own ORBIT_CHANNEL constant (single source
    of truth — it ships inside the patcher and is embedded as ccPatchChannel)."""
    src = PATCHER.read_text(encoding="utf-8")
    new, n = re.subn(
        r'^ORBIT_CHANNEL:\s*str\s*=\s*"[^"]*"',
        f'ORBIT_CHANNEL: str = "{channel}"',
        src, count=1, flags=re.M,
    )
    if n != 1:
        print("[ship] ABORT: could not find ORBIT_CHANNEL in stable/patch_codex.py to "
              "stamp the channel. Nothing changed.", file=sys.stderr)
        raise SystemExit(1)
    PATCHER.write_text(new, encoding="utf-8")
    print(f"[ship] patch_codex.py ORBIT_CHANNEL = {channel} (tag now ships inside the patcher)")


def main() -> int:
    args = sys.argv[1:]
    channel = "stable" if "--stable" in args else "experimental"
    no_certify = "--no-certify" in args

    # Stamp the channel FIRST so the certify run, the archived copy, and the manifest
    # mirror all carry the same shipped-with-the-patcher tag.
    stamp_channel(channel)

    newest = None
    if not no_certify:
        with tempfile.TemporaryDirectory(prefix="codex-orbit-ship-") as tmp:
            out = Path(tmp) / "out.vsix"
            logf = Path(tmp) / "ship.log"
            cmd = [sys.executable, str(PATCHER), TARGET, "--out", str(out),
                   "--download-dir", tmp, "--log", str(logf), "--patcher-version", "ship"]
            print(f"[ship] Pulling newest Codex + patching ({channel})...")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            log = ((logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else "")
                   + proc.stdout + proc.stderr)
            if "Overall status: sidebar injected" not in log:
                print("[ship] ABORT: patcher did not report success. Nothing changed.\n"
                      + log[-2000:], file=sys.stderr)
                return 1
            m = re.search(r"Target:.* v(\d+\.\d+\.\d+)", log)
            if not m:
                print("[ship] ABORT: could not read the newest Codex version from the "
                      "patcher log. Nothing changed.", file=sys.stderr)
                return 1
            newest = m.group(1)
            STABLE_VERSION.write_text(newest + "\n", encoding="utf-8")
            STABLE_VERSION_NESTED.write_text(newest + "\n", encoding="utf-8")
            print(f"[ship] certified Codex {newest} -> stable_version.txt")
            if "JS syntax check passed" not in log:
                print("[ship] WARNING: JS syntax check did NOT run (node not on PATH?). "
                      "Install node for a fully-verified release.", file=sys.stderr)

    CHANNEL_FILE.write_text(channel + "\n", encoding="utf-8")
    print(f"[ship] release_channel.txt  = {channel}")

    print("[ship] Building (archive patcher + wrapper VSIX)...")
    build = subprocess.run([sys.executable, str(ROOT / "build.py")], capture_output=True, text=True)
    print(build.stdout + build.stderr)
    if build.returncode != 0:
        print("[ship] ABORT: build.py failed.", file=sys.stderr)
        return 1

    pv = (ROOT / "patcher_version.txt").read_text(encoding="utf-8").strip()
    wv = (ROOT / "wrapper_version.txt").read_text(encoding="utf-8").strip()
    print("\n" + "=" * 64)
    print(f"  READY TO PUSH — patcher v{pv}, wrapper v{wv}, "
          f"certified Codex {newest or '(unchanged)'}, channel {channel.upper()}")
    print("=" * 64)
    print("  Commit + push (then confirm the CDN serves the new CODE):")
    print("    git add stable/patch_codex.py patcher_version.txt stable/patcher_version.txt \\")
    print("            stable_version.txt stable/stable_version.txt release_channel.txt \\")
    print("            patchers/ \"Codex Orbit-/\" wrapper_version.txt \\")
    print("            latest/codex-orbit.vsix builds/BUILD_LOG.md builds/codex-orbit-build-*.vsix")
    print("    git commit ; git push origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
