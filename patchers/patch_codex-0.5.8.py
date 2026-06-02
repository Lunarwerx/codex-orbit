#!/usr/bin/env python
"""Codex Orbit patcher — v0.5.x, REBUILT FROM SCRATCH.

Injects ONE self-contained "Codex Orbit" sidebar into Codex's webview. The sidebar
gets its chat list by INTERCEPTING Codex's own data transport (the thread list the
host pushes to the webview via messages), filters to the CURRENT project, and
renders it with search, pinned/starred sections (right-click to toggle, stored
locally), real SVG icons, a full-width New Task button, drag-to-resize and a
collapse that shrinks to a thin button rail. A DOM scrape of Codex's stable
`data-app-action-sidebar-*` rows is kept as a fallback + to enable click-to-open.
`window.codexOrbitDump()` downloads a debug JSON so issues can be diagnosed
without asking the user to read the console.

  * One appended IIFE — no surgery on minified Codex code, so it does NOT drift on
    Codex updates. Depends only on the wire data shape + stable data-attributes.
  * `copy_patched_assets` keeps that name: the Orbit wrapper's OTA loader requires
    that marker string to accept a patcher over the air.
"""
from __future__ import annotations
import argparse, datetime as dt, json, platform, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path

__version__ = "0.5.8"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
HELPER_PREFIX = "window-app-action-helpers-"

