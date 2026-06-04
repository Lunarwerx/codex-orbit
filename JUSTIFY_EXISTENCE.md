# Codex Orbit Justification Notes

## Stable Asset Baseline

**Files:** `stable/patch_codex.py`, `stable/codex_assets/**`

Codex Orbit currently patches `openai.chatgpt` by replaying a verified patched
asset baseline for Codex `26.5519.32039`. This is intentional. The previous
dynamic patcher was built for another extension's bundle shape, while the Codex
patches already exist as known-good minified assets. Copying the verified files
keeps the first Codex reboot deterministic and easy to verify.

The patcher fails closed when the target Codex version differs from
`SUPPORTED_VERSION`. That prevents a mismatched asset bundle from being written
over a newer OpenAI release.

## Installed Patch Marker

**Files:** `stable/patch_codex.py`, `Codex Orbit/extension.js`

The patcher writes `extension/codex-orbit-patch.json` into the patched Codex
VSIX. The wrapper reads this marker to decide whether Codex is stock, patched,
or outdated. This replaces webview-string detection and gives Codex Orbit a
clear patch identity independent of minified bundle contents.

## Build Path

**File:** `build.py`

The Codex build bundles only the wrapper, `stable/patch_codex.py`, and
`stable/codex_assets/**`. The previous rollback archive path was removed from
the build because the archived patchers target a different upstream extension
and should not be offered inside Codex Orbit.

## Stable Version Pin

**Files:** `stable_version.txt`, `stable/stable_version.txt`

The stable pin is `26.5519.32039`, matching the bundled asset baseline. It
should move only when a new stock Codex VSIX has been patched, verified, and
promoted into `stable/codex_assets`.

## Dynamic Patcher (supersedes asset-replay)

**Files:** `stable/patch_codex.py`, `tools/gen_patch_spec.py`,
`tools/build_dynamic_patcher.py`, `tools/emit_patcher.py`

