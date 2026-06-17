#!/usr/bin/env python
"""Codex Orbit patcher — v0.5.x, REBUILT FROM SCRATCH.

Injects ONE self-contained "Codex Orbit" sidebar into Codex's webview. The sidebar
gets its chat list by INTERCEPTING Codex's own data transport (the thread list the
host pushes to the webview via messages), filters to the CURRENT project, and
renders it with search, pinned/starred sections (right-click to toggle, stored
locally), real SVG icons, a full-width New Task button, drag-to-resize and a
collapse that shrinks to a thin button rail. A DOM scrape of Codex's stable
`data-app-action-sidebar-*` rows is kept as a fallback + to enable click-to-open.
`window.codexOrbitDump()` captures a debug JSON so issues can be diagnosed
without asking the user to read the console.

  * One appended IIFE — no surgery on minified Codex code, so it does NOT drift on
    Codex updates. Depends only on the wire data shape + stable data-attributes.
  * `copy_patched_assets` keeps that name: the Orbit wrapper's OTA loader requires
    that marker string to accept a patcher over the air.
"""
from __future__ import annotations
import argparse, datetime as dt, json, platform, re, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path

__version__ = "0.5.43"
# Release channel that ships INSIDE every patched build. The Orbit launcher reads it
# back as `ccPatchChannel` from the patched webview (installed tag), and
# tools/archive_patcher.py mirrors it into the rollback manifest's `channel` field
# (list/available tag). DEFAULT experimental — only `tools/ship.py --stable` flips it.
# Format is load-bearing: tools/ship.py and archive_patcher.py read it via the regex
# ^ORBIT_CHANNEL:\s*str\s*=\s*"([^"]+)" — keep the `: str =` shape.
ORBIT_CHANNEL: str = "experimental"
DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
MARKETPLACE_QUERY_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
LOG_PATH = None
# Injection host candidates, in priority order. app-main-* is the Vite app entry —
# present and loaded in every Codex build, referenced by the webview HTML directly,
# so it is a stable in-place host. window-app-action-helpers-* was the old host but
# Codex REMOVED it in build 5609 (which hard-bricked the patch), so it is kept only
# as a fallback for older baselines. The first prefix that resolves to a real chunk wins.
HELPER_PREFIXES = ["app-main-", "window-app-action-helpers-"]

# Toggleable patches (the wrapper's PATCHES section). Each id matches a userFacing
# module in patch_modules/catalog.json. The wrapper persists the user's unchecked set
# and passes `--disable id1,id2`; we resolve that into ENABLED_FEATURES and gate the
# matching injection. Unknown ids are ignored leniently (a newer wrapper sending an id
# an older patcher doesn't know just no-ops). Non-gateable parts always apply.
GATEABLE_FEATURES = {"workspace-filter", "status-dots"}
ENABLED_FEATURES = None  # None = apply everything; otherwise a set of enabled ids


