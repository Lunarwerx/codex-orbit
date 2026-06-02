#!/usr/bin/env python
"""Codex Orbit dynamic patcher (self-contained, OTA-shippable).

Patches whatever openai.chatgpt (Codex) it downloads by replaying a set of
anchored edits captured from the verified baseline, plus a programmatic
cache-bust rename. No bundled codex_assets needed at runtime -- the whole spec is
embedded below. Version-agnostic: anchors are located by content, and edits whose
anchors have drifted on a newer Codex are skipped (logged) rather than crashing,
so a Codex always installs and remaining gaps are closed by pushing patcher fixes.

The function name `copy_patched_assets` is intentional: the Orbit wrapper's OTA
loader requires that marker string to accept a patcher over the air.
"""
from __future__ import annotations
import argparse, base64, datetime as dt, gzip, json, platform, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path

__version__ = "0.4.0"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
SPEC_B64 = "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"

PKG_COMMANDS = [
    {"command": "chatgpt.renameTask", "title": "Rename Task", "category": "Codex", "icon": "$(edit)"},
    {"command": "chatgpt.pinTask", "title": "Pin Task", "category": "Codex", "icon": "$(pinned)"},
    {"command": "chatgpt.unpinTask", "title": "Unpin Task", "category": "Codex", "icon": "$(pinned-dirty)"},
    {"command": "chatgpt.starTask", "title": "Star Task", "category": "Codex", "icon": "$(star-full)"},
    {"command": "chatgpt.unstarTask", "title": "Unstar Task", "category": "Codex", "icon": "$(star-empty)"},
]
_WV = "(webviewId == 'chatgpt.sidebarView' || webviewId == 'chatgpt.sidebarSecondaryView') && codexTask == true"
PKG_MENUS = {
    "webview/context": [
        {"command": "chatgpt.renameTask", "group": "navigation@1", "when": _WV},
        {"command": "chatgpt.pinTask", "group": "navigation@2", "when": _WV + " && !codexPinned"},
        {"command": "chatgpt.unpinTask", "group": "navigation@2", "when": _WV + " && codexPinned == true"},
        {"command": "chatgpt.starTask", "group": "navigation@3", "when": _WV + " && !codexStarred"},
        {"command": "chatgpt.unstarTask", "group": "navigation@3", "when": _WV + " && codexStarred == true"},
    ],
    "chat/chatSessions": [
        {"command": "chatgpt.renameTask", "group": "inline@50", "when": "chatSessionType == openai-codex"},
    ],
}

def log(m):
    line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

def _spec():
    return json.loads(gzip.decompress(base64.b64decode(SPEC_B64)).decode("utf-8"))

def detect_target_platform():
    mach = platform.machine().lower(); arch = "arm64" if mach in ("arm64", "aarch64") else "x64"
    if sys.platform.startswith("win"): return f"win32-{arch}"
    if sys.platform == "darwin": return f"darwin-{arch}"
    if sys.platform.startswith("linux"): return f"linux-{arch}"
    return None

def marketplace_item_from_target(t):
    if t.startswith(("http://", "https://")):
        i = urllib.parse.parse_qs(urllib.parse.urlparse(t).query).get("itemName", [""])[0].strip(); return i or None
    if "." in t and not any(s in t for s in ("/", "\\")) and not t.lower().endswith(".vsix"): return t
    return None

