#!/usr/bin/env python
"""Codex Orbit patcher — v0.5.x, REBUILT FROM SCRATCH.

Injects ONE self-contained "Codex Orbit" sidebar into Codex's webview. The sidebar
gets its chat list by INTERCEPTING Codex's own data transport (the thread list the
host pushes to the webview via messages), filters to the CURRENT project, and
renders it with search, pinned/starred sections, real SVG icons, drag-to-resize and
a collapse that keeps the chats visible. A DOM scrape of Codex's stable
`data-app-action-sidebar-*` rows is kept as a fallback + to enable click-to-open.

  * One appended IIFE — no surgery on minified Codex code, so it does NOT drift on
    Codex updates. Depends only on the wire data shape + stable data-attributes.
  * `copy_patched_assets` keeps that name: the Orbit wrapper's OTA loader requires
    that marker string to accept a patcher over the air.
"""
from __future__ import annotations
import argparse, datetime as dt, json, platform, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path

__version__ = "0.5.5"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
HELPER_PREFIX = "window-app-action-helpers-"

SIDEBAR_IIFE = r"""
;(() => {
  try {
    if (typeof window === "undefined" || typeof document === "undefined" || window.__codexOrbitSidebarV4) return;
    window.__codexOrbitSidebarV4 = true;

    const COLLAPSED_KEY="codexOrbitCollapsedV4", GROUP_KEY="codexOrbitGroupsV4", WIDTH_KEY="codexOrbitWidthV4";
    const OPEN_WIDTH=320;
    const A={row:"[data-app-action-sidebar-thread-row]",id:"data-app-action-sidebar-thread-id",title:"data-app-action-sidebar-thread-title",active:"data-app-action-sidebar-thread-active",pinned:"data-app-action-sidebar-thread-pinned",projectLabel:"data-app-action-sidebar-project-label",projectRow:"[data-app-action-sidebar-project-row]",sectionHeading:"[data-app-action-sidebar-section-heading]"};
    const IC={
      search:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="7" cy="7" r="4.3"/><line x1="10.3" y1="10.3" x2="14" y2="14" stroke-linecap="round"/></svg>',
      plus:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="8" y1="3.2" x2="8" y2="12.8"/><line x1="3.2" y1="8" x2="12.8" y2="8"/></svg>',
      gear:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="8" cy="8" r="2.1"/><path stroke-linecap="round" d="M8 1.6v1.5M8 12.9v1.5M14.4 8h-1.5M3.1 8H1.6M12.5 3.5l-1.05 1.05M4.55 11.45 3.5 12.5M12.5 12.5l-1.05-1.05M4.55 4.55 3.5 3.5"/></svg>',
      chev:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="6.5,3.5 11,8 6.5,12.5"/></svg>'
    };

    let shell=null, collapsed=false, search="", groupState=Object.create(null), dataThreads=[];
    try{ collapsed=localStorage.getItem(COLLAPSED_KEY)==="true"; groupState=JSON.parse(localStorage.getItem(GROUP_KEY)||"{}")||{}; }catch{}
    const clean=(v)=>String(v||"").replace(/\s+/g," ").trim();
    const pick=(o,keys)=>{ for(const k of keys){ if(o&&o[k]!=null) return o[k]; } return undefined; };

    // ---------- TRANSPORT INTERCEPT: pluck the thread list out of host messages ----------
    function looksThready(o){
      if(!o||typeof o!=="object"||Array.isArray(o)) return false;
      const title=pick(o,["title","name","summary","label"]);
      const id=pick(o,["id","threadId","conversationId","sessionId","uuid"]);
      return typeof title==="string" && id!=null;
    }
    function findThreadArray(d,depth){
      if(depth>7||!d||typeof d!=="object") return null;
      if(Array.isArray(d)){
        if(d.length){ const good=d.filter(looksThready).length; if(good>=Math.max(1,Math.ceil(d.length*0.6))) return d; }
        for(const x of d){ const r=findThreadArray(x,depth+1); if(r) return r; }
        return null;
      }
      for(const k of ["threads","data","items","list","results","conversations","sessions","tasks"]){ if(d[k]!=null){ const r=findThreadArray(d[k],depth+1); if(r) return r; } }
      for(const k in d){ try{ const r=findThreadArray(d[k],depth+1); if(r) return r; }catch{} }
      return null;
    }
    function projectOf(raw){
      const p=pick(raw,["project","projectName","workspace","workspaceName","folder","folderName"]);
      if(typeof p==="string"&&p.trim()) return clean(p);
      if(p&&typeof p==="object"){ const l=pick(p,["label","name","title","id"]); if(l) return clean(l); }
      const pid=pick(raw,["projectId","workspaceId","folderId","cwd","workingDirectory","repo","repoPath"]);
      if(typeof pid==="string"&&pid.trim()){ const parts=pid.replace(/[\\/]+$/,"").split(/[\\/]/); return clean(parts[parts.length-1])||clean(pid); }
      return "Other";
    }
    function tsOf(raw){ let v=pick(raw,["updatedAt","updated_at","lastModified","modifiedAt","lastMessageAt","lastActivityAt","mtime","createdAt","created_at"]); if(v==null) return 0; if(typeof v==="number") return v<1e12?v*1000:v; const n=Date.parse(v); return isNaN(n)?0:n; }
    function normalizeRaw(raw){
      if(!looksThready(raw)) return null;
      const id=String(pick(raw,["id","threadId","conversationId","sessionId","uuid"]));
      let title=clean(pick(raw,["title","name","summary","label"]))||"Untitled";
      const starred=title.startsWith("⭐ ")||raw.starred===true||raw.favorited===true;
      const pinned=title.replace(/^⭐\s*/,"").startsWith("📌 ")||raw.pinned===true;
      const current=raw.current===true||raw.isCurrent===true||raw.isCurrentWorkspace===true||raw.inCurrentWorkspace===true||raw.selected===true||raw.active===true||raw.isActive===true;
      return {__id:id,id,title,project:projectOf(raw),pinned,starred,active:current,current,ts:tsOf(raw),source:"data",raw};
    }
    function ingest(payload){
      try{
        const arr=findThreadArray(payload,0);
        if(!arr||!arr.length) return;
        const map=new Map(dataThreads.map((t)=>[t.__id,t]));
        let changed=false;
        for(const raw of arr){ const n=normalizeRaw(raw); if(n){ map.set(n.__id,n); changed=true; } }
        if(changed){ dataThreads=[...map.values()]; try{ window.__codexOrbitThreads=dataThreads; }catch{} scheduleRender(); }
      }catch{}
    }
    // Observe-only: host->webview RPC responses arrive as window "message" events.
    window.addEventListener("message",(e)=>{ try{ ingest(e.data); }catch{} },true);

    // ---------- DOM fallback (native sidebar view, if present) ----------
    function domThreads(){
      const sel=A.projectRow+","+A.sectionHeading+","+A.row, out=[], seen=new Set(); let group="Chats";
      document.querySelectorAll(sel).forEach((el)=>{
        if(el.matches(A.projectRow)){ group=clean(el.getAttribute(A.projectLabel))||clean(el.textContent)||"Project"; return; }
        if(el.matches(A.sectionHeading)){ group=clean(el.textContent)||group; return; }
        if(!el.matches(A.row)) return;
        const id=el.getAttribute(A.id)||clean(el.getAttribute(A.title))||String(out.length);
        if(seen.has(id)) return; seen.add(id);
        let title=clean(el.getAttribute(A.title))||clean(el.textContent)||"Untitled";
        const starred=title.startsWith("⭐ ");
        const pinned=title.replace(/^⭐\s*/,"").startsWith("📌 ")||el.getAttribute(A.pinned)==="true";
        out.push({__id:id,id,title,project:group,pinned,starred,active:el.getAttribute(A.active)==="true",current:el.getAttribute(A.active)==="true",ts:0,source:"dom",element:el});
      });
      return out;
    }
    function allThreads(){
      const dom=domThreads();
      if(dataThreads.length){
        const byId=new Map(dataThreads.map((t)=>[t.__id,{...t}]));
        for(const d of dom){ const e=byId.get(d.__id); if(e){ e.element=d.element; } else { byId.set(d.__id,d); } }
        return [...byId.values()];
      }
      return dom;
    }
    // Current project: an explicit current/selected thread wins; else the most
    // recently-updated thread's project; else the first.
    function currentProject(){
      const list=allThreads();
      const c=list.find((t)=>t.current); if(c) return c.project;
      let best=null,bt=-1; for(const t of list){ const ts=t.ts||0; if(ts>bt){ bt=ts; best=t; } }
      if(best&&bt>0) return best.project;
      return list.length?list[0].project:null;
    }

    function ensureStyle(){
      if(document.getElementById("codexOrbitStyleV4")) return;
      const s=document.createElement("style"); s.id="codexOrbitStyleV4";
      s.textContent=`
:root{--cox-open:${OPEN_WIDTH}px;--cox-closed:200px}
.coxSidebar{position:fixed;top:0;right:0;bottom:0;width:var(--cox-open);z-index:100;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);font-family:var(--vscode-font-family,system-ui,sans-serif);font-size:12px;transition:width .14s ease}
.coxSidebar *{box-sizing:border-box}
.coxResize{position:absolute;left:-3px;top:0;bottom:0;width:6px;cursor:col-resize;z-index:1}
.coxResize:hover{background:var(--vscode-focusBorder,#4d8dff)}
.coxHead{height:36px;display:flex;align-items:center;gap:4px;padding:0 6px;border-bottom:1px solid var(--vscode-sideBar-border,#282828)}
.coxTitle{flex:1;min-width:0;font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--vscode-descriptionForeground,#9d9d9d);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxBtn{width:24px;height:24px;flex:0 0 24px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:5px;background:transparent;color:var(--vscode-icon-foreground,#b8b8b8);cursor:pointer;padding:0}
.coxBtn:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:var(--vscode-foreground,#fff)}
.coxBtn svg{width:15px;height:15px;display:block}
.coxSearchWrap{margin:8px}
.coxSearch{width:100%;height:28px;border:1px solid var(--vscode-input-border,transparent);border-radius:5px;background:var(--vscode-input-background,#1f1f1f);color:var(--vscode-input-foreground,#ddd);padding:0 8px;font:inherit;outline:none}
.coxSearch:focus{border-color:var(--vscode-focusBorder,#4d8dff)}
.coxSearchWrap.coxHidden{display:none}
.coxList{flex:1;min-height:0;overflow:auto;padding:0 6px 12px}
.coxGroupBtn{width:100%;height:24px;display:flex;align-items:center;gap:6px;border:0;background:transparent;color:var(--vscode-descriptionForeground,#9a9a9a);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;margin-top:6px}
.coxGroupBtn:hover{color:#ddd}
.coxGroupName{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
.coxRow{width:100%;min-height:28px;display:flex;align-items:center;gap:7px;border:0;border-radius:5px;background:transparent;color:var(--vscode-foreground,#d4d4d4);cursor:pointer;padding:4px 7px;text-align:left}
.coxRow:hover{background:var(--vscode-list-hoverBackground,rgba(255,255,255,.07))}
.coxRow.act{background:var(--vscode-list-activeSelectionBackground,#37373d);color:#fff}
.coxMark{width:12px;flex:0 0 12px;text-align:center;font-size:10px}
.coxRowT{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxEmpty{margin:22px 12px;color:var(--vscode-descriptionForeground,#969696);text-align:center;line-height:1.45}
.coxSideOpen body{padding-right:var(--cox-open)!important}
.coxSideClosed body{padding-right:var(--cox-closed)!important}
.coxSideClosed .coxSidebar{width:var(--cox-closed)}
.coxSideClosed .coxTitle,.coxSideClosed .coxSearchWrap{display:none}
`;
      document.head.appendChild(s);
    }
    function syncChrome(){
      document.documentElement.classList.add("coxSideOpen");
      document.documentElement.classList.toggle("coxSideClosed",collapsed);
      try{ localStorage.setItem(COLLAPSED_KEY,String(collapsed)); }catch{}
    }
    let renderTimer=null;
    function scheduleRender(){ clearTimeout(renderTimer); renderTimer=setTimeout(render,80); }
    function ensureShell(){
      ensureStyle();
      if(shell) return shell;
      shell=document.createElement("aside"); shell.className="coxSidebar"; shell.setAttribute("aria-label","Codex Orbit chats");
      shell.innerHTML=`
        <div class="coxResize" title="Drag to resize"></div>
        <div class="coxHead">
          <div class="coxTitle">Codex Orbit</div>
          <button class="coxBtn coxSearchToggle" type="button" title="Search chats">${IC.search}</button>
          <button class="coxBtn coxNew" type="button" title="New task">${IC.plus}</button>
          <button class="coxBtn coxSettings" type="button" title="Settings">${IC.gear}</button>
          <button class="coxBtn coxCollapse" type="button" title="Collapse / expand">${IC.chev}</button>
        </div>
        <div class="coxSearchWrap coxHidden"><input class="coxSearch" type="search" placeholder="Search chats" aria-label="Search chats"></div>
        <div class="coxList" role="list"></div>`;
      document.body.appendChild(shell);
      const clickNative=(sels)=>{ for(const s of sels){ let el=null; try{ el=document.querySelector(s); }catch{} if(el&&!el.closest(".coxSidebar")){ el.click(); return true; } } return false; };
      shell.querySelector(".coxSearch").addEventListener("input",(e)=>{ search=e.target.value||""; render(); });
      shell.querySelector(".coxCollapse").addEventListener("click",()=>{ collapsed=!collapsed; syncChrome(); render(); });
      shell.querySelector(".coxSearchToggle").addEventListener("click",()=>{ const w=shell.querySelector(".coxSearchWrap"); const hid=w.classList.toggle("coxHidden"); if(!hid){ const i=w.querySelector(".coxSearch"); if(i){ i.focus(); i.select(); } } });
      shell.querySelector(".coxNew").addEventListener("click",()=>{ clickNative(["[aria-label*='new task' i]","[aria-label*='new chat' i]","[aria-label*='new codex' i]","[aria-label*='new conversation' i]","[aria-label*='compose' i]"]); });
      shell.querySelector(".coxSettings").addEventListener("click",()=>{ clickNative(["[aria-label*='codex settings' i]","[aria-label*='open settings' i]","[aria-label='Settings' i]","[title*='settings' i]"]); });
      const handle=shell.querySelector(".coxResize"); let rw=0,rx=0;
      const onMove=(ev)=>{ const w=Math.max(200,Math.min(window.innerWidth*0.6,rw+(rx-ev.clientX))); document.documentElement.style.setProperty("--cox-open",w+"px"); };
      const onUp=()=>{ document.removeEventListener("pointermove",onMove); document.removeEventListener("pointerup",onUp); try{ localStorage.setItem(WIDTH_KEY,String(parseInt(getComputedStyle(document.documentElement).getPropertyValue("--cox-open"))||OPEN_WIDTH)); }catch{} };
      handle.addEventListener("pointerdown",(ev)=>{ ev.preventDefault(); rw=shell.getBoundingClientRect().width; rx=ev.clientX; document.addEventListener("pointermove",onMove); document.addEventListener("pointerup",onUp); });
      try{ const sw=parseInt(localStorage.getItem(WIDTH_KEY)||""); if(sw>=200) document.documentElement.style.setProperty("--cox-open",sw+"px"); }catch{}
      syncChrome();
      return shell;
    }
    function openThread(t){
      if(t.element&&typeof t.element.click==="function"){ t.element.click(); return; }
      try{ const row=document.querySelector(`[data-app-action-sidebar-thread-id="${(window.CSS&&CSS.escape)?CSS.escape(t.id):t.id}"]`); if(row&&typeof row.click==="function"){ row.click(); } }catch{}
    }
    function addRow(parent,t){
      const b=document.createElement("button"); b.type="button"; b.className="coxRow"+(t.active?" act":""); b.title=t.title;
      const mark=document.createElement("span"); mark.className="coxMark"; mark.textContent=t.pinned?"📌":(t.starred?"⭐":"");
      const tt=document.createElement("span"); tt.className="coxRowT"; tt.textContent=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,"");
      b.append(mark,tt);
      b.addEventListener("click",()=>openThread(t));
      b.addEventListener("contextmenu",(ev)=>{ if(t.element){ ev.preventDefault(); t.element.dispatchEvent(new MouseEvent("contextmenu",{bubbles:true,cancelable:true,clientX:ev.clientX,clientY:ev.clientY})); } });
      parent.appendChild(b);
    }
    function addGroup(list,name,rows){
      if(!rows.length) return;
      const sec=document.createElement("section");
      const gb=document.createElement("button"); gb.type="button"; gb.className="coxGroupBtn";
      const ic=document.createElement("span"); ic.textContent=groupState[name]===false?"+":"-";
      const nm=document.createElement("span"); nm.className="coxGroupName"; nm.textContent=name;
      gb.append(ic,nm);
      gb.addEventListener("click",()=>{ groupState[name]=groupState[name]===false; try{localStorage.setItem(GROUP_KEY,JSON.stringify(groupState));}catch{} render(); });
      sec.appendChild(gb);
      if(groupState[name]!==false){ for(const r of rows) addRow(sec,r); }
      list.appendChild(sec);
    }
    function render(){
      const side=ensureShell(); const list=side.querySelector(".coxList");
      let rows=allThreads();
      const cur=currentProject();
      try{ window.__codexOrbitCurrentProject=cur; }catch{}
      if(cur){ const f=rows.filter((t)=>t.project===cur); rows=f.length?f:rows; }   // current project only; fall back to all if that would be empty
      const needle=search.toLowerCase();
      if(needle) rows=rows.filter((t)=>t.title.toLowerCase().includes(needle)||(t.project||"").toLowerCase().includes(needle));
      list.textContent="";
      if(!rows.length){ const e=document.createElement("div"); e.className="coxEmpty"; e.textContent=search?"No matching chats.":"No chats found yet."; list.appendChild(e); return; }
      const pinned=rows.filter((t)=>t.pinned), starred=rows.filter((t)=>!t.pinned&&t.starred), rest=rows.filter((t)=>!t.pinned&&!t.starred);
      addGroup(list,"📌 Pinned",pinned);
      addGroup(list,"⭐ Starred",starred);
      const order=[],by=new Map(); for(const r of rest){ if(!by.has(r.project)){by.set(r.project,[]);order.push(r.project);} by.get(r.project).push(r); }
      for(const n of order) addGroup(list,n,by.get(n));
    }
    function start(){
      if(!document.body){ setTimeout(start,60); return; }
      ensureShell(); render();
      new MutationObserver(scheduleRender).observe(document.documentElement,{childList:true,subtree:true});
      window.addEventListener("focus",()=>setTimeout(render,80));
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
    if "__codexOrbitSidebarV4" not in text:
        text += "\n" + SIDEBAR_IIFE
    new_name = stem + "-codexpatch.js"
    (wv / new_name).write_text(text, encoding="utf-8", newline="")
    if helper.name != new_name and helper.exists():
        helper.unlink()
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
