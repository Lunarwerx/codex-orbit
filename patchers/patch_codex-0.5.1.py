#!/usr/bin/env python
"""Codex Orbit patcher — v0.5.x, REBUILT FROM SCRATCH.

Step one of the clean rebuild. This patcher does exactly ONE thing: it injects a
self-contained "Codex Orbit" sidebar into Codex's webview. The sidebar reads
Codex's OWN chat rows and project/section structure straight from the DOM (the
approach proven by the original Claude-Script patcher) and renders them, grouped
by project, in a panel of our own — WITHOUT reorganizing Codex's native list and
WITHOUT any of the old patch's rename/pin/workspace-groups edits.

Why this shape:
  * It is a single appended IIFE — no surgery on minified Codex code, so it does
    NOT drift when Codex ships an update. It only depends on Codex's stable
    `data-app-action-sidebar-*` attributes.
  * `copy_patched_assets` keeps that name because the Orbit wrapper's OTA loader
    requires that marker string to accept a patcher over the air.

Earlier versions (0.4.x — the brother's full patch) remain installable via
"Use previous versions".
"""
from __future__ import annotations
import argparse, datetime as dt, json, platform, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path

__version__ = "0.5.0"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
HELPER_PREFIX = "window-app-action-helpers-"  # the webview module that loads in the sidebar context

