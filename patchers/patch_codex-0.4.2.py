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