`stable/patch_codex.py` is now a **self-contained dynamic patcher**, replacing the
asset-replay version. **Job:** make "Install newest" pull the newest Codex and
patch it — like Claude Code Orbit. **Why vs. rejected:** asset-replay copied
pre-captured minified files for ONE Codex build; Codex's webview asset filenames
change every release, and the OTA loader ships only a single `.py` (no
`codex_assets/` folder), so asset-replay produced both "Add a new baseline" and
"Missing bundled Codex assets" failures. The dynamic patcher embeds the patch as
anchored edits (gzip+base64) extracted from the verified baseline, locates each
target file by content, applies what matches and **skips drifted anchors** rather
than crashing — so a Codex always installs and gaps close via patcher pushes (no
VSIX reinstall). **Primitive:** keeps the `copy_patched_assets` function name the
Orbit wrapper's OTA loader requires as its accept marker. **Correctness gate:**
reproduces `stable/codex_assets` byte-for-byte (modulo line endings) from stock
26.5519; verified valid (`node --check`) on newest 26.5527. **Debt:** ~11
version-specific edits (history wiring, host command registration, header) anchor
on minified locals that drift; these need semantic re-anchoring + identifier
capture (Claude Code Orbit's `_capture_*` pattern) — tracked, closed via pushes.

## Version Picker (no "stable vs experimental")

**Files:** `patchers/manifest.json`, `build.py`, `Codex Orbit/extension.js`

Codex Orbit follows the Claude Code Orbit model: one list of verified
(patcher, Codex) baselines, all equally "stable", and the user flips to a
previous one if the newest misbehaves. There is no separate experimental mode.

- `patchers/manifest.json` is the rollback registry the "Previous versions"
  picker reads. `build.py` bundles `patchers/**` into the VSIX so the picker
  works offline from first install. Each entry is `{version, codex, file,
  build}`; today there is one baseline (patcher `0.3.1` → Codex `26.5519.32039`).
- `enablePrevious()` installs the bundled baseline by reusing the bundled
  `stable/patch_codex.py` (which carries its `codex_assets`) when
  `entry.codex === stable pin` — one source of truth, no duplicated asset tree.
  Self-contained archived patchers (future baselines) still load from
  `patchers/<file>`.
- `enable()` ("Install newest") now pins `--version` to the newest baseline we
  have assets for instead of the Marketplace's newest. **Why:** the asset-replay
  patcher fails closed on any unverified Codex, so chasing the Marketplace newest
  guaranteed a broken install once OpenAI shipped past the baseline. A newer
  Codex is surfaced as info, never patched blind.

**Debt to grow the list:** because the patcher is asset-replay (not a dynamic
patcher like Claude Code Orbit's), each new Codex version in the picker needs its
own captured baseline via RELEASE_RULES "Promoting A New Codex Version". A
dynamic Codex patcher would remove that per-version cost and give full version
parity with Claude Code Orbit.

## Icon Canvas Trim

**File:** `Codex Orbit/media/codex-orbit.png`

The shipped logo is a 1254×1254 PNG whose glyph fills the full canvas width
(content fill 100%×74%, natural aspect preserved). **Job:** render at the same
visual size as sibling icons in the activity bar and the webview hero. **Why vs.
rejected:** the prior canvas baked ~40% transparent vertical padding (60% height
fill), so it rendered tiny next to the 95–100%-fill recommendation icons; CSS
`object-fit` can't recover this because transparent pixels count as image
content, so the source PNG is the only place to fix it. **Primitive:** the single
`media/codex-orbit.png` reused for the package icon, activity-bar container icon,
and webview logo — one asset, all three usages corrected at once. (Author-supplied
artwork; do not re-crop programmatically — it's manually tuned.) No version bump;
VSIX rebuilt as build #5.

## Strict-Module Syntax Gate + Dead Settings-Panel Removal (v0.5.14)

**Files:** `stable/patch_codex.py`

**Symptom:** the patched webview helper threw `Uncaught SyntaxError: Unexpected
token '*'` at runtime. **Root cause:** the injected `SIDEBAR_IIFE` carried a dead
inline settings-panel block (`showSettingsPanel`/`hideSettingsPanel`) that had been
disabled by a `/* … */` wrap; an edit lost the opening `/*` but left the closing
`*/`, so the block became live code followed by an orphaned comment-close — invalid
in an ES module.

- **Subtract, not patch.** The block was 100% dead — `showSettingsPanel` was never
  called, `settingsVisible` never read, and `.coxSettingsPane`/`.coxSettingsBody`
  were never created. So the fix is **deletion** of the whole block (and the orphan
  `*/`), not re-adding a `/*` to preserve dead code. One source of truth; nothing
  that shouldn't exist can break again.
- **Why the blade missed it:** `verify()` ran `node --check <file>`. For a file with
  `import`/`export`, Node auto-detects ESM but uses a **lenient** parser that accepts
  an orphaned `*/` (exit 0) — while the webview's V8 module loader rejects it. So a
  broken patch shipped with a green check. **Sharpened:** `verify()` now feeds the
  helper to `node --input-type=module --check -` via stdin (encoding forced to UTF-8
  for the ⭐📌🗑🪲 glyphs), the **same strict module parser the webview runs**. This
  catches orphaned comment-closes and the whole "valid-as-script, invalid-as-module"
  class before the VSIX is ever written. Regression-confirmed: the old broken helper
  now fails the gate at line 422; the rebuilt helper passes.

**Verdict:** live. Justified by the runtime crash it removes and the detection gap it
closes. Bumped patcher `0.5.13 → 0.5.14`, archived to the rollback registry as
build #28.

## Sidebar Click Delegation (v0.5.15)

**Files:** `stable/patch_codex.py`

**Symptom:** right-click → "Open" navigated a chat, but a plain left-click on the
same row did nothing. **Root cause:** the sidebar's `MutationObserver` (watching the
whole document) re-runs `render()` ~constantly as Codex's webview mutates, and
`render()` does `list.textContent=""` then rebuilds every row as a NEW `<button>`.
Per-row `click` listeners died with their buttons: a render landing between mousedown
and mouseup left the two on different elements, so the browser emitted no `click`.
The right-click menu was immune only because `.coxMenu` lives on `document.body`,
outside the re-rendered `.coxList`.

- **Fix the class, not the row.** Every interactive element inside `.coxList` (rows
  AND group headers) had the same defect. So routing moved to **event delegation on
  the persistent `.coxList`** — one `click` + one `contextmenu` listener attached once
  in `ensureShell()`. `.coxList` survives `render()` (only its children are replaced),
  and the browser dispatches `click` to it as the common ancestor even when the inner
  button is swapped mid-gesture, so the whole re-render-eats-the-click class is gone.
- **Primitive:** a `WeakMap` (row `<button>` → thread) set in `addRow`, read by the
  delegated handler; group collapse keyed by a `data-cox-group` attribute. One lookup
  path, no duplicated routing logic. Per-row/per-group listeners deleted.
- **Why vs. rejected:** diffing the list instead of full-rebuild, or pausing the
  observer during a click, both add state and still leave the click on a doomed
  element; delegation is the standard, minimal answer and needs no render rewrite.

**Verdict:** live. Bumped patcher `0.5.14 → 0.5.15`, archived as build #29.

## Render-Storm Fix — the real reason rows wouldn't open (v0.5.16)

**Files:** `stable/patch_codex.py`

v0.5.15's delegation was the right pattern for the wrong model. The true cause:
`start()` observed `document.documentElement` (whole subtree, `childList`), and
`render()` rewrites our own `.coxList` — which is *inside* that subtree. So every
render scheduled the next one **~80ms later, forever**: a self-sustaining storm that
rebuilt the list ~12×/s even at idle. Consequences: (1) a rebuild almost always landed
between a row's `pointerdown` and `mouseup`, and **Chromium fires no `click` when the
mousedown target has been detached** — so delegation had nothing to catch; (2) the
constant full rebuild pegged the webview ("might have crashed").

- **Cut the self-trigger.** The observer now skips mutations where
  `shell.contains(m.target)` — it reacts only to *real* Codex changes, not to its own
  writes. Renders go from 12×/s-forever to rare/on-demand. This is the subtraction
  that matters: the storm simply stops existing.
- **Freeze during the gesture.** `interacting` is set on `pointerdown` in `.coxList`
  (and clears any pending render), released on `pointerup`/`pointercancel`;
  `scheduleRender()` early-returns while set. The pressed row now survives to `mouseup`,
  so a genuine `click` fires and the (kept) delegated handler routes it.
- **Why vs. rejected:** diffing the list or disconnecting the observer per-render are
  heavier and still leave the idle storm's root (self-observation) in place; filtering
  our own subtree out is the one-line removal of the actual cause.

**Verdict:** live. Bumped patcher `0.5.15 → 0.5.16`, archived as build #30. Delegation
(v0.5.15) stays — it is correct *given* the row now survives the gesture.

## Workspace Filtering — path-authoritative (v0.5.17)

**Files:** `stable/patch_codex.py`

The sidebar intercepts Codex's *full* wire thread list (every workspace) and filters
it to the current one. It was leaking other workspaces' chats (Connections, SayDeploy,
…). Ground truth (verified on disk): every Codex session's `rollout-*.jsonl`
`session_meta` carries an absolute `cwd`, and the ~10 active workspaces have distinct
full paths. So workspace identity = the cwd path, and Codex's
`active-workspace-roots[0]` is that path for the open window.

- **Make the path decide, first.** `currentRows` now calls
  `setCurrent(activeRoots[0], …)` before any label/native heuristic, and only falls
  back to the open chat's cwd if roots haven't arrived — an opened cross-workspace chat
  no longer hijacks the filter. `inCurrent` treats any thread that carries a `cwd` as
  decided by PATH alone (exact workspace or a subfolder); the folder-basename / project
  label match that leaked same-named or mislabeled threads is gone, kept only for the
  degenerate case of a thread with no cwd at all.
- **Why vs. rejected:** label/basename matching is inherently ambiguous across
  workspaces; the native-sidebar scope can't help because Codex may list all
  workspaces and DOM rows carry no cwd. The full path is the only unambiguous key, and
  Codex already hands it to us via `active-workspace-roots`.
- **Open risk (tracked):** effectiveness depends on the *wire* thread objects carrying
  `cwd`/`workingDirectory` (the on-disk session has it; the host may or may not forward
  it). `normalizeRaw` already extracts it and the fallbacks prevent an empty list, so
  this is regression-safe either way. If wire data lacks cwd, the next step is a
  host-side thread-id→cwd map read from `~/.codex/sessions`. Confirm via
  `window.codexOrbitDump()`.

**Verdict:** live. Bumped patcher `0.5.16 → 0.5.17`, archived as build #31.

## Diagnostics affordance — "Copy diagnostics" (v0.5.18)

**Files:** `stable/patch_codex.py`

0.5.17 shipped the path-authoritative filter but the leak persisted with 0.5.17
verified installed — so at runtime either `activeRoots` is empty or the wire threads
carry no matching `cwd`, and I could not see which from outside the webview. **Job:**
make the runtime truth (activeRoots, curRoot/curLabel, each thread's raw cwd/project)
reachable without the webview devtools console, which is fiddly to target in VS Code.
A right-click **"Copy diagnostics"** item (the menu already works) runs
`codexOrbitDump()` — copies to clipboard, downloads `codex-orbit-debug.json`, and logs
— and the dump now samples 40 threads + 6 raw wire objects so chats from the *leaking*
workspaces are included. **Why vs. rejected:** guessing a fourth filter heuristic
blind; this is the subtract-the-uncertainty move — read the data, then fix once. Permanent
support value beyond this bug. **Verdict:** live. Bumped `0.5.17 → 0.5.18`, build #32.

## Workspace Filtering — found "current" via the open chat / RPC (v0.5.19)

**Files:** `stable/patch_codex.py`

Root cause, found by reading Codex's own bundle (not guessing): the sidebar already
knows every chat's project (that is why grouping works) — the gap was knowing which
project is **current**. Codex delivers `active-workspace-roots` as an **RPC response**
(`"active-workspace-roots":async()=>({roots:...})`, read on the webview as
`(...active-workspace-roots...).roots?.[0]` via React Query), NOT a typed broadcast —
so our window-message interceptor (`findRoots`) never matched it, `curRoot/curLabel`
stayed empty, and `currentRows` punted to "show all".

- **`findRoots` now deep-scans** any incoming message for a `roots` array of paths
  (catches the `{...,result:{roots:[...]}}` RPC reply shape, wherever nested).
- **`openThreadId()` + URL-first `currentRows`:** the open chat's id is in the route
  (`/local/<id>`, `/remote/<id>`, `/worktree-init*/<id>` — confirmed in the bundle), and
  that chat is by definition in the current workspace. We resolve it to a thread and use
  its project/cwd as "home" — a transport-independent signal needing no message
  interception. Captured roots and an active-flagged chat are fallbacks.
- **`inCurrent`** already filters by exact project name when a chat carries no cwd, so
  once `curLabel` is set from the open chat's project, only that workspace's chats stay.

**Why vs. rejected:** chasing a per-chat `cwd` on the wire was the wrong axis — the
discriminator we reliably have is the project label; the missing piece was just "which
label is current", which the URL hands us directly. **Verdict:** live. Bumped
`0.5.18 → 0.5.19`, archived as build #33.

## Workspace Filtering — host stamps the workspace (the single source of truth) (v0.5.20)

**Files:** `stable/patch_codex.py`

0.5.16–0.5.19 each added another *webview-side* heuristic to guess "which workspace is
home" (URL parse, RPC sniff, active-flag, native-DOM scrape, persisted guess) — five
workarounds for one fact — and the holes all line up on the **task-list / home view**:
it is React Router's index route, so there is no `/local/<id>` in the URL (signal #1
blank), `active-workspace-roots-updated` is a payload-less ping whose roots arrive on a
separate React-Query RPC the window listener races (signal #2 blank), nothing is
flagged current (#3), and no native sidebar rows exist (#4). With every signal dark and
`CUR_KEY` empty, `currentRows()` fell to its last line `return rows.length<=8?rows:…` —
and with exactly 8 tasks the "don't be barren" cap returned **every project**. A second
road existed too: even with home known, an empty `inCurrent` match fell *through* the
`if(f.length) return f` guard into that same show-all cap.

- **Subtract the guessing; add one truth.** The extension HOST knows the workspace for
  certain — `Oe.workspace.workspaceFolders` (== `zF()`, the same source Codex's own
  `"active-workspace-roots":async()=>({roots:zF()})` handler uses). `inject_workspace_meta`
  stamps it into the webview HTML as `<meta name="codex-orbit-workspace"
  content='{"r":path,"l":name}'>` from `webviewMetaTags()` — which BOTH the production
  and development HTML generators call, so the tag is present on **every** view before
  any chat opens, with no RPC race and no DOM dependency. The sidebar's `hostWorkspace()`
  reads it as signal **#0**; the five heuristics demote to a fallback for a host bundle
  we failed to patch (kept, not deleted, because they are the graceful-degradation path
  if a future Codex renames the anchor — justified, not debt).
- **Close the leak.** When home is known, `currentRows` now returns `rows.filter(inCurrent)`
  **even if empty** — knowing home means never showing not-home. The `if(f.length)`
  fall-through that turned an empty match into "show all projects" is gone.
- **Why vs. rejected (host surgery):** the patcher's stated ethos is "no host surgery so
  it doesn't drift" — but it already string-patches minified webview locals
  (`expose_native_openers`), and a sixth webview heuristic would still be blind on the
  home view. Host injection is the user's own "one source of truth, rebuild correctly"
  directive made literal. **CSP-safe:** the webview CSP is `script-src ${cspSource}` with
  no inline/nonce, so an injected `<script>` is blocked — a `<meta>` is the only legal
  channel; the sidebar reads it via `getAttribute`. Round-trip (JSON → `pl()`
  HTML-escape → `getAttribute` decode → `JSON.parse`) verified for Windows backslash
  paths, quotes, `&`, `<`, and empty.
- **Sharpened the blade:** `verify()` now also `node --check`s the **host** bundle (a
  broken host bundle bricks all of Codex, not just the sidebar) and logs whether the
  `codex-orbit-workspace` stamp actually landed — a missed anchor is visible in the
  build log instead of silently shipping the old "shows all" behaviour. The anchor is
  the **semantic method name** `webviewMetaTags` (not a minified local), so it survives
  Codex churn better than the opener anchors; `Oe`/`pl` are wrapped in try/catch so an
  identifier drift no-ops gracefully (host still parses, webview falls back).

**Verdict:** live. Bumped `0.5.19 → 0.5.20`, archived as build #34.

**Confirmed live on install (diagnostics):** `hostWorkspace` stamp present, `activeRoots:[]`
and `nativeRowCount:0` (both legacy signals blank), `threadCount:1628` intercepted →
`filteredCount:1`. The host `<meta>` does 100% of the filtering; the webview heuristics
never fire on the home view, exactly as designed.

## Drop the redundant project header when filtered to one workspace (v0.5.21)

**Files:** `stable/patch_codex.py`

Once v0.5.20 filters the list to the current workspace, the only project group is that
workspace — so its header (`CODEX ORBIT`) just repeats the sidebar's own title
(`Codex Orbit`) directly above it. `render()` now lists the non-pinned/non-starred chats
**flat** when `order.length<=1`, and keeps per-project headers only when >1 project is
present (the blind-fallback case, where the label actually disambiguates). Pinned/Starred
section headers are untouched — those still carry meaning. **Why vs. rejected:**
special-casing "hide if header == title" is narrower and breaks the moment the workspace
folder name differs from the product name; "one group ⇒ no group label" is the general
truth and needs no name comparison. **Verdict:** live. Bumped `0.5.20 → 0.5.21`.

## Sidebar feature parity: settings menu, filter, per-row actions, status dots (v0.5.22)

**Files:** `stable/patch_codex.py`, `FEATURES.md`

Mirror Codex's native sidebar in OUR UI. Reverse-engineering Codex's bundle (3 agents)
produced three load-bearing truths that shaped the design — captured in `FEATURES.md`:
- **Codex has no native "star"** (`star-*.js` is just an icon) → ours, local.
- **Codex's per-chat color is DORMANT** — `sidebar-thread-metadata[id].labelColor` exists
  but there is no palette, no setter, and the row never renders it → ours, end to end.
- **Local chat status is NOT on the intercepted wire list** (it lives in live Jotai atoms;
  we see `{type:"notLoaded"}`). Only REMOTE tasks carry status inline → status dots are
  authoritative for remote, best-effort (usually gray) for local. Documented gap.

What shipped, and the primitive each reuses:
- **Host channel** (`expose_host_channel`): `acquireVsCodeApi()` may be called once and
  Codex already calls it, so we WRAP its call site to tee the instance into
  `window.__codexOrbitVsApi`. `coxPost(type,payload)` then posts the SAME messages Codex's
  own code posts — no second acquire (which throws). This is the one primitive that makes
  "call their function" possible (archive, run-command).
- **Settings menu** (gear button): our UI, Codex's `run-command` dispatch. Exact 7-item
  flyout is from a Codex newer than our baseline, so a few command ids are best-known; a
  miss is a harmless no-op and `codexOrbitDump().hostChannel` reports whether the channel
  is live, so ids are tunable in the fix-and-push loop. **Why vs. rejected:** clicking the
  native gear menu has no stable selector (the cog carries no aria/data-attr); `run-command`
  is the stable contract.
- **Filter menu**: implemented over data we already hold (no native dep). Pinned/Starred
  (ours), Untitled (`!title.trim()`), Age (`now-(updatedAt??createdAt)`), Running/Waiting
  (derived status). Persisted (`codexOrbitFilterV4`).
- **Per-chat color**: palette popup (clear + 6 colors we define), persisted
  (`codexOrbitColorsV4`), rendered as an inset left-border on our row. We own it because
  Codex ships nothing to call.
- **Hover toolbar** (star/pin/color/archive on `.coxRow` hover): the row became a
  `div[role=button]` so action `<button>`s can nest legally; routed by the existing
  delegated `.coxList` handler (`[data-cox-act]` checked before row-open).
- **Archive**: Codex's real `archive-conversation` command via the host channel (+ both
  envelope shapes), plus an optimistic local hide (`codexOrbitArchivedV4`) so OUR list
  updates instantly. **Open risk:** if the bare-postMessage envelope is wrong, the chat is
  hidden from our list but not actually archived — tunable once confirmed against the live
  host.
- **Status dots**: `statusOf` → DOT color (running=blue, waiting=orange, failed=red,
  review=green, idle=gray), matching Codex's tone mapping.

**Verdict:** live; applies clean (strict-module parse + host bundle check pass, all 15
feature markers present in the built VSIX). Runtime confidence varies by feature (see
FEATURES.md) — the user verifies by install per the fix-and-push loop. Bumped
`0.5.21 → 0.5.22`, archived as build #36.

## Sidebar parity polish — from install feedback (v0.5.23)

**Files:** `stable/patch_codex.py`

Five corrections after using v0.5.22:
- **Left gap.** The persistent `coxMark` (📌/⭐) span sat 12px wide even when empty,
  indenting every title. Removed — pin/star are conveyed by the Pinned/Starred section
  headers and the lit hover buttons, so the inline mark was redundant. Row is now
  `dot · title · actions`.
- **Floating action container.** The hover toolbar was `position:absolute` with its own
  background + shadow — read as a separate widget. Made it an inline flex member of the
  row (`margin-left:auto`, no bg/shadow); on hover the title truncates to make room, the
  native VS Code pattern. **Justify:** we own the row, so the actions should BE the row.
- **Dead settings toggles.** YOLO mode + Chat preview header were placeholders with guessed
  ids and no readable state — dead buttons. **Subtracted** (justify-or-die): better absent
  than lying. Settings now lists only the 5 items wired to a real `run-command` id.
- **Color barely visible.** Was a 3px left bar only. Now tints the WHOLE row (left bar +
  a faint full-row fill via an inset box-shadow overlay that survives `:hover`), so it
  clearly reads as "this container is colored." The status dot stays separate (by design).
- **Archived section.** Archived chats no longer vanish — they drop into their own
  collapsible **"Archived"** group at the bottom (mirrors Codex's native layout), and the
  archive action toggles (archive ⇄ unarchive, optimistic + best-effort `*-conversation`
  command). **Untitled-chats filter removed** — Codex auto-titles every chat, so it had
  no job.

**Verdict:** live; strict-module parse + host bundle check pass; all changes confirmed in
the built VSIX. Bumped `0.5.22 → 0.5.23`, archived as build #37.

## Row subtitles + counted collapsible sections + status-dot rendering (v0.5.24)

**Files:** `stable/patch_codex.py`

Match Codex's native row + section chrome:
- **Second line under each title:** `relTime(ts)` ("12 min ago" / "19 hrs ago" / "2 days
  ago") when idle, or live status text ("Thinking…" / "Question" / "Failed") when active.
  Row is now two lines (`coxRowMain` stacks title + subtitle). A 30s `setInterval`
  re-render keeps the relative times fresh.
- **Left indicator by state:** an animated CSS **spinner** while running, else a colored
  dot (blue/orange/red/gray). `statusOf` now consults a `liveStatus` Map first (populated
  by the event-stream listener — wired next), then falls back to wire/remote status.
- **Counted, collapsible sections:** every group header (`⭐ Starred`, `📌 Pinned`,
  `Sessions`, `Archived`) gets a chevron + a right-aligned count badge and collapses on
  click (persisted in `groupState`). The single-workspace main list is now a **"Sessions"**
  group (not flat) with its count — matching Codex; per-project headers remain only for the
  multi-workspace blind-fallback. Order: Starred, Pinned, Sessions, Archived.

**Known gap (next push):** live local "Thinking…/Question" needs Codex's per-thread status
EVENTS (not the chat list, which carries `status:notLoaded`). The rendering + `liveStatus`
plumbing are in place; the event-stream listener is being wired from a fresh RE pass — until
then locals show the relative time and the spinner/orange only light up for status we can
already read (remote tasks). **Verdict:** live; strict-module parse passes. Bumped
`0.5.23 → 0.5.24`, archived as build #39.

## Orbit Kit alignment — Patches toggle system (wrapper 1.2.0 / patcher 0.5.32)

**Files:** `orbit.config.json`, `ORBIT_KIT.md`, `patch_modules/catalog.json`,
`tools/orbit_config.py`, `tools/patches.py`, `Codex Orbit/extension.js`, `stable/patch_codex.py`

Adopt Claude Code Orbit's "Orbit Kit": one product-agnostic wrapper, the swap surface is
`orbit.config.json`, and features become **toggleable Patches** the user checks on/off.

- **What we took:** the kit's **Patches system** + the kit identity surface
  (`orbit.config.json` for Codex, `patch_modules/catalog.json` describing our modules, the
  `tools/`). The wrapper's PATCHES section (a collapsible checkbox list) persists the
  unchecked ids to `codexOrbit.disabledPatches` and passes `--disable id1,id2` to the
  patcher on the next Install/Update. Patcher side: `GATEABLE_FEATURES` + `feature_on()` +
  `--disable/--enable` args gate the matching injection. Two toggles ship:
  `workspace-filter` (gates `inject_workspace_meta`) and `status-dots` (gates
  `expose_status_stream`). Verified: `--disable` skips them (host `<meta>` absent / status
  hook not injected), no-disable applies both.
- **What we did NOT take, and why (justify-or-die).** The user asked to "use theirs" wholesale.
  A subagent ported the full 2900-line kit wrapper; verification proved the kit wrapper is
  **Claude-coupled in the CORE install flow, not just detection**: its `enable()` patches the
  NEWEST Codex with **no `--version` pin**, but our asset-replay patcher *fails closed* on any
  unverified Codex (it must pin to the certified build via `stable_version.txt`). A blind swap
  meant re-validating the entire **unrecoverable** install/OTA path against Codex with no
  runtime test — the exact "massive problem" the user told us to flag. So we **kept our proven
  install/detection/OTA flow** (codex-orbit-patch.json marker, `def copy_patched_assets` OTA
  guard, version-pinned `enable()`, the reaper deleted/never-ported) and **grafted only the
  kit's Patches additions** onto it. Same end state (Patches + kit config), zero risk to the
  update path. **Primitive:** our wrapper and the kit share one ancestor, so "graft the
  Patches delta" reuses the kit's exact UI/CSS/JS verbatim — not a fork, a cherry-pick.
- **Kit-identity is real but install stays ours:** `orbit.config.json` documents Codex's 12
  swap fields; `tools/orbit_config.py`/`patches.py` are the kit's drift/registry tooling.
  `orbit.config.json._doc.note` records that Codex keeps its own version-pinned install flow.

**Verdict:** live; node-check + strict-module parse + full/`--disable` patch runs pass; all
graft markers + preserved detection confirmed in the built VSIX. Wrapper `1.1.13 → 1.2.0`
(ships via OTA), patcher `0.5.31 → 0.5.32`, archived as build #47.

## Live per-chat status — the real wiring (v0.5.25)

**Files:** `stable/patch_codex.py`

Closes v0.5.24's known gap. A dedicated RE pass established the load-bearing fact: **Codex's
live status never reaches `window`** — `turn/started`, `turn/completed`,
`thread/status/changed`, `item/*requestApproval*`, `item/tool/requestUserInput` arrive over
the app-server IPC bridge (`vscode://codex/ipc-request` + `H.subscribe`), land in
`onNotification`, and mutate Jotai atoms the React rows read directly. The one
window-observable signal (`ipc-broadcast` → `thread-stream-state-changed`) is multi-window
follower-sync only and rarely fires in a single VS Code window — so a window listener alone
is a dead feature.

- **The reliable hook:** every status/turn/approval notification funnels its new conversation
  state through the SEMANTIC method `updateConversationState(id, updater)` (verified in the
  shipped 5519 chunk `app-server-manager-signals-DRv4QdiA.js`). `expose_status_stream`
  appends one call — `try{window.__codexOrbitStatusHook&&__codexOrbitStatusHook(e,r)}catch{}`
  — AFTER `applyConversationState(e,r)` runs. The sidebar's `deriveStatus(state)` reproduces
  Codex's own row logic (systemError/turn-failed→failed; active+waitingOnApproval/UserInput
  or a pending request→waiting; active/turn-inProgress→running; else idle) into a `liveStatus`
  map that `statusOf()` consults first.
- **Why this point, not a window listener / not the broadcast:** it is the single choke point
  ALL status lands on; it is a stable semantic name (survives churn better than minified
  locals); and it is the only place reachable without reading Jotai atoms.
- **Safety:** the injection is anchored on the EXACT 5519 method body and only APPENDS a
  try/catch'd side-effect — the original behaviour is unchanged. If the anchor ever drifts it
  simply doesn't apply (status falls back to best-effort), it can never break Codex. `verify()`
  now also strict-module-parses the patched status chunk (a broken one would break Codex's
  conversation engine) and confirms the hook landed. `codexOrbitDump()` reports `statusHook`
  + the live `liveStatus` entries so an id-format mismatch (hook id vs wire id) is visible.

**Verdict:** live; all four checks pass (helper + host bundle + status chunk strict parse,
hook confirmed in the built VSIX). Bumped `0.5.24 → 0.5.25`, archived as build #40.

## Row/menu polish from feedback (v0.5.26)

**Files:** `stable/patch_codex.py`

- **Dot top-aligned + neutral gray.** The idle dot used `var(--vscode-descriptionForeground)`,
  which is WARM in the user's theme — it read orange on the selected row (the tell: the
  subtitle said "49 min ago" = idle, yet the dot looked orange). Fixed to `#6e6e6e` (theme-
  independent gray) and `align-self:flex-start;margin-top:5px` so it sits on the title line,
  not centered against the two-line block. Spinner likewise.
- **Right-click menu = Codex's.** Now just **Pin · Star · Archive**, then an inline color
  swatch row (clear + 6) — set color in one click, no submenu. **Removed** Open (clicking the
  row already opens), the separate "Set color…" item, and "Filter to this chat". **Subtract:**
  each removed option had no unique job the row/headers don't already serve.
- **Copy diagnostics → gear menu.** Kept (it's the debugging lifeline for the status-id check)
  but moved out of the row menu into Settings, so the row menu stays clean.

**Verdict:** live; all syntax checks pass; menu/dot changes confirmed in the built VSIX.
Bumped `0.5.25 → 0.5.26`, archived as build #41.

## Newest-first sort + UUID-robust live status (v0.5.27)

**Files:** `stable/patch_codex.py`

Two fixes from watching a new chat appear:
- **Newest on top.** `render()` now `rows.sort((a,b)=>(b.ts||0)-(a.ts||0))` before grouping, so
  a new/just-active chat sorts above older ones (every section sorted, not insertion order).
- **Spinner on new/thinking chats — UUID match.** The status hook's conversationId and the
  wire row id can carry different prefixes (`z()`-normalized), so an exact-string match missed.
  Both sides are Codex UUIDs, so `liveStatus` is now keyed by the embedded UUID (`uuidOf`) and
  `statusOf` looks up by the row's UUID — bridging the two id forms so a thinking chat shows
  the spinner once it lands in the list. (The ~10s list-appearance lag is Codex's own
  push cadence — accepted; the dump's `liveStatus` confirms the hook fires meanwhile.)

**Verdict:** live; all syntax checks pass. Bumped `0.5.26 → 0.5.27`, archived as build #42.

## Model picker unclickable — our z-index covered Codex's popover (v0.5.33)

**Files:** `stable/patch_codex.py`

**Symptom:** in patched Codex, clicking the model dropdown / "change model" did nothing,
but the `/model` slash command worked. **Root cause (RE-confirmed against Codex's bundle):**
Codex's model picker is a **Radix dropdown portaled to `document.body`, `position:fixed`,
`z-index:50`**. Our sidebar is ALSO a `<body>` child but at **`z-index:2147483647`** (the
32-bit max), so — as DOM siblings under body, stacking decided purely by z-index — our panel
painted over the entire picker layer and ate the pointer. `/model` works because it's a JS
command that never touches that DOM layer (which is the tell: keyboard works, click doesn't).

- **Fix:** stop using the absurd max z-index. `.coxSidebar` (open + collapsed) → `45`,
  `.coxMenu` → `49`. Now: Codex content (~0) < our sidebar (45) < our menus (49) < Codex's
  popover layer (50). The picker renders ON TOP of our panel and is clickable; our menus
  still sit above our panel; Codex modals/toasts (≥50) correctly sit above us. `body{padding-
  right}` is unchanged — it reserves layout space and (correctly) does not move the fixed
  popover. **Justify-or-die:** `2147483647` was "be on top of everything," which is wrong —
  a sidebar must be above CONTENT but below the host's transient popovers.
- **Version-independent:** the fix is in our injected CSS, so it applies to whatever Codex
  build is patched (the bug reproduced on the newest Codex too).

**Verdict:** live; patch applies clean, max z-index gone, picker layer (50) now above ours.
Bumped `0.5.32 → 0.5.33` (both version files), archived as build #50.

## Crash fix (webview suicide) + selected-chat indicator + darker dot (v0.5.28)

**Files:** `stable/patch_codex.py`

- **CRASH: opening a non-current chat blanked the whole webview.** `routeTo`'s last-resort
  `setTimeout(()=>{ if(location.pathname!==path) window.location.href=path },120)` set the
  webview's `location.href` to a relative app path (`/local/<id>`) whenever Codex's resulting
  URL didn't byte-match our constructed one within 120ms — which is the norm for any chat
  that isn't already open (Codex normalizes the route). In a vscode-webview that loads a
  non-existent resource and **blanks the entire webview** ("committed seppuku"). The current
  chat never tripped it (its URL already matches). **Removed** the href fallback entirely —
  host-message + app-postMessage + `history.pushState`+popstate already navigate; worst case
  now is a no-switch, never a crash. **Justify-or-die:** a fallback that destroys the app is
  worse than no fallback.
- **Selected-chat indicator.** The open chat (by URL id, UUID-matched) now gets the `.act`
  highlight plus a left accent bar (`.coxRow.act::before`), re-applied on `popstate` so it
  tracks as you switch chats. Previously selection only showed if the wire data happened to
  flag the row active — usually it didn't.
- **Darker idle dot.** `#6e6e6e → #565656` (the nicer, darker gray, closer to Codex).
- **Defensive:** `ensureShell` re-appends the panel if Codex ever detaches it from `body`.

**Verdict:** live; all syntax checks pass; six change-markers confirmed in the built VSIX.
Bumped `0.5.27 → 0.5.28`, archived as build #43.

## Render storm killed — fixes ~20s status lag + frozen spinner (v0.5.29)

**Files:** `stable/patch_codex.py`

Both symptoms (status appearing ~20s late, and the "spinner" showing as a static ring) traced
to ONE cause: the `MutationObserver` reacted to ANY DOM mutation outside our shell. When a chat
streams tokens, Codex mutates the transcript ~12x/s, so the observer fired a full list rebuild
~12x/s. That (a) **saturated the event loop** — the status hook set `liveStatus` instantly but
the actual DOM render queued ~20s behind — and (b) **destroyed+recreated the spinner element
every frame**, restarting its CSS animation so it never visibly rotated.

- **Gate the observer to native sidebar rows only.** It now re-renders only when an
  `[data-app-action-sidebar-thread-row]`/`-project-row` is added/removed — never on transcript
  streaming (text deltas are text nodes, `nodeType!==1`, skipped cheaply). Status/list/nav
  already update via their own signals (status hook, message ingest, popstate/focus); the 30s
  interval refreshes relative times. No storm ⇒ the hook's render lands in ~80ms (not 20s) and
  the spinner element persists between status changes, so it animates.
- **Spinner contrast:** faint ring (`rgba(255,255,255,.16)`) + a bright blue rotating arc, 10px,
  so the rotation reads clearly.
- This is the v0.5.16 storm fix completed: that round stopped the observer self-triggering on
  OUR writes; this round stops it triggering on Codex's transcript writes.

**Verdict:** live; all syntax checks pass. Bumped BOTH `patcher_version.txt` files (per
[[dual-patcher-version-files]]). `0.5.28 → 0.5.29`, archived as build #44.
