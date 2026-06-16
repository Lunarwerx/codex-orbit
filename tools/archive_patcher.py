#!/usr/bin/env python
"""archive_patcher.py — snapshot the CURRENT patcher into the rollback registry so
users can always "Use previous versions" (the CCO model, ported to Codex).

build.py calls archive_current() on every build, so a snapshot happens
automatically — no separate command, nothing to remember. That is the "save
every version" half of the rollback feature: each patcher version is preserved as
patchers/patch_codex-<ver>.py and recorded in patchers/manifest.json, and they
NEVER get deleted. Re-running on an already-archived version refreshes it in place.

Why record a Codex pin per patcher: the dynamic patcher's anchors match a window
of Codex releases. Rollback re-installs the archived patcher pinned to THIS
recorded Codex version, so every pick is a known-good (patcher, Codex) pair.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATCHER = ROOT / "stable" / "patch_codex.py"           # the live dynamic patcher
PATCHER_VERSION_SRC = ROOT / "patcher_version.txt"
RELEASE_CHANNEL_SRC = ROOT / "release_channel.txt"
STABLE_VERSION_SRC = ROOT / "stable" / "stable_version.txt"
PATCHERS_DIR = ROOT / "patchers"
MANIFEST = PATCHERS_DIR / "manifest.json"
BUILDS_DIR = ROOT / "builds"
EXT_NAME = "codex-orbit"


def read_version(path: Path, label: str) -> str:
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    v = path.read_text(encoding="utf-8").strip().split()[0]
    if not v:
        raise SystemExit(f"{label} is empty: {path}")
    return v


def read_patcher_channel() -> "str | None":
    """The channel embedded in the patcher's own ORBIT_CHANNEL constant — the single
    source of truth for the tag (also embedded into the patched webview as ccPatchChannel).
    Returns 'experimental'/'stable' or None when the marker is absent."""
    try:
        src = PATCHER.read_text(encoding="utf-8")
        m = re.search(r'^ORBIT_CHANNEL:\s*str\s*=\s*"([^"]+)"', src, flags=re.M)
        if m:
            c = m.group(1).strip().lower()
            if c in ("experimental", "stable"):
                return c
    except Exception:
        pass
    return None


def read_release_channel_file() -> "str | None":
    """Back-compat fallback: the old side-file tag, used only if the patcher lacks ORBIT_CHANNEL."""
    try:
        if RELEASE_CHANNEL_SRC.exists():
            c = RELEASE_CHANNEL_SRC.read_text(encoding="utf-8").strip().lower()
            if c in ("experimental", "stable"):
                return c
    except Exception:
        pass
    return None


def current_build_number() -> "int | None":
    if not BUILDS_DIR.exists():
        return None
    n = None
    for p in BUILDS_DIR.glob(f"{EXT_NAME}-build-*.vsix"):
        try:
            num = int(p.stem.rsplit("-", 1)[1])
            n = num if n is None else max(n, num)
        except (ValueError, IndexError):
            continue
    return n


def load_manifest() -> dict:
    if MANIFEST.exists():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if not isinstance(data.get("patchers"), list):
            raise SystemExit("manifest.json malformed: missing 'patchers' list")
        return data
    return {
        "schema": 1,
        "comment": "Rollback registry of Codex Orbit patcher versions. Maintained by tools/archive_patcher.py; build.py calls it every build. Never delete entries.",
        "patchers": [],
    }


def archive_current(verbose: bool = True, build_number: "int | None" = None) -> dict:
    """Snapshot stable/patch_codex.py into patchers/ + manifest (idempotent)."""
    if not PATCHER.exists():
        raise SystemExit(f"Patcher not found: {PATCHER}")
    version = read_version(PATCHER_VERSION_SRC, "patcher_version.txt")
    codex = read_version(STABLE_VERSION_SRC, "stable/stable_version.txt")
    # Channel ships INSIDE the patcher (ORBIT_CHANNEL) — single source of truth, also
    # embedded into the patched webview as ccPatchChannel. The manifest entry mirrors it
    # for fast listing. Fall back to release_channel.txt, then the default (experimental).
    channel = read_patcher_channel() or read_release_channel_file() or "experimental"

    PATCHERS_DIR.mkdir(exist_ok=True)
    dest_name = f"patch_codex-{version}.py"
    shutil.copyfile(PATCHER, PATCHERS_DIR / dest_name)

    manifest = load_manifest()
    entry = {
        "version": version,
        "channel": channel,
        "build": build_number if build_number is not None else current_build_number(),
        "codex": codex,
        # `claude` mirrors `codex` because the shared Orbit launcher reads the certified
        # version from entry.claude (Claude-named upstream); keep both so the launcher's
        # "certified against vX" display works for Codex too.
        "claude": codex,
        "file": dest_name,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    patchers = manifest["patchers"]
    existing = next((i for i, p in enumerate(patchers) if p.get("version") == version), None)
    if existing is not None:
        notes = patchers[existing].get("notes")
        if notes:
            entry["notes"] = notes
        patchers[existing] = entry
        action = "refreshed"
    else:
        patchers.append(entry)
        action = "added"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if verbose:
        print(f"Archived patcher v{version} ({action}) -> patchers/{dest_name}")
        print(f"  registry now: " + ", ".join(p["version"] for p in patchers))
    entry["_action"] = action
    return entry


def main() -> int:
    archive_current(verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
