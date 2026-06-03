# Codex Orbit — Sidebar Feature Parity Plan

Goal: our sidebar should mirror Codex's native sidebar — settings menu, filter, per-row
actions (star/pin/color/archive), and status-colored dots — but rendered by OUR UI and,
where possible, calling Codex's OWN functions.

Findings below are reverse-engineered from Codex's bundle
(`stable/codex_assets/webview/assets/` + the full clean copy under `.tmp/`). The headline:
**two of these features don't exist natively the way they appear**, so we own them.

## Transport: the host channel
Everything that "calls Codex's function" goes through the VS Code host via
`acquireVsCodeApi().postMessage({...payload, type})`. `acquireVsCodeApi()` can be called
only once per webview and Codex already called it, so we **tee Codex's instance** into a
global (`window.__codexOrbitPost`) by patching the setting-storage chunk where
`acquireVsCodeApi()` is assigned. Confirmed pattern: `dispatchMessage(type,payload){ lr.postMessage({...payload,type}) }`.

## 1. Settings menu (gear button, next to Search)
Codex's gear items. We render only the ones wired to a REAL `run-command` id (via the host
channel `coxPost("run-command",{id})`): Account & usage, Switch model, Switch account,
Custom instructions, Color theme.
- **YOLO mode + Chat preview header REMOVED (v0.5.23):** their command ids/state are not in
  our bundled baseline, so they were dead placeholder buttons — subtracted (better absent
  than lying). Re-add once we capture the running build's exact ids.
- **Caveat (honest):** the flyout is from a NEWER Codex than our baseline, so a few of the
  5 ids are best-known/derived; a miss is a harmless no-op. `codexOrbitDump().hostChannel`
  reports whether the channel is live so ids are tunable. **Status: 5 real items, best-effort.**

## 2. Filter menu (filter button)
TYPE: Pinned, Starred, Running, Waiting · AGE: 1h/24h/7d/30d. (Untitled filter dropped in
v0.5.23 — Codex auto-titles every chat, so it had no job.) Implemented in OUR render()
over data we already hold — no native dependency:
- Pinned = our pin set. Starred = our star set.
- Running = derived status `running`; Waiting = derived status `waiting` (see #5; reliable
  for remote tasks which carry status inline, best-effort for local).
- Age = `now - (updatedAt ?? createdAt)` ≤ bucket (remote ts is seconds → ×1000).
**Status: fully ours, shippable.**

## 2b. Archived section (v0.5.23)
Archived chats drop into a collapsible "Archived" group at the bottom (Codex's native
layout), not removed. Archive action toggles (archive ⇄ unarchive). `codexOrbitArchivedV4`
holds our local set; `archive-conversation` / `unarchive-conversation` posted best-effort.

## 3. Per-chat color (the swatch palette)
**Truth: Codex's color feature is DORMANT** — the storage field `sidebar-thread-metadata[id].labelColor`
exists and the rename dialog has color props, but there is NO palette, NO setter, and the
row never renders the color. So there is nothing to "call."
- We own it: a palette popup (clear + 6 colors), persisted locally (`codexOrbitColorsV4`),
  rendered as a left-border tint on our row. We define the 6 colors.
**Status: fully ours, shippable.**

## 4. Per-row hover toolbar: star · pin · color · archive
Icons appear on row hover (we already had these in the right-click menu).
- **Pin:** real native command `set-thread-pinned {params:{threadId,pinned}}`. We keep our
  local pin for instant UI; optionally mirror to native. (Native pin = server list, not a
  title hack.)
- **Star:** **no native star exists** — `star-*.js` is just an icon. Ours, local. Keep.
- **Color:** see #3 (ours).
- **Archive:** real native command `archive-conversation {conversationId}` (our history
  patch already uses it). Wire via host channel + optimistic row removal.
**Status: star/pin/color ours; archive native — shippable once host channel is in.**

## 5. Status dots (gray → blue/orange/red)
Codex derives one status string and maps to a tone:
`running→blue (info)`, `waiting→orange (warning)`, `failed→red (danger)`, `review→green`,
`idle→gray`.
- **Remote tasks** carry it inline: `task_status_display.latest_turn_status_display.turn_status`
  (`in_progress`/`pending`→running, `failed`/`cancelled`→failed) + `has_unread_turn`→review.
- **Local chats:** status lives in live Jotai atoms (`threadRuntimeStatus.type` ∈
  `notLoaded|idle|active|systemError` + `activeFlags` waitingOnApproval/UserInput + latest
  turn status), NOT on the wire list we intercept (we see `{type:"notLoaded"}`). So local
  live status is **not visible from our interception point** without reading atoms.
- We implement the full color mapping over whatever status we CAN read (remote inline +
  any `status.type` present). Gray default otherwise.
**Status: mapping shippable; local live updates are data-limited (documented gap).**

## Color palette (ours, since Codex ships none)
none(clear) · red #e5484d · orange #f5a524 · yellow #f5d90a · green #30a46c · blue #3b82f6 · purple #8b5cf6
