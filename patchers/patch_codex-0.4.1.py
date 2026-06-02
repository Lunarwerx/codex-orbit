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
    fname = f"{pub}.{name}-{sel['version']}{suf}.vsix"
    # Cache the (large) stock VSIX across runs so iterating on the patcher does
    # not re-download hundreds of MB each click. Keyed by version+platform, so a
    # genuinely newer Codex still triggers a fresh download.
    cache = Path(tempfile.gettempdir()) / "codex-orbit-cache"
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / fname
    if dest.exists() and dest.stat().st_size > 1_000_000:
        log(f"Using cached Codex VSIX ({dest.stat().st_size} bytes): {fname}")
        return dest
    log(f"Downloading {pub}.{name} {sel['version']} {sp or 'platform-neutral'}")
    part = dest.with_name(dest.name + ".part")
    urllib.request.urlretrieve(pkg["source"], part)
    part.replace(dest)  # atomic: never leave a half-downloaded file in cache
    log(f"Downloaded VSIX size: {dest.stat().st_size} bytes (cached)")
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