def download_marketplace_vsix(item, dest_dir, version=None, target_platform=None):
    target_platform = target_platform or detect_target_platform()
    body = {"filters": [{"criteria": [{"filterType": 7, "value": item}]}], "flags": 403}
    req = urllib.request.Request(MARKETPLACE_QUERY_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json;api-version=7.2-preview.1", "User-Agent": "codex-orbit-patcher"})
    with urllib.request.urlopen(req, timeout=60) as r: data = json.load(r)
    ext = data["results"][0]["extensions"][0]
    cands = [v for v in ext["versions"] if not version or v["version"] == version]
    sel = next((v for v in cands if target_platform and v.get("targetPlatform") == target_platform), None)
    if sel is None: sel = next((v for v in cands if not v.get("targetPlatform")), None)
    if sel is None and cands: sel = cands[0]
    if sel is None:
        if version: raise RuntimeError(f"Version {version} not found for {item}")
        sel = ext["versions"][0] if ext["versions"] else None
        if sel is None: raise RuntimeError(f"No versions for {item}")
    pkg = next(f for f in sel["files"] if f.get("assetType", "").endswith("VSIXPackage"))
    pub = ext["publisher"]["publisherName"]; name = ext["extensionName"]
    sp = sel.get("targetPlatform"); suf = f"-{sp}" if sp else ""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{pub}.{name}-{sel['version']}{suf}.vsix"
    log(f"Downloading {pub}.{name} {sel['version']} {sp or 'platform-neutral'}")
    urllib.request.urlretrieve(pkg["source"], dest)
    log(f"Downloaded VSIX size: {dest.stat().st_size} bytes")
    return dest

def assert_codex(ext_dir):
    p = ext_dir / "package.json"
    if not p.exists(): raise RuntimeError("Missing extension/package.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    eid = f"{m.get('publisher')}.{m.get('name')}"
    if eid != DEFAULT_MARKETPLACE_ITEM: raise RuntimeError(f"Expected {DEFAULT_MARKETPLACE_ITEM}, got {eid}")
    return m

def apply_edits(text, edits):
    ops = []; missed = []
    for e in edits:
        if e["op"] == "append":
            ops.append((len(text), 0, e["inserted"])); continue
        anc = e["anchor"]; i = text.find(anc)
        if i == -1 or text.find(anc, i + 1) != -1:
            missed.append(anc[-30:]); continue
        pos = i + len(anc)
        if e["removed"] and text[pos:pos + len(e["removed"])] != e["removed"]:
            missed.append("rm:" + anc[-26:]); continue
        ops.append((pos, len(e["removed"]), e["inserted"]))
    ops.sort(key=lambda o: o[0], reverse=True)
    for pos, rl, ins in ops: text = text[:pos] + ins + text[pos + rl:]
    return text, len(ops), missed

def _choose(wv, prefix, edits):
    cands = [p for p in wv.glob(prefix + "*.js") if not p.name.endswith(".js.map")]
    best = None
    for p in cands:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        patched, applied, missed = apply_edits(txt, edits)
        if best is None or applied > best[1]: best = (p, applied, missed, patched)
    return best

def patch_package_json(ext_dir):
    p = ext_dir / "package.json"; m = json.loads(p.read_text(encoding="utf-8"))
    c = m.setdefault("contributes", {})
    cmds = c.setdefault("commands", []); have = {x.get("command") for x in cmds}
    for cmd in PKG_COMMANDS:
        if cmd["command"] not in have: cmds.append(dict(cmd))
    menus = c.setdefault("menus", {})
    for mk, items in PKG_MENUS.items():
        tgt = menus.setdefault(mk, []); seen = {json.dumps(x, sort_keys=True) for x in tgt}
        for it in items:
            if json.dumps(it, sort_keys=True) not in seen: tgt.append(dict(it))
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log("Patched package.json (commands + menus)")

def copy_patched_assets(extension_dir, patcher_version):
    """Dynamic patch entrypoint (marker-named for the OTA loader)."""
    spec = _spec(); roles = spec["roles"]; ext = Path(extension_dir); wv = ext / "webview" / "assets"
    rename_stems = []
    host = ext / "out" / "extension.js"
    if host.exists() and roles.get("host"):
        txt = host.read_text(encoding="utf-8", errors="ignore")
        txt, applied, missed = apply_edits(txt, roles["host"]["edits"])
        host.write_text(txt, encoding="utf-8", newline="")
        log(f"host out/extension.js: {applied} applied" + (f", {len(missed)} drifted (skipped)" if missed else ""))
    for role in ("header", "history", "setting-storage", "helper"):
        info = roles.get(role)
        if not info: continue
        chosen = _choose(wv, info["prefix"], info["edits"]) if wv.exists() else None
        if not chosen:
            log(f"{role}: no matching file found -- skipped (Codex still installs)"); continue
        path, applied, missed, txt = chosen
        path.write_text(txt, encoding="utf-8", newline="")
        log(f"{role} -> {path.name}: {applied} applied" + (f", {len(missed)} drifted (skipped)" if missed else ""))
        if info["rename"]: rename_stems.append(path.stem)
    if wv.exists():
        for f in wv.glob("*.js"):
            t = f.read_text(encoding="utf-8", errors="ignore"); o = t
            for st in rename_stems: t = t.replace(st, st + "-codexpatch")
            if t != o: f.write_text(t, encoding="utf-8", newline="")
        for st in rename_stems:
            src = wv / (st + ".js")
            if src.exists(): src.rename(wv / (st + "-codexpatch.js"))
    patch_package_json(ext)
    marker = {"tool": "Codex Orbit", "patcherVersion": patcher_version, "target": DEFAULT_MARKETPLACE_ITEM,
              "targetVersion": json.loads((ext / 'package.json').read_text(encoding='utf-8')).get('version'),
              "patchedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "mode": "dynamic"}
    (ext / "codex-orbit-patch.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    log("Wrote codex-orbit-patch.json marker")

def verify_dynamic(ext_dir):
    node = shutil.which("node")
    files = [ext_dir / "out" / "extension.js"] + list((ext_dir / "webview" / "assets").glob("*-codexpatch.js"))
    files += list((ext_dir / "webview" / "assets").glob("app-main-*.js"))
    if node:
        for f in files:
            if f.exists():
                r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
                if r.returncode != 0:
                    tail = (r.stderr or "").strip().splitlines()[-1:] or ["?"]
                    raise RuntimeError(f"Patched JS invalid: {f.name}: {tail[0]}")
        log("JS syntax check passed")
    else:
        log("node not found -- skipping JS syntax check")
    txt = (ext_dir / "out" / "extension.js").read_text(encoding="utf-8", errors="ignore")
    for feat, needle in (("task-context bridge", "codexWithTaskContext"), ("rename command", "chatgpt.renameTask")):
        if needle not in txt: log(f"NOTE: feature not yet wired on this Codex build: {feat} (push a patcher fix)")

def zip_dir(src, dest):
    if dest.exists(): dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src.rglob("*"):
            if p.is_file(): z.write(p, p.relative_to(src).as_posix())

def resolve_target(args):
    raw = Path(args.target).expanduser()
    if raw.exists() or raw.suffix.lower() == ".vsix":
        t = raw.resolve()
        if not t.exists(): raise RuntimeError(f"VSIX not found: {t}")
        log(f"Using local target: {t}"); return t
    item = marketplace_item_from_target(args.target)
    if item is None: raise RuntimeError(f"Not a Marketplace item or file: {args.target}")
    return download_marketplace_vsix(item, Path(args.download_dir).expanduser().resolve(), args.version or None, args.target_platform or None)

def main():
    global LOG_PATH
    p = argparse.ArgumentParser(description="Codex Orbit dynamic patcher")
    p.add_argument("target", nargs="?", default=DEFAULT_MARKETPLACE_ITEM)
    p.add_argument("--out", default=""); p.add_argument("--version", default="")
    p.add_argument("--target-platform", default=""); p.add_argument("--download-dir", default=".")
    p.add_argument("--log", default="codex-vsix-patch.log"); p.add_argument("--download-only", action="store_true")
    p.add_argument("--patcher-version", default="dev")
    a = p.parse_args()
    LOG_PATH = Path(a.log).expanduser().resolve(); LOG_PATH.write_text("", encoding="utf-8")
    log(f"Codex Orbit dynamic patcher v{__version__} (patcher-version {a.patcher_version})")
    target = resolve_target(a)
    if a.download_only:
        print(f"STOCK_VSIX_PATH: {target}", flush=True); log("Download-only mode"); return 0
    out = Path(a.out).resolve() if a.out else (Path(a.download_dir).resolve() / "patched.vsix")
    with tempfile.TemporaryDirectory(prefix="codex-dyn-") as tmp:
        root = Path(tmp) / "vsix"
        with zipfile.ZipFile(target) as z: z.extractall(root)
        ext = root / "extension"
        m = assert_codex(ext); log(f"Target: {m.get('displayName')} v{m.get('version')}")
        copy_patched_assets(ext, a.patcher_version)
        verify_dynamic(ext)
        log("Writing patched VSIX"); zip_dir(root, out)
    log(f"Patched VSIX written: {out}"); log("Overall status: dynamic patch complete")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log(f"Patch run failed: {exc}"); raise