def feature_on(fid):
    """True if feature `fid` should be applied. Non-gateable ids are always on."""
    if ENABLED_FEATURES is None or fid not in GATEABLE_FEATURES:
        return True
    return fid in ENABLED_FEATURES

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
      usage:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round"><circle cx="8" cy="8" r="5.4" opacity=".24"/><path d="M8 2.6a5.4 5.4 0 0 1 5.4 5.4"/></svg>',
      star:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M8 2.3l1.7 3.5 3.8.5-2.8 2.7.7 3.8L8 11.3 4.6 12.8l.7-3.8L2.5 6.3l3.8-.5z"/></svg>',
      pin:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"><path d="M9.6 2.4l4 4-2.1.6-2.1 2.1-.4 2.9-3.9-3.9 2.9-.4 2.1-2.1z"/><line x1="5.1" y1="10.9" x2="2.4" y2="13.6"/></svg>',
      archive:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"><rect x="2.4" y="3" width="11.2" height="3" rx="1"/><path d="M3.5 6.3v6.2a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V6.3"/><line x1="6.4" y1="8.9" x2="9.6" y2="8.9"/></svg>',
      dot:'<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="4.4" fill="currentColor"/></svg>'
    };

    let shell=null, collapsed=false, search="", groupState=Object.create(null), dataThreads=[], routeThreads=new Map(), pins=new Set(), stars=new Set(), activeRoots=[], colors=new Map(), archived=new Set(), curOpenUuid="";
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
    let liveStatus=new Map();   // uuid -> running|waiting|failed, fed by the status hook
    let usageStatus=null, usageRows=[], usageLabels=[], usageUpdatedAt=0, accountInfo={};
    // Codex ids are UUIDs; the status hook's conversationId and the wire row id can carry
    // different prefixes (host:/local:/...), so match on the embedded UUID to bridge them.
    function uuidOf(s){ const m=String(s||"").match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i); return m?m[0].toLowerCase():""; }
    function statusOf(t){
      const ls=liveStatus.get(uuidOf(t&&t.id)||String(t&&t.id))||liveStatus.get(String(t&&t.id))||liveStatus.get(String(t&&t.__id));
      if(ls) return ls;
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
    const DOT={running:"var(--vscode-charts-blue,#3b82f6)",waiting:"var(--vscode-charts-orange,#f5a524)",failed:"var(--vscode-charts-red,#e5484d)",review:"var(--vscode-charts-green,#30a46c)",idle:"#565656"};
    // Relative time for the row's second line (Codex shows "12 min ago", "19 hrs ago", ...).
    function relTime(ts){ if(!ts) return ""; const s=Math.max(0,(Date.now()-ts)/1000); if(s<45) return "just now"; const m=Math.round(s/60); if(m<60) return m+" min ago"; const h=Math.round(m/60); if(h<24) return h+(h===1?" hr ago":" hrs ago"); const d=Math.round(h/24); if(d<30) return d+(d===1?" day ago":" days ago"); const mo=Math.round(d/30); if(mo<12) return mo+(mo===1?" mo ago":" mos ago"); return Math.round(d/365)+" yr ago"; }
    function titleFromState(state){
      try{
        const direct=pick(state,["title","name","summary","label"]);
        if(typeof direct==="string"&&clean(direct)) return clean(direct);
        let turns=state&&state.turns; if(turns&&typeof turns.values==="function"&&!Array.isArray(turns)) turns=[...turns.values()];
        if(Array.isArray(turns)){
          for(const turn of turns){
            const text=pick(turn||{},["text","prompt","message","content"]);
            if(typeof text==="string"&&clean(text)) return clean(text).slice(0,80);
            const items=(turn&&turn.items)||(turn&&turn.messages);
            if(Array.isArray(items)){
              for(const it of items){ const tx=pick(it||{},["text","content","message"]); if(typeof tx==="string"&&clean(tx)) return clean(tx).slice(0,80); }
            }
          }
        }
      }catch{}
      return "";
    }
    // Second line: live status text when active, else the relative time.
    function subText(t,st){ if(st==="running") return "Thinking…"; if(st==="waiting") return "Question"; if(st==="failed") return "Failed"; return relTime(t.ts); }
    // Derive a chat state from Codex's conversation-state object (the shape the status hook
    // receives) — matches Codex's own row logic: systemError/turn failed => failed; active +
    // waitingOnApproval/UserInput (or a pending approval/input request) => waiting; active /
    // turn inProgress => running; else idle.
    function deriveStatus(s){
      try{
        if(!s||typeof s!=="object") return null;
        const rt=s.threadRuntimeStatus;
        if(rt&&rt.type==="systemError") return "failed";
        if(rt&&rt.type==="active"){ const f=rt.activeFlags||[]; return (f.indexOf&&(f.indexOf("waitingOnApproval")>=0||f.indexOf("waitingOnUserInput")>=0))?"waiting":"running"; }
        let turns=s.turns; if(turns&&typeof turns.values==="function"&&!Array.isArray(turns)) turns=[...turns.values()];
        const lt=turns&&turns.length&&turns[turns.length-1];
        if(lt&&lt.status==="inProgress") return "running";
        if(lt&&lt.status==="failed") return "failed";
        let reqs=s.requests; if(reqs&&typeof reqs.values==="function"&&!Array.isArray(reqs)) reqs=[...reqs.values()];
        if(reqs&&reqs.length&&reqs.some&&reqs.some((r)=>r&&typeof r.method==="string"&&/requestApproval|requestUserInput|requestOptionPicker/.test(r.method))) return "waiting";
        if(rt&&rt.type==="idle") return "idle";
      }catch{}
      return "idle";
    }
    // The patcher tees Codex's updateConversationState(id,newState) into this hook (every
    // status/turn/approval change funnels through it). We keep a per-chat live state that
    // statusOf() consults first, and re-render on change.
    try{ window.__codexOrbitStatusHook=function(id,state){ try{ const k=uuidOf(id)||String(id),s=deriveStatus(state); if(s&&s!=="idle"){ const made=rememberStatusThread(id,state,s); if(liveStatus.get(k)!==s){ liveStatus.set(k,s); scheduleRender(); } else if(made) scheduleRender(); } else if(liveStatus.has(k)){ liveStatus.delete(k); scheduleRender(); } }catch{} }; }catch{}

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
    function setUsageStatus(raw){
      if(raw==null) return;
      usageStatus=raw; usageUpdatedAt=Date.now();
      try{ window.__codexOrbitUsageStatus=raw; }catch{}
      updateUsageButton();
    }
    function setUsageLabels(labels){
      if(!Array.isArray(labels)) return;
      usageLabels=labels; usageUpdatedAt=Date.now();
      updateUsageButton();
    }
    function setUsageRows(rows){
      if(!Array.isArray(rows)) return;
      usageRows=rows; usageUpdatedAt=Date.now();
      try{ window.__codexOrbitUsageRows=rows; }catch{}
      updateUsageButton();
    }
    function ingestUsage(payload){
      let found=null, labels=null;
      (function walk(o,depth){
        if(found&&labels) return;
        if(!o||typeof o!=="object"||depth>7) return;
        if(o.rateLimitStatus!=null||o.rate_limit_status!=null) found=o.rateLimitStatus||o.rate_limit_status;
        if(Array.isArray(o.usageRows)||Array.isArray(o.usage_rows)) setUsageRows(o.usageRows||o.usage_rows);
        if(Array.isArray(o.usageLimits)||Array.isArray(o.usage_limits)) labels=o.usageLimits||o.usage_limits;
        if(Array.isArray(o)){ for(const x of o){ walk(x,depth+1); if(found&&labels) return; } return; }
        for(const k in o){ try{ walk(o[k],depth+1); }catch{} if(found&&labels) return; }
      })(payload,0);
      if(found!=null) setUsageStatus(found);
      if(labels!=null) setUsageLabels(labels);
    }
    function ingestAccount(payload){
      let changed=false;
      const safe=(v)=>{ const s=clean(v); if(!s||s.length>180) return ""; if(/^eyJ|Bearer\s+/i.test(s)) return ""; return s; };
      const set=(k,v)=>{ const s=safe(v); if(s&&accountInfo[k]!==s){ accountInfo=Object.assign({},accountInfo,{[k]:s}); changed=true; } };
      (function walk(o,depth){
        if(!o||typeof o!=="object"||depth>7) return;
        if(Array.isArray(o)){ for(const x of o) walk(x,depth+1); return; }
        const email=safe(o.email||o.userEmail||o.user_email||o.accountEmail||o.account_email);
        if(email&&email.indexOf("@")>0) set("email",email);
        set("authMethod",o.authMethod||o.auth_method||o.authProvider||o.provider);
        set("organization",o.organization||o.organizationName||o.orgName||o.org_name||o.workspaceName||o.teamName||o.accountName);
        set("plan",o.plan||o.planName||o.plan_name||o.subscriptionPlan||o.subscription_plan||o.sku||o.skuName||o.serviceTier||o.service_tier);
        set("accountId",o.accountId||o.account_id||o.chatgpt_account_id);
        for(const k in o){ try{ walk(o[k],depth+1); }catch{} }
      })(payload,0);
      if(changed) try{ window.__codexOrbitAccountInfo=accountInfo; }catch{}
    }
    // Observe-only: host->webview RPC responses arrive as window "message" events.
    window.addEventListener("message",(e)=>{ try{ ingest(e.data); }catch{} try{ ingestRoots(e.data); }catch{} try{ ingestUsage(e.data); }catch{} try{ ingestAccount(e.data); }catch{} },true);
    try{
      window.addEventListener("codex-orbit-rate-limit",(e)=>setUsageStatus(e.detail),true);
      window.addEventListener("codex-orbit-usage-limits",(e)=>setUsageLabels(e.detail),true);
      window.addEventListener("codex-orbit-usage-rows",(e)=>setUsageRows(e.detail),true);
      if(window.__codexOrbitRateLimitStatus) setUsageStatus(window.__codexOrbitRateLimitStatus);
      if(Array.isArray(window.__codexOrbitUsageRows)) setUsageRows(window.__codexOrbitUsageRows);
      if(window.__codexOrbitUsageLimits) setUsageLabels(window.__codexOrbitUsageLimits);
    }catch{}

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
    function allThreads(){ const dom=domThreads(); return withRouteThreads(mergeThreads(dom),dom); }
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
    function threadMatchesId(t,id){
      const u=uuidOf(id);
      return !!t&&(String(t.id)===String(id)||String(t.__id)===String(id)||(!!u&&(uuidOf(t.id)===u||uuidOf(t.__id)===u)));
    }
    function currentRouteKind(){
      const p=String(location.pathname||"");
      if(/\/remote\//.test(p)) return "remote";
      if(/\/worktree-init/i.test(p)) return "pending-worktree";
      return "local";
    }
    function rememberOpenThread(rows,nativeRows){
      const oid=openThreadId();
      if(!oid) return null;
      const known=(rows||[]).find((t)=>threadMatchesId(t,oid))||(nativeRows||[]).find((t)=>threadMatchesId(t,oid));
      if(known){ routeThreads.delete(oid); return known; }
      const hw=hostWorkspace();
      if(hw) setCurrent(hw.r,hw.l);
      const old=routeThreads.get(oid)||{};
      const activeNative=(nativeRows||[]).find((t)=>t.current||t.active);
      const root=(hw&&hw.r)||curRoot||"";
      const label=(hw&&hw.l)||curLabel||lastSeg(root)||"Sessions";
      const kind=currentRouteKind();
      const t={
        ...old,
        __id:oid,
        id:oid,
        title:clean(activeNative&&activeNative.title)||old.title||"Current task",
        project:clean(label)||"Sessions",
        cwd:root,
        hostId:kind==="remote"?"remote":"local",
        kind,
        pinned:false,
        starred:false,
        active:true,
        current:true,
        ts:old.ts||Date.now(),
        source:"route",
        raw:{synthetic:true}
      };
      routeThreads.set(oid,t);
      return t;
    }
    function rememberStatusThread(id,state,st){
      const sid=String(id||""); if(!sid) return false;
      const hw=hostWorkspace(); if(hw) setCurrent(hw.r,hw.l);
      const old=routeThreads.get(sid)||routeThreads.get(uuidOf(sid))||{};
      const root=(hw&&hw.r)||curRoot||"";
      const label=(hw&&hw.l)||curLabel||lastSeg(root)||"Sessions";
      const oid=openThreadId(), sameOpen=!oid||threadMatchesId({id:sid,__id:sid},oid);
      const kind=sameOpen?currentRouteKind():(old.kind||"local");
      const t={
        ...old,
        __id:sid,
        id:sid,
        title:titleFromState(state)||old.title||"Current task",
        project:clean(label)||old.project||"Sessions",
        cwd:root||old.cwd||"",
        hostId:kind==="remote"?"remote":"local",
        kind,
        pinned:false,
        starred:false,
        active:sameOpen,
        current:sameOpen,
        ts:old.ts||Date.now(),
        source:"status",
        raw:{synthetic:true,status:st}
      };
      routeThreads.set(sid,t);
      return !old.id;
    }
    function withRouteThreads(rows,nativeRows){
      rememberOpenThread(rows,nativeRows);
      if(!routeThreads.size) return rows;
      const out=rows.slice();
      for(const t of routeThreads.values()){ if(!out.some((r)=>threadMatchesId(r,t.id))) out.unshift(t); }
      return out;
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
    function nativeTaskTitle(raw){
      let s=titleKey(raw);
      s=s.replace(/\s*(?:just now|\d+\s*(?:s|sec|secs|m|min|mins|h|hr|hrs|d|day|days|mo|mos|yr|yrs)(?:\s+ago)?)$/i,"").trim();
      return threadTitleKey(s);
    }
    function filterNativeTaskLists(scopedRows){
      try{
        const allowed=new Set((scopedRows||[]).map((t)=>threadTitleKey(t.title)).filter(Boolean));
        if(!allowed.size) return;
        const heads=[...document.querySelectorAll("div,section,h1,h2,h3,span,p")].filter((el)=>!el.closest(".coxSidebar")&&clean(el.textContent)==="Tasks");
        for(const h of heads){
          let root=h.parentElement, panel=null;
          for(let i=0;i<6&&root&&root!==document.body;i++,root=root.parentElement){
            const tx=clean(root.textContent);
            if(/View all\s*\(/i.test(tx)&&tx.length<10000){ panel=root; break; }
          }
          if(!panel) continue;
          const viewAlls=[...panel.querySelectorAll("a,button,[role='button'],[tabindex],div,span")].filter((el)=>{
            if(el.closest(".coxSidebar")) return false;
            const pos=h.compareDocumentPosition(el);
            if(!(pos&Node.DOCUMENT_POSITION_FOLLOWING)) return false;
            const raw=clean(el.textContent);
            return /^View all\b/i.test(raw)&&raw.length<80;
          });
          for(const el of viewAlls){
            const target=el.closest("a,button,[role='button'],[tabindex]")||el;
            if(target&&target!==panel) target.classList.add("coxNativeTaskHidden");
          }
          const candidates=[...panel.querySelectorAll("a,button,[role='button'],[tabindex]")].filter((el)=>{
            if(el.closest(".coxSidebar")) return false;
            const pos=h.compareDocumentPosition(el);
            if(!(pos&Node.DOCUMENT_POSITION_FOLLOWING)) return false;
            const raw=clean(el.textContent);
            if(!raw||raw==="Tasks"||/^View all\b/i.test(raw)||/^New\b/i.test(raw)||raw.length>180) return false;
            return !!nativeTaskTitle(raw);
          });
          for(const el of candidates){
            const key=nativeTaskTitle(el.textContent);
            el.classList.toggle("coxNativeTaskHidden",!!key&&!allowed.has(key));
          }
        }
      }catch{}
    }

    function ensureStyle(){
      if(document.getElementById("codexOrbitStyleV4")) return;
      const s=document.createElement("style"); s.id="codexOrbitStyleV4";
      s.textContent=`
:root{--cox-open:${OPEN_WIDTH}px;--cox-rail:46px}
.coxSidebar{position:fixed;top:0;right:0;bottom:0;width:var(--cox-open);z-index:45;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);font-family:var(--vscode-font-family,system-ui,sans-serif);font-size:12px;transition:width .14s ease}
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
.coxGroupBtn{width:100%;min-height:24px;display:flex;align-items:center;gap:4px;border:0;background:transparent;color:var(--vscode-descriptionForeground,#9a9a9a);font-size:11.5px;font-weight:600;cursor:pointer;margin-top:6px;padding:0 2px}
.coxGroupBtn:hover{color:#ddd}
.coxGroupChev{display:inline-flex;width:13px;flex:0 0 13px;color:var(--vscode-descriptionForeground,#8a8a8a)}
.coxGroupChev svg{width:11px;height:11px;transform:rotate(90deg);transition:transform .12s}
.coxGroupBtn.coll .coxGroupChev svg{transform:rotate(0deg)}
.coxGroupName{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
.coxCount{flex:0 0 auto;margin-left:6px;min-width:18px;height:16px;padding:0 6px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;border-radius:8px;background:var(--vscode-badge-background,rgba(255,255,255,.12));color:var(--vscode-badge-foreground,#ccc)}
.coxRow{width:100%;min-height:34px;display:flex;align-items:center;gap:8px;border:0;border-radius:5px;background:transparent;color:var(--vscode-foreground,#d4d4d4);cursor:pointer;padding:5px 8px;text-align:left}
.coxRow:hover{background:var(--vscode-list-hoverBackground,rgba(255,255,255,.07))}
.coxRow.act{background:var(--vscode-list-activeSelectionBackground,#37373d);color:#fff}
.coxRowMain{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px;overflow:hidden}
.coxRowT{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxRowSub{font-size:10.5px;line-height:1.25;color:var(--vscode-descriptionForeground,#8a8a8a);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxRowSub.waiting{color:var(--vscode-charts-orange,#f5a524)}
.coxRowSub.failed{color:var(--vscode-charts-red,#e5484d)}
.coxRowSub.running{color:var(--vscode-charts-blue,#6ea8ff)}
.coxSpin{width:10px;height:10px;flex:0 0 10px;border-radius:50%;border:1.6px solid rgba(255,255,255,.16);border-top-color:var(--vscode-charts-blue,#4d8dff);animation:coxspin .7s linear infinite;align-self:flex-start;margin-top:4px}
@keyframes coxspin{to{transform:rotate(360deg)}}
.coxUsage{color:var(--vscode-charts-yellow,#f5d90a)}
.coxUsage.loading svg{animation:coxspin .9s linear infinite}
.coxUsage.hasUsage{color:var(--vscode-charts-yellow,#f5d90a)}
.coxUsagePanel{width:276px;padding:8px}
.coxUsageHead{height:22px;display:flex;align-items:center;justify-content:space-between;margin:0 2px 7px;color:var(--vscode-descriptionForeground,#a8a8a8);font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em}
.coxUsageFresh{border:0;background:transparent;color:var(--vscode-icon-foreground,#b8b8b8);width:22px;height:22px;border-radius:5px;cursor:pointer;padding:0}
.coxUsageFresh:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:var(--vscode-foreground,#fff)}
.coxUsageGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.coxGauge{min-width:0;text-align:center;color:var(--vscode-foreground,#ddd)}
.coxGaugeRing{width:58px;height:58px;margin:0 auto 6px;border-radius:50%;position:relative;display:grid;place-items:center;background:conic-gradient(var(--cox-gauge-color,#30a46c) var(--cox-gauge-pct,0%),rgba(255,255,255,.07) 0)}
.coxGaugeRing::after{content:"";position:absolute;inset:7px;border-radius:50%;background:var(--vscode-menu-background,#252526)}
.coxGaugePct{position:relative;z-index:1;font-size:14px;font-weight:750;color:var(--cox-gauge-color,#30a46c)}
.coxGaugeTitle{font-size:11.5px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxGaugeSub{margin-top:1px;font-size:10.5px;color:var(--vscode-descriptionForeground,#969696);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coxUsageRows{margin-top:9px;border-top:1px solid var(--vscode-menu-separatorBackground,#3f3f46);padding-top:6px}
.coxUsageRow{display:grid;grid-template-columns:1fr auto;gap:8px;font-size:11.5px;line-height:1.45;color:var(--vscode-descriptionForeground,#a8a8a8)}
.coxUsageRow strong{font-weight:650;color:var(--vscode-foreground,#ddd)}
.coxUsageLoading{display:flex;align-items:center;gap:8px;padding:8px 4px 10px;color:var(--vscode-descriptionForeground,#a8a8a8);font-size:12px}
.coxUsageLoading .coxSpin{margin:0;align-self:center;border-top-color:var(--vscode-charts-yellow,#f5d90a)}
.coxAccountDialog{width:min(500px,calc(100vw - 36px));max-height:min(760px,calc(100vh - 36px));padding:0;overflow:auto}
.coxAccountHead{height:46px;display:flex;align-items:center;gap:12px;padding:0 14px 0 16px;border-bottom:1px solid var(--vscode-widget-border,var(--vscode-menu-border,#454545))}
.coxAccountHead .coxDialogTitle{margin:0;flex:1}
.coxAccountBody{padding:14px 16px 16px}
.coxAcctSection{margin:0 0 20px}
.coxAcctSection:last-child{margin-bottom:0}
.coxAcctSectionTitle{margin:0 0 10px;color:var(--vscode-descriptionForeground,#a8a8a8);font-size:10.5px;font-weight:750;letter-spacing:.06em;text-transform:uppercase}
.coxAcctRow{display:grid;grid-template-columns:130px minmax(0,1fr);gap:12px;align-items:start;min-height:26px;font-size:12.5px}
.coxAcctRow span{color:var(--vscode-descriptionForeground,#a8a8a8)}
.coxAcctRow strong{min-width:0;text-align:right;font-weight:500;color:var(--vscode-foreground,#e8e8e8);overflow:hidden;text-overflow:ellipsis}
.coxUsageGridFull{margin-top:4px;gap:14px}
.coxAccountDialog .coxGaugeRing{width:64px;height:64px}
.coxUsageNote{margin:9px 0 0;color:var(--vscode-descriptionForeground,#9f9f9f);font-size:12px;line-height:1.45}
.coxAccountActions{justify-content:flex-start;margin-top:10px}
.coxColorRow{display:flex;flex-wrap:wrap;gap:7px;padding:7px 9px 5px}
.coxEmpty{margin:22px 12px;color:var(--vscode-descriptionForeground,#969696);text-align:center;line-height:1.45}
.coxMenu{position:fixed;z-index:49;min-width:150px;background:var(--vscode-menu-background,#252526);color:var(--vscode-menu-foreground,#cccccc);border:1px solid var(--vscode-menu-border,#454545);border-radius:6px;padding:4px;box-shadow:0 6px 18px rgba(0,0,0,.45)}
.coxMenuItem{display:block;width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:5px 10px;border-radius:4px;cursor:pointer;font:inherit;font-size:12px}
.coxMenuItem:hover{background:var(--vscode-menu-selectionBackground,#04395e);color:var(--vscode-menu-selectionForeground,#fff)}
.coxMenuSep{height:1px;margin:4px 6px;background:var(--vscode-menu-separatorBackground,#454545)}
.coxNewMini{display:none}
.coxSideOpen body{padding-right:var(--cox-open)!important}
.coxSideClosed body{padding-right:0!important}
.coxSideClosed .coxSidebar{left:auto;right:0;top:0;bottom:auto;width:auto;height:auto;z-index:45;border:0;border-left:1px solid var(--vscode-sideBar-border,#2b2b2b);border-bottom:1px solid var(--vscode-sideBar-border,#2b2b2b);border-radius:0 0 0 8px;box-shadow:0 4px 14px rgba(0,0,0,.35);transition:none}
.coxSideClosed .coxHead{border-bottom:0;padding:3px 5px;gap:2px}
.coxSideClosed .coxTitle,.coxSideClosed .coxSearchWrap,.coxSideClosed .coxNewBtn,.coxSideClosed .coxList,.coxSideClosed .coxResize{display:none}
.coxSideClosed .coxNewMini{display:inline-flex}
.coxSideClosed .coxCollapse svg{transform:rotate(180deg)}
.coxRow{position:relative}
.coxDot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#565656;align-self:flex-start;margin-top:5px}
.coxRow.act::before{content:"";position:absolute;left:0;top:5px;bottom:5px;width:2px;border-radius:0 2px 2px 0;background:var(--vscode-focusBorder,#5b9dff)}
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
.coxSideHidden body{padding-right:0!important}
.coxSideHidden .coxSidebar{display:none!important}
.coxModalShade{position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.38);display:flex;align-items:center;justify-content:center;padding:18px}
.coxDialog{width:min(360px,calc(100vw - 36px));background:var(--vscode-quickInput-background,var(--vscode-editor-background,#1f1f1f));color:var(--vscode-foreground,#ddd);border:1px solid var(--vscode-widget-border,var(--vscode-menu-border,#454545));border-radius:8px;box-shadow:0 18px 44px rgba(0,0,0,.55);padding:16px}
.coxDialogTitle{font-size:14px;font-weight:650;margin:0 0 8px}
.coxDialogBody{font-size:12.5px;line-height:1.45;color:var(--vscode-descriptionForeground,#b8b8b8);margin:0 0 16px}
.coxDialogActions{display:flex;justify-content:flex-end;gap:8px}
.coxDialogBtn{min-width:72px;height:28px;border:1px solid var(--vscode-button-border,transparent);border-radius:5px;padding:0 12px;font:inherit;font-weight:600;cursor:pointer;background:var(--vscode-button-secondaryBackground,#303030);color:var(--vscode-button-secondaryForeground,#ddd)}
.coxDialogBtn:hover{background:var(--vscode-button-secondaryHoverBackground,#3c3c3c)}
.coxDialogBtn.primary{background:var(--vscode-button-background,#0e639c);color:var(--vscode-button-foreground,#fff)}
.coxDialogBtn.primary:hover{background:var(--vscode-button-hoverBackground,#1177bb)}
.coxInstrDialog{width:min(720px,calc(100vw - 36px));padding:0;overflow:hidden}
.coxInstrTabs{height:42px;display:grid;grid-template-columns:1fr 1fr 38px;border-bottom:1px solid var(--vscode-widget-border,var(--vscode-menu-border,#454545))}
.coxInstrTab,.coxInstrClose{border:0;background:transparent;color:var(--vscode-descriptionForeground,#a8a8a8);font:inherit;font-weight:650;cursor:pointer}
.coxInstrTab{position:relative}
.coxInstrTab.on{color:var(--vscode-foreground,#fff)}
.coxInstrTab.on::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:var(--vscode-focusBorder,#8b5cf6)}
.coxInstrClose{font-size:20px;font-weight:400}
.coxInstrClose:hover,.coxInstrTab:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:var(--vscode-foreground,#fff)}
.coxInstrBody{padding:12px 14px 14px}
.coxInstrStatus{min-height:18px;margin-bottom:7px;color:var(--vscode-descriptionForeground,#a8a8a8);font-size:11.5px}
.coxInstrText{display:block;width:100%;height:min(340px,45vh);resize:vertical;border:1px solid var(--vscode-input-border,#3c3c3c);border-radius:5px;background:var(--vscode-input-background,var(--vscode-editor-background,#1e1e1e));color:var(--vscode-input-foreground,#ddd);font:12px/1.45 var(--vscode-editor-font-family,Consolas,monospace);padding:9px 10px;outline:none}
.coxInstrText:focus{border-color:var(--vscode-focusBorder,#4d8dff)}
.coxInstrText::placeholder{color:var(--vscode-input-placeholderForeground,#8a8a8a)}
.coxInstrDialog .coxDialogActions{padding-top:10px}
.coxNativeTaskHidden{display:none!important}
`;
      document.head.appendChild(s);
    }
    function isAuthScreen(){
      try{
        const p=String(location.pathname||"").toLowerCase();
        if(/\/(login|welcome|onboarding|select-workspace|app-connect-oauth-callback)(\/|$)/.test(p)) return true;
        if(document.querySelector("[data-testid*='login' i],[data-testid*='onboarding' i]")) return true;
      }catch{}
      return false;
    }
    function syncChrome(){
      const hidden=isAuthScreen();
      document.documentElement.classList.toggle("coxSideHidden",hidden);
      document.documentElement.classList.add("coxSideOpen");
      document.documentElement.classList.toggle("coxSideClosed",collapsed);
      try{ localStorage.setItem(COLLAPSED_KEY,String(collapsed)); }catch{}
    }
    let renderTimer=null;
    function scheduleRender(){ if(interacting) return; clearTimeout(renderTimer); renderTimer=setTimeout(render,80); }
    const clickNative=(sels)=>{ for(const s of sels){ let el=null; try{ el=document.querySelector(s); }catch{} if(el&&!el.closest(".coxSidebar")){ el.click(); return true; } } return false; };
    function ensureShell(){
      ensureStyle();
      if(shell){ try{ if(!document.body.contains(shell)) document.body.appendChild(shell); }catch{} syncChrome(); return shell; }
      shell=document.createElement("aside"); shell.className="coxSidebar"; shell.setAttribute("aria-label","Codex Orbit chats");
      shell.innerHTML=`
        <div class="coxResize" title="Drag to resize"></div>
        <div class="coxHead">
          <div class="coxTitle">Codex Orbit</div>
          <button class="coxBtn coxNewMini" type="button" title="New task">${IC.plus}</button>
          <button class="coxBtn coxUsage loading" type="button" title="Usage remaining">${IC.usage}</button>
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
      shell.querySelector(".coxUsage").addEventListener("click",(e)=>{ e.stopPropagation(); if(collapsed){ collapsed=false; syncChrome(); } showUsageMenu(shell.querySelector(".coxUsage")); });
      shell.querySelector(".coxFilter").addEventListener("click",(e)=>{ e.stopPropagation(); if(collapsed){ collapsed=false; syncChrome(); } showFilterMenu(shell.querySelector(".coxFilter")); });
      shell.querySelector(".coxSettings").addEventListener("click",(e)=>{ e.stopPropagation(); if(collapsed){ collapsed=false; syncChrome(); } showSettingsMenu(shell.querySelector(".coxSettings")); });
      const newTask=()=>{ clickNative(["[aria-label*='new task' i]","[aria-label*='new chat' i]","[aria-label*='new codex' i]","[aria-label*='new conversation' i]","[aria-label*='new session' i]","[aria-label*='compose' i]","[title*='new task' i]","[title*='new session' i]"]); pulseFreshThread(); };
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
      // Host message (Codex's extension host routes it), then app postMessage, then a
      // history pushState+popstate. NO window.location.href fallback: in a vscode-webview,
      // navigating location to a relative app path ("/local/<id>") loads a non-existent
      // resource and BLANKS the whole webview — that was the "open a non-current chat and
      // the panel kills itself" crash. Worst case now: the chat just doesn't switch.
      let ok=false;
      ok=hostPost("navigate-to-route",{path})||ok;
      ok=appPost("navigate-to-route",{path})||ok;
      ok=navTo(path)||ok;
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
      // Codex-style: Pin / Star / Archive, then a color swatch row. Open was redundant
      // (clicking the row opens it); Filter-to-chat and the separate Set-color item are
      // gone; diagnostics stay available only through window.codexOrbitDump().
      add(isPinned(t)?"Unpin":"Pin",()=>{ if(pins.has(t.id))pins.delete(t.id); else { pins.add(t.id); stars.delete(t.id); } saveSet(PIN_KEY,pins); saveSet(STAR_KEY,stars); });
      add(isStarred(t)?"Unstar":"Star",()=>{ if(stars.has(t.id))stars.delete(t.id); else { stars.add(t.id); pins.delete(t.id); } saveSet(STAR_KEY,stars); saveSet(PIN_KEY,pins); });
      add(archived.has(t.id)?"Unarchive":"Archive",()=>archiveThread(t));
      sep();
      const row=document.createElement("div"); row.className="coxColorRow";
      const cur=colors.get(t.id)||"";
      const setC=(k)=>{ if(k) colors.set(t.id,k); else colors.delete(t.id); saveColors(); closeMenu(); render(); };
      const swatch=(k,c,title,none)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxSwatch"+(none?" coxNone":"")+((k===cur||(!k&&!cur))?" on":""); b.title=title; if(c) b.style.background=c; if(none) b.textContent="⊘"; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); setC(k); }); row.appendChild(b); };
      swatch("","","None",true); for(const p of PALETTE) swatch(p.k,p.c,p.k,false);
      m.appendChild(row);
      placeAt(m,x,y);
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
    // ---------- usage remaining (Codex's native tray data, Orbit's compact popup) ----------
    function clampPct(v){ const n=Number(v); if(!isFinite(n)) return null; const p=(n>=0&&n<=1)?n*100:n; return Math.max(0,Math.min(100,Math.round(p))); }
    function num(o,keys){ for(const k of keys){ const v=o&&o[k]; if(v!=null&&v!==""&&!isNaN(Number(v))) return Number(v); } return null; }
    function val(o,keys){ for(const k of keys){ if(o&&o[k]!=null&&o[k]!=="") return o[k]; } return null; }
    function resetMs(v){ if(v==null||v==="") return 0; if(typeof v==="number") return v<1e12?v*1000:v; const n=Date.parse(v); return isNaN(n)?0:n; }
    function shortClock(ms){ if(!ms) return ""; try{ const d=new Date(ms), now=new Date(); if(d.toDateString()===now.toDateString()) return d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"}); return d.toLocaleDateString([],{month:"short",day:"numeric"}); }catch{} return ""; }
    function relReset(ms){ if(!ms) return ""; const diff=ms-Date.now(); if(diff<=0) return "resets soon"; const h=Math.round(diff/36e5); if(h<1) return "resets in <1h"; if(h<24) return "resets in "+h+"h"; const d=Math.round(h/24); return "resets in "+d+"d"; }
    function windowText(mins){ if(!mins) return ""; if(mins%10080===0) return Math.round(mins/10080)+"w"; if(mins%1440===0) return Math.round(mins/1440)+"d"; if(mins%60===0) return Math.round(mins/60)+"h"; return Math.round(mins)+"m"; }
    function usageName(o,mins,index){
      const raw=clean(val(o,["limitName","limit_name","name","label","model","bucket","key"])||"");
      if(raw&&raw.toLowerCase()!=="null") return raw.replace(/[-_]+/g," ").replace(/\b\w/g,(c)=>c.toUpperCase());
      if(mins&&mins<=360) return "Session";
      if(mins&&mins>=10080) return index>1?"Weekly model":"Weekly";
      if(mins&&mins>=1440) return "Daily";
      return "Usage";
    }
    function collectBuckets(raw){
      const out=[], seen=new WeakSet(), sigs=new Set();
      function add(o,index){
        const used=clampPct(num(o,["usedPercent","used_percent","usedPercentage","usagePercent","percentUsed"]));
        const rem0=clampPct(num(o,["remainingPercent","remaining_percent","remainingPercentage","percentRemaining"]));
        if(used==null&&rem0==null) return;
        const rem=rem0!=null?rem0:Math.max(0,100-used);
        const mins=num(o,["windowDurationMins","window_duration_mins","windowMinutes","window_minutes","durationMins","durationMinutes"]);
        const reset=resetMs(val(o,["resetsAt","resets_at","resetAt","reset_at","endsAt","expiresAt"]));
        const name=usageName(o,mins,index);
        const sig=[name,mins||"",reset||"",rem].join("|");
        if(sigs.has(sig)) return; sigs.add(sig);
        out.push({name,remaining:rem,used:used!=null?used:100-rem,window:windowText(mins),resetAt:reset});
      }
      function walk(o,depth){
        if(!o||typeof o!=="object"||depth>9) return;
        if(seen.has(o)) return; seen.add(o);
        add(o,out.length);
        if(Array.isArray(o)){ for(const x of o) walk(x,depth+1); return; }
        for(const k in o){ try{ walk(o[k],depth+1); }catch{} }
      }
      walk(raw,0);
      return out.slice(0,6);
    }
    function bucketsFromRows(rows){
      const out=[], sigs=new Set();
      function add(src,bucket,index){
        if(!bucket||typeof bucket!=="object") return;
        const used=clampPct(num(bucket,["usedPercent","used_percent","usedPercentage","usagePercent","percentUsed"]));
        const rem0=clampPct(num(bucket,["remainingPercent","remaining_percent","remainingPercentage","percentRemaining"]));
        if(used==null&&rem0==null) return;
        const rem=used!=null?Math.max(0,100-used):rem0;
        const mins=num(bucket,["windowDurationMins","window_duration_mins","windowMinutes","window_minutes","durationMins","durationMinutes"]);
        const reset=resetMs(val(bucket,["resetsAt","resets_at","resetAt","reset_at","endsAt","expiresAt"]));
        const name=usageName(Object.assign({},bucket,{limitName:val(src,["limitName","limit_name","name"])}),mins,index);
        const sig=[name,mins||"",reset||"",rem].join("|");
        if(sigs.has(sig)) return; sigs.add(sig);
        out.push({name,remaining:rem,used:used!=null?used:100-rem,window:windowText(mins),resetAt:reset});
      }
      for(const row of rows||[]){
        const snap=row&&row.snapshot?row.snapshot:row;
        add(row,snap&&snap.primary,out.length);
        add(row,snap&&snap.secondary,out.length);
        add(row,row&&row.bucket,out.length);
      }
      return out.slice(0,3);
    }
    function bucketsFromLabels(labels){
      const out=[];
      for(const it of labels||[]){
        const label=clean(typeof it==="string"?it:(it&&it.label));
        if(!label) continue;
        const m=label.match(/^(.*?)\s*(\d{1,3})%/);
        if(!m) continue;
        const first=clean(m[1]), p=clampPct(m[2]);
        const reset=clean(label.slice(m.index+m[0].length).replace(/^[^\w\d]+/,""));
        let name=first;
        if(/^\d+\s*(h|m|d|w)$/i.test(name)) name="Session";
        if(!name) name="Usage";
        out.push({name,remaining:p,used:100-p,window:first,resetText:reset});
      }
      return out;
    }
    function usageBuckets(){ let b=bucketsFromLabels(usageLabels); if(!b.length) b=bucketsFromRows(usageRows); if(!b.length) b=collectBuckets(usageStatus); return b; }
    function gaugeColor(p){ return p<=20?"var(--vscode-charts-red,#e5484d)":p<=55?"var(--vscode-charts-yellow,#f5d90a)":"var(--vscode-charts-green,#30a46c)"; }
    function updateUsageButton(){
      const b=shell&&shell.querySelector(".coxUsage"); if(!b) return;
      const buckets=usageBuckets(), has=!!buckets.length;
      b.classList.toggle("loading",!has);
      b.classList.toggle("hasUsage",has);
      b.title=has?("Usage remaining: "+buckets[0].remaining+"%"):"Usage remaining";
    }
    function usageCard(bucket){
      const d=document.createElement("div"); d.className="coxGauge";
      const color=gaugeColor(bucket.remaining);
      const sub=bucket.window||(bucket.resetText||shortClock(bucket.resetAt));
      d.innerHTML='<div class="coxGaugeRing"><span class="coxGaugePct"></span></div><div class="coxGaugeTitle"></div><div class="coxGaugeSub"></div>';
      d.querySelector(".coxGaugeRing").style.setProperty("--cox-gauge-pct",bucket.remaining+"%");
      d.querySelector(".coxGaugeRing").style.setProperty("--cox-gauge-color",color);
      d.querySelector(".coxGaugePct").textContent=bucket.remaining+"%";
      d.querySelector(".coxGaugePct").style.color=color;
      d.querySelector(".coxGaugeTitle").textContent=bucket.name;
      d.querySelector(".coxGaugeSub").textContent=sub;
      return d;
    }
    function showUsageMenu(btn){
      closeMenu();
      const m=document.createElement("div"); m.className="coxMenu coxUsagePanel";
      const head=document.createElement("div"); head.className="coxUsageHead"; head.innerHTML='<span>Usage</span><button class="coxUsageFresh" type="button" title="Refresh">&#8635;</button>'; m.appendChild(head);
      const buckets=usageBuckets().slice(0,3);
      if(buckets.length){
        const grid=document.createElement("div"); grid.className="coxUsageGrid"; buckets.forEach((b)=>grid.appendChild(usageCard(b))); m.appendChild(grid);
      } else {
        const loading=document.createElement("div"); loading.className="coxUsageLoading"; loading.innerHTML='<span class="coxSpin"></span><span>Loading Codex usage...</span>'; m.appendChild(loading);
        setTimeout(()=>{ try{ if(document.body.contains(m)&&!usageBuckets().length) loading.innerHTML='<span>Codex has not published usage data yet.</span>'; }catch{} },1800);
      }
      m.querySelector(".coxUsageFresh").addEventListener("click",(ev)=>{ ev.stopPropagation(); try{ if(window.__codexOrbitRateLimitStatus) setUsageStatus(window.__codexOrbitRateLimitStatus); if(Array.isArray(window.__codexOrbitUsageRows)) setUsageRows(window.__codexOrbitUsageRows); if(window.__codexOrbitUsageLimits) setUsageLabels(window.__codexOrbitUsageLimits); coxPost("refresh-rate-limit-status",{}); }catch{} showUsageMenu(btn); });
      anchorMenu(m,btn||shell.querySelector(".coxUsage")||shell.querySelector(".coxSettings"));
    }
    function refreshUsageData(){
      try{
        if(window.__codexOrbitRateLimitStatus) setUsageStatus(window.__codexOrbitRateLimitStatus);
        if(Array.isArray(window.__codexOrbitUsageRows)) setUsageRows(window.__codexOrbitUsageRows);
        if(window.__codexOrbitUsageLimits) setUsageLabels(window.__codexOrbitUsageLimits);
        if(window.__codexOrbitAccountInfo) accountInfo=Object.assign({},accountInfo,window.__codexOrbitAccountInfo);
        coxPost("refresh-rate-limit-status",{});
      }catch{}
    }
    function planFromUsage(){
      const seen=new Set(), vals=[];
      const add=(v)=>{ const s=clean(v); if(s&&!seen.has(s)&&!/^\d+%$/.test(s)){ seen.add(s); vals.push(s); } };
      const scan=(o,depth)=>{
        if(!o||typeof o!=="object"||depth>5) return;
        if(Array.isArray(o)){ for(const x of o) scan(x,depth+1); return; }
        add(o.plan||o.planName||o.plan_name||o.subscriptionPlan||o.subscription_plan||o.serviceTier||o.service_tier||o.sku||o.skuName);
        for(const k in o){ try{ scan(o[k],depth+1); }catch{} }
      };
      scan(usageStatus,0); scan(usageRows,0);
      return vals[0]||"";
    }
    function showAccountUsageDialog(){
      closeMenu(); closeOrbitDialog(); refreshUsageData();
      const shade=document.createElement("div"); shade.className="coxModalShade";
      const d=document.createElement("div"); d.className="coxDialog coxAccountDialog"; d.setAttribute("role","dialog"); d.setAttribute("aria-modal","true");
      d.innerHTML='<div class="coxAccountHead"><div class="coxDialogTitle">Account & Usage</div><button class="coxInstrClose coxAccountClose" type="button" title="Close">&times;</button></div><div class="coxAccountBody"></div>';
      shade.appendChild(d); document.body.appendChild(shade);
      const body=d.querySelector(".coxAccountBody");
      const row=(parent,k,v)=>{ const r=document.createElement("div"); r.className="coxAcctRow"; const a=document.createElement("span"); a.textContent=k; const b=document.createElement("strong"); b.textContent=v||"Not published by Codex"; r.append(a,b); parent.appendChild(r); };
      const section=(title)=>{ const s=document.createElement("section"); s.className="coxAcctSection"; const h=document.createElement("div"); h.className="coxAcctSectionTitle"; h.textContent=title; s.appendChild(h); body.appendChild(s); return s; };
      function renderDialog(){
        body.textContent="";
        const acct=section("Account");
        row(acct,"Auth method",accountInfo.authMethod||"Codex");
        row(acct,"Email",accountInfo.email||"");
        row(acct,"Organization",accountInfo.organization||"");
        row(acct,"Plan",accountInfo.plan||planFromUsage()||"");
        if(accountInfo.accountId) row(acct,"Account ID",accountInfo.accountId);
        const usage=section("Usage");
        const buckets=usageBuckets().slice(0,3);
        if(buckets.length){
          const grid=document.createElement("div"); grid.className="coxUsageGrid coxUsageGridFull"; buckets.forEach((b)=>grid.appendChild(usageCard(b))); usage.appendChild(grid);
          const note=document.createElement("div"); note.className="coxUsageNote"; note.textContent=usageUpdatedAt?("Updated "+relTime(usageUpdatedAt)):"Live Codex rate-limit data"; usage.appendChild(note);
        } else {
          const p=document.createElement("p"); p.className="coxUsageNote"; p.textContent="Codex has not published usage data to this webview yet."; usage.appendChild(p);
        }
        const actions=document.createElement("div"); actions.className="coxDialogActions coxAccountActions";
        const retry=document.createElement("button"); retry.type="button"; retry.className="coxDialogBtn primary"; retry.textContent="Retry";
        retry.addEventListener("click",()=>{ refreshUsageData(); setTimeout(renderDialog,250); });
        actions.appendChild(retry); usage.appendChild(actions);
        const contrib=section("What's contributing to your limits?");
        const p=document.createElement("p"); p.className="coxUsageNote";
        p.textContent="Codex has not published per-factor usage attribution in this VS Code webview yet. When it does, this section will show it here instead of guessing.";
        contrib.appendChild(p);
      }
      const done=()=>closeOrbitDialog();
      shade.addEventListener("click",(ev)=>{ if(ev.target===shade) done(); });
      d.querySelector(".coxAccountClose").addEventListener("click",done);
      renderDialog();
    }
    // ---------- settings menu (our UI, Codex's own settings navigation) ----------
    // Codex's gear/settings actions are NOT a generic "run-command" host message — that
    // type does not exist in the host (verified against Codex 26.5609: the host's
    // onDidReceiveMessage switch has zero 'run-command' cases, so such a post is silently
    // dropped — which is why every old gear item no-op'd while local Copy diagnostics still
    // worked). Codex opens a settings pane by posting {type:"show-settings",section:<slug>}
    // to the host, routed by `case'show-settings': this.showSettings({section},e)` ->
    // navigates /settings/<slug>. Verified slugs in 26.5609: usage, personalization,
    // appearance, profile (settings-sections-*.js). `window.codexOrbitDump()` reports whether
    // the host channel is live (hostChannel:true) so this stays diagnosable.
    function showSettings(section){ return coxPost("show-settings",{section}); }
    // Log out by replaying Codex's OWN action: its profile button posts {type:"log-out"}
    // through the vscode-api singleton's LOCAL bus (dispatchHostMessage -> deliverMessage),
    // NOT to the extension host. We reach that same bus from injected JS via window.postMessage:
    // the singleton's handleMessage validates e.origin===location.origin (true for a self-post)
    // then runs deliverMessage("log-out",...) -> Codex's logout handler (et("logout",{hostId})
    // + navigate to /login). Verified in Codex 26.5609 (vscode-api-*.js, app-main case"log-out").
    function logOut(){ try{ window.postMessage({type:"log-out"},"*"); return true; }catch(e){ return false; } }
    function closeOrbitDialog(){ document.querySelectorAll(".coxModalShade").forEach((e)=>e.remove()); }
    function copyText(text){
      try{ navigator.clipboard.writeText(text); return true; }catch(e){
        try{ const ta=document.createElement("textarea"); ta.value=text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); return true; }catch(_){}}
      return false;
    }
    function showOrbitInfo(title,body){
      closeMenu(); closeOrbitDialog();
      const shade=document.createElement("div"); shade.className="coxModalShade";
      const d=document.createElement("div"); d.className="coxDialog"; d.setAttribute("role","dialog"); d.setAttribute("aria-modal","true");
      const h=document.createElement("div"); h.className="coxDialogTitle"; h.textContent=title;
      const p=document.createElement("p"); p.className="coxDialogBody"; p.textContent=body;
      const a=document.createElement("div"); a.className="coxDialogActions";
      const close=document.createElement("button"); close.type="button"; close.className="coxDialogBtn primary"; close.textContent="Close";
      a.appendChild(close); d.append(h,p,a); shade.appendChild(d); document.body.appendChild(shade);
      const done=()=>closeOrbitDialog();
      shade.addEventListener("click",(ev)=>{ if(ev.target===shade) done(); });
      close.addEventListener("click",done);
      setTimeout(()=>{ try{ close.focus(); }catch{} },0);
    }
    function showInstructionsDialog(){
      closeMenu(); closeOrbitDialog();
      const shade=document.createElement("div"); shade.className="coxModalShade";
      const d=document.createElement("div"); d.className="coxDialog coxInstrDialog"; d.setAttribute("role","dialog"); d.setAttribute("aria-modal","true");
      d.innerHTML='<div class="coxInstrTabs"><button class="coxInstrTab on" type="button" data-scope="project">Project</button><button class="coxInstrTab" type="button" data-scope="global">Global</button><button class="coxInstrClose" type="button" title="Close">×</button></div><div class="coxInstrBody"><div class="coxInstrStatus">Loading...</div><textarea class="coxInstrText" spellcheck="false" placeholder="Type whatever you want"></textarea><div class="coxDialogActions"><button class="coxDialogBtn primary coxInstrSave" type="button">Save</button><button class="coxDialogBtn coxInstrOpen" type="button">Open in Editor</button></div></div>';
      shade.appendChild(d); document.body.appendChild(shade);
      const hw=hostWorkspace(), root=(hw&&hw.r)||curRoot||"";
      const agentsPath=()=>root?root.replace(/[\\/]+$/,"")+(/\\/.test(root)?"\\":"/")+"AGENTS.md":"";
      const files={
        project:{scope:"project",label:"Project",path:agentsPath(),content:"",loaded:false,dirty:false,error:""},
        global:{scope:"global",label:"Global",path:"",content:"",loaded:false,dirty:false,error:""}
      };
      let active="project";
      const status=d.querySelector(".coxInstrStatus"), text=d.querySelector(".coxInstrText"), save=d.querySelector(".coxInstrSave"), open=d.querySelector(".coxInstrOpen");
      const tabBtns=[...d.querySelectorAll(".coxInstrTab")];
      function scopePayload(scope){ const f=files[scope]; const p={scope}; if(scope==="project"&&f.path) p.path=f.path; return p; }
      function statusText(f){ if(f.error) return f.error; if(!f.loaded) return "Loading..."; if(f.dirty) return "Unsaved changes"; return "File loaded ("+(f.content||"").length+" chars)"; }
      function renderInstr(){
        const f=files[active];
        tabBtns.forEach((b)=>b.classList.toggle("on",b.dataset.scope===active));
        if(!f.dirty||document.activeElement!==text) text.value=f.content||"";
        status.textContent=statusText(f);
        save.disabled=!f.loaded&&!!f.error;
        open.disabled=active==="project"&&!f.path;
      }
      function request(scope){
        const ok=coxPost("codex-orbit-read-agents",scopePayload(scope));
        if(!ok){ files[scope].loaded=true; files[scope].error="Host unavailable"; renderInstr(); }
      }
      function done(){ window.removeEventListener("message",onMsg,true); closeOrbitDialog(); }
      function readMsg(data){
        if(data&&typeof data==="object"){
          if(data.type==="codex-orbit-agents-file"||data.type==="codex-orbit-agents-saved") return data;
          if(data.message) return readMsg(data.message);
          if(data.data) return readMsg(data.data);
        }
        return null;
      }
      function onMsg(ev){
        const msg=readMsg(ev.data); if(!msg) return;
        const scope=msg.scope==="global"?"global":"project", f=files[scope];
        f.loaded=true; f.path=msg.path||f.path||"";
        f.error=msg.error?String(msg.error):"";
        if(!f.dirty||msg.type==="codex-orbit-agents-saved"){ f.content=typeof msg.content==="string"?msg.content:(f.content||""); f.dirty=false; }
        if(scope===active) renderInstr();
      }
      window.addEventListener("message",onMsg,true);
      shade.addEventListener("click",(ev)=>{ if(ev.target===shade) done(); });
      d.querySelector(".coxInstrClose").addEventListener("click",done);
      tabBtns.forEach((b)=>b.addEventListener("click",()=>{ files[active].content=text.value; active=b.dataset.scope==="global"?"global":"project"; renderInstr(); setTimeout(()=>{ try{text.focus();}catch{} },0); }));
      text.addEventListener("input",()=>{ const f=files[active]; f.content=text.value; f.dirty=true; status.textContent=statusText(f); });
      save.addEventListener("click",()=>{ const f=files[active]; f.content=text.value; f.dirty=true; f.error=""; status.textContent="Saving..."; coxPost("codex-orbit-save-agents",Object.assign(scopePayload(active),{content:f.content})); });
      open.addEventListener("click",()=>coxPost("codex-orbit-open-agents",scopePayload(active)));
      request("project"); request("global"); renderInstr();
      setTimeout(()=>{ try{ text.focus(); }catch{} },0);
    }
    function showConfirmLogOut(){
      closeMenu(); closeOrbitDialog();
      const shade=document.createElement("div"); shade.className="coxModalShade";
      const d=document.createElement("div"); d.className="coxDialog"; d.setAttribute("role","dialog"); d.setAttribute("aria-modal","true");
      d.innerHTML='<div class="coxDialogTitle">Log out?</div><p class="coxDialogBody">Switching accounts will sign you out of Codex in this window.</p><div class="coxDialogActions"><button class="coxDialogBtn coxCancel" type="button">Cancel</button><button class="coxDialogBtn primary coxOk" type="button">Yes</button></div>';
      shade.appendChild(d); document.body.appendChild(shade);
      const cancel=()=>closeOrbitDialog();
      shade.addEventListener("click",(ev)=>{ if(ev.target===shade) cancel(); });
      d.querySelector(".coxCancel").addEventListener("click",cancel);
      d.querySelector(".coxOk").addEventListener("click",()=>{ closeOrbitDialog(); logOut(); });
      setTimeout(()=>{ try{ d.querySelector(".coxCancel").focus(); }catch{} },0);
    }
    function showSettingsMenu(btn){
      closeMenu();
      const m=document.createElement("div"); m.className="coxMenu coxSettingsMenu";
      const item=(label,fn)=>{ const b=document.createElement("button"); b.type="button"; b.className="coxMenuItem"; b.textContent=label; b.addEventListener("click",(ev)=>{ ev.stopPropagation(); closeMenu(); fn(); }); m.appendChild(b); };
      // "Switch model" was removed: composer.openModelPicker is an in-composer popover
      // toggle with no host/settings-section path, so it can't be triggered from here —
      // better absent than a dead button. "Switch account" logs out (-> /login, where you
      // sign in as a different account) via Codex's own local log-out bus; the rest open a
      // native settings pane via show-settings.
      item("Account & usage",()=>showAccountUsageDialog());
      item("Switch account",()=>showConfirmLogOut());
      item("Custom instructions",()=>showInstructionsDialog());
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
      const sel=(curOpenUuid&&uuidOf(t.id)===curOpenUuid)||t.active;   // the chat you're viewing
      const b=document.createElement("div"); b.className="coxRow"+(sel?" act":""); b.setAttribute("role","button"); b.tabIndex=0; b.title=t.title;
      const st=statusOf(t);
      // Left indicator: a spinner while the agent is thinking, else a status-colored dot
      // (blue=running, orange=waiting/question, red=failed, gray=idle).
      let ind;
      if(st==="running"){ ind=document.createElement("span"); ind.className="coxSpin"; }
      else { ind=document.createElement("span"); ind.className="coxDot"; ind.style.background=DOT[st]||DOT.idle; }
      ind.title=st;
      // Per-chat color tints the WHOLE row — a left bar plus a faint full-row fill that
      // survives :hover (inset box-shadow overlay paints above the background).
      const col=colors.get(t.id); if(col){ const hx=colorOf(col)||col; b.style.boxShadow="inset 3px 0 0 "+hx+", inset 0 0 0 100px "+hx+"22"; }
      // Two lines: title, then the relative time OR live status ("Thinking…"/"Question").
      const main=document.createElement("span"); main.className="coxRowMain";
      const tt=document.createElement("span"); tt.className="coxRowT"; tt.textContent=t.title.replace(/^⭐\s*/,"").replace(/^📌\s*/,"");
      const sub=document.createElement("span"); sub.className="coxRowSub"+(st!=="idle"?" "+st:""); sub.textContent=subText(t,st);
      main.append(tt,sub);
      const acts=document.createElement("span"); acts.className="coxActs";
      const mk=(act,title,svg,on)=>{ const x=document.createElement("button"); x.type="button"; x.className="coxAct"+(on?" on":""); x.title=title; x.dataset.coxAct=act; x.innerHTML=svg; acts.appendChild(x); };
      const arch=archived.has(t.id);
      mk("star",isStarred(t)?"Unstar":"Star",IC.star,isStarred(t));
      mk("pin",isPinned(t)?"Unpin":"Pin",IC.pin,isPinned(t));
      mk("color","Set color",IC.dot,!!col);
      mk("archive",arch?"Unarchive":"Archive",IC.archive,arch);
      b.append(ind,main,acts);
      rowMap.set(b,t);   // open + actions + right-click are routed by the delegated .coxList handlers
      parent.appendChild(b);
    }
    function addGroup(list,name,rows){
      if(!rows.length) return;
      const sec=document.createElement("section");
      const collapsed=groupState[name]===false;
      const gb=document.createElement("button"); gb.type="button"; gb.className="coxGroupBtn"+(collapsed?" coll":""); gb.dataset.coxGroup=name;
      const chev=document.createElement("span"); chev.className="coxGroupChev"; chev.innerHTML=IC.chev;
      const nm=document.createElement("span"); nm.className="coxGroupName"; nm.textContent=name;
      const cnt=document.createElement("span"); cnt.className="coxCount"; cnt.textContent=rows.length;   // session counter, like Codex
      gb.append(chev,nm,cnt);   // collapse/expand routed by the delegated .coxList handler
      sec.appendChild(gb);
      if(!collapsed){ for(const r of rows) addRow(sec,r); }
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
      curOpenUuid=uuidOf(openThreadId());   // highlight the row of the chat being viewed
      const nativeRows=domThreads();
      const hw=hostWorkspace(); if(hw) setCurrent(hw.r,hw.l);
      const merged=withRouteThreads(mergeThreads(nativeRows),nativeRows);
      let rows=currentRows(merged,nativeRows);   // filtered to the active workspace (native task rows or Codex's roots[0])
      filterNativeTaskLists(rows);
      const needle=search.toLowerCase();
      if(needle) rows=rows.filter((t)=>t.title.toLowerCase().includes(needle)||(t.project||"").toLowerCase().includes(needle));
      rows=applyFilter(rows);
      rows.sort((a,b)=>(b.ts||0)-(a.ts||0));   // newest chat on top (sorts every section)
      const fb=side.querySelector(".coxFilter"); if(fb) fb.classList.toggle("on",!!filterActive());
      // Archived chats (ours + any Codex flags) drop into their own section at the bottom,
      // like Codex's native "Archived" group — not removed.
      const isArch=(t)=>archived.has(t.id)||(t.raw&&t.raw.archived===true);
      const arch=rows.filter(isArch); rows=rows.filter((t)=>!isArch(t));
      list.textContent="";
      if(!rows.length&&!arch.length){ const e=document.createElement("div"); e.className="coxEmpty"; e.textContent=search?"No matching chats.":(filterActive()?"No chats match the filter.":"No chats found yet."); list.appendChild(e); return; }
      const pinned=rows.filter(isPinned), starred=rows.filter((t)=>!isPinned(t)&&isStarred(t)), rest=rows.filter((t)=>!isPinned(t)&&!isStarred(t));
      addGroup(list,"⭐ Starred",starred);
      addGroup(list,"📌 Pinned",pinned);
      const order=[],by=new Map(); for(const r of rest){ if(!by.has(r.project)){by.set(r.project,[]);order.push(r.project);} by.get(r.project).push(r); }
      // Single workspace (the normal filtered case): one collapsible "Sessions" group with
      // a count, exactly like Codex. Per-project headers only in the blind-fallback case
      // (multiple workspaces leaked), where the label actually disambiguates.
      if(order.length<=1){ addGroup(list,"Sessions",rest); }
      else { for(const n of order) addGroup(list,n,by.get(n)); }
      addGroup(list,"Archived",arch);   // its own collapsible header at the bottom
    }

    // ---------- self-diagnostics: capture a debug snapshot, with optional download ----------
    window.codexOrbitDump=function(opts){
      const labels=(sel)=>[...document.querySelectorAll(sel)].map((b)=>b.getAttribute("aria-label")||b.getAttribute("title")||clean(b.textContent)).filter(Boolean);
      const anchors=[...document.querySelectorAll("a[href]")].map((a)=>a.getAttribute("href")).filter((h)=>h&&h[0]==="/").slice(0,40);
      const all=allThreads();
      const nativeEls=[...document.querySelectorAll(A.row)];
      const data={
        at:new Date().toISOString(),
        version:"0.5.43",
        location:{href:location.href,pathname:location.pathname,hash:location.hash,search:location.search},
        hostWorkspace:hostWorkspace(),
        hostChannel:!!(window.__codexOrbitVsApi&&window.__codexOrbitVsApi.postMessage)||(typeof window.__codexPostMessage==="function"),
        statusHook:!!window.__codexOrbitStatusHook,
        usageHook:!!window.__codexOrbitRateLimitStatus,
        usageRows:usageRows,
        usageLabels:usageLabels,
        accountInfo:accountInfo,
        liveStatus:[...liveStatus.entries()].slice(0,20),
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
      if(!opts||opts.download!==false) try{
        const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
        const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="codex-orbit-debug.json";
        document.body.appendChild(a); a.click(); setTimeout(()=>{ try{URL.revokeObjectURL(a.href);}catch{} a.remove(); },200);
      }catch(e){ console.warn("[Codex Orbit] dump download blocked:",e); }
      console.log("[Codex Orbit] debug dump",data);
      return data;
    };

    function start(){
      if(!document.body){ setTimeout(start,60); return; }
      hookHistory();
      ensureShell(); render();
      updateUsageButton();
      const filterHomeTasks=()=>{ try{ filterNativeTaskLists(currentRows(allThreads(),domThreads())); }catch{} };
      filterHomeTasks(); setTimeout(filterHomeTasks,250); setTimeout(filterHomeTasks,1000); setInterval(filterHomeTasks,10000);
      // Re-render only when Codex's NATIVE SIDEBAR rows change (add/remove) — NOT the
      // conversation transcript. The old observer reacted to ANY DOM mutation outside our
      // shell, so an active chat streaming tokens fired it ~12x/s: a list-rebuild storm that
      // (a) saturated the event loop, so the status display lagged ~20s behind reality, and
      // (b) destroyed+recreated the spinner element every frame, restarting its CSS animation
      // so it looked like a static ring instead of spinning. Status, the chat list, and
      // navigation update via their own signals (the status hook, the message ingest,
      // popstate/focus); the interval below keeps relative times fresh. (Text-delta streaming
      // is text nodes — nodeType!==1 — so the gate skips it cheaply.)
      const sbSel=A.row+","+A.projectRow;
      const touchesSb=(nodes)=>{ for(const n of nodes){ try{ if(n.nodeType===1&&((n.matches&&n.matches(sbSel))||(n.querySelector&&n.querySelector(sbSel)))) return true; }catch{} } return false; };
      new MutationObserver((muts)=>{
        if(interacting) return;
        for(const m of muts){
          if(shell&&shell.contains(m.target)) continue;
          if(touchesSb(m.addedNodes)||touchesSb(m.removedNodes)){ scheduleRender(); break; }
        }
      }).observe(document.documentElement,{childList:true,subtree:true});
      window.addEventListener("focus",()=>scheduleRender());
      window.addEventListener("hashchange",()=>{ rememberOpenThread(); scheduleRender(); });
      window.addEventListener("popstate",()=>scheduleRender());   // update the selected-chat highlight on navigation
      setInterval(()=>scheduleRender(),30000);   // keep relative times ("12 min ago") fresh
    }
    function pulseFreshThread(){
      const until=Date.now()+45000;
      const tick=()=>{
        try{ rememberOpenThread(); }catch{}
        scheduleRender();
        try{ window.dispatchEvent(new Event("focus")); document.dispatchEvent(new Event("visibilitychange")); }catch{}
        if(Date.now()<until) setTimeout(tick,500);
      };
      tick();
    }
    function hookHistory(){
      if(window.__codexOrbitHistoryHooked) return;
      window.__codexOrbitHistoryHooked=true;
      const fire=()=>setTimeout(()=>{ try{ rememberOpenThread(); }catch{} scheduleRender(); },0);
      for(const name of ["pushState","replaceState"]){
        try{
          const orig=history[name];
          if(typeof orig!=="function") continue;
          history[name]=function(){ const r=orig.apply(this,arguments); fire(); return r; };
        }catch{}
      }
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


def patch_webview_js(helper) -> bool:
    """Embed the Orbit build/channel markers into the patched webview chunk.

    TWO jobs, both required by the shared Orbit launcher (pulled from claude-code-orbit):
    1. MARKER CHECK: the launcher's OTA loader accepts a fetched patcher only if its
       source contains the literal string `def patch_webview_js`. Without this function
       the launcher rejects our patcher with "OTA patcher fetch failed" — regardless of
       the patcher actually working. (The launcher's marker is the Claude patcher's
       function name; our real injector is copy_patched_assets, so we add this too.)
    2. INSTALLED TAG: append `var ccPatchBuildVersion="<v>";var ccPatchChannel="<ch>";`
       so the launcher can read the installed build's version + release channel straight
       from the patched webview (mirrored into the manifest by archive_patcher.py).

    Appended (never prepended) so it can't disturb the chunk's ES-module import order.
    Idempotent: no-op if the marker is already present."""
    text = helper.read_text(encoding="utf-8", errors="ignore")
    if "ccPatchChannel=" in text:
        return True
    marker = f'\n;var ccPatchBuildVersion="{__version__}";var ccPatchChannel="{ORBIT_CHANNEL}";'
    helper.write_text(text + marker, encoding="utf-8", newline="")
    return True


def copy_patched_assets(extension_dir, patcher_version):
    """The whole patch: append the Codex Orbit sidebar IIFE to a webview entry chunk
    IN PLACE. Keep the name copy_patched_assets — the Orbit wrapper's OTA loader
    requires this exact string ("def copy_patched_assets") to accept a patcher.

    We append in place (no rename) to the first resolvable host in HELPER_PREFIXES —
    exactly how expose_status_stream / expose_host_channel below already patch their
    chunks. The old approach renamed the host chunk to *-codexpatch.js and rewrote
    every import that referenced it; that bricked the moment Codex removed the host
    chunk (build 5609). In-place append removes that whole failure class: there is no
    rename to keep in sync, and a renamed/removed host falls through to the next
    candidate instead of crashing."""
    ext = Path(extension_dir); wv = ext / "webview" / "assets"
    if not wv.exists(): raise RuntimeError("webview/assets not found")
    # Locate the sidebar host now, but DON'T inject yet.
    helper = None
    for prefix in HELPER_PREFIXES:
        cands = sorted(p for p in wv.glob(prefix + "*.js")
                       if not p.name.endswith(".map") and "-codexpatch" not in p.name)
        if cands:
            helper = cands[0]; break
    if helper is None:
        raise RuntimeError(f"No injection host found (tried: {', '.join(HELPER_PREFIXES)})")
    # Patch the discrete hook chunks FIRST, while every chunk is still clean. ORDER IS
    # LOad-BEARING: the sidebar IIFE itself MENTIONS window.__codexOrbitVsApi and
    # window.__codexOrbitStatusHook, so if it were injected first, the "already patched?"
    # scans in expose_host_channel / expose_status_stream would see those mentions in the
    # host chunk and skip the REAL wrap/splice (it only worked before by glob-order luck;
    # injecting into app-main-* exposed the bug). Inject the self-contained IIFE LAST.
    expose_native_openers(wv)
    expose_host_channel(wv)
    expose_usage_status(wv)
    expose_usage_rows(wv)
    if feature_on("status-dots"):
        expose_status_stream(wv)
    else:
        log("Skipping status-dots (patch disabled) — rows show relative time only")
    if feature_on("workspace-filter"):
        inject_workspace_meta(ext)
    else:
        log("Skipping workspace-filter (patch disabled) — sidebar shows every project")
    inject_agents_opener(ext)
    text = helper.read_text(encoding="utf-8", errors="ignore")
    if "__codexOrbitSidebarV4" not in text:
        text += "\n" + SIDEBAR_IIFE
        helper.write_text(text, encoding="utf-8", newline="")
    patch_webview_js(helper)   # embed ccPatchChannel/build markers + satisfy the OTA marker check
    log(f"Injected Codex Orbit sidebar into {helper.name} (channel {ORBIT_CHANNEL})")
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


# Usage remaining. Codex already computes the native tray-menu usage labels from the
# live rate-limit query; Orbit only needs that same object surfaced in-window so the
# sidebar can render a compact dropdown without navigating to Settings.
USAGE_TRAY_RE = re.compile(
    r"let\s+([A-Za-z_$][\w$]*)=(\{\.\.\.[^;]{0,3500}?usageLimits:"
    r"[A-Za-z_$][\w$]*\(\{intl:[A-Za-z_$][\w$]*,rateLimitStatus:([A-Za-z_$][\w$]*)\}\)\}),"
    r"([A-Za-z_$][\w$]*)=JSON\.stringify\(\1\);"
)

USAGE_ROWS_RE = re.compile(
    r"(function\s+[A-Za-z_$][\w$]*\(([A-Za-z_$][\w$]*)\)\{if\(\2==null\)return\[\];"
    r"let\s+([A-Za-z_$][\w$]*)=\[\],[\s\S]{0,5000}?additional_rate_limits[\s\S]{0,5000}?)(return\s+\3\})"
)


def expose_usage_status(wv):
    """Expose Codex's tray-menu rate-limit data for the Orbit usage popup."""
    for f in wv.glob("*.js"):
        if f.name.endswith(".map"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "__codexOrbitRateLimitStatus" in text and "tray-menu-threads-changed" in text:
            log("Usage status bridge already present")
            return True
        if "tray-menu-threads-changed" not in text or "usageLimits:" not in text:
            continue
        m = USAGE_TRAY_RE.search(text)
        if not m:
            continue
        tray_var, tray_obj, rate_var, json_var = m.groups()
        injected = (
            f"let {tray_var}={tray_obj};"
            f"try{{window.__codexOrbitRateLimitStatus={rate_var};"
            f"window.__codexOrbitUsageLimits={tray_var}.usageLimits;"
            f'window.dispatchEvent(new CustomEvent("codex-orbit-rate-limit",{{detail:{rate_var}}}));'
            f'window.dispatchEvent(new CustomEvent("codex-orbit-usage-limits",{{detail:{tray_var}.usageLimits}}));'
            f"}}catch(_co){{}}let {json_var}=JSON.stringify({tray_var});"
        )
        f.write_text(text[:m.start()] + injected + text[m.end():], encoding="utf-8", newline="")
        log(f"Exposed usage status bridge in {f.name}")
        return True
    log("Usage tray anchor not found; usage popup will use message/label fallbacks")
    return False


def expose_usage_rows(wv):
    """Expose Codex's normalized rate-limit rows for the Orbit usage popup.

    The tray-menu bridge only runs when Codex builds its native tray payload. The
    normalized row builder lives in the shared rate-limit module used by the
    composer/settings usage UI, so this catches the 5h/weekly data even when the
    tray object never appears."""
    for f in wv.glob("*.js"):
        if f.name.endswith(".map"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "additional_rate_limits" not in text or "rate_limit_name" not in text or "used_percent" not in text:
            continue
        if "__codexOrbitUsageRows" in text and "codex-orbit-usage-rows" in text:
            log("Usage rows bridge already present")
            return True
        m = USAGE_ROWS_RE.search(text)
        if not m:
            continue
        arg, rows = m.group(2), m.group(3)
        injected = (
            f"{m.group(1)}try{{window.__codexOrbitRateLimitStatus={arg};"
            f"window.__codexOrbitUsageRows={rows};"
            f'window.dispatchEvent(new CustomEvent("codex-orbit-rate-limit",{{detail:{arg}}}));'
            f'window.dispatchEvent(new CustomEvent("codex-orbit-usage-rows",{{detail:{rows}}}));'
            f"}}catch(_co){{}}{m.group(4)}"
        )
        f.write_text(text[:m.start()] + injected + text[m.end():], encoding="utf-8", newline="")
        log(f"Exposed usage rows bridge in {f.name}")
        return True
    log("Usage rows anchor not found; usage popup may need Codex to publish tray data")
    return False


# Live per-chat status. Codex's status notifications (thread/status/changed, turn/started,
# turn/completed, item/*requestApproval*, item/tool/requestUserInput, ...) all funnel the new
# conversation state through the SEMANTIC method updateConversationState(id, updater). We
# append a hook call AFTER the original applies — wrapped in try/catch, zero behaviour change.
# SAFE: if the anchor ever drifts it simply doesn't apply (status stays best-effort),
# it can NEVER break Codex. Status is otherwise unreachable from a window listener — it
# rides the app-server IPC bridge into Jotai atoms, never onto `window`.
# The minified state-merge helper is renamed every build (Nn in 5519, hr in 5609, …), so
# we capture it with \w+ instead of pinning a literal — the method name
# updateConversationState is semantic and stable, only the helper churns. We re-emit the
# whole matched method and splice the hook call in before its closing brace.
STATUS_ANCHOR_RE = re.compile(
    r"updateConversationState\(e,t\)\{let n=this\.getConversation\(e\);"
    r"if\(n==null\)return;let r=\w+\(n,t\);this\.applyConversationState\(e,r\)\}"
)
STATUS_HOOK_TAIL = ";try{if(window.__codexOrbitStatusHook)window.__codexOrbitStatusHook(e,r)}catch(_co){}}"


def expose_status_stream(wv):
    """Tee Codex's per-conversation status into window.__codexOrbitStatusHook so the sidebar
    can show live Thinking/Question/Failed. See the STATUS_ANCHOR_RE note above."""
    for f in wv.glob("*.js"):
        if f.name.endswith(".map"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "__codexOrbitStatusHook" in text:
            log("Live-status hook already present")
            return True
        m = STATUS_ANCHOR_RE.search(text)
        if m:
            inject = m.group(0)[:-1] + STATUS_HOOK_TAIL  # drop the method's closing } , re-add it after the hook
            f.write_text(text[:m.start()] + inject + text[m.end():], encoding="utf-8", newline="")
            log(f"Exposed live-status hook (window.__codexOrbitStatusHook) in {f.name}")
            return True
    log("updateConversationState anchor not found; live-status hook NOT applied — status stays best-effort")
    return False


# Host-side single source of truth. Anchored on the (semantic, stable) method name
# webviewMetaTags — NOT on a minified local — so it survives Codex churn better than
# the webview opener anchors (confirmed still present in 5609). `Oe` is the vscode-module
# alias in webviewMetaTags' own module (confirmed for this baseline). We DON'T depend on
# Codex's HTML escaper anymore (it was `pl` in 5519, `$l` in 5609 — a moving target);
# we escape the JSON string inline instead, so only the vscode alias can drift, and the
# try/catch makes even that a harmless no-op (the webview falls back to its URL/RPC/DOM
# heuristics; the host bundle still parses).
HOST_META_ANCHOR = "webviewMetaTags(e){let r=[],n=this.findPanelByWebview(e);"
HOST_META_SUFFIX = (
    'try{var __coxWF=Oe.workspace.workspaceFolders,'
    '__coxJ=JSON.stringify({'
    'r:(__coxWF&&__coxWF[0]&&__coxWF[0].uri&&__coxWF[0].uri.fsPath)||"",'
    'l:(__coxWF&&__coxWF[0]&&__coxWF[0].name)||""}),'
    '__coxQ=__coxJ.replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");'
    'r.push(`<meta name="codex-orbit-workspace" content="${__coxQ}">`)}catch(__coxE){}'
)

AGENTS_OPEN_ANCHOR = 'case"set-telemetry-user":'
AGENTS_OPEN_CASE = (
    'case"codex-orbit-read-agents":{let n=r.scope==="global"?"global":"project",o="",i="",s=!1,a=null;'
    'if(n==="global"){let i=At({preferWsl:pr()});o=nde.join(i,"AGENTS.md")}'
    'else{let i=Oe.workspace.workspaceFolders&&Oe.workspace.workspaceFolders[0];'
    'o=typeof r.path==="string"&&r.path?r.path:(i&&i.uri?nde.join(i.uri.fsPath,"AGENTS.md"):"")}'
    'if(o)try{i=await iC.promises.readFile(o,"utf8"),s=!0}catch(c){let l=c;if(!("code"in l&&l.code==="ENOENT"))a=String(l&&l.message||l)}'
    'this.postMessageToWebview(e,{type:"codex-orbit-agents-file",scope:n,path:o,content:i,exists:s,error:a});break}'
    'case"codex-orbit-save-agents":{let n=r.scope==="global"?"global":"project",o="",i=typeof r.content==="string"?r.content:"",s=null;'
    'if(n==="global"){let i=At({preferWsl:pr()});o=nde.join(i,"AGENTS.md")}'
    'else{let i=Oe.workspace.workspaceFolders&&Oe.workspace.workspaceFolders[0];'
    'o=typeof r.path==="string"&&r.path?r.path:(i&&i.uri?nde.join(i.uri.fsPath,"AGENTS.md"):"")}'
    'if(o)try{await iC.promises.mkdir(nde.dirname(o),{recursive:!0});await iC.promises.writeFile(o,i,"utf8")}catch(a){s=String(a&&a.message||a)}else s="No workspace folder";'
    'this.postMessageToWebview(e,{type:"codex-orbit-agents-saved",scope:n,path:o,content:i,exists:!s,error:s});break}'
    'case"codex-orbit-open-agents":{let n=r.scope==="global"?"global":"project",o="";'
    'if(n==="global"){let i=At({preferWsl:pr()});o=nde.join(i,"AGENTS.md")}'
    'else{let i=Oe.workspace.workspaceFolders&&Oe.workspace.workspaceFolders[0];'
    'o=typeof r.path==="string"&&r.path?r.path:(i&&i.uri?nde.join(i.uri.fsPath,"AGENTS.md"):"")}'
    'if(o){await iC.promises.mkdir(nde.dirname(o),{recursive:!0});'
    'try{await iC.promises.access(o)}catch(i){let s=i;if("code"in s&&s.code==="ENOENT")await iC.promises.writeFile(o,"");else throw i}'
    'await Oe.commands.executeCommand("vscode.open",Oe.Uri.file(o))}break}'
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


def inject_agents_opener(ext):
    """Add a tiny Codex host message so the sidebar can open/create AGENTS.md."""
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
        log(f"Host bundle not found ({main_rel}); AGENTS.md opener NOT injected")
        return False
    text = host.read_text(encoding="utf-8", errors="ignore")
    if "codex-orbit-save-agents" in text:
        log("AGENTS.md opener already present in host bundle")
        return True
    if AGENTS_OPEN_ANCHOR not in text:
        log("Host message switch anchor NOT found; AGENTS.md opener NOT injected")
        return False
    host.write_text(text.replace(AGENTS_OPEN_ANCHOR, AGENTS_OPEN_CASE + AGENTS_OPEN_ANCHOR, 1), encoding="utf-8", newline="")
    log(f"Injected AGENTS.md opener into host bundle {host.name}")
    return True


def verify(ext_dir):
    node = shutil.which("node")
    # The sidebar is appended in place (no -codexpatch rename), so locate the patched
    # host by its content marker rather than its name — works whatever chunk we landed on.
    f = next((p for p in (ext_dir / "webview" / "assets").glob("*.js")
              if not p.name.endswith(".map") and "__codexOrbitSidebarV4" in p.read_text(encoding="utf-8", errors="ignore")), None)
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
    # Strict-check the status chunk we hooked (an ESM webview chunk — a broken one would break
    # Codex's conversation engine, not just our sidebar). Same strict module parser as the helper.
    if node:
        sc = next((p for p in (ext_dir / "webview" / "assets").glob("*.js")
                   if not p.name.endswith(".map") and "__codexOrbitStatusHook" in p.read_text(encoding="utf-8", errors="ignore")), None)
        if sc:
            rs = subprocess.run([node, "--input-type=module", "--check", "-"],
                                input=sc.read_text(encoding="utf-8", errors="ignore"), capture_output=True, text=True, encoding="utf-8")
            if rs.returncode != 0:
                tail = (rs.stderr or "").strip().splitlines()
                raise RuntimeError(f"Patched status chunk invalid ({sc.name}): {' | '.join(tail[-4:]) if tail else '?'}")
            log("Status chunk syntax check passed; live-status hook confirmed present")
        else:
            log("NOTE live-status hook NOT present (updateConversationState anchor missed) — live status stays best-effort")
        uc = next((p for p in (ext_dir / "webview" / "assets").glob("*.js")
                   if not p.name.endswith(".map") and "__codexOrbitUsageRows" in p.read_text(encoding="utf-8", errors="ignore")), None)
        if uc:
            ru = subprocess.run([node, "--input-type=module", "--check", "-"],
                                input=uc.read_text(encoding="utf-8", errors="ignore"), capture_output=True, text=True, encoding="utf-8")
            if ru.returncode != 0:
                tail = (ru.stderr or "").strip().splitlines()
                raise RuntimeError(f"Patched usage chunk invalid ({uc.name}): {' | '.join(tail[-4:]) if tail else '?'}")
            log("Usage chunk syntax check passed; rate-limit rows hook confirmed present")
        else:
            log("NOTE usage rows hook NOT present — usage popup falls back to tray/message data")


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
    p.add_argument("--disable", default="", help="comma-separated gateable feature ids to leave OUT")
    p.add_argument("--enable", default="", help="comma-separated gateable feature ids to apply (others off)")
    a = p.parse_args()
    global ENABLED_FEATURES
    if a.enable.strip():
        ENABLED_FEATURES = {x.strip() for x in a.enable.split(",") if x.strip()}
    elif a.disable.strip():
        disabled = {x.strip() for x in a.disable.split(",") if x.strip()}
        ENABLED_FEATURES = GATEABLE_FEATURES - disabled
    LOG_PATH = Path(a.log).expanduser().resolve(); LOG_PATH.write_text("", encoding="utf-8")
    log(f"Codex Orbit sidebar patcher v{__version__} (patcher-version {a.patcher_version})")
    if ENABLED_FEATURES is not None:
        off = sorted(GATEABLE_FEATURES - ENABLED_FEATURES)
        if off: log(f"Patches disabled: {', '.join(off)}")
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
