# Codex Orbit — PRIME DIRECTIVE (read this first, every time)

**The entire purpose of Codex Orbit is to save the user from ever reinstalling a
VSIX.** That is the whole product. Everything below serves it.

## The only loop that matters

1. Codex ships an update and it breaks something in the patch.
2. The user tells you exactly what broke.
3. **You immediately fix the ONE patcher (`stable/patch_codex.py`), bump the
   patcher version, and push to GitHub. No deliberation, no "it didn't apply,"
   no asking permission to bump — the user has given standing permission to bump
   and push on every fix.**
4. The user clicks **Check for updates**, installs the patcher you just pushed,
   and tells you whether it worked.
5. Repeat forever.

If a push makes things worse, the user clicks **Use previous versions** and
reinstalls the last-known-good patcher (the picker shows recent versions). That
rollback safety net is WHY you should fix-and-push without hesitation — a bad
push is never catastrophic.

## Hard rules

- **Default action = edit `stable/patch_codex.py`, bump its version, push.**
  Every time. Do not respond with analysis-instead-of-a-push.
- **Bumping the patcher version is REQUIRED for the update to appear.** `Check
  for updates` compares the installed patcher version against
  `patcher_version.txt`. If you push patcher code without bumping
  `patcher_version.txt` (and `stable/patcher_version.txt`), the user sees "no
  update." So: every patcher fix → bump → push, or it's invisible.
- **The ONLY file you normally change is the patcher.** The two sanctioned
  wrapper (`Codex Orbit/extension.js`) exceptions the user asked for:
  1. **"Use previous versions" must be visible on EVERY pane except the
     downloading/working step** (so rollback is always one click away).
  2. (Reserved for any future explicitly-requested wrapper change.)
  Wrapper changes ship via the same loop: bump `package.json` + `wrapper_version.txt`,
  `python build.py`, push `latest/codex-orbit.vsix` — `Check for updates` then
  offers the wrapper update and auto-installs it (still no manual VSIX install).
- **The patcher is dynamic and version-agnostic** (anchors located by content,
  drifted edits skip rather than crash). When Codex refactors, re-anchor the
  broken edits against a CLEAN extract of the new Codex (see
  `tools/` + memory `dynamic-patcher-migration`). Never anchor on a dir a prior
  patch run mutated.
- **Do not lecture the user about what you can/can't verify.** Fix, bump, push.
  The user verifies by installing and reporting. That IS the verification.

## Every version is saved forever (the rollback registry)

`python build.py` automatically calls `tools/archive_patcher.py`, which snapshots
the current `stable/patch_codex.py` into `patchers/patch_codex-<version>.py` and
upserts an entry in `patchers/manifest.json` (keyed by `patcher_version.txt`).
**It never deletes older entries.** So the loop is: bump `patcher_version.txt`
→ `python build.py` (archives the new version, keeps every old one) → push
`patchers/` + `latest/codex-orbit.vsix`. "Use previous versions" then lists every
version ever shipped, and a rollback runs that EXACT archived file
(`enablePrevious` loads `patchers/<entry.file>`, never the live patcher).

NEVER hand-prune `patchers/` or the manifest. Bumping the patcher version without
running `build.py` would skip the archive — always build so the snapshot happens.
This is the CCO model; it is the user's #1 requirement: every previous version
stays installable so a bad push is always one click from recovery.

(Exception, on Jacob's explicit word: a one-time registry RESET when adopting a new
launcher contract — e.g. 2026-06-16, when the new launcher required channel tags +
the `patch_webview_js` marker, so all pre-channel patchers were cleared and the
registry restarted at the first channel-tagged version. Git history retains the old
snapshots. This is NOT routine pruning — only when Jacob says so.)

## Releases default to EXPERIMENTAL (Jacob's standing rule)

Every release pushed from this repo is **experimental by default**. Unless Jacob
says the word **"stable"** for that specific release, it ships experimental — no
exceptions, and don't ask which channel. Red EXPERIMENTAL = "maybe I won't update";
green STABLE = "cool, I'll update." This lets Jacob push potentially-broken
experimental builds freely — other users see the red tag and hold off.

The tag ships **inside the patcher itself** — the single source of truth is the
**`ORBIT_CHANNEL`** constant in `stable/patch_codex.py`
(`ORBIT_CHANNEL: str = "experimental"`). On patch, `patch_webview_js` embeds it into
the patched webview as **`ccPatchChannel`**; on build, `tools/archive_patcher.py`
mirrors it into each `patchers/manifest.json` entry's `channel` field. So the wrapper
reads the **installed** tag from the patched webview and the **list/available** tag
from the patcher-sourced manifest — nothing is defaulted. `release_channel.txt` is
still written for back-compat with already-installed wrappers, but the patcher is the
source of truth. Each archived patcher carries its own embedded tag, so older
versions keep their real tag forever — no backfills.

## "Push an update" = `python tools/ship.py` (one command)

When Jacob says **"push an update"**, the prep is a single script — never hand-feed
the Codex version again:

```
python tools/ship.py            # experimental (default)
python tools/ship.py --stable   # stable — ONLY when Jacob says "stable"
```

It stamps the channel into `stable/patch_codex.py`, re-certifies against the
**newest Codex** from the Marketplace (writes `stable_version.txt` to that version —
never a hand-typed one), writes `release_channel.txt`, and runs `build.py` (which
archives the patcher into the rollback registry WITH its channel, then builds the
wrapper VSIX). Then commit + push the printed file list and **confirm the raw CDN
serves the new patcher CODE before telling anyone it's ready** — the launcher's OTA
reads `stable/patch_codex.py` straight from `main`.

Two rails, both infallible: every release certifies against whatever Codex is
**newest at ship time**; every release is **tagged** (default experimental, stable
ONLY on Jacob's word). The only two tags are experimental and stable.

## The launcher is shared — its markers are our patcher's contract

The wrapper/launcher (install / update / previous-versions + the red/green channel
tags) is pulled from `Lunarwerx/claude-code-orbit` and rebranded at build (see the
top of this file + CLAUDE.md). It hardcodes a few Claude-named markers our patcher
MUST satisfy or OTA breaks:
- It accepts a fetched OTA patcher only if the file contains `def patch_webview_js`
  (keep that function in `stable/patch_codex.py` — it also embeds `ccPatchChannel`).
- It reads the certified version from each manifest entry's `claude` field, so
  `archive_patcher.py` mirrors our `codex` version into a `claude` field too.

If the channel UI or these markers need to change, request it **upstream** — do NOT
edit the launcher here. (Known upstream gap: the installed-tag reader looks at
`webview/index.js`, a Claude path Codex doesn't have, so the installed tag falls
back to the manifest/default; the available/list tag works.)
