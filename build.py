#!/usr/bin/env python
"""Build Codex Orbit.

Every run creates a numbered VSIX in builds/ and copies it to
latest/codex-orbit.vsix. Version numbers are read from package.json and the
stable/ text files; the build does not bump them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Wrapper dir is "Codex Orbit-" (trailing hyphen on purpose): the user's folder-patcher
# recurses when a child dir shares its parent's name, so the wrapper dir is kept distinct
# from the project root "Codex Orbit". The hyphen never reaches the VSIX (files are bundled
# under "extension/...", not by source-dir name).
WRAPPER_DIR = ROOT / "Codex Orbit-"
STABLE_DIR = ROOT / "stable"
PATCHER_SRC = STABLE_DIR / "patch_codex.py"
CODEX_ASSETS_DIR = STABLE_DIR / "codex_assets"
STABLE_VERSION_SRC = STABLE_DIR / "stable_version.txt"
STABLE_PATCHER_VERSION_SRC = STABLE_DIR / "patcher_version.txt"
STABLE_README_SRC = STABLE_DIR / "README.md"
README_SRC = ROOT / "README.md"
BUILDS_DIR = ROOT / "builds"
PATCHERS_DIR = ROOT / "patchers"
LATEST_DIR = ROOT / "latest"
LATEST_VSIX = LATEST_DIR / "codex-orbit.vsix"
WRAPPER_VERSION_SRC = ROOT / "wrapper_version.txt"
BUILD_LOG = BUILDS_DIR / "BUILD_LOG.md"
EXT_NAME = "codex-orbit"

# Two icons on purpose: <Icon> is what VS Code shows in-editor (transparent
# white mark, looks right on the dark Extensions UI and our webview/activity
# bar, which all reuse media/codex-orbit.png). Services.Icons.Default is the
# Marketplace web listing, which renders on white where a transparent mark
# vanishes -> it points at media/codex-orbit-store.png (same mark, solid black
# background). Store gets the black box; the app never sees it.
VSIX_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}" />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Categories>Other</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Icon>extension/media/codex-orbit.png</Icon>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" Version="[1.94.0,)" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Icons.Default" Path="extension/media/codex-orbit-store.png" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
  </Assets>
</PackageManifest>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json" />
  <Default Extension="js"   ContentType="application/javascript" />
  <Default Extension="py"   ContentType="text/x-python" />
  <Default Extension="png"  ContentType="image/png" />
  <Default Extension="svg"  ContentType="image/svg+xml" />
  <Default Extension="xml"  ContentType="application/xml" />
  <Default Extension="md"   ContentType="text/markdown" />
  <Default Extension="vsixmanifest" ContentType="text/xml" />
</Types>
"""

INCLUDED_PATHS = [
    Path("package.json"),
    Path("extension.js"),
    Path("media/codex-orbit.png"),
    Path("media/codex-orbit-store.png"),
    Path("media/rec-saydeploy.png"),
    Path("media/rec-claude-code-orbit.png"),
    Path("media/rec-copilot-suite.png"),
    Path("media/rec-paramount.png"),
    Path("media/rec-connexions.png"),
]


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit(f"{label} is empty: {path}")
    return value


def load_manifest() -> dict:
    return json.loads((WRAPPER_DIR / "package.json").read_text(encoding="utf-8"))


