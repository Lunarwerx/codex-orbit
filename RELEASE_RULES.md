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
   - This is the exact `openai.chatgpt` version the bundled
     `stable/codex_assets` baseline supports.

## Build

Use the repository build script:

```powershell
python build.py
```

That creates `builds/codex-orbit-build-<N>.vsix`, updates
`latest/codex-orbit.vsix`, writes `wrapper_version.txt`, and appends to
`builds/BUILD_LOG.md`.

## Verify A Baseline

Run the stable patcher against the stock Codex VSIX:

```powershell
python stable\patch_codex.py Potentials\Codex\openai.chatgpt-26.5519.32039.vsix --out .tmp\codex-test-patched.vsix --patcher-version dev --log .tmp\codex-test.log
```

Required pass conditions:

- Patcher exits with code 0.
- Verification passes.
- `node --check "Codex Orbit\extension.js"` passes.
- `python -m py_compile build.py stable\patch_codex.py` passes.
- Built wrapper VSIX contains `extension/stable/patch_codex.py` and
  `extension/stable/codex_assets/**`.

## Promoting A New Codex Version

1. Obtain the new stock `openai.chatgpt` VSIX.
2. Create a patched version and extract the patched files into
   `stable/codex_assets`.
3. Update `SUPPORTED_VERSION` in `stable/patch_codex.py`.
4. Update `stable_version.txt` and `stable/stable_version.txt`.
5. Bump `patcher_version.txt` and `stable/patcher_version.txt`.
6. Run the verification commands above.
7. Build with `python build.py`.
