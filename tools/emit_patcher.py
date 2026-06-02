"""Assemble the self-contained dynamic stable/patch_codex.py from the template
plus the embedded spec blob and package-contributions block."""
import pathlib

blob = open('.tmp/embed_blob.txt').read().strip()
pkg = open('.tmp/pkg_block.txt', encoding='utf-8').read()

TEMPLATE = r'''#!/usr/bin/env python
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
SPEC_B64 = "__SPEC_B64__"

__PKG_BLOCK__

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
'''

src = TEMPLATE.replace("__SPEC_B64__", blob).replace("__PKG_BLOCK__", pkg)
pathlib.Path('stable/patch_codex.py').write_text(src, encoding='utf-8')
print("wrote stable/patch_codex.py", len(src), "bytes")