def next_build_number() -> int:
    BUILDS_DIR.mkdir(exist_ok=True)
    latest = 0
    for p in BUILDS_DIR.glob(f"{EXT_NAME}-build-*.vsix"):
        try:
            latest = max(latest, int(p.stem.rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            pass
    return latest + 1


def add_file(zf: zipfile.ZipFile, files_added: list[str], src: Path, arc: str) -> None:
    if not src.exists():
        raise SystemExit(f"Missing file: {src}")
    files_added.append(arc)
    zf.write(src, arc)


def add_tree(zf: zipfile.ZipFile, files_added: list[str], src_dir: Path, arc_dir: str) -> None:
    if not src_dir.exists():
        raise SystemExit(f"Missing directory: {src_dir}")
    for path in sorted(src_dir.rglob("*")):
        if path.is_file():
            arc = f"{arc_dir}/{path.relative_to(src_dir).as_posix()}"
            add_file(zf, files_added, path, arc)


def ensure_sibling_rec(wrapper_dir: Path) -> None:
    """Re-insert the Claude Code Orbit cross-recommendation into the (already identity-
    stamped) launcher so Codex Orbit shows Claude Code Orbit — mirroring how Claude Code
    Orbit shows Codex Orbit.

    WHY: the shared launcher cross-recommends the sibling Orbit product and dynamically
    hides whichever product is SELF (SELF_EXT_ID). But our identity stamp rewrites the
    'lunarwerx.claude-code-orbit' rec into a duplicate 'lunarwerx.codex-orbit', which the
    launcher then hides as self — so Claude Code Orbit vanishes from the list. Until the
    launcher/stamp is fixed UPSTREAM (its proper home), we re-insert the sibling rec on
    every build. Idempotent; no-op once the sibling rec is already present."""
    import re as _re
    ext = wrapper_dir / "extension.js"
    if not ext.exists():
        return
    text = ext.read_text(encoding="utf-8")
    if "lunarwerx.claude-code-orbit" in text:
        return  # already present (e.g. upstream fixed it) — leave it alone
    claude_rec = ('{ id: "lunarwerx.claude-code-orbit", name: "Claude Code Orbit", '
                  'tag: "The Orbit patcher for Claude Code.", icon: recIcon("rec-claude-code-orbit.png") }')
    new, n = _re.subn(r'\{\s*id:\s*"lunarwerx\.codex-orbit",[^}]*\}', claude_rec, text, count=1)
    if n != 1:
        print("  [recs] WARNING: no codex-orbit self-rec found to convert; Claude Code "
              "Orbit rec NOT added (launcher recs format changed — check upstream).")
        return
    ext.write_text(new, encoding="utf-8")
    print("  [recs] re-inserted Claude Code Orbit sibling rec (stamp clobbers it; fix upstream)")


def build(out: Path | None = None) -> Path:
    manifest = load_manifest()
    ensure_sibling_rec(WRAPPER_DIR)
    stable_version = read_required_text(STABLE_VERSION_SRC, "stable Codex version").split()[0]
    patcher_version = read_required_text(STABLE_PATCHER_VERSION_SRC, "stable patcher version").split()[0]
    build_number = None
    if out is None:
        build_number = next_build_number()
        out = BUILDS_DIR / f"{EXT_NAME}-build-{build_number}.vsix"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    print(f"Bundling Codex Orbit -> {out.name}")
    print(f"  patcher src:       stable/patch_codex.py")
    print(f"  known-good Codex:  {stable_version}")
    print(f"  patcher ver:       {patcher_version}")

    # Snapshot the current patcher into the rollback registry BEFORE bundling, so
    # every build preserves this version under patchers/ and the manifest grows.
    # This is the "save every previous version" half of the picker — automatic,
    # nothing to remember (mirrors Claude Code Orbit). Bundled below via patchers/.
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tools"))
    from archive_patcher import archive_current
    archive_current(verbose=True, build_number=build_number)

    files_added: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr(
            "extension.vsixmanifest",
            VSIX_MANIFEST.format(
                name=manifest["name"],
                version=manifest["version"],
                publisher=manifest["publisher"],
                display=manifest["displayName"],
                description=manifest["description"],
            ),
        )
        for rel in INCLUDED_PATHS:
            add_file(zf, files_added, WRAPPER_DIR / rel, f"extension/{rel.as_posix()}")

        add_file(zf, files_added, PATCHER_SRC, "extension/stable/patch_codex.py")
        # NOTE: stable/codex_assets is intentionally NOT bundled. The patcher is dynamic
        # (content-anchored injection) and reads NOTHING from codex_assets at runtime — it
        # was the old asset-replay baseline. Bundling it just shipped ~2 MB of dead, and
        # version-stale, minified JS in every VSIX. The repo copy stays only as a dev
        # reference for tools/ (engine_gate, gen_patch_spec).
        zf.writestr("extension/stable/stable_version.txt", stable_version + "\n")
        zf.writestr("extension/stable/patcher_version.txt", patcher_version + "\n")
        zf.writestr("extension/patch_version.txt", patcher_version + "\n")
        zf.writestr("extension/STABLE_VERSION.txt", stable_version + "\n")
        files_added.extend([
            f"extension/stable/stable_version.txt ({stable_version})",
            f"extension/stable/patcher_version.txt ({patcher_version})",
            f"extension/patch_version.txt ({patcher_version})",
            f"extension/STABLE_VERSION.txt ({stable_version})",
        ])

        # Rollback registry: the "Previous versions" picker reads
        # extension/patchers/manifest.json. Bundling it makes the picker work
        # offline from the moment Orbit is installed — every entry is a verified
        # (patcher, Codex) baseline the user can flip to.
        if PATCHERS_DIR.exists():
            add_tree(zf, files_added, PATCHERS_DIR, "extension/patchers")

        if STABLE_README_SRC.exists():
            add_file(zf, files_added, STABLE_README_SRC, "extension/stable/README.md")
        if README_SRC.exists():
            readme = README_SRC.read_text(encoding="utf-8")
            readme = readme.replace("Codex Orbit-/media/", "media/").replace("Codex Orbit/media/", "media/")
            zf.writestr("extension/README.md", readme)
            files_added.append("extension/README.md")

    LATEST_DIR.mkdir(exist_ok=True)
    shutil.copyfile(out, LATEST_VSIX)
    WRAPPER_VERSION_SRC.write_text(manifest["version"] + "\n", encoding="utf-8")

    if build_number is not None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"- **Build #{build_number}** - `{out.name}` - "
            f"pkg {manifest['version']}, stable Codex {stable_version}, "
            f"patcher {patcher_version} - {ts}\n"
        )
        if BUILD_LOG.exists():
            BUILD_LOG.write_text(BUILD_LOG.read_text(encoding="utf-8") + line, encoding="utf-8")
        else:
            BUILD_LOG.write_text("# Build log\n\n" + line, encoding="utf-8")

    print(f"  files:   {len(files_added) + 2}")
    print(f"  output:  {out}")
    print(f"  latest:  {LATEST_VSIX}")
    print(f"  size:    {out.stat().st_size / 1024:.1f} KB")
    print("\n" + "=" * 56)
    print(f"  BUILD {'#' + str(build_number) if build_number is not None else '(custom --out)'} COMPLETE")
    print(f"     file:     {out.name}")
    print(f"     bundled:  stable Codex {stable_version} / patcher {patcher_version}")
    print(f"     pkg ver:  {manifest['version']}")
    print("=" * 56)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Codex Orbit VSIX")
    parser.add_argument("--out", help="Explicit output path")
    parser.add_argument("--clean", action="store_true", help="Wipe Codex Orbit builds before building")
    args = parser.parse_args()
    if args.clean and BUILDS_DIR.exists():
        for p in BUILDS_DIR.glob(f"{EXT_NAME}-build-*.vsix"):
            p.unlink()
            print(f"  removed {p.name}")
    build(Path(args.out).resolve() if args.out else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
