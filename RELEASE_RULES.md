# Codex Orbit Release Rules

Codex Orbit has three separate version concepts:

1. **Wrapper version**
   - File: `Codex Orbit/package.json`
   - This is the VSIX Marketplace version for the wrapper.
   - Do not bump it during ordinary local builds.

2. **Patcher version**
   - Files: `patcher_version.txt`, `stable/patcher_version.txt`
   - This is written into `codex-orbit-patch.json` inside the patched Codex
     extension.
   - Bump it only when promoting a new Codex patcher/baseline.

3. **Stable Codex version**
   - Files: `stable_version.txt`, `stable/stable_version.txt`
   - The certified `openai.chatgpt` version: the newest Codex build the dynamic
     patcher has been test-run against. `enable()` pins the install to it.

## Build

Use the repository build script:

```powershell
python build.py
```

That creates `builds/codex-orbit-build-<N>.vsix`, updates
`latest/codex-orbit.vsix`, writes `wrapper_version.txt`, archives the current
patcher into `patchers/` (with its `ORBIT_CHANNEL` tag), and appends to
`builds/BUILD_LOG.md`.

## Cut a release (channel-aware): `python tools/ship.py`

For an actual release, prefer `ship.py` over a bare `build.py` — it stamps the
release channel and certifies against the newest Codex in one step:

```powershell
python tools/ship.py            # experimental (DEFAULT — Jacob's standing rule)
python tools/ship.py --stable   # stable — ONLY when Jacob explicitly says "stable"
python tools/ship.py --no-certify   # channel-stamp + build only (skip newest-Codex re-certify)
```

It stamps `ORBIT_CHANNEL` in `stable/patch_codex.py`, writes `release_channel.txt`,
re-certifies (writes `stable_version.txt`), and runs `build.py`. Then commit + push
the printed file list and confirm the CDN serves the new patcher code. See
`AGENTS.md` § "Releases default to EXPERIMENTAL" for the full channel rule.

## Verify A Baseline

Run the stable patcher against the certified stock Codex VSIX (it downloads +
caches from the Marketplace; `node` must be on PATH for the strict JS checks):

```powershell
python stable\patch_codex.py openai.chatgpt --version 26.5609.30741 --target-platform win32-x64 --out .tmp\codex-test-patched.vsix --patcher-version dev --log .tmp\codex-test.log
```

Required pass conditions:

- Patcher exits with code 0.
- Verification passes — the log shows: `JS syntax check passed`, `Host bundle
  syntax check passed; workspace <meta> stamp confirmed present`, and `Status
  chunk syntax check passed; live-status hook confirmed present`. (Native row
  openers may log a "not found" fallback — they degrade gracefully to DOM/route
  and are never fatal.)
- `node --check "Codex Orbit-\extension.js"` passes. (Note the trailing `-` in
  the wrapper dir name.)
- `python -m py_compile build.py stable\patch_codex.py` passes.
- Built wrapper VSIX contains `extension/stable/patch_codex.py`.

## Promoting A New Codex Version

The patcher is dynamic (content-anchored), so promotion is "run it against the new
Codex, re-anchor anything that drifted, then bump + build." There is no
`SUPPORTED_VERSION` constant and no `codex_assets` to regenerate.

1. Find the newest `openai.chatgpt` version (Marketplace, or the wrapper's
   "latest Codex" status line).
2. Run the patcher against it (see *Verify A Baseline*). Read the log:
   - All anchors hit + all syntax checks pass → nothing drifted; go to step 4.
   - An anchor logs "not found" / a feature is missing → that edit drifted.
3. Re-anchor the drifted edits in `stable/patch_codex.py` against a CLEAN extract
   of the new Codex (never a dir a prior patch run mutated). Prefer making the
   anchor version-agnostic (regex/capture group, prioritized host list) over
   pinning a new literal. Re-run step 2 until clean.
4. Update `stable_version.txt` and `stable/stable_version.txt` to the new version.
5. Bump `patcher_version.txt`, `stable/patcher_version.txt`, and `__version__` in
   `stable/patch_codex.py` (all three must match).
6. Build with `python build.py` (snapshots the new patcher into `patchers/`).
7. Bump the wrapper `Codex Orbit-/package.json` version too so existing users pick
   up the new certified pin — the wrapper bundles `stable_version.txt` and
   `enable()` pins to the bundled copy.
8. Commit + push `stable/`, `patchers/`, `latest/`, and the version files.
