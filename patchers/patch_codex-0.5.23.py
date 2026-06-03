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

__version__ = "0.5.23"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
HELPER_PREFIX = "window-app-action-helpers-"

SIDEBAR_IIFE = r"""
;(() => {
  try {
    if (typeof window === "undefined" || typeof document === "undefined" || window.__codexOrbitSidebarV4) return;
    window.__codexOrbitSidebarV4 = true;

    const COLLAPSED_KEY="codexOrbitCollapsedV4", GROUP_KEY="codexOrbitGroupsV4", WIDTH_KEY="codexOrbitWidthV4", PIN_KEY="codexOrbitPinsV4", STAR_KEY="codexOrbitStarsV4", CUR_KEY="codexOrbitCurrentV4", COLOR_KEY="codexOrbitColorsV4", ARCH_KEY="codexOrbitArchivedV4", FILTER_KEY="codexOrbitFilterV4";
    const OPEN_WIDTH=320;
    // Our palette (Codex ships no color set — its labelColor store is dormant, no UI).
    const PALETTE=[{k:"red",c:"#e5484d"},{k:"orange",c:"#f5a524"},{k:"yellow",c:"#f5d90a"},{k:"green",c:"#30a46c"},{k:"blue",c:"#3b82f6"},{k:"purple",c:"#8b5cf6"}];
    const colorOf=(k)=>{ const p=PALETTE.find((x)=>x.k===k); return p?p.c:""; };
    const A={row:"[data-app-action-sidebar-thread-row]",id:"data-app-action-sidebar-thread-id",title:"data-app-action-sidebar-thread-title",active:"data-app-action-sidebar-thread-active",pinned:"data-app-action-sidebar-thread-pinned",hostId:"data-app-action-sidebar-thread-host-id",kind:"data-app-action-sidebar-thread-kind",projectLabel:"data-app-action-sidebar-project-label",projectRow:"[data-app-action-sidebar-project-row]",sectionHeading:"[data-app-action-sidebar-section-heading]"};
    const IC={
      search:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="7" cy="7" r="4.3"/><line x1="10.3" y1="10.3" x2="14" y2="14" stroke-linecap="round"/></svg>',
      plus:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="8" y1="3.2" x2="8" y2="12.8"/><line x1="3.2" y1="8" x2="12.8" y2="8"/></svg>',
      chev:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="6.5,3.5 11,8 6.5,12.5"/></svg>',
      gear:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="2.1"/><path d="M8 1.6v1.8M8 12.6v1.8M14.4 8h-1.8M3.4 8H1.6M12.5 3.5l-1.3 1.3M4.8 11.2l-1.3 1.3M12.5 12.5l-1.3-1.3M4.8 4.8L3.5 3.5"/></svg>',
      filter:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"><path d="M2.5 3.5h11l-4.1 4.9v4l-2.8 1.3V8.4z"/></svg>',
      star:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M8 2.3l1.7 3.5 3.8.5-2.8 2.7.7 3.8L8 11.3 4.6 12.8l.7-3.8L2.5 6.3l3.8-.5z"/></svg>',
      pin:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"><path d="M9.6 2.4l4 4-2.1.6-2.1 2.1-.4 2.9-3.9-3.9 2.9-.4 2.1-2.1z"/><line x1="5.1" y1="10.9" x2="2.4" y2="13.6"/></svg>',
      archive:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"><rect x="2.4" y="3" width="11.2" height="3" rx="1"/><path d="M3.5 6.3v6.2a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V6.3"/><line x1="6.4" y1="8.9" x2="9.6" y2="8.9"/></svg>',
      dot:'<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="4.4" fill="currentColor"/></svg>'
    };

    let shell=null, collapsed=false, search="", groupState=Object.create(null), dataThreads=[], pins=new Set(), stars=new Set(), activeRoots=[], colors=new Map(), archived=new Set();
    let filterState={types:[],age:0};
    const rowMap=new WeakMap();  // row element -> thread; delegated .coxList handlers read this so clicks survive the list re-render
    let interacting=false;       // true while the pointer is down on the list — freezes render() so the pressed row is not destroyed mid-click
    try{ collapsed=localStorage.getItem(COLLAPSED_KEY)==="true"; groupState=JSON.parse(localStorage.getItem(GROUP_KEY)||"{}")||{}; pins=new Set(JSON.parse(localStorage.getItem(PIN_KEY)||"[]")); stars=new Set(JSON.parse(localStorage.getItem(STAR_KEY)||"[]")); colors=new Map(Object.entries(JSON.parse(localStorage.getItem(COLOR_KEY)||"{}"))); archived=new Set(JSON.parse(localStorage.getItem(ARCH_KEY)||"[]")); filterState=Object.assign(filterState,JSON.parse(localStorage.getItem(FILTER_KEY)||"{}")); }catch{}
    const saveSet=(k,s)=>{ try{ localStorage.setItem(k,JSON.stringify([...s])); }catch{} };
    const saveColors=()=>{ try{ localStorage.setItem(COLOR_KEY,JSON.stringify(Object.fromEntries(colors))); }catch{} };
    const saveFilter=()=>{ try{ localStorage.setItem(FILTER_KEY,JSON.stringify(filterState)); }catch{} };
    const clean=(v)=>String(v||"").replace(/\s+/g," ").trim();
    const pick=(o,keys)=>{ for(const k of keys){ if(o&&o[k]!=null) return o[k]; } return undefined; };
    const isPinned=(t)=>pins.has(t.id)||t.pinned;
    const isStarred=(t)=>stars.has(t.id)||t.starred;
    // Host channel: Codex calls acquireVsCodeApi() exactly once; the patcher tees that
    // single instance into window.__codexOrbitVsApi (see expose_host_channel). This lets
    // us post the SAME host messages Codex's own code posts (archive-conversation,
    // run-command, ...) — no second acquire (which would throw).
    function coxPost(type,payload){
      try{ const a=window.__codexOrbitVsApi; if(a&&a.postMessage){ a.postMessage(Object.assign({},payload||{},{type})); return true; } }catch{}
      try{ if(typeof window.__codexPostMessage==="function"){ window.__codexPostMessage(type,payload||{}); return true; } }catch{}
      return false;
    }
    // Derived chat status -> dot color, matching Codex's own tone mapping
    // (running=blue, waiting=orange, failed=red, review=green, idle=gray). REMOTE tasks
    // carry status inline on the wire; LOCAL chats keep it in live atoms we can't see from
    // the intercepted list, so locals are best-effort (usually idle until they expose it).
    function statusOf(t){
      const raw=(t&&t.raw)||t||{};
      try{
        const d=raw.task_status_display||raw.taskStatusDisplay;
        const ts=d&&(d.latest_turn_status_display||d.latestTurnStatusDisplay);
        const tv=ts&&(ts.turn_status||ts.turnStatus);
        if(tv){ if(tv==="failed"||tv==="cancelled") return "failed"; if(tv==="in_progress"||tv==="pending") return "running"; }
        if(raw.archived===true) return "idle";
        const st=raw.status&&(raw.status.type||raw.status);
        if(st==="active"){ const f=(raw.status&&raw.status.activeFlags)||[]; return (f.indexOf&&(f.indexOf("waitingOnApproval")>=0||f.indexOf("waitingOnUserInput")>=0))?"waiting":"running"; }
        if(st==="systemError"||raw.failed===true) return "failed";
        const lt=raw.turns&&raw.turns.length&&raw.turns[raw.turns.length-1];
        if(lt&&lt.status==="failed") return "failed";
        if(lt&&lt.status==="inProgress") return "running";
        if(raw.has_unread_turn===true||raw.hasUnreadTurn===true) return "review";
      }catch{}
      return "idle";
    }
    const DOT={running:"var(--vscode-charts-blue,#3b82f6)",waiting:"var(--vscode-charts-orange,#f5a524)",failed:"var(--vscode-charts-red,#e5484d)",review:"var(--vscode-charts-green,#30a46c)",idle:"var(--vscode-descriptionForeground,#7a7a7a)"};

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
      const hostId=clean(pick(raw,["hostId","host","hostName"]));
      // Codex marks local chats with hostId "local"; anything else is a remote host.
      const kind=clean(pick(raw,["kind","threadKind","workspaceKind","type"]))||(hostId&&hostId!=="local"?"remote":"local");
      return {__id:id,id,title,project:projectOf(raw),cwd,hostId,kind,pinned,starred,active:current,current,ts:tsOf(raw),source:"data",raw};
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
      // active-workspace-roots is delivered as an RPC RESPONSE — Codex's webview asks
      // the host for it and the host replies {..., result:{roots:[...]}} (we saw the
      // handler: "active-workspace-roots":async()=>({roots:...})). It is NOT a typed
      // broadcast, so the old type-only check never matched. Deep-scan any incoming
      // message for a `roots` array of filesystem paths, wherever it is nested.
      let found=null;
      (function walk(o,depth){
        if(found||!o||typeof o!=="object"||depth>6) return;
        if(Array.isArray(o.roots)&&o.roots.length&&o.roots.every((x)=>typeof x==="string"&&/[\\/]/.test(x))){ found=o.roots; return; }
        if(Array.isArray(o)){ for(const x of o){ walk(x,depth+1); if(found) return; } return; }
        for(const k in o){ try{ walk(o[k],depth+1); }catch{} if(found) return; }
      })(d,0);
      return found;
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
        const hostId=clean(el.getAttribute(A.hostId)), kind=clean(el.getAttribute(A.kind))||(hostId&&hostId!=="local"?"remote":"local");
        out.push({__id:id,id,title,project:group,cwd:"",hostId,kind,pinned,starred,active:el.getAttribute(A.active)==="true",current:el.getAttribute(A.active)==="true",ts:0,source:"dom",element:el});
      });
      return out;
    }
    function mergeThreads(dom){
      if(dataThreads.length){
        const byId=new Map(dataThreads.map((t)=>[t.__id,{...t}]));
        for(const d of dom){ const e=byId.get(d.__id); if(e){ e.element=d.element; if(!e.hostId&&d.hostId)e.hostId=d.hostId; if(!e.kind&&d.kind)e.kind=d.kind; } else { byId.set(d.__id,d); } }
        return [...byId.values()];
      }
      return dom;
    }
    function allThreads(){ return mergeThreads(domThreads()); }
    // The current workspace from Codex's OWN signals — never reset to "show all"
    // just because one signal is momentarily absent. Two are kept, EITHER suffices,
    // and the pair is PERSISTED so a missed/late active-workspace-roots message or a
    // list-only view can't dump every project back into the list:
    //   curRoot  = normalized path (the open chat's cwd, or active-workspace-roots[0])
    //   curLabel = project label   (the open chat's project, or root's last segment)
    function normPath(p){ return String(p||"").replace(/\\/g,"/").replace(/\/+$/,"").toLowerCase(); }
    function lastSeg(p){ const n=normPath(p); return n?n.split("/").pop():""; }
    // The OPEN chat's id is right in the route: /local/<id>, /remote/<id>,
    // /worktree-init-v2/<id>. That chat is, by definition, in the current workspace —
    // a transport-independent "which workspace is home" signal (no RPC needed).
    function openThreadId(){
      try{ const m=String(location.pathname||"").match(/\/(?:local|remote|worktree-init[^/]*)\/([^/?#]+)/); if(m) return decodeURIComponent(m[1]); }catch{}
      return "";
    }
    // AUTHORITATIVE workspace — the single source of truth. The extension HOST knows
    // the VS Code workspace for certain (Oe.workspace.workspaceFolders) and stamps it
    // into the page as <meta name="codex-orbit-workspace" content='{"r":path,"l":name}'>
    // (injected by inject_workspace_meta into webviewMetaTags, which BOTH HTML
    // generators call). Present on EVERY view — the task-list/home view included —
    // before any chat is opened and with no RPC race. The URL/roots/active-flag
    // heuristics below are now only a fallback for a host bundle we failed to patch.
    function hostWorkspace(){
      try{
        const m=document.querySelector('meta[name="codex-orbit-workspace"]');
        if(!m) return null;
        const v=m.getAttribute("content"); if(!v) return null;
        const o=JSON.parse(v);
        if(o&&(o.r||o.l)) return o;
      }catch{}
      return null;
    }
    let curRoot="", curLabel="";
    try{ const c=JSON.parse(localStorage.getItem(CUR_KEY)||"{}"); curRoot=c.r||""; curLabel=c.l||""; }catch{}
    function setCurrent(root,label){
      const r=normPath(root||""), l=clean(label||"").toLowerCase();
      let ch=false;
      if(r&&r!==curRoot){ curRoot=r; ch=true; }
      if(l&&l!==curLabel){ curLabel=l; ch=true; }
      if(ch){ try{ localStorage.setItem(CUR_KEY,JSON.stringify({r:curRoot,l:curLabel})); }catch{} }
    }
    function inCurrent(t){
      const c=normPath(t.cwd);
      if(curRoot){
        // A thread that carries a cwd is decided by PATH alone: the exact workspace or
        // a subfolder of it. Never let a shared project label pull another workspace in
        // (this is what was leaking Connections/SayDeploy/etc. into the list).
        if(c) return c===curRoot||c.indexOf(curRoot+"/")===0;
        // No cwd on this thread (e.g. a remote/cloud task of this project): match the
        // workspace label OR the root's folder basename (host gives both signals).
        const pj=clean(t.project).toLowerCase();
        return (!!curLabel&&pj===curLabel)||(!!pj&&pj===lastSeg(curRoot));
      }
      if(curLabel){ if(clean(t.project).toLowerCase()===curLabel) return true; if(c&&lastSeg(t.cwd)===curLabel) return true; }
      return false;
    }
    function threadTitleKey(s){ return titleKey(s).toLowerCase(); }
    function nativeScopedRows(rows,nativeRows){
      if(!nativeRows||!nativeRows.length) return null;
      const activeNative=nativeRows.find((t)=>t.current||t.active);
      if(activeNative){
        setCurrent(activeNative.cwd,activeNative.project);
        const activeProject=clean(activeNative.project).toLowerCase();
        const sameProject=rows.filter((t)=>clean(t.project).toLowerCase()===activeProject);
        if(sameProject.length) return sameProject;
      }
      if(curLabel){
        const sameProject=rows.filter((t)=>clean(t.project).toLowerCase()===curLabel);
        if(sameProject.length) return sameProject;
      }
      const ids=new Set(), titles=new Set();
      for(const n of nativeRows){
        if(n.__id) ids.add(String(n.__id));
        if(n.id) ids.add(String(n.id));
        const tk=threadTitleKey(n.title);
        if(tk) titles.add(tk);
      }
      const scoped=rows.filter((t)=>ids.has(String(t.__id))||ids.has(String(t.id))||titles.has(threadTitleKey(t.title)));
      if(scoped.length){
        const a=nativeRows.find((t)=>t.current||t.active)||nativeRows[0];
        if(a) setCurrent(a.cwd,a.project);
        return scoped;
      }
      return null;
    }
    function currentRows(rows,nativeRows){
      // Establish the CURRENT workspace, most-reliable signal first. We already know
      // every chat's project (that's the grouping) — the only question is which is home.
      //  0) AUTHORITATIVE: the host stamped the real VS Code workspace into the page.
      //     This works on the task-list/home view where every signal below is blank —
      //     which is exactly where the old build fell through and dumped ALL projects.
      const hw=hostWorkspace();
      if(hw) setCurrent(hw.r,hw.l);
      //  1) The OPEN chat (its id is in the URL). Its project/cwd IS the current one.
      const oid=openThreadId();
      if(oid){
        const ot=rows.find((t)=>String(t.id)===oid||String(t.__id)===oid)
              ||(nativeRows||[]).find((t)=>String(t.id)===oid||String(t.__id)===oid);
        if(ot) setCurrent(ot.cwd,ot.project);
      }
      //  2) Codex's active-workspace-roots[0] (a path), if we captured the RPC reply.
      if(!curRoot&&!curLabel&&activeRoots[0]) setCurrent(activeRoots[0],lastSeg(activeRoots[0]));
      //  3) Any chat the data/DOM marks current/active.
      if(!curRoot&&!curLabel){ const a=rows.find((t)=>t.current||t.active)||(nativeRows||[]).find((t)=>t.current||t.active); if(a) setCurrent(a.cwd,a.project); }
      // Known workspace -> filter (by cwd path when a chat carries one, else by exact
      // project name). When home is KNOWN we return only its threads — even if that is
      // an EMPTY set. Falling through to the blind "show a few" cap on an empty match is
      // precisely what leaked every other project into the list (you have 8 tasks, the
      // cap was <=8, so it showed all 8). Knowing home means never showing not-home.
      if(curRoot||curLabel){
        try{window.__codexOrbitCurrentProject=curLabel||lastSeg(curRoot)||null;}catch{}
        return rows.filter(inCurrent);
      }
      // Workspace still unknown: scope to Codex's native sidebar by precise id/title.
      const nativeScope=nativeScopedRows(rows,nativeRows);
      if(nativeScope) return nativeScope;
      // Truly blind (no host meta, no open chat, no roots, no active flag, no native
      // rows): prefer the active chat; otherwise show a few rows so it isn't barren.
      const actives=rows.filter((t)=>t.current||t.active);
      if(actives.length){ try{window.__codexOrbitCurrentProject=null;}catch{} return actives; }
      try{window.__codexOrbitCurrentProject=null;}catch{}
      return rows.length<=8?rows:rows.slice(0,8);
    }

    function ensureStyle(){
      if(document.getElementById("codexOrbitStyleV4")) return;
      const s=document.createElement("style"); s.id="codexOrbitStyleV4";
      s.textContent=`
:root{--cox-open:${OPEN_WIDTH}px;--cox-rail:46px}
.coxSidebar{position:fixed;top:0;right:0;bottom:0;width:var(--cox-open);z-index:2147483647;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);font-family:var(--vscode-font-family,system-ui,sans-serif);font-size:12px;transition:width .14s ease}
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
.coxRowT{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxEmpty{margin:22px 12px;color:var(--vscode-descriptionForeground,#969696);text-align:center;line-height:1.45}
.coxMenu{position:fixed;z-index:2147483647;min-width:150px;background:var(--vscode-menu-background,#252526);color:var(--vscode-menu-foreground,#cccccc);border:1px solid var(--vscode-menu-border,#454545);border-radius:6px;padding:4px;box-shadow:0 6px 18px rgba(0,0,0,.45)}
.coxMenuItem{display:block;width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:5px 10px;border-radius:4px;cursor:pointer;font:inherit;font-size:12px}
.coxMenuItem:hover{background:var(--vscode-menu-selectionBackground,#04395e);color:var(--vscode-menu-selectionForeground,#fff)}
.coxMenuSep{height:1px;margin:4px 6px;background:var(--vscode-menu-separatorBackground,#454545)}
.coxNewMini{display:none}
.coxSideOpen body{padding-right:var(--cox-open)!important}
.coxSideClosed body{padding-right:0!important}
.coxSideClosed .coxSidebar{left:auto;right:0;top:0;bottom:auto;width:auto;height:auto;z-index:2147483647;border:0;border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);border-bottom:1px solid var(--vscode-sideBar-border,#2b2b2b);border-radius:0 0 0 8px;box-shadow:0 4px 14px rgba(0,0,0,.35);transition:none}
.coxSideClosed .coxHead{border-bottom:0;padding:3px 5px;gap:2px}
.coxSideClosed .coxTitle,.coxSideClosed .coxSearchWrap,.coxSideClosed .coxNewBtn,.coxSideClosed .coxList,.coxSideClosed .coxResize{display:none}
.coxSideClosed .coxNewMini{display:inline-flex}
.coxSideClosed .coxCollapse svg{transform:rotate(180deg)}
.coxRow{position:relative}
.coxDot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:var(--vscode-descriptionForeground,#7a7a7a)}
.coxActs{display:none;align-items:center;gap:1px;margin-left:auto;padding-left:4px;flex:0 0 auto}
.coxRow:hover .coxActs{display:inline-flex}
.coxAct{width:21px;height:21px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:4px;background:transparent;color:var(--vscode-icon-foreground,#9a9a9a);cursor:pointer;padding:0}
.coxAct:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.13));color:#fff}
.coxAct.on{color:var(--vscode-focusBorder,#5b9dff)}
.coxAct svg{width:13px;height:13px;display:block}
.coxBtn.on{color:var(--vscode-focusBorder,#5b9dff)}
.coxMenuHead{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--vscode-descriptionForeground,#8a8a8a);padding:6px 10px 2px}
.coxMenuItem.coxCheck{position:relative;padding-left:24px}
.coxMenuItem.coxCheck.on::before{content:"✓";position:absolute;left:8px;top:5px;font-size:11px;color:var(--vscode-focusBorder,#7aa6ff)}
.coxColorMenu{display:flex;gap:6px;padding:8px}
.coxSwatch{width:21px;height:21px;border-radius:50%;border:2px solid transparent;cursor:pointer;padding:0;color:#999;font-size:12px;line-height:1;display:inline-flex;align-items:center;justify-content:center;background:transparent}
.coxSwatch.on{border-color:var(--vscode-focusBorder,#fff)}
.coxSwatch.coxNone{border:1px solid var(--vscode-menu-border,#555)}
`;
      document.head.appendChild(s);
    }
    function syncChrome(){
      document.documentElement.classList.add("coxSideOpen");
      document.documentElement.classList.toggle("coxSideClosed",collapsed);
      try{ localStorage.setItem(COLLAPSED_KEY,String(collapsed)); }catch{}
    }
    let renderTimer=null;
    function scheduleRender(){ if(interacting) return; clearTimeout(renderTimer); renderTimer=setTimeout(render,80); }
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
          <button class="coxBtn coxFilter" type="button" title="Filter chats">${IC.filter}</button>
          <button class="coxBtn coxSettings" type="button" title="Settings">${IC.gear}</button>
          <button class="coxBtn coxCollapse" type="button" title="Collapse / expand">${IC.chev}</button>
        </div>
        <div class="coxSearchWrap coxHidden"><input class="coxSearch" type="search" placeholder="Search chats" aria-label="Search chats"></div>
        <button class="coxNewBtn" type="button" title="New task"><span class="coxNewIco">${IC.plus}</span><span class="coxNewLbl">New Task</span></button>
        <div class="coxList" role="list"></div>`;
      document.body.appendChild(shell);
      // Event delegation on the persistent .coxList: row <button>s are rebuilt on
      // every render(), so per-element listeners die with their buttons. One listener
      // on the container survives. NOTE: delegation alone is NOT enough — if render()
      // removes the pressed row between pointerdown and mouseup, Chromium fires no
      // `click` at all (detached mousedown target), so there is nothing to delegate.
      // The interaction freeze below + the self-trigger guard on the observer are what
      // actually keep the row alive through the gesture so this `click` ever fires.
      const coxList=shell.querySelector(".coxList");
      coxList.addEventListener("click",(e)=>{
        const tgt=e.target; if(!tgt||!tgt.closest) return;
        const act=tgt.closest("[data-cox-act]");
        if(act){ e.stopPropagation(); const r=act.closest(".coxRow"); const t=r&&rowMap.get(r); if(t) rowAction(act.dataset.coxAct,t,e); return; }
        const row=tgt.closest(".coxRow");
        if(row){ const t=rowMap.get(row); if(t) openThread(t); return; }
        const grp=tgt.closest(".coxGroupBtn");
        if(grp&&grp.dataset.coxGroup!=null){ const name=grp.dataset.coxGroup; groupState[name]=groupState[name]===false; try{localStorage.setItem(GROUP_KEY,JSON.stringify(groupState));}catch{} render(); }
      });
      coxList.addEventListener("contextmenu",(e)=>{
        const tgt=e.target; if(!tgt||!tgt.closest) return;
        const row=tgt.closest(".coxRow"); if(!row) return;
        e.preventDefault(); e.stopPropagation();
        const t=rowMap.get(row); if(t) showMenu(e.clientX,e.clientY,t);
      });
      // Freeze re-render while the pointer is down on the list: a render() landing
      // between pointerdown and mouseup removes the pressed row, and Chromium then
      // fires NO click (detached mousedown target). Hold renders until release.
      coxList.addEventListener("pointerdown",()=>{ interacting=true; clearTimeout(renderTimer); },true);
      const endInteract=()=>{ if(interacting){ interacting=false; scheduleRender(); } };
      document.addEventListener("pointerup",endInteract,true);
      document.addEventListener("pointercancel",endInteract,true);
      shell.querySelector(".coxSearch").addEventListener("input",(e)=>{ search=e.target.value||""; render(); });
      shell.querySelector(".coxCollapse").addEventListener("click",()=>{ collapsed=!collapsed; syncChrome(); render(); });
      shell.querySelector(".coxSearchToggle").addEventListener("click",()=>{ if(collapsed){ collapsed=false; syncChrome(); } const w=shell.querySelector(".coxSearchWrap"); const hid=w.classList.toggle("coxHidden"); if(!hid){ const i=w.querySelector(".coxSearch"); if(i){ i.focus(); i.select(); } } });
      shell.querySelector(".coxFilter").addEventListener("click",(e)=>{ e.stopPropagation(); if(collapsed){ collapsed=false; syncChrome(); } showFilterMenu(shell.querySelector(".coxFilter")); });
      shell.querySelector(".coxSettings").addEventListener("click",(e)=>{ e.stopPropagation(); if(collapsed){ collapsed=false; syncChrome(); } showSettingsMenu(shell.querySelector(".coxSettings")); });
      const newTask=()=>{ clickNative(["[aria-label*='new task' i]","[aria-label*='new chat' i]","[aria-label*='new codex' i]","[aria-label*='new conversation' i]","[aria-label*='new session' i]","[aria-label*='compose' i]","[title*='new task' i]","[title*='new session' i]"]); };
      shell.querySelector(".coxNewBtn").addEventListener("click",newTask);
      shell.querySelector(".coxNewMini").addEventListener("click",newTask);
      const handle=shell.querySelector(".coxResize"); let rw=0,rx=0;
      const onMove=(ev)=>{ const w=Math.max(200,Math.min(window.innerWidth*0.6,rw+(rx-ev.clientX))); document.documentElement.style.setProperty("--cox-open",w+"px"); };
      const onUp=()=>{ document.removeEventListener("pointermove",onMove); document.removeEventListener("pointerup",onUp); try{ localStorage.setItem(WIDTH_KEY,String(parseInt(getComputedStyle(document.documentElement).getPropertyValue("--cox-open"))||OPEN_WIDTH)); }catch{} };
      handle.addEventListener("pointerdown",(ev)=>{ ev.preventDefault(); rw=shell.getBoundingClientRect().width; rx=ev.clientX; document.addEventListener("pointermove",onMove); document.addEventListener("pointerup",onUp); });
      try{ const sw=parseInt(localStorage.getItem(WIDTH_KEY)||""); if(sw>=200) document.documentElement.style.setProperty("--cox-open",sw+"px"); }catch{}
      syncChrome();
      return shell;
    }
    // Keep React Router's history-package state object so its popstate handler reads
    // a valid index (a bare {} confuses it); only the pathname changes.
    function navTo(path){ try{ const st=window.history.state; window.history.pushState(st&&typeof st==="object"?st:{},"",path); window.dispatchEvent(new PopStateEvent("popstate",{state:window.history.state})); return true; }catch{ return false; } }
    function appPost(type,payload){ try{ window.postMessage({...(payload||{}),type},window.location.origin||"*"); return true; }catch{ return false; } }
    function hostPost(type,payload){ try{ if(typeof window.__codexPostMessage==="function"){ window.__codexPostMessage(type,payload||{}); return true; } }catch{} return false; }
    function routeTo(path){
      // 1) Try host message (reliable — Codex's extension host handles routing).
      let ok=false;
      ok=hostPost("navigate-to-route",{path})||ok;
      ok=appPost("navigate-to-route",{path})||ok;
      ok=navTo(path)||ok;
      setTimeout(()=>{ try{ if(location.pathname!==path) window.location.href=path; }catch{} },120);
      return ok;
    }
    const titleKey=(s)=>clean(s).replace(/^⭐\s*/,"").replace(/^📌\s*/,"");
    function clickTarget(el){
      if(!el) return null;
      const q="a,button,[role='button'],[tabindex]";
      try{ if(el.matches&&el.matches(q)) return el; }catch{}
      try{ if(el.querySelector){ const child=el.querySelector(q); if(child) return child; } }catch{}
      return (el.closest&&el.closest(q))||el;
    }
    function clickStrong(el){
      const target=clickTarget(el);
      if(!target) return false;
      try{ target.scrollIntoView({block:"nearest",inline:"nearest"}); }catch{}
      let pos={clientX:0,clientY:0};
      try{ const r=target.getBoundingClientRect(); pos={clientX:r.left+(r.width/2),clientY:r.top+(r.height/2)}; }catch{}
      const ev=(name,Ctor,extra)=>{ try{ target.dispatchEvent(new Ctor(name,{bubbles:true,cancelable:true,view:window,...pos,...(extra||{})})); }catch{} };
      ev("pointerover",window.PointerEvent||MouseEvent,{pointerId:1,buttons:0});
      ev("mouseover",MouseEvent,{buttons:0});
      ev("pointerdown",window.PointerEvent||MouseEvent,{pointerId:1,buttons:1});
      ev("mousedown",MouseEvent,{buttons:1});
      ev("pointerup",window.PointerEvent||MouseEvent,{pointerId:1,buttons:0});
      ev("mouseup",MouseEvent,{buttons:0});
      try{ target.click(); return true; }catch{}
      ev("click",MouseEvent,{buttons:0});
      return true;
    }
    function threadPath(t){
      const kind=(t.kind||"").toLowerCase();
      if(kind==="pending-worktree") return "/worktree-init-v2/"+encodeURIComponent(t.id);
      const remote=(kind==="remote")||(t.hostId&&t.hostId.toLowerCase()!=="local");
      return (remote?"/remote/":"/local/")+encodeURIComponent(t.id);
    }
    function clickThenRoute(el,path){
      const before=location.pathname+location.search+location.hash;
      if(!clickStrong(el)) return false;
      setTimeout(()=>{ const now=location.pathname+location.search+location.hash; if(now===before) routeTo(path); },90);
      return true;
    }
    // Find the native Codex sidebar row that matches this thread by title.
    // Returns the DOM element or null.
    function findNativeRow(t){
      const want=titleKey(t.title);
      const rows=document.querySelectorAll(A.row);
      for(const el of rows){
        const elTitle=titleKey(el.getAttribute(A.title)||el.textContent||"");
        if(elTitle===want) return el;
        // Fuzzy match: one contains the other
        if(elTitle&&want&&(elTitle.includes(want)||want.includes(elTitle))) return el;
      }
      return null;
    }
    function openThread(t){
      const path=threadPath(t);
      // 1) Click the native Codex sidebar row (the ONE reliable path).
      //    Match by TITLE, not by ID — IDs differ between wire data and DOM.
      const nativeRow=t.element||findNativeRow(t);
      if(nativeRow&&clickThenRoute(nativeRow,path)) return;
      // 2) Try the opener registered by Codex's own component.
      try{
        if(typeof window.__codexOrbitOpenThreadById==="function"){
          if(window.__codexOrbitOpenThreadById(t.id)||window.__codexOrbitOpenThreadById(t.__id)) return;
        }
      }catch{}
      // 3) Hard fallback: route by path. The host postMessage path has been
      //    beefed up to try window.location.href as last resort.
      routeTo(path);
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
      add("Set color…",()=>showColorMenu(x,y,t));
      add("Archive",()=>archiveThread(t));
      add("Filter to this chat",()=>{ search=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,""); const sw=shell.querySelector(".coxSearchWrap"); sw.classList.remove("coxHidden"); const i=sw.querySelector(".coxSearch"); if(i) i.value=search; });
      sep();
      // Diagnostics: capture exactly what the webview sees (activeRoots, curRoot/
      // curLabel, and each thread's raw cwd/project) so workspace-filtering bugs are
      // fixed from real data, not guesses. Copies to clipboard AND downloads a file.
      add("Copy diagnostics",()=>{
        let d={}; try{ d=(window.codexOrbitDump&&window.codexOrbitDump())||{}; }catch(e){}
        const s=JSON.stringify(d,null,2);
        try{ navigator.clipboard.writeText(s); }
        catch(e){ try{ const ta=document.createElement("textarea"); ta.value=s; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }catch(_){} }
      });
      document.body.appendChild(m);
      const r=m.getBoundingClientRect();
      m.style.left=Math.max(6,Math.min(x,window.innerWidth-r.width-8))+"px";
      m.style.top=Math.max(6,Math.min(y,window.innerHeight-r.height-8))+"px";
    }
    function placeAt(m,x,y){ document.body.appendChild(m); const r=m.getBoundingClientRect(); m.style.left=Math.max(6,Math.min(x,window.innerWidth-r.width-8))+"px"; m.style.top=Math.max(6,Math.min(y,window.innerHeight-r.height-8))+"px"; }
    function anchorMenu(m,btn){ document.body.appendChild(m); const br=btn.getBoundingClientRect(),mr=m.getBoundingClientRect(); m.style.left=Math.max(6,Math.min(br.right-mr.width,window.innerWidth-mr.width-8))+"px"; m.style.top=Math.min(br.bottom+4,window.innerHeight-mr.height-8)+"px"; }
    // ---------- per-chat color (ours: Codex ships no palette/setter/render) ----------
    function showColorMenu(x,y,t){
      closeMenu();
      const m=document.createElement("div"); m.className="coxMenu coxColorMenu";
      const cur=colors.get(t.id)||"";
      const setC=(k)=>{ if(k) colors.set(t.id,k); else colors.delete(t.id); saveColors(); closeMenu(); render(); };
      const sw=(k,c,title,none)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxSwatch"+(none?" coxNone":"")+((k===cur||(!k&&!cur))?" on":""); b.title=title; if(c) b.style.background=c; if(none) b.textContent="⊘"; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); setC(k); }); m.appendChild(b); };
      sw("","","None",true); for(const p of PALETTE) sw(p.k,p.c,p.k,false);
      placeAt(m,x,y);
    }
    // ---------- filter menu (ours, over the data we already hold) ----------
    function showFilterMenu(btn){
      closeMenu();
      const f=filterState, m=document.createElement("div"); m.className="coxMenu coxFilterMenu";
      const head=(s)=>{ const h=document.createElement("div"); h.className="coxMenuHead"; h.textContent=s; m.appendChild(h); };
      const sep=()=>{ const d=document.createElement("div"); d.className="coxMenuSep"; m.appendChild(d); };
      const typeRow=(k,label)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxMenuItem coxCheck"+(((f.types||[]).indexOf(k)>=0)?" on":""); b.textContent=label; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); f.types=f.types||[]; const i=f.types.indexOf(k); if(i>=0)f.types.splice(i,1); else f.types.push(k); b.classList.toggle("on"); saveFilter(); render(); }); m.appendChild(b); };
      const ageRow=(v,label)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxMenuItem coxCheck"+(f.age===v?" on":""); b.textContent=label; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); f.age=(f.age===v?0:v); saveFilter(); render(); closeMenu(); }); m.appendChild(b); };
      head("Type"); typeRow("pinned","Pinned"); typeRow("starred","Starred"); typeRow("running","Running"); typeRow("waiting","Waiting");
      sep(); head("Age"); ageRow(1,"Last 1 hour"); ageRow(2,"Last 24 hours"); ageRow(3,"Last 7 days"); ageRow(4,"Last 30 days");
      sep();
      const clr=document.createElement("button"); clr.type="button"; clr.className="coxMenuItem"; clr.textContent="Clear all"; clr.addEventListener("click",(ev)=>{ ev.stopPropagation(); filterState={types:[],age:0}; saveFilter(); render(); closeMenu(); }); m.appendChild(clr);
      anchorMenu(m,btn);
    }
    function filterActive(){ const f=filterState; return (f.types&&f.types.length)||f.age; }
    // ---------- settings menu (our UI, Codex's own run-command actions) ----------
    // The webview dispatches menu actions via the "run-command" host message
    // (case 'run-command': md(e.id)&&nu(e.id)). We render Codex's exact 7-item gear menu
    // and post the SAME command ids. The newest gear menu is from a Codex newer than our
    // bundled baseline, so a few ids are best-known/derived — a miss is a harmless no-op,
    // and `window.codexOrbitDump()` reports whether the host channel is live so we can tune.
    function runCmd(id){ return coxPost("run-command",{id}); }
    function showSettingsMenu(btn){
      closeMenu();
      const m=document.createElement("div"); m.className="coxMenu coxSettingsMenu";
      const item=(label,fn)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxMenuItem"; b.textContent=label; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); fn(); closeMenu(); }); m.appendChild(b); };
      // Only items wired to a real Codex run-command id. YOLO mode / Chat preview header
      // were removed — their command ids are not in our bundled baseline, so they would be
      // dead buttons; better to not exist than to lie. (Re-add once we capture the ids.)
      item("Account & usage",()=>runCmd("settings"));
      item("Switch model",()=>runCmd("composer.openModelPicker"));
      item("Switch account",()=>runCmd("logOut"));
      item("Custom instructions",()=>runCmd("personalitySettings"));
      item("Color theme",()=>runCmd("switchTheme"));
      anchorMenu(m,btn);
    }
    // ---------- row hover actions ----------
    function archiveThread(t){
      // Toggle. Codex's own command (our history patch uses archive-conversation); post
      // both envelope shapes to maximise acceptance, plus an optimistic local move into/out
      // of the Archived section so OUR list updates at once — and it stays reversible.
      if(archived.has(t.id)){ archived.delete(t.id); coxPost("unarchive-conversation",{conversationId:t.id}); coxPost("unarchive-conversation",{params:{conversationId:t.id}}); }
      else { archived.add(t.id); coxPost("archive-conversation",{conversationId:t.id}); coxPost("archive-conversation",{params:{conversationId:t.id}}); }
      saveSet(ARCH_KEY,archived); render();
    }
    function rowAction(act,t,ev){
      if(act==="star"){ if(stars.has(t.id))stars.delete(t.id); else { stars.add(t.id); pins.delete(t.id); } saveSet(STAR_KEY,stars); saveSet(PIN_KEY,pins); render(); }
      else if(act==="pin"){ if(pins.has(t.id))pins.delete(t.id); else { pins.add(t.id); stars.delete(t.id); } saveSet(PIN_KEY,pins); saveSet(STAR_KEY,stars); render(); }
      else if(act==="color"){ showColorMenu(ev.clientX,ev.clientY,t); }
      else if(act==="archive"){ archiveThread(t); }
    }
    document.addEventListener("click",(e)=>{ if(!e.target.closest||!e.target.closest(".coxMenu")) closeMenu(); },true);
    document.addEventListener("keydown",(e)=>{ if(e.key==="Escape") closeMenu(); });

    function addRow(parent,t){
      // A div (role=button) — not a <button> — so the hover action <button>s can nest
      // without invalid button-in-button markup.
      const b=document.createElement("div"); b.className="coxRow"+(t.active?" act":""); b.setAttribute("role","button"); b.tabIndex=0; b.title=t.title;
      const st=statusOf(t);
      const dot=document.createElement("span"); dot.className="coxDot"; dot.style.background=DOT[st]||DOT.idle; dot.title=st;
      // Per-chat color tints the WHOLE row — a left bar plus a faint full-row fill that
      // survives :hover (inset box-shadow overlay paints above the background). Clearly
      // visible; the status dot is a separate signal and is intentionally NOT recolored.
      const col=colors.get(t.id); if(col){ const hx=colorOf(col)||col; b.style.boxShadow="inset 3px 0 0 "+hx+", inset 0 0 0 100px "+hx+"22"; }
      const tt=document.createElement("span"); tt.className="coxRowT"; tt.textContent=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,"");
      const acts=document.createElement("span"); acts.className="coxActs";
      const mk=(act,title,svg,on)=>{ const x=document.createElement("button"); x.type="button"; x.className="coxAct"+(on?" on":""); x.title=title; x.dataset.coxAct=act; x.innerHTML=svg; acts.appendChild(x); };
      const arch=archived.has(t.id);
      mk("star",isStarred(t)?"Unstar":"Star",IC.star,isStarred(t));
      mk("pin",isPinned(t)?"Unpin":"Pin",IC.pin,isPinned(t));
      mk("color","Set color",IC.dot,!!col);
      mk("archive",arch?"Unarchive":"Archive",IC.archive,arch);
      b.append(dot,tt,acts);
      rowMap.set(b,t);   // open + actions + right-click are routed by the delegated .coxList handlers
      parent.appendChild(b);
    }
    function addGroup(list,name,rows){
      if(!rows.length) return;
      const sec=document.createElement("section");
      const gb=document.createElement("button"); gb.type="button"; gb.className="coxGroupBtn"; gb.dataset.coxGroup=name;
      const nm=document.createElement("span"); nm.className="coxGroupName"; nm.textContent=name;
      gb.append(nm);   // collapse/expand routed by the delegated .coxList handler
      sec.appendChild(gb);
      if(groupState[name]!==false){ for(const r of rows) addRow(sec,r); }
      list.appendChild(sec);
    }
    const AGE_MS={1:36e5,2:864e5,3:6048e5,4:2592e6}; // 1h, 24h, 7d, 30d
    function applyFilter(rows){
      const f=filterState, types=f.types||[]; let out=rows;
      if(types.length){ out=out.filter((t)=>{ const st=statusOf(t); return types.some((k)=>k==="pinned"?isPinned(t):k==="starred"?isStarred(t):k==="running"?st==="running":k==="waiting"?st==="waiting":false); }); }
      if(f.age&&AGE_MS[f.age]){ const now=Date.now(),ms=AGE_MS[f.age]; out=out.filter((t)=>t.ts&&(now-t.ts)<=ms); }
      return out;
    }
    function render(){
      const side=ensureShell(); const list=side.querySelector(".coxList");
      const nativeRows=domThreads();
      let rows=currentRows(mergeThreads(nativeRows),nativeRows);   // filtered to the active workspace (native task rows or Codex's roots[0])
      const needle=search.toLowerCase();
      if(needle) rows=rows.filter((t)=>t.title.toLowerCase().includes(needle)||(t.project||"").toLowerCase().includes(needle));
      rows=applyFilter(rows);
      const fb=side.querySelector(".coxFilter"); if(fb) fb.classList.toggle("on",!!filterActive());
      // Archived chats (ours + any Codex flags) drop into their own section at the bottom,
      // like Codex's native "Archived" group — not removed.
      const isArch=(t)=>archived.has(t.id)||(t.raw&&t.raw.archived===true);
      const arch=rows.filter(isArch); rows=rows.filter((t)=>!isArch(t));
      list.textContent="";
      if(!rows.length&&!arch.length){ const e=document.createElement("div"); e.className="coxEmpty"; e.textContent=search?"No matching chats.":(filterActive()?"No chats match the filter.":"No chats found yet."); list.appendChild(e); return; }
      const pinned=rows.filter(isPinned), starred=rows.filter((t)=>!isPinned(t)&&isStarred(t)), rest=rows.filter((t)=>!isPinned(t)&&!isStarred(t));
      addGroup(list,"📌 Pinned",pinned);
      addGroup(list,"⭐ Starred",starred);
      const order=[],by=new Map(); for(const r of rest){ if(!by.has(r.project)){by.set(r.project,[]);order.push(r.project);} by.get(r.project).push(r); }
      // We filter to the current workspace, so every remaining chat is the same project
      // — a project header here just repeats the sidebar's own "Codex Orbit" title. List
      // them flat; only keep per-project headers if more than one project is present (the
      // blind-fallback case), where the label actually disambiguates.
      if(order.length<=1){ for(const r of rest) addRow(list,r); }
      else { for(const n of order) addGroup(list,n,by.get(n)); }
      addGroup(list,"Archived",arch);   // its own collapsible header at the bottom
    }

    // ---------- self-diagnostics: download a debug snapshot, no console copy/paste ----------
    window.codexOrbitDump=function(){
      const labels=(sel)=>[...document.querySelectorAll(sel)].map((b)=>b.getAttribute("aria-label")||b.getAttribute("title")||clean(b.textContent)).filter(Boolean);
      const anchors=[...document.querySelectorAll("a[href]")].map((a)=>a.getAttribute("href")).filter((h)=>h&&h[0]==="/").slice(0,40);
      const all=allThreads();
      const nativeEls=[...document.querySelectorAll(A.row)];
      const data={
        at:new Date().toISOString(),
        version:"0.5.23",
        location:{href:location.href,pathname:location.pathname,hash:location.hash,search:location.search},
        hostWorkspace:hostWorkspace(),
        hostChannel:!!(window.__codexOrbitVsApi&&window.__codexOrbitVsApi.postMessage)||(typeof window.__codexPostMessage==="function"),
        activeRoots:activeRoots,
        currentProject:(window.__codexOrbitCurrentProject||null),
        curRoot:curRoot, curLabel:curLabel,
        activeThread:(all.find((t)=>t.active)||{}).title||null,
        threadCount:dataThreads.length,
        filteredCount:currentRows(all,domThreads()).length,
        projects:[...new Set(all.map((t)=>t.project))],
        sampleThreads:all.slice(0,40).map((t)=>({id:t.id,title:t.title,project:t.project,cwd:t.cwd,hostId:t.hostId,kind:t.kind,active:t.active,source:t.source,hasEl:!!t.element})),
        nativeRowCount:nativeEls.length,
        nativeRows:nativeEls.slice(0,12).map((el)=>({id:el.getAttribute(A.id),title:clean(el.getAttribute(A.title)||el.textContent),hostId:el.getAttribute(A.hostId),kind:el.getAttribute(A.kind),active:el.getAttribute(A.active)})),
        pins:[...pins], stars:[...stars],
        routeAnchors:anchors,
        sampleRaw:dataThreads.slice(0,6).map((t)=>t.raw),
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
      // Re-render only on REAL Codex changes. render() rewrites our own .coxList,
      // which lives inside documentElement — observing the whole subtree made render
      // re-trigger itself every 80ms forever (a storm that rebuilt the list ~12x/s,
      // shredding clicks and pegging the CPU). Skip mutations inside our own shell.
      new MutationObserver((muts)=>{
        if(interacting) return;
        for(const m of muts){ if(shell&&shell.contains(m.target)) continue; scheduleRender(); break; }
      }).observe(document.documentElement,{childList:true,subtree:true});
      window.addEventListener("focus",()=>scheduleRender());
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
    expose_native_openers(wv)
    expose_host_channel(wv)
    inject_workspace_meta(ext)
    marker = {"tool": "Codex Orbit", "patcherVersion": patcher_version, "target": DEFAULT_MARKETPLACE_ITEM,
              "targetVersion": json.loads((ext / 'package.json').read_text(encoding='utf-8')).get('version'),
              "patchedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "mode": "sidebar-only"}
    (ext / "codex-orbit-patch.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    log("Wrote codex-orbit-patch.json marker")


def expose_native_openers(wv):
    """Expose Codex's real row navigation closures so Orbit can route without
    guessing URL shapes that drift between Codex builds."""
    local_old_anchor = "let St=Re??void 0,Ct;"
    local_new_anchor = "let At=Je??void 0,jt;"
    remote_old_anchor = "}else P=t[4],ge=t[5],F=t[6];let I="
    remote_new_anchor = "}else F=t[4],R=t[5],z=t[6];let xe="
    local_old_bridge = (
        "try{"
        "(window.__codexOrbitLocalOpeners||(window.__codexOrbitLocalOpeners=new Map())).set(String(n),()=>je(n,r));"
        "window.__codexOrbitOpenThreadById=function(id){"
        "try{let f=window.__codexOrbitLocalOpeners&&window.__codexOrbitLocalOpeners.get(String(id));if(f){f();return true}}catch{}"
        "try{let f=window.__codexOrbitRemoteOpeners&&window.__codexOrbitRemoteOpeners.get(String(id));if(f){f();return true}}catch{}"
        "return false};"
        "}catch{}"
    )
    local_new_bridge = (
        "try{"
        "(window.__codexOrbitLocalOpeners||(window.__codexOrbitLocalOpeners=new Map())).set(String(n),()=>{g?.();Ve(n,i)});"
        "window.__codexOrbitOpenThreadById=function(id){"
        "try{let f=window.__codexOrbitLocalOpeners&&window.__codexOrbitLocalOpeners.get(String(id));if(f){f();return true}}catch{}"
        "try{let f=window.__codexOrbitRemoteOpeners&&window.__codexOrbitRemoteOpeners.get(String(id));if(f){f();return true}}catch{}"
        "return false};"
        "}catch{}"
    )
    remote_old_bridge = (
        "}else P=t[4],ge=t[5],F=t[6];"
        "try{"
        "(window.__codexOrbitRemoteOpeners||(window.__codexOrbitRemoteOpeners=new Map())).set(String(P),ge);"
        "window.__codexOrbitOpenThreadById=window.__codexOrbitOpenThreadById||function(id){"
        "try{let f=window.__codexOrbitLocalOpeners&&window.__codexOrbitLocalOpeners.get(String(id));if(f){f();return true}}catch{}"
        "try{let f=window.__codexOrbitRemoteOpeners&&window.__codexOrbitRemoteOpeners.get(String(id));if(f){f();return true}}catch{}"
        "return false};"
        "}catch{}let I="
    )
    remote_new_bridge = (
        "}else F=t[4],R=t[5],z=t[6];"
        "try{"
        "(window.__codexOrbitRemoteOpeners||(window.__codexOrbitRemoteOpeners=new Map())).set(String(F),R);"
        "window.__codexOrbitOpenThreadById=window.__codexOrbitOpenThreadById||function(id){"
        "try{let f=window.__codexOrbitLocalOpeners&&window.__codexOrbitLocalOpeners.get(String(id));if(f){f();return true}}catch{}"
        "try{let f=window.__codexOrbitRemoteOpeners&&window.__codexOrbitRemoteOpeners.get(String(id));if(f){f();return true}}catch{}"
        "return false};"
        "}catch{}let xe="
    )
    patched = []
    for f in wv.glob("*.js"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        changed = False
        if local_old_anchor in text and "(window.__codexOrbitLocalOpeners||" not in text:
            text = text.replace(local_old_anchor, local_old_bridge + local_old_anchor, 1)
            changed = True
        if local_new_anchor in text and "(window.__codexOrbitLocalOpeners||" not in text:
            text = text.replace(local_new_anchor, local_new_bridge + local_new_anchor, 1)
            changed = True
        if remote_old_anchor in text and "(window.__codexOrbitRemoteOpeners||" not in text:
            text = text.replace(remote_old_anchor, remote_old_bridge, 1)
            changed = True
        if remote_new_anchor in text and "(window.__codexOrbitRemoteOpeners||" not in text:
            text = text.replace(remote_new_anchor, remote_new_bridge, 1)
            changed = True
        if changed:
            f.write_text(text, encoding="utf-8", newline="")
            patched.append(f.name)
    if patched:
        log(f"Exposed native Codex row openers in {', '.join(patched)}")
    else:
        log("Native row opener anchors not found; Orbit will use DOM/route fallbacks")


def expose_host_channel(wv):
    """Tee Codex's single acquireVsCodeApi() instance into window.__codexOrbitVsApi so the
    injected sidebar can post the SAME host messages Codex's own code posts (e.g.
    archive-conversation, run-command). acquireVsCodeApi() may be called only ONCE per
    webview and Codex already calls it, so we WRAP its existing call site to capture the
    instance into a global — never a second call (which would throw)."""
    call = "acquireVsCodeApi()"
    wrap = "(window.__codexOrbitVsApi=acquireVsCodeApi())"
    for f in wv.glob("*.js"):
        if f.name.endswith(".map"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "__codexOrbitVsApi" in text:
            log("Host channel already exposed")
            return True
        if call in text:
            f.write_text(text.replace(call, wrap, 1), encoding="utf-8", newline="")
            log(f"Exposed host channel (window.__codexOrbitVsApi) in {f.name}")
            return True
    log("acquireVsCodeApi() not found; host channel NOT exposed — archive/settings commands will no-op")
    return False


# Host-side single source of truth. Anchored on the (semantic, stable) method name
# webviewMetaTags — NOT on a minified local — so it survives Codex churn better than
# the webview opener anchors. `Oe` (vscode alias) and `pl` (the HTML escaper) live in
# the same class/module scope and are confirmed present for this Codex baseline; if a
# future Codex renames them the try/catch makes the stamp a harmless no-op (the host
# bundle still parses; the webview falls back to its URL/RPC/DOM heuristics).
HOST_META_ANCHOR = "webviewMetaTags(e){let r=[],n=this.findPanelByWebview(e);"
HOST_META_SUFFIX = (
    'try{var __coxWF=Oe.workspace.workspaceFolders;'
    'r.push(`<meta name="codex-orbit-workspace" content="${pl(JSON.stringify({'
    'r:(__coxWF&&__coxWF[0]&&__coxWF[0].uri&&__coxWF[0].uri.fsPath)||"",'
    'l:(__coxWF&&__coxWF[0]&&__coxWF[0].name)||""}))}">`)}catch(__coxE){}'
)


def inject_workspace_meta(ext):
    """Stamp the REAL VS Code workspace into the webview HTML so the sidebar never has
    to guess which project is "home". The extension HOST knows it for certain
    (Oe.workspace.workspaceFolders); the webview's task-list view does not (no open
    chat in the URL, the active-workspace-roots reply races a window-message listener).
    So we emit <meta name="codex-orbit-workspace" content='{"r":path,"l":name}'> from
    webviewMetaTags(), which BOTH the production and development HTML generators call —
    present on every view, before any chat opens. CSP-safe: the webview CSP is
    `script-src ${cspSource}` with no inline/nonce, so an injected <script> would be
    blocked, but a <meta> tag is fine and the sidebar reads it via getAttribute."""
    try:
        main_rel = (json.loads((ext / "package.json").read_text(encoding="utf-8")).get("main") or "out/extension.js")
    except Exception:
        main_rel = "out/extension.js"
    host = ext / main_rel.lstrip("./")
    if not host.exists():
        for cand in ("out/extension.js", "dist/extension.js", "extension.js"):
            if (ext / cand).exists():
                host = ext / cand; break
    if not host.exists():
        log(f"Host bundle not found ({main_rel}); workspace <meta> NOT injected — sidebar uses webview-side fallbacks")
        return False
    text = host.read_text(encoding="utf-8", errors="ignore")
    if "codex-orbit-workspace" in text:
        log("Workspace <meta> already present in host bundle")
        return True
    if HOST_META_ANCHOR not in text:
        log("webviewMetaTags anchor NOT found in host bundle (Codex refactored?); workspace <meta> NOT injected — re-anchor needed")
        return False
    host.write_text(text.replace(HOST_META_ANCHOR, HOST_META_ANCHOR + HOST_META_SUFFIX, 1), encoding="utf-8", newline="")
    log(f"Injected workspace <meta> into host bundle {host.name} — single source of truth for current-workspace filtering")
    return True


def verify(ext_dir):
    node = shutil.which("node")
    f = next((p for p in (ext_dir / "webview" / "assets").glob(HELPER_PREFIX + "*-codexpatch.js")), None)
    if node and f:
        # The helper is an ES module (import/export). `node --check <file>` on such
        # a file auto-detects ESM but uses a LENIENT parser that silently accepts an
        # orphaned block-comment close (`*/` with no matching `/*`) — exit 0 — yet the
        # webview's V8 module loader rejects it ("Uncaught SyntaxError: Unexpected
        # token '*'"), so a broken patch ships invisibly. Forcing module mode via
        # stdin uses the SAME strict parser the webview runs, catching that whole
        # class before we ever write the VSIX. (This is how the blade now catches it.)
        src = f.read_text(encoding="utf-8", errors="ignore")
        # encoding="utf-8" is required: the sidebar JS contains emoji (⭐ 📌 🗑 🪲);
        # the Windows default (cp1252) cannot encode them on the stdin pipe.
        r = subprocess.run([node, "--input-type=module", "--check", "-"],
                           input=src, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            tail = (r.stderr or "").strip().splitlines()
            detail = " | ".join(tail[-4:]) if tail else "?"
            raise RuntimeError(f"Patched JS invalid ({f.name}): {detail}")
        log("JS syntax check passed (strict module parse)")
    else:
        log("node not found or helper missing — skipping JS syntax check")
    # Also strict-check the patched HOST bundle. A broken host bundle bricks the ENTIRE
    # Codex extension (not just the sidebar), so this is the higher-stakes check; and we
    # confirm the workspace <meta> stamp actually landed so a missed anchor is visible
    # in the log instead of silently shipping the old "shows all projects" behaviour.
    host = next((ext_dir / c for c in ("out/extension.js", "dist/extension.js", "extension.js") if (ext_dir / c).exists()), None)
    if node and host:
        rh = subprocess.run([node, "--check", str(host)], capture_output=True, text=True, encoding="utf-8")
        if rh.returncode != 0:
            tail = (rh.stderr or "").strip().splitlines()
            raise RuntimeError(f"Patched host bundle invalid ({host.name}): {' | '.join(tail[-4:]) if tail else '?'}")
        if "codex-orbit-workspace" in host.read_text(encoding="utf-8", errors="ignore"):
            log("Host bundle syntax check passed; workspace <meta> stamp confirmed present")
        else:
            log("Host bundle syntax check passed; NOTE workspace <meta> stamp ABSENT (anchor missed — filter will use webview fallbacks)")


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
