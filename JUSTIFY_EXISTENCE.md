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
