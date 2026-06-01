import{Jr as e,ai as t,ci as n,hi as r,li as i,mi as a,ni as o}from"./src-E5Oyj7ej.js";import{Ji as s}from"./app-server-manager-signals-DRv4QdiA.js";function c(e){return Math.max(0,-e.scrollTop)}function l(e,t){let n=Math.max(0,t);e.scrollTop=n===0?0:-n}var u={reviewFileExpanded:`data-app-action-review-file-expanded`,reviewFileToggle:`data-app-action-review-file-toggle`,reviewPath:`data-review-path`,reviewScroll:`data-app-action-review-scroll`,sidebarProjectCollapsed:`data-app-action-sidebar-project-collapsed`,sidebarProjectId:`data-app-action-sidebar-project-id`,sidebarProjectLabel:`data-app-action-sidebar-project-label`,sidebarProjectListId:`data-app-action-sidebar-project-list-id`,sidebarProjectRow:`data-app-action-sidebar-project-row`,sidebarProjectSelect:`data-app-action-sidebar-select-project`,sidebarProjectShowAll:`data-app-action-sidebar-project-show-all`,sidebarProjectShowAllToggle:`data-app-action-sidebar-project-show-all-toggle`,sidebarScroll:`data-app-action-sidebar-scroll`,sidebarSection:`data-app-action-sidebar-section`,sidebarSectionCollapsed:`data-app-action-sidebar-section-collapsed`,sidebarSectionHeading:`data-app-action-sidebar-section-heading`,sidebarSectionToggle:`data-app-action-sidebar-section-toggle`,sidebarThreadActive:`data-app-action-sidebar-thread-active`,sidebarThreadHostId:`data-app-action-sidebar-thread-host-id`,sidebarThreadId:`data-app-action-sidebar-thread-id`,sidebarThreadKind:`data-app-action-sidebar-thread-kind`,sidebarThreadPinned:`data-app-action-sidebar-thread-pinned`,sidebarThreadRow:`data-app-action-sidebar-thread-row`,sidebarThreadTitle:`data-app-action-sidebar-thread-title`,timelineScroll:`data-app-action-timeline-scroll`},d={reviewFile:`[${u.reviewPath}]`,reviewFileToggle:`[${u.reviewFileToggle}]`,reviewScroll:`[${u.reviewScroll}]`,sidebarProjectList:e=>`[${u.sidebarProjectListId}="${CSS.escape(e)}"]`,sidebarProjectRow:`[${u.sidebarProjectRow}]`,sidebarProjectSelect:`[${u.sidebarProjectSelect}]`,sidebarProjectShowAllToggle:`[${u.sidebarProjectShowAllToggle}]`,sidebarScroll:`[${u.sidebarScroll}]`,sidebarSection:`[${u.sidebarSection}]`,sidebarSectionToggle:`[${u.sidebarSectionToggle}]`,sidebarThreadRow:`[${u.sidebarThreadRow}]`,timelineScroll:`[${u.timelineScroll}]`,timelineTurn:`[data-content-search-turn-key]`},f=[d.sidebarSection,d.sidebarProjectRow,d.sidebarThreadRow].join(`,`),p={reviewFile:e=>({[u.reviewPath]:e}),reviewFileToggle:e=>({[u.reviewFileExpanded]:String(e),[u.reviewFileToggle]:``}),reviewScroll:{[u.reviewScroll]:``},sidebarProjectList:({projectId:e,showAll:t})=>({[u.sidebarProjectListId]:e,[u.sidebarProjectShowAll]:String(t)}),sidebarProjectRow:({collapsed:e,label:t,projectId:n})=>({[u.sidebarProjectCollapsed]:String(e),[u.sidebarProjectId]:n,[u.sidebarProjectLabel]:t,[u.sidebarProjectRow]:``}),sidebarProjectSelect:{[u.sidebarProjectSelect]:``},sidebarProjectShowAllToggle:{[u.sidebarProjectShowAllToggle]:``},sidebarScroll:{[u.sidebarScroll]:``},sidebarSection:({collapsed:e,heading:t})=>({[u.sidebarSection]:``,[u.sidebarSectionCollapsed]:String(e),[u.sidebarSectionHeading]:t}),sidebarSectionToggle:{[u.sidebarSectionToggle]:``},sidebarThreadRow:({active:e,hostId:t,id:n,kind:r,pinned:i,title:a})=>({[u.sidebarThreadActive]:String(e),[u.sidebarThreadHostId]:t??``,[u.sidebarThreadId]:n,[u.sidebarThreadKind]:r,[u.sidebarThreadPinned]:String(i),[u.sidebarThreadRow]:``,[u.sidebarThreadTitle]:a,"data-vscode-context":JSON.stringify({codexTask:!0,webviewSection:`codex-task`,codexThreadId:n,codexThreadTitle:a,codexStarred:String(a??``).trim().startsWith(`⭐ `),codexPinned:String(a??``).trim().replace(/^⭐\s*/,``).startsWith(`📌 `),preventDefaultContextMenuItems:!0})}),timelineScroll:{[u.timelineScroll]:``}},m=`current`,h=t(m),g=o(`type`,[i({type:t(`pixels`),y:n()}),i({type:t(`pages`),count:n()}),i({type:t(`edge`),edge:e([`top`,`bottom`])})]),_=e([`previous`,`next`]),v=r([i({heading:a()}),i({ordinal:n().int().nonnegative()})]),y=r([i({projectId:a()}),i({label:a()}),i({ordinal:n().int().nonnegative()})]);function b(e){let t=document.querySelector(e);if(t==null)throw Error(`Missing app action target: ${e}`);return t}function x(e,t,n={}){switch(t.type){case`pixels`:e.scrollBy({top:t.y,behavior:`auto`});return;case`pages`:e.scrollBy({top:e.clientHeight*t.count,behavior:`auto`});return;case`edge`:if(n.isReversed){l(e,t.edge===`bottom`?0:e.scrollHeight);return}e.scrollTo({top:t.edge===`top`?0:e.scrollHeight,behavior:`auto`});return}}function S(e){let t=Array.from(document.querySelectorAll(d.sidebarSection));if(`ordinal`in e){let n=t[e.ordinal];if(n==null)throw Error(`Missing sidebar section at ordinal ${e.ordinal}`);return n}let n=t.filter(t=>(t.dataset.appActionSidebarSectionHeading??``)===e.heading);if(n.length===0)throw Error(`Missing sidebar section: ${e.heading}`);if(n.length>1)throw Error(`Ambiguous sidebar section: ${e.heading}`);return n[0]}function C(e){let t=Array.from(document.querySelectorAll(d.sidebarProjectRow));if(`ordinal`in e){let n=t[e.ordinal];if(n==null)throw Error(`Missing sidebar project at ordinal ${e.ordinal}`);return n}let n=t.filter(t=>`projectId`in e?t.dataset.appActionSidebarProjectId===e.projectId:t.dataset.appActionSidebarProjectLabel===e.label);if(n.length===0)throw Error(`projectId`in e?`Missing sidebar project: ${e.projectId}`:`Missing sidebar project: ${e.label}`);if(n.length>1)throw Error(`projectId`in e?`Ambiguous sidebar project: ${e.projectId}`:`Ambiguous sidebar project: ${e.label}`);return n[0]}function w(e,t){if(t.type===`edge`){x(e,t,{isReversed:!0});return}l(e,c(e)-(t.type===`pixels`?t.y:e.clientHeight*t.count))}function T(e,t){let n=O(e,t);if(n==null){w(e,{type:`edge`,edge:t===`previous`?`top`:`bottom`});return}let r=e.getBoundingClientRect(),i=n.getBoundingClientRect(),a=c(e)+(r.bottom-i.bottom);l(e,t===`previous`?Math.max(0,a-e.clientHeight+i.height):Math.max(0,a))}function E(e){let t=s(e),n=Array.from(document.querySelectorAll(d.reviewFile)),r=n.find(e=>s(e.dataset.reviewPath??``)===t)??null;if(r!=null)return r;let i=n.filter(e=>{let n=s(e.dataset.reviewPath??``);return n.endsWith(`/${t}`)||t.endsWith(`/${n}`)});if(i.length===1)return i[0];let a=n.map(e=>e.dataset.reviewPath).filter(e=>e!=null);throw i.length>1?Error(`Ambiguous review file row: ${e}\nAvailable review paths:\n${a.join(`
`)}`):Error(`Missing review file row: ${e}\nAvailable review paths:\n${a.join(`
`)}`)}function D(e){return d.sidebarProjectList(e)}function O(e,t){let n=e.getBoundingClientRect(),r=Array.from(e.querySelectorAll(d.timelineTurn)),i=null;for(let e of r){let r=e.getBoundingClientRect();if(t===`previous`){if(r.top>=n.top-1)continue;(i==null||r.top>i.getBoundingClientRect().top)&&(i=e);continue}r.bottom<=n.bottom+1||(i==null||r.bottom<i.getBoundingClientRect().bottom)&&(i=e)}return i}export{f as _,C as a,x as c,y as d,v as f,d as g,p as h,E as i,w as l,g as m,h as n,D as o,_ as p,b as r,S as s,m as t,T as u,c as v,l as y};
//# sourceMappingURL=window-app-action-helpers-CuuVVkGv-codexpatch.js.map
;(function(){try{if(typeof document==="undefined"||window.__codexTaskContextBridgeV5)return;window.__codexTaskContextBridgeV5=!0;let l="",u=0;function c(e){let t=e.getAttribute(`data-app-action-sidebar-thread-id`)||``;if(!t)return null;let n=(e.getAttribute(`data-app-action-sidebar-thread-title`)||e.textContent||``).trim(),a=n.replace(/^⭐\s*/,``),r={codexTask:!0,webviewSection:`codex-task`,codexThreadId:t,codexThreadTitle:n,codexStarred:n.startsWith(`⭐ `),codexPinned:a.startsWith(`📌 `),preventDefaultContextMenuItems:!0},o=JSON.stringify(r);e.setAttribute(`data-vscode-context`,o);for(let i of e.querySelectorAll(`*`))i.setAttribute(`data-vscode-context`,o);window.__codexLastTaskContext=r;return r}function p(){return window.__codexLastTaskContext||c(document.querySelector(`[data-app-action-sidebar-thread-row]:hover`))||c(document.querySelector(`[data-app-action-sidebar-thread-row]`))}function d(e,t){if(!t||typeof window.__codexPostMessage!="function")return;let n=Date.now();if(!e||e!==l||n-u>500){l=e,u=n;window.__codexPostMessage(`codex-task-context`,t)}}function s(e){let t=e&&e.target;if(t instanceof Element){let e=t.closest(`[data-app-action-sidebar-thread-row]`);if(e){let t=c(e);t&&d(t.codexThreadId,t)}}}function i(){document.querySelectorAll(`[data-app-action-sidebar-thread-row]`).forEach(c)}window.addEventListener(`message`,function(e){let t=e&&e.data;if(t&&t.type===`codex-request-task-context`){let e=p();typeof window.__codexPostMessage=="function"&&window.__codexPostMessage(`codex-task-context-response`,{...(e||{}),requestId:t.requestId})}},!0);document.addEventListener(`pointerover`,s,!0);document.addEventListener(`mousemove`,s,!0);document.addEventListener(`pointerdown`,s,!0);document.addEventListener(`contextmenu`,s,!0);new MutationObserver(i).observe(document.documentElement,{childList:!0,subtree:!0,attributes:!0,attributeFilter:[`data-app-action-sidebar-thread-id`,`data-app-action-sidebar-thread-title`]});setTimeout(i,0),setTimeout(i,250),setTimeout(i,1000)}catch(e){console.warn(`codex task context bridge failed`,e)}})();
;(() => {
  try {
    if (typeof window === "undefined" || typeof document === "undefined" || window.__codexOrbitSidebarV1) return;
    window.__codexOrbitSidebarV1 = true;

    const COLLAPSED_KEY = "codexOrbitSidebarCollapsed";
    const GROUP_KEY = "codexOrbitSidebarGroupState";
    const OPEN_WIDTH = 360;
    const CLOSED_WIDTH = 38;
    let shell = null;
    let nativeSource = null;
    let collapsed = false;
    let searchText = "";
    let groupState = Object.create(null);

    try {
      collapsed = localStorage.getItem(COLLAPSED_KEY) === "true";
      groupState = JSON.parse(localStorage.getItem(GROUP_KEY) || "{}") || Object.create(null);
    } catch {}

    const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

    function ensureStyle() {
      if (document.getElementById("codexOrbitSidebarStyle")) return;
      const style = document.createElement("style");
      style.id = "codexOrbitSidebarStyle";
      style.textContent = `
        :root{--codex-orbit-sidebar-open:${OPEN_WIDTH}px;--codex-orbit-sidebar-closed:${CLOSED_WIDTH}px}
        .codexOrbitNativeSource{display:none!important}
        .codexOrbitSidebar{position:fixed;top:34px;right:0;bottom:0;width:var(--codex-orbit-sidebar-open);z-index:2147482000;display:flex;flex-direction:column;background:var(--vscode-sideBar-background,#171717);color:var(--vscode-sideBar-foreground,var(--vscode-foreground,#d4d4d4));border-left:1px solid var(--vscode-sideBar-border,var(--vscode-panel-border,#2b2b2b));box-shadow:-18px 0 30px rgba(0,0,0,.16);font-family:var(--vscode-font-family,ui-sans-serif,system-ui,sans-serif);font-size:12px;transition:width .16s ease}
        .codexOrbitSidebar *{box-sizing:border-box}
        .codexOrbitSidebarHeader{height:40px;display:flex;align-items:center;gap:8px;padding:0 10px;border-bottom:1px solid var(--vscode-sideBar-border,var(--vscode-panel-border,#282828))}
        .codexOrbitSidebarTitle{min-width:0;flex:1;font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--vscode-descriptionForeground,#9d9d9d);text-transform:uppercase}
        .codexOrbitCount{min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;border-radius:9px;background:var(--vscode-badge-background,#3a3a3a);color:var(--vscode-badge-foreground,#fff);font-size:10px}
        .codexOrbitIconButton{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:5px;background:transparent;color:var(--vscode-icon-foreground,#b8b8b8);cursor:pointer}
        .codexOrbitIconButton:hover{background:var(--vscode-toolbar-hoverBackground,rgba(255,255,255,.08));color:var(--vscode-foreground,#fff)}
        .codexOrbitNew{height:26px;margin:8px 10px 6px;border:1px solid var(--vscode-button-border,transparent);border-radius:5px;background:var(--vscode-button-secondaryBackground,#252525);color:var(--vscode-button-secondaryForeground,#d8d8d8);font-size:12px;font-weight:600;cursor:pointer}
        .codexOrbitNew:hover{background:var(--vscode-button-secondaryHoverBackground,#303030)}
        .codexOrbitSearchWrap{position:relative;margin:0 10px 8px}
        .codexOrbitSearch{width:100%;height:28px;border:1px solid var(--vscode-input-border,transparent);border-radius:5px;background:var(--vscode-input-background,#1f1f1f);color:var(--vscode-input-foreground,#ddd);padding:0 8px 0 24px;font:inherit;outline:none}
        .codexOrbitSearch:focus{border-color:var(--vscode-focusBorder,#4d8dff)}
        .codexOrbitSearchMark{position:absolute;left:8px;top:7px;color:var(--vscode-descriptionForeground,#858585);pointer-events:none}
        .codexOrbitList{flex:1;min-height:0;overflow:auto;padding:0 8px 12px;scrollbar-gutter:stable}
        .codexOrbitGroup{margin-top:8px}
        .codexOrbitGroupButton{width:100%;height:24px;display:flex;align-items:center;gap:6px;border:0;background:transparent;color:var(--vscode-descriptionForeground,#9a9a9a);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;cursor:pointer}
        .codexOrbitGroupButton:hover{color:var(--vscode-foreground,#ddd)}
        .codexOrbitGroupName{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
        .codexOrbitRow{width:100%;height:28px;display:flex;align-items:center;gap:7px;border:0;border-radius:5px;background:transparent;color:var(--vscode-foreground,#d4d4d4);cursor:pointer;padding:0 7px;text-align:left}
        .codexOrbitRow:hover{background:var(--vscode-list-hoverBackground,rgba(255,255,255,.07))}
        .codexOrbitRow.isActive{background:var(--vscode-list-activeSelectionBackground,#37373d);color:var(--vscode-list-activeSelectionForeground,#fff)}
        .codexOrbitPin{width:10px;flex:0 0 10px;color:var(--vscode-descriptionForeground,#8a8a8a);text-align:center}
        .codexOrbitRowTitle{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .codexOrbitKind{max-width:78px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--vscode-descriptionForeground,#8f8f8f);font-size:11px}
        .codexOrbitEmpty{margin:24px 12px;color:var(--vscode-descriptionForeground,#969696);line-height:1.45;text-align:center}
        .codexOrbitSidebarOpen body{padding-right:var(--codex-orbit-sidebar-open)!important}
        .codexOrbitSidebarCollapsed body{padding-right:var(--codex-orbit-sidebar-closed)!important}
        .codexOrbitSidebarCollapsed .codexOrbitSidebar{width:var(--codex-orbit-sidebar-closed)}
        .codexOrbitSidebarCollapsed .codexOrbitSidebarTitle,.codexOrbitSidebarCollapsed .codexOrbitCount,.codexOrbitSidebarCollapsed .codexOrbitNew,.codexOrbitSidebarCollapsed .codexOrbitSearchWrap,.codexOrbitSidebarCollapsed .codexOrbitList{display:none}
        .codexOrbitSidebarCollapsed .codexOrbitSidebarHeader{padding:0 7px;justify-content:center;border-bottom:0}
        .codexOrbitSidebarCollapsed .codexOrbitIconButton:not(.codexOrbitCollapse){display:none}
        @media(max-width:760px){.codexOrbitSidebarOpen body{padding-right:0!important}.codexOrbitSidebar{top:40px;width:min(86vw,var(--codex-orbit-sidebar-open));transform:translateX(calc(100% - var(--codex-orbit-sidebar-closed)))}.codexOrbitSidebar:hover{transform:translateX(0)}.codexOrbitSidebar:not(:hover){width:var(--codex-orbit-sidebar-closed)}.codexOrbitSidebar:not(:hover) .codexOrbitSidebarTitle,.codexOrbitSidebar:not(:hover) .codexOrbitCount,.codexOrbitSidebar:not(:hover) .codexOrbitNew,.codexOrbitSidebar:not(:hover) .codexOrbitSearchWrap,.codexOrbitSidebar:not(:hover) .codexOrbitList{display:none}}
      `;
      document.head.appendChild(style);
    }

    function syncChrome() {
      document.documentElement.classList.add("codexOrbitSidebarOpen");
      document.documentElement.classList.toggle("codexOrbitSidebarCollapsed", collapsed);
      try { localStorage.setItem(COLLAPSED_KEY, String(collapsed)); } catch {}
    }

    function findNewButton() {
      const selectors = [
        'button[aria-label*="New" i]',
        'button[title*="New" i]',
        'a[aria-label*="New" i]',
        '[data-testid*="new" i]'
      ];
      for (const selector of selectors) {
        const found = document.querySelector(selector);
        if (found && typeof found.click === "function") return found;
      }
      return null;
    }

    function ensureShell() {
      ensureStyle();
      if (shell) return shell;
      shell = document.createElement("aside");
      shell.className = "codexOrbitSidebar";
      shell.setAttribute("aria-label", "Codex Orbit workspace chats");
      shell.innerHTML = `
        <div class="codexOrbitSidebarHeader">
          <div class="codexOrbitSidebarTitle">Sessions</div>
          <span class="codexOrbitCount">0</span>
          <button class="codexOrbitIconButton codexOrbitRefresh" type="button" title="Refresh">R</button>
          <button class="codexOrbitIconButton codexOrbitCollapse" type="button" title="Collapse sidebar">&lt;</button>
        </div>
        <button class="codexOrbitNew" type="button">New Session</button>
        <div class="codexOrbitSearchWrap">
          <span class="codexOrbitSearchMark">?</span>
          <input class="codexOrbitSearch" type="search" placeholder="Search workspace chats" aria-label="Search workspace chats">
        </div>
        <div class="codexOrbitList" role="list"></div>
      `;
      document.body.appendChild(shell);
      shell.querySelector(".codexOrbitSearch")?.addEventListener("input", (event) => {
        searchText = event.target.value || "";
        render();
      });
      shell.querySelector(".codexOrbitCollapse")?.addEventListener("click", () => {
        collapsed = !collapsed;
        syncChrome();
      });
      shell.querySelector(".codexOrbitRefresh")?.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("open-recent-tasks-menu"));
        setTimeout(render, 160);
      });
      shell.querySelector(".codexOrbitNew")?.addEventListener("click", () => {
        const button = findNewButton();
        if (button) button.click();
      });
      syncChrome();
      return shell;
    }

    function sourceCandidates() {
      return Array.from(document.querySelectorAll("div.overscroll-contain"))
        .filter((element) => element.querySelector("[data-app-action-sidebar-thread-row]"))
        .sort((left, right) =>
          right.querySelectorAll("[data-app-action-sidebar-thread-row]").length -
          left.querySelectorAll("[data-app-action-sidebar-thread-row]").length
        );
    }

    function findSource() {
      const source = sourceCandidates()[0];
      if (!source) return nativeSource;
      if (nativeSource && nativeSource !== source) nativeSource.classList.remove("codexOrbitNativeSource");
      nativeSource = source;
      nativeSource.classList.add("codexOrbitNativeSource");
      return nativeSource;
    }

    function rowTitle(row) {
      return clean(row.getAttribute("data-app-action-sidebar-thread-title")) ||
        clean(row.querySelector("[data-app-action-sidebar-thread-title]")?.textContent) ||
        clean(row.textContent) ||
        "Untitled";
    }

    function collectRows() {
      const source = findSource();
      const rows = [];
      if (!source) return rows;
      const seen = new Set();
      let group = "Workspace";
      source.querySelectorAll("[data-codex-workspace-header],[data-app-action-sidebar-thread-row]").forEach((element) => {
        if (element.matches("[data-codex-workspace-header]")) {
          group = clean(element.textContent) || "Workspace";
          return;
        }
        if (!element.matches("[data-app-action-sidebar-thread-row]")) return;
        const id = element.getAttribute("data-app-action-sidebar-thread-id") || `${rowTitle(element)}-${rows.length}`;
        if (seen.has(id)) return;
        seen.add(id);
        rows.push({
          id,
          title: rowTitle(element),
          kind: clean(element.getAttribute("data-app-action-sidebar-thread-kind")),
          host: clean(element.getAttribute("data-app-action-sidebar-thread-host-id")),
          pinned: element.getAttribute("data-app-action-sidebar-thread-pinned") === "true",
          active: element.getAttribute("data-app-action-sidebar-thread-active") === "true",
          group,
          element
        });
      });
      return rows;
    }

    function makeButton(className) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      return button;
    }

    function render() {
      const sidebar = ensureShell();
      const list = sidebar.querySelector(".codexOrbitList");
      const source = findSource();
      const needle = searchText.toLowerCase();
      const rows = collectRows().filter((row) =>
        !needle || `${row.title} ${row.group} ${row.kind}`.toLowerCase().includes(needle)
      );
      sidebar.querySelector(".codexOrbitCount").textContent = String(rows.length);
      list.textContent = "";

      if (!source) {
        const empty = document.createElement("div");
        empty.className = "codexOrbitEmpty";
        empty.textContent = "Open Codex home to load workspace chats.";
        list.appendChild(empty);
        return;
      }
      if (!rows.length) {
        const empty = document.createElement("div");
        empty.className = "codexOrbitEmpty";
        empty.textContent = searchText ? "No matching workspace chats." : "No chats for this workspace yet.";
        list.appendChild(empty);
        return;
      }

      const groups = [];
      for (const row of rows) {
        let group = groups.find((item) => item.name === row.group);
        if (!group) {
          group = { name: row.group, rows: [] };
          groups.push(group);
        }
        group.rows.push(row);
      }

      for (const group of groups) {
        const section = document.createElement("section");
        section.className = "codexOrbitGroup";
        const groupButton = makeButton("codexOrbitGroupButton");
        const icon = document.createElement("span");
        const label = document.createElement("span");
        const count = document.createElement("span");
        icon.textContent = groupState[group.name] === false ? "+" : "-";
        label.className = "codexOrbitGroupName";
        label.textContent = group.name;
        count.textContent = String(group.rows.length);
        groupButton.append(icon, label, count);
        groupButton.addEventListener("click", () => {
          groupState[group.name] = groupState[group.name] === false;
          try { localStorage.setItem(GROUP_KEY, JSON.stringify(groupState)); } catch {}
          render();
        });
        section.appendChild(groupButton);

        if (groupState[group.name] !== false) {
          for (const row of group.rows) {
            const button = makeButton(`codexOrbitRow${row.active ? " isActive" : ""}`);
            const pin = document.createElement("span");
            const title = document.createElement("span");
            const kind = document.createElement("span");
            pin.className = "codexOrbitPin";
            pin.textContent = row.pinned ? "*" : "";
            title.className = "codexOrbitRowTitle";
            title.textContent = row.title;
            kind.className = "codexOrbitKind";
            kind.textContent = row.kind && row.kind !== "local" ? row.kind : "";
            button.title = row.title;
            button.append(pin, title, kind);
            button.addEventListener("click", () => row.element.click());
            button.addEventListener("contextmenu", (event) => {
              event.preventDefault();
              row.element.dispatchEvent(new MouseEvent("contextmenu", {
                bubbles: true,
                cancelable: true,
                clientX: event.clientX,
                clientY: event.clientY
              }));
            });
            section.appendChild(button);
          }
        }
        list.appendChild(section);
      }
    }

    function start() {
      if (!document.body) {
        setTimeout(start, 50);
        return;
      }
      ensureShell();
      render();
      let timer = null;
      new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(render, 120);
      }).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: [
          "data-app-action-sidebar-thread-title",
          "data-app-action-sidebar-thread-active",
          "data-app-action-sidebar-thread-pinned"
        ]
      });
      window.addEventListener("focus", () => setTimeout(render, 80));
      document.addEventListener("visibilitychange", () => setTimeout(render, 80));
    }

    start();
  } catch (error) {
    console.warn("Codex Orbit sidebar failed", error);
  }
})();
