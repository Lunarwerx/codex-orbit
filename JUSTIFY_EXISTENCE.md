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