SIDEBAR_IIFE = r"""
;(() => {
  try {
    if (typeof window === "undefined" || typeof document === "undefined" || window.__codexOrbitSidebarV4) return;
    window.__codexOrbitSidebarV4 = true;

    const COLLAPSED_KEY="codexOrbitCollapsedV4", GROUP_KEY="codexOrbitGroupsV4", WIDTH_KEY="codexOrbitWidthV4", PIN_KEY="codexOrbitPinsV4", STAR_KEY="codexOrbitStarsV4";
    const OPEN_WIDTH=320;
    const A={row:"[data-app-action-sidebar-thread-row]",id:"data-app-action-sidebar-thread-id",title:"data-app-action-sidebar-thread-title",active:"data-app-action-sidebar-thread-active",pinned:"data-app-action-sidebar-thread-pinned",projectLabel:"data-app-action-sidebar-project-label",projectRow:"[data-app-action-sidebar-project-row]",sectionHeading:"[data-app-action-sidebar-section-heading]"};
    const IC={
      search:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="7" cy="7" r="4.3"/><line x1="10.3" y1="10.3" x2="14" y2="14" stroke-linecap="round"/></svg>',
      plus:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="8" y1="3.2" x2="8" y2="12.8"/><line x1="3.2" y1="8" x2="12.8" y2="8"/></svg>',
      gear:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="8" cy="8" r="2.1"/><path stroke-linecap="round" d="M8 1.6v1.5M8 12.9v1.5M14.4 8h-1.5M3.1 8H1.6M12.5 3.5l-1.05 1.05M4.55 11.45 3.5 12.5M12.5 12.5l-1.05-1.05M4.55 4.55 3.5 3.5"/></svg>',
      chev:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="6.5,3.5 11,8 6.5,12.5"/></svg>'
    };

    let shell=null, collapsed=false, search="", groupState=Object.create(null), dataThreads=[], pins=new Set(), stars=new Set(), activeRoots=[];
    try{ collapsed=localStorage.getItem(COLLAPSED_KEY)==="true"; groupState=JSON.parse(localStorage.getItem(GROUP_KEY)||"{}")||{}; pins=new Set(JSON.parse(localStorage.getItem(PIN_KEY)||"[]")); stars=new Set(JSON.parse(localStorage.getItem(STAR_KEY)||"[]")); }catch{}
    const saveSet=(k,s)=>{ try{ localStorage.setItem(k,JSON.stringify([...s])); }catch{} };
    const clean=(v)=>String(v||"").replace(/\s+/g," ").trim();
    const pick=(o,keys)=>{ for(const k of keys){ if(o&&o[k]!=null) return o[k]; } return undefined; };
    const isPinned=(t)=>pins.has(t.id)||t.pinned;
    const isStarred=(t)=>stars.has(t.id)||t.starred;

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
      const cwd=clean(pick(raw,["cwd","workingDirectory","workspaceRoot","projectPath","repoPath","folderPath","rootPath"]));
      return {__id:id,id,title,project:projectOf(raw),cwd,pinned,starred,active:current,current,ts:tsOf(raw),source:"data",raw};
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
    // Codex's "active-workspace-roots(-updated)" host message carries roots[0] =
    // the active workspace. Capture it from the same stream (no guessing).
    function findRoots(d){
      if(!d||typeof d!=="object") return null;
      const ty=d.type||(d.data&&d.data.type);
      const roots=d.roots||(d.data&&d.data.roots);
      if(typeof ty==="string"&&ty.indexOf("active-workspace-roots")>=0&&Array.isArray(roots)&&roots.length) return roots;
      const cand=roots||(d.payload&&d.payload.roots)||(d.body&&d.body.roots);
      if(Array.isArray(cand)&&cand.length&&cand.every((x)=>typeof x==="string"&&/[\\/]/.test(x))) return cand;
      return null;
    }
    function ingestRoots(payload){
      const r=findRoots(payload);
      if(r&&r.length){ const j=JSON.stringify(r); if(j!==JSON.stringify(activeRoots)){ activeRoots=r; try{ window.__codexOrbitRoots=r; }catch{} scheduleRender(); } }
    }
    // Observe-only: host->webview RPC responses arrive as window "message" events.
    window.addEventListener("message",(e)=>{ try{ ingest(e.data); }catch{} try{ ingestRoots(e.data); }catch{} },true);

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
        out.push({__id:id,id,title,project:group,cwd:"",pinned,starred,active:el.getAttribute(A.active)==="true",current:el.getAttribute(A.active)==="true",ts:0,source:"dom",element:el});
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
    // The current workspace, taken from Codex's OWN signal: the "active-workspace-roots"
    // host message (roots[0] = active workspace), matched to each chat by its cwd. Same
    // source Codex uses to group its native sidebar — no guessing, no DOM scraping.
    function normPath(p){ return String(p||"").replace(/\\/g,"/").replace(/\/+$/,"").toLowerCase(); }
    function lastSeg(p){ const n=normPath(p); return n?n.split("/").pop():""; }
    function inWorkspace(t,root){
      const r=normPath(root); if(!r) return false;
      const c=normPath(t.cwd);
      if(c&&(c===r||c.indexOf(r+"/")===0||r.indexOf(c+"/")===0)) return true;
      const ls=lastSeg(root); return !!ls && (t.project||"").toLowerCase()===ls;
    }
    function currentRows(rows){
      const root=activeRoots[0];
      if(root){ const f=rows.filter((t)=>inWorkspace(t,root)); try{window.__codexOrbitCurrentProject=lastSeg(root);}catch{} return f.length?f:rows; }
      const a=rows.find((t)=>t.current);
      if(a){ try{window.__codexOrbitCurrentProject=a.project;}catch{} const f=rows.filter((t)=>t.project===a.project); return f.length?f:rows; }
      try{window.__codexOrbitCurrentProject=null;}catch{}
      return rows; // workspace not known yet -> show all (never a wrong guess)
    }

    function ensureStyle(){
      if(document.getElementById("codexOrbitStyleV4")) return;
      const s=document.createElement("style"); s.id="codexOrbitStyleV4";
      s.textContent=`
:root{--cox-open:${OPEN_WIDTH}px;--cox-rail:46px}
.coxSidebar{position:fixed;top:0;right:0;bottom:0;width:var(--cox-open);z-index:100;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);font-family:var(--vscode-font-family,system-ui,sans-serif);font-size:12px;transition:width .14s ease}
.coxSidebar *{box-sizing:border-box}
.coxResize{position:absolute;left:-3px;top:0;bottom:0;width:6px;cursor:col-resize;z-index:1}
.coxResize:hover{background:var(--vscode-focusBorder,#4d8dff)}
.coxHead{height:36px;display:flex;align-items:center;gap:4px;padding:0 6px;border-bottom:1px solid var(--vscode-sideBar-border,#282828)}
.coxTitle{flex:1;min-width:0;font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--vscode-descriptionForeground,#9d9d9d);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxBtn{width:24px;height:24px;flex:0 0 24px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:5px;background:transparent;color:var(--vscode-icon-foreground,#b8b8b8);cursor:pointer;padding:0}
.coxBtn:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:var(--vscode-foreground,#fff)}
.coxBtn svg{width:15px;height:15px;display:block}
.coxNewBtn{display:flex;align-items:center;justify-content:center;gap:7px;margin:8px;height:30px;border:1px solid var(--vscode-button-border,var(--vscode-input-border,#3a3a3a));border-radius:6px;background:var(--vscode-button-secondaryBackground,#2b2b2b);color:var(--vscode-button-secondaryForeground,var(--vscode-foreground,#eee));cursor:pointer;font:inherit;font-weight:600}
.coxNewBtn:hover{background:var(--vscode-button-secondaryHoverBackground,#383838)}
.coxNewBtn svg{width:14px;height:14px;display:block}
.coxNewIco{display:inline-flex}
.coxSearchWrap{margin:0 8px 8px}
.coxSearch{width:100%;height:28px;border:1px solid var(--vscode-input-border,transparent);border-radius:5px;background:var(--vscode-input-background,#1f1f1f);color:var(--vscode-input-foreground,#ddd);padding:0 8px;font:inherit;outline:none}
.coxSearch:focus{border-color:var(--vscode-focusBorder,#4d8dff)}
.coxSearchWrap.coxHidden{display:none}
.coxList{flex:1;min-height:0;overflow:auto;padding:0 6px 12px}
.coxGroupBtn{width:100%;height:24px;display:flex;align-items:center;border:0;background:transparent;color:var(--vscode-descriptionForeground,#9a9a9a);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;margin-top:6px}
.coxGroupBtn:hover{color:#ddd}
.coxGroupName{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
.coxRow{width:100%;min-height:28px;display:flex;align-items:center;gap:7px;border:0;border-radius:5px;background:transparent;color:var(--vscode-foreground,#d4d4d4);cursor:pointer;padding:4px 7px;text-align:left}
.coxRow:hover{background:var(--vscode-list-hoverBackground,rgba(255,255,255,.07))}
.coxRow.act{background:var(--vscode-list-activeSelectionBackground,#37373d);color:#fff}
.coxMark{width:12px;flex:0 0 12px;text-align:center;font-size:10px}
.coxRowT{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxEmpty{margin:22px 12px;color:var(--vscode-descriptionForeground,#969696);text-align:center;line-height:1.45}
.coxMenu{position:fixed;z-index:101;min-width:150px;background:var(--vscode-menu-background,#252526);color:var(--vscode-menu-foreground,#cccccc);border:1px solid var(--vscode-menu-border,#454545);border-radius:6px;padding:4px;box-shadow:0 6px 18px rgba(0,0,0,.45)}
.coxMenuItem{display:block;width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:5px 10px;border-radius:4px;cursor:pointer;font:inherit;font-size:12px}
.coxMenuItem:hover{background:var(--vscode-menu-selectionBackground,#04395e);color:var(--vscode-menu-selectionForeground,#fff)}
.coxMenuSep{height:1px;margin:4px 6px;background:var(--vscode-menu-separatorBackground,#454545)}
.coxNewMini{display:none}
.coxSideOpen body{padding-right:var(--cox-open)!important}
.coxSideClosed body{padding-right:0!important}
.coxSideClosed .coxSidebar{left:auto;right:8px;top:44px;bottom:auto;width:auto;height:auto;border:1px solid var(--vscode-sideBar-border,#2b2b2b);border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,.4);transition:none}
.coxSideClosed .coxHead{border-bottom:0;padding:3px 5px;gap:2px}
.coxSideClosed .coxTitle,.coxSideClosed .coxSearchWrap,.coxSideClosed .coxNewBtn,.coxSideClosed .coxList,.coxSideClosed .coxResize{display:none}
.coxSideClosed .coxNewMini{display:inline-flex}
.coxSideClosed .coxCollapse svg{transform:rotate(180deg)}
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
    const clickNative=(sels)=>{ for(const s of sels){ let el=null; try{ el=document.querySelector(s); }catch{} if(el&&!el.closest(".coxSidebar")){ el.click(); return true; } } return false; };
    function ensureShell(){
      ensureStyle();
      if(shell) return shell;
      shell=document.createElement("aside"); shell.className="coxSidebar"; shell.setAttribute("aria-label","Codex Orbit chats");
      shell.innerHTML=`
        <div class="coxResize" title="Drag to resize"></div>
        <div class="coxHead">
          <div class="coxTitle">Codex Orbit</div>
          <button class="coxBtn coxNewMini" type="button" title="New task">${IC.plus}</button>
          <button class="coxBtn coxSearchToggle" type="button" title="Search chats">${IC.search}</button>
          <button class="coxBtn coxSettings" type="button" title="Settings">${IC.gear}</button>
          <button class="coxBtn coxCollapse" type="button" title="Collapse / expand">${IC.chev}</button>
        </div>
        <div class="coxSearchWrap coxHidden"><input class="coxSearch" type="search" placeholder="Search chats" aria-label="Search chats"></div>
        <button class="coxNewBtn" type="button" title="New task"><span class="coxNewIco">${IC.plus}</span><span class="coxNewLbl">New Task</span></button>
        <div class="coxList" role="list"></div>`;
      document.body.appendChild(shell);
      shell.querySelector(".coxSearch").addEventListener("input",(e)=>{ search=e.target.value||""; render(); });
      shell.querySelector(".coxCollapse").addEventListener("click",()=>{ collapsed=!collapsed; syncChrome(); render(); });
      shell.querySelector(".coxSearchToggle").addEventListener("click",()=>{ if(collapsed){ collapsed=false; syncChrome(); } const w=shell.querySelector(".coxSearchWrap"); const hid=w.classList.toggle("coxHidden"); if(!hid){ const i=w.querySelector(".coxSearch"); if(i){ i.focus(); i.select(); } } });
      const newTask=()=>{ clickNative(["[aria-label*='new task' i]","[aria-label*='new chat' i]","[aria-label*='new codex' i]","[aria-label*='new conversation' i]","[aria-label*='new session' i]","[aria-label*='compose' i]","[title*='new task' i]","[title*='new session' i]"]); };
      shell.querySelector(".coxNewBtn").addEventListener("click",newTask);
      shell.querySelector(".coxNewMini").addEventListener("click",newTask);
      shell.querySelector(".coxSettings").addEventListener("click",()=>{ clickNative(["[aria-label*='codex settings' i]","[aria-label*='open settings' i]","[aria-label='Settings' i]","[title*='settings' i]"]); });
      const handle=shell.querySelector(".coxResize"); let rw=0,rx=0;
      const onMove=(ev)=>{ const w=Math.max(200,Math.min(window.innerWidth*0.6,rw+(rx-ev.clientX))); document.documentElement.style.setProperty("--cox-open",w+"px"); };
      const onUp=()=>{ document.removeEventListener("pointermove",onMove); document.removeEventListener("pointerup",onUp); try{ localStorage.setItem(WIDTH_KEY,String(parseInt(getComputedStyle(document.documentElement).getPropertyValue("--cox-open"))||OPEN_WIDTH)); }catch{} };
      handle.addEventListener("pointerdown",(ev)=>{ ev.preventDefault(); rw=shell.getBoundingClientRect().width; rx=ev.clientX; document.addEventListener("pointermove",onMove); document.addEventListener("pointerup",onUp); });
      try{ const sw=parseInt(localStorage.getItem(WIDTH_KEY)||""); if(sw>=200) document.documentElement.style.setProperty("--cox-open",sw+"px"); }catch{}
      syncChrome();
      return shell;
    }
    function navTo(path){ try{ window.history.pushState({},"",path); window.dispatchEvent(new PopStateEvent("popstate")); return true; }catch{ return false; } }
    function openThread(t){
      // 1) native row, if Codex's own sidebar happens to be mounted (uses its own handler)
      if(t.element&&typeof t.element.click==="function"){ t.element.click(); return; }
      try{ const row=document.querySelector(`[data-app-action-sidebar-thread-id="${(window.CSS&&CSS.escape)?CSS.escape(t.id):t.id}"]`); if(row&&typeof row.click==="function"){ row.click(); return; } }catch{}
      // 2) React Router (unstable_HistoryRouter): local chats live at /local/<id>
      navTo("/local/"+encodeURIComponent(t.id));
    }
    // ---------- right-click context menu (our sidebar, our menu) ----------
    function closeMenu(){ document.querySelectorAll(".coxMenu").forEach((e)=>e.remove()); }
    function showMenu(x,y,t){
      closeMenu();
      const m=document.createElement("div"); m.className="coxMenu";
      const add=(label,fn)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxMenuItem"; b.textContent=label; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); fn(); closeMenu(); render(); }); m.appendChild(b); };
      const sep=()=>{ const d=document.createElement("div"); d.className="coxMenuSep"; m.appendChild(d); };
      add(isPinned(t)?"Unpin":"Pin to top",()=>{ if(pins.has(t.id))pins.delete(t.id); else { pins.add(t.id); stars.delete(t.id); } saveSet(PIN_KEY,pins); saveSet(STAR_KEY,stars); });
      add(isStarred(t)?"Unstar":"Star",()=>{ if(stars.has(t.id))stars.delete(t.id); else { stars.add(t.id); pins.delete(t.id); } saveSet(STAR_KEY,stars); saveSet(PIN_KEY,pins); });
      sep();
      add("Open",()=>openThread(t));
      add("Filter to this chat",()=>{ search=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,""); const sw=shell.querySelector(".coxSearchWrap"); sw.classList.remove("coxHidden"); const i=sw.querySelector(".coxSearch"); if(i) i.value=search; });
      document.body.appendChild(m);
      const r=m.getBoundingClientRect();
      m.style.left=Math.max(6,Math.min(x,window.innerWidth-r.width-8))+"px";
      m.style.top=Math.max(6,Math.min(y,window.innerHeight-r.height-8))+"px";
    }
    document.addEventListener("click",(e)=>{ if(!e.target.closest||!e.target.closest(".coxMenu")) closeMenu(); },true);
    document.addEventListener("keydown",(e)=>{ if(e.key==="Escape") closeMenu(); });

    function addRow(parent,t){
      const b=document.createElement("button"); b.type="button"; b.className="coxRow"+(t.active?" act":""); b.title=t.title;
      const mark=document.createElement("span"); mark.className="coxMark"; mark.textContent=isPinned(t)?"📌":(isStarred(t)?"⭐":"");
      const tt=document.createElement("span"); tt.className="coxRowT"; tt.textContent=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,"");
      b.append(mark,tt);
      b.addEventListener("click",()=>openThread(t));
      b.addEventListener("contextmenu",(ev)=>{ ev.preventDefault(); ev.stopPropagation(); showMenu(ev.clientX,ev.clientY,t); });
      parent.appendChild(b);
    }
    function addGroup(list,name,rows){
      if(!rows.length) return;
      const sec=document.createElement("section");
      const gb=document.createElement("button"); gb.type="button"; gb.className="coxGroupBtn";
      const nm=document.createElement("span"); nm.className="coxGroupName"; nm.textContent=name;
      gb.append(nm);
      gb.addEventListener("click",()=>{ groupState[name]=groupState[name]===false; try{localStorage.setItem(GROUP_KEY,JSON.stringify(groupState));}catch{} render(); });
      sec.appendChild(gb);
      if(groupState[name]!==false){ for(const r of rows) addRow(sec,r); }
      list.appendChild(sec);
    }
    function render(){
      const side=ensureShell(); const list=side.querySelector(".coxList");
      let rows=currentRows(allThreads());   // filtered to the active workspace (Codex's roots[0])
      const needle=search.toLowerCase();
      if(needle) rows=rows.filter((t)=>t.title.toLowerCase().includes(needle)||(t.project||"").toLowerCase().includes(needle));
      list.textContent="";
      if(!rows.length){ const e=document.createElement("div"); e.className="coxEmpty"; e.textContent=search?"No matching chats.":"No chats found yet."; list.appendChild(e); return; }
      const pinned=rows.filter(isPinned), starred=rows.filter((t)=>!isPinned(t)&&isStarred(t)), rest=rows.filter((t)=>!isPinned(t)&&!isStarred(t));
      addGroup(list,"📌 Pinned",pinned);
      addGroup(list,"⭐ Starred",starred);
      const order=[],by=new Map(); for(const r of rest){ if(!by.has(r.project)){by.set(r.project,[]);order.push(r.project);} by.get(r.project).push(r); }
      for(const n of order) addGroup(list,n,by.get(n));
    }

    // ---------- self-diagnostics: download a debug snapshot, no console copy/paste ----------
    window.codexOrbitDump=function(){
      const labels=(sel)=>[...document.querySelectorAll(sel)].map((b)=>b.getAttribute("aria-label")||b.getAttribute("title")||clean(b.textContent)).filter(Boolean);
      const anchors=[...document.querySelectorAll("a[href]")].map((a)=>a.getAttribute("href")).filter((h)=>h&&h[0]==="/").slice(0,40);
      const data={
        at:new Date().toISOString(),
        version:"0.5.8",
        location:{href:location.href,pathname:location.pathname,hash:location.hash,search:location.search},
        activeRoots:activeRoots,
        currentProject:(window.__codexOrbitCurrentProject||null),
        activeThread:(allThreads().find((t)=>t.active)||{}).title||null,
        threadCount:dataThreads.length,
        projects:[...new Set(allThreads().map((t)=>t.project))],
        sampleCwds:allThreads().slice(0,8).map((t)=>t.cwd).filter(Boolean),
        pins:[...pins], stars:[...stars],
        routeAnchors:anchors,
        sampleRaw:dataThreads.slice(0,4).map((t)=>t.raw),
        nativeButtons:labels("button[aria-label],button[title]").slice(0,80)
      };
      try{ localStorage.setItem("codexOrbitDebug",JSON.stringify(data)); }catch{}
      try{
        const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
        const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="codex-orbit-debug.json";
        document.body.appendChild(a); a.click(); setTimeout(()=>{ try{URL.revokeObjectURL(a.href);}catch{} a.remove(); },200);
      }catch(e){ console.warn("[Codex Orbit] dump download blocked:",e); }
      console.log("[Codex Orbit] debug dump",data);
      return data;
    };

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