# --------------------------------------------------------------------------- #
# The entire patch: one self-contained sidebar IIFE, appended to a webview file.
# Depends ONLY on Codex's stable data-attributes, so Codex updates don't break it.
# --------------------------------------------------------------------------- #
SIDEBAR_IIFE = r"""
;(() => {
  try {
    if (typeof window === "undefined" || typeof document === "undefined" || window.__codexOrbitSidebarV2) return;
    window.__codexOrbitSidebarV2 = true;

    const COLLAPSED_KEY = "codexOrbitSidebarCollapsedV2";
    const GROUP_KEY = "codexOrbitSidebarGroupsV2";
    const OPEN_WIDTH = 320, CLOSED_WIDTH = 36;
    const A = {
      row: "[data-app-action-sidebar-thread-row]",
      id: "data-app-action-sidebar-thread-id",
      title: "data-app-action-sidebar-thread-title",
      active: "data-app-action-sidebar-thread-active",
      pinned: "data-app-action-sidebar-thread-pinned",
      kind: "data-app-action-sidebar-thread-kind",
      projectRow: "[data-app-action-sidebar-project-row]",
      projectLabel: "data-app-action-sidebar-project-label",
      sectionHeading: "[data-app-action-sidebar-section-heading]",
    };
    let shell = null, collapsed = false, search = "", groups = Object.create(null);
    try {
      collapsed = localStorage.getItem(COLLAPSED_KEY) === "true";
      groups = JSON.parse(localStorage.getItem(GROUP_KEY) || "{}") || Object.create(null);
    } catch {}
    const clean = (v) => String(v || "").replace(/\s+/g, " ").trim();

    function ensureStyle() {
      if (document.getElementById("codexOrbitSidebarStyleV2")) return;
      const s = document.createElement("style");
      s.id = "codexOrbitSidebarStyleV2";
      s.textContent = `
:root{--cox-open:${OPEN_WIDTH}px;--cox-closed:${CLOSED_WIDTH}px}
.coxSidebar{position:fixed;top:34px;right:0;bottom:0;width:var(--cox-open);z-index:2147482000;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);font-family:var(--vscode-font-family,system-ui,sans-serif);font-size:12px;transition:width .14s ease}
.coxSidebar *{box-sizing:border-box}
.coxHead{height:38px;display:flex;align-items:center;gap:6px;padding:0 8px;border-bottom:1px solid var(--vscode-sideBar-border,#282828)}
.coxTitle{flex:1;min-width:0;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--vscode-descriptionForeground,#9d9d9d)}
.coxCount{min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;border-radius:9px;background:var(--vscode-badge-background,#3a3a3a);color:var(--vscode-badge-foreground,#fff);font-size:10px}
.coxBtn{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:5px;background:transparent;color:var(--vscode-icon-foreground,#b8b8b8);cursor:pointer}
.coxBtn:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:#fff}
.coxSearchWrap{margin:8px;position:relative}
.coxSearch{width:100%;height:28px;border:1px solid var(--vscode-input-border,transparent);border-radius:5px;background:var(--vscode-input-background,#1f1f1f);color:var(--vscode-input-foreground,#ddd);padding:0 8px;font:inherit;outline:none}
.coxSearch:focus{border-color:var(--vscode-focusBorder,#4d8dff)}
.coxList{flex:1;min-height:0;overflow:auto;padding:0 6px 12px}
.coxGroupBtn{width:100%;height:24px;display:flex;align-items:center;gap:6px;border:0;background:transparent;color:var(--vscode-descriptionForeground,#9a9a9a);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;margin-top:6px}
.coxGroupBtn:hover{color:#ddd}
.coxGroupName{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
.coxRow{width:100%;height:28px;display:flex;align-items:center;gap:7px;border:0;border-radius:5px;background:transparent;color:var(--vscode-foreground,#d4d4d4);cursor:pointer;padding:0 7px;text-align:left}
.coxRow:hover{background:var(--vscode-list-hoverBackground,rgba(255,255,255,.07))}
.coxRow.act{background:var(--vscode-list-activeSelectionBackground,#37373d);color:#fff}
.coxPin{width:10px;flex:0 0 10px;color:#8a8a8a;text-align:center}
.coxRowT{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxEmpty{margin:22px 12px;color:var(--vscode-descriptionForeground,#969696);text-align:center;line-height:1.45}
.coxResize{position:absolute;left:-3px;top:0;bottom:0;width:6px;cursor:col-resize;z-index:1}
.coxResize:hover{background:var(--vscode-focusBorder,#4d8dff)}
.coxReopen{position:fixed;top:40px;right:8px;z-index:2147482001;width:26px;height:26px;display:none;align-items:center;justify-content:center;border:1px solid var(--vscode-sideBar-border,#2b2b2b);border-radius:6px;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-icon-foreground,#b8b8b8);cursor:pointer;font-size:13px}
.coxReopen:hover{color:#fff}
.coxSideOpen body{padding-right:var(--cox-open)!important}
.coxSideClosed body{padding-right:0!important}
.coxSideClosed .coxSidebar{transform:translateX(100%)}
.coxSideClosed .coxReopen{display:inline-flex}
`;
      document.head.appendChild(s);
    }
    function syncChrome() {
      document.documentElement.classList.add("coxSideOpen");
      document.documentElement.classList.toggle("coxSideClosed", collapsed);
      try { localStorage.setItem(COLLAPSED_KEY, String(collapsed)); } catch {}
    }
    function ensureShell() {
      ensureStyle();
      if (shell) return shell;
      shell = document.createElement("aside");
      shell.className = "coxSidebar";
      shell.setAttribute("aria-label", "Codex Orbit chats");
      shell.innerHTML = `
        <div class="coxResize" title="Drag to resize"></div>
        <div class="coxHead">
          <div class="coxTitle">Codex Orbit</div>
          <span class="coxCount">0</span>
          <button class="coxBtn coxCollapse" type="button" title="Collapse">&lt;</button>
        </div>
        <div class="coxSearchWrap"><input class="coxSearch" type="search" placeholder="Search chats" aria-label="Search chats"></div>
        <div class="coxList" role="list"></div>`;
      document.body.appendChild(shell);
      const reopen = document.createElement("button");
      reopen.className = "coxReopen"; reopen.type = "button"; reopen.title = "Open Codex Orbit"; reopen.textContent = "‹";
      reopen.addEventListener("click", () => { collapsed = false; syncChrome(); render(); });
      document.body.appendChild(reopen);
      shell.querySelector(".coxSearch").addEventListener("input", (e) => { search = e.target.value || ""; render(); });
      shell.querySelector(".coxCollapse").addEventListener("click", () => { collapsed = true; syncChrome(); render(); });
      // drag-to-resize from the left edge
      const handle = shell.querySelector(".coxResize");
      let rw = 0, rx = 0;
      const onMove = (ev) => {
        const w = Math.max(220, Math.min(window.innerWidth * 0.6, rw + (rx - ev.clientX)));
        document.documentElement.style.setProperty("--cox-open", w + "px");
      };
      const onUp = () => {
        document.removeEventListener("pointermove", onMove); document.removeEventListener("pointerup", onUp);
        try { localStorage.setItem("codexOrbitSidebarWidthV2", String(parseInt(getComputedStyle(document.documentElement).getPropertyValue("--cox-open")) || OPEN_WIDTH)); } catch {}
      };
      handle.addEventListener("pointerdown", (ev) => {
        ev.preventDefault(); rw = shell.getBoundingClientRect().width; rx = ev.clientX;
        document.addEventListener("pointermove", onMove); document.addEventListener("pointerup", onUp);
      });
      try { const sw = parseInt(localStorage.getItem("codexOrbitSidebarWidthV2") || ""); if (sw >= 220) document.documentElement.style.setProperty("--cox-open", sw + "px"); } catch {}
      syncChrome();
      return shell;
    }
    // Read Codex's own rows + project/section structure in document order — the
    // most recent project/section header before a row is that row's group. This
    // is exactly how Codex associates a chat with a project; we just mirror it.
    function collect() {
      const sel = `${A.projectRow},${A.sectionHeading},${A.row}`;
      const out = [];
      const seen = new Set();
      let group = "Chats";
      document.querySelectorAll(sel).forEach((el) => {
        if (el.matches(A.projectRow)) { group = clean(el.getAttribute(A.projectLabel)) || clean(el.textContent) || "Project"; return; }
        if (el.matches(A.sectionHeading)) { group = clean(el.textContent) || group; return; }
        if (!el.matches(A.row)) return;
        const id = el.getAttribute(A.id) || `${out.length}`;
        if (seen.has(id)) return;
        seen.add(id);
        const title = clean(el.getAttribute(A.title)) || clean(el.textContent) || "Untitled";
        out.push({ id, title, group, element: el,
          pinned: el.getAttribute(A.pinned) === "true",
          active: el.getAttribute(A.active) === "true" });
      });
      return out;
    }
    function render() {
      const side = ensureShell();
      const list = side.querySelector(".coxList");
      const needle = search.toLowerCase();
      const rows = collect().filter((r) => !needle || r.title.toLowerCase().includes(needle) || r.group.toLowerCase().includes(needle));
      side.querySelector(".coxCount").textContent = String(rows.length);
      if (collapsed) return;
      list.textContent = "";
      if (!rows.length) {
        const e = document.createElement("div");
        e.className = "coxEmpty";
        e.textContent = search ? "No matching chats." : "No chats found yet.";
        list.appendChild(e); return;
      }
      const order = [];
      const byGroup = new Map();
      for (const r of rows) { if (!byGroup.has(r.group)) { byGroup.set(r.group, []); order.push(r.group); } byGroup.get(r.group).push(r); }
      for (const name of order) {
        const sec = document.createElement("section");
        const gb = document.createElement("button");
        gb.type = "button"; gb.className = "coxGroupBtn";
        const ic = document.createElement("span"); ic.textContent = groups[name] === false ? "+" : "-";
        const nm = document.createElement("span"); nm.className = "coxGroupName"; nm.textContent = name;
        const ct = document.createElement("span"); ct.textContent = String(byGroup.get(name).length);
        gb.append(ic, nm, ct);
        gb.addEventListener("click", () => { groups[name] = groups[name] === false; try { localStorage.setItem(GROUP_KEY, JSON.stringify(groups)); } catch {} render(); });
        sec.appendChild(gb);
        if (groups[name] !== false) {
          for (const r of byGroup.get(name)) {
            const b = document.createElement("button");
            b.type = "button"; b.className = "coxRow" + (r.active ? " act" : ""); b.title = r.title;
            const pin = document.createElement("span"); pin.className = "coxPin"; pin.textContent = r.pinned ? "*" : "";
            const t = document.createElement("span"); t.className = "coxRowT"; t.textContent = r.title;
            b.append(pin, t);
            b.addEventListener("click", () => r.element.click());
            b.addEventListener("contextmenu", (ev) => { ev.preventDefault(); r.element.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: ev.clientX, clientY: ev.clientY })); });
            sec.appendChild(b);
          }
        }
        list.appendChild(sec);
      }
    }
    function start() {
      if (!document.body) { setTimeout(start, 60); return; }
      ensureShell(); render();
      let t = null;
      new MutationObserver(() => { clearTimeout(t); t = setTimeout(render, 120); })
        .observe(document.documentElement, { childList: true, subtree: true, attributes: true,
          attributeFilter: [A.title, A.active, A.pinned] });
      window.addEventListener("focus", () => setTimeout(render, 80));
    }
    start();
  } catch (e) { console.warn("Codex Orbit sidebar failed", e); }
})();
"""


