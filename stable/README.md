# Codex Orbit stable patcher

This folder is the locked, known-working fallback that ships inside the Codex
Orbit wrapper VSIX.

The current stable patcher is certified against `openai.chatgpt` version
`26.5609.30741`. It injects the current-workspace Codex Orbit sidebar (plus the
host channel, live-status, and workspace `<meta>` hooks) by CONTENT ANCHOR — no
files are copied from `codex_assets` at runtime — and writes
`codex-orbit-patch.json` into the patched Codex extension so the wrapper can
detect installed patch state.

Files:

- `patch_codex.py` - the production dynamic patcher shipped in the VSIX.
- `codex_assets/` - a DEV-ONLY reference extract (the old asset-replay baseline);
  read by `tools/` for diffing, NOT bundled in the VSIX and NOT read at runtime.
- `stable_version.txt` - the certified Codex version `enable()` pins to.
- `patcher_version.txt` - the Codex Orbit patcher version written to the marker.

Only promote this folder after the patcher has been test-run against the exact
target Codex VSIX and the generated VSIX passes verification.
