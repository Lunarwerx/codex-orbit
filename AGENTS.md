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