def log(m):
    line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


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
    cache = Path(tempfile.gettempdir()) / "codex-orbit-cache"; cache.mkdir(parents=True, exist_ok=True)
    dest = cache / fname
    if dest.exists() and dest.stat().st_size > 1_000_000:
        log(f"Using cached Codex VSIX ({dest.stat().st_size} bytes): {fname}"); return dest
    log(f"Downloading {pub}.{name} {sel['version']} {sp or 'platform-neutral'}")
    part = dest.with_name(dest.name + ".part")
    urllib.request.urlretrieve(pkg["source"], part); part.replace(dest)
    log(f"Downloaded VSIX size: {dest.stat().st_size} bytes (cached)")
    return dest


def assert_codex(ext_dir):
    p = ext_dir / "package.json"
    if not p.exists(): raise RuntimeError("Missing extension/package.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    eid = f"{m.get('publisher')}.{m.get('name')}"
    if eid != DEFAULT_MARKETPLACE_ITEM: raise RuntimeError(f"Expected {DEFAULT_MARKETPLACE_ITEM}, got {eid}")
    return m


def copy_patched_assets(extension_dir, patcher_version):
    """The whole patch: append the Codex Orbit sidebar IIFE to the webview helper
    module and cache-bust it. Marker-named for the OTA loader."""
    ext = Path(extension_dir); wv = ext / "webview" / "assets"
    if not wv.exists(): raise RuntimeError("webview/assets not found")
    cands = [p for p in wv.glob(HELPER_PREFIX + "*.js") if not p.name.endswith(".map")]
    if not cands: raise RuntimeError(f"No {HELPER_PREFIX}*.js found")
    helper = cands[0]
    stem = helper.stem
    text = helper.read_text(encoding="utf-8", errors="ignore")
    if "__codexOrbitSidebarV2" not in text:
        text += "\n" + SIDEBAR_IIFE
    new_name = stem + "-codexpatch.js"
    (wv / new_name).write_text(text, encoding="utf-8", newline="")
    if helper.name != new_name and helper.exists():
        helper.unlink()
    # cache-bust: rewrite references to the old stem across webview JS
    for f in wv.glob("*.js"):
        t = f.read_text(encoding="utf-8", errors="ignore")
        if stem in t and f.name != new_name:
            f.write_text(t.replace(stem, stem + "-codexpatch"), encoding="utf-8", newline="")
    log(f"Injected Codex Orbit sidebar into {new_name}")
    marker = {"tool": "Codex Orbit", "patcherVersion": patcher_version, "target": DEFAULT_MARKETPLACE_ITEM,
              "targetVersion": json.loads((ext / 'package.json').read_text(encoding='utf-8')).get('version'),
              "patchedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "mode": "sidebar-only"}
    (ext / "codex-orbit-patch.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    log("Wrote codex-orbit-patch.json marker")


def verify(ext_dir):
    node = shutil.which("node")
    f = next((p for p in (ext_dir / "webview" / "assets").glob(HELPER_PREFIX + "*-codexpatch.js")), None)
    if node and f:
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"Patched JS invalid: {(r.stderr or '').strip().splitlines()[-1:]}")
        log("JS syntax check passed")
    else:
        log("node not found or helper missing — skipping JS syntax check")


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
    p = argparse.ArgumentParser(description="Codex Orbit sidebar patcher")
    p.add_argument("target", nargs="?", default=DEFAULT_MARKETPLACE_ITEM)
    p.add_argument("--out", default=""); p.add_argument("--version", default="")
    p.add_argument("--target-platform", default=""); p.add_argument("--download-dir", default=".")
    p.add_argument("--log", default="codex-vsix-patch.log"); p.add_argument("--download-only", action="store_true")
    p.add_argument("--patcher-version", default="dev")
    a = p.parse_args()
    LOG_PATH = Path(a.log).expanduser().resolve(); LOG_PATH.write_text("", encoding="utf-8")
    log(f"Codex Orbit sidebar patcher v{__version__} (patcher-version {a.patcher_version})")
    target = resolve_target(a)
    if a.download_only:
        print(f"STOCK_VSIX_PATH: {target}", flush=True); log("Download-only mode"); return 0
    out = Path(a.out).resolve() if a.out else (Path(a.download_dir).resolve() / "patched.vsix")
    with tempfile.TemporaryDirectory(prefix="codex-orbit-") as tmp:
        root = Path(tmp) / "vsix"
        with zipfile.ZipFile(target) as z: z.extractall(root)
        ext = root / "extension"
        m = assert_codex(ext); log(f"Target: {m.get('displayName')} v{m.get('version')}")
        copy_patched_assets(ext, a.patcher_version)
        verify(ext)
        log("Writing patched VSIX"); zip_dir(root, out)
    log(f"Patched VSIX written: {out}"); log("Overall status: sidebar injected")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log(f"Patch run failed: {exc}"); raise
