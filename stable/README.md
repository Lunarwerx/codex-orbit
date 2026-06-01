# Codex Orbit stable patcher

This folder is the locked, known-working fallback that ships inside the Codex
Orbit wrapper VSIX.

The current stable patcher targets `openai.chatgpt` version `26.5519.32039`.
It applies the verified patched asset baseline from `stable/codex_assets`,
including the current-workspace Codex Orbit sidebar, and writes
`codex-orbit-patch.json` into the patched Codex extension so the wrapper can
detect installed patch state.

Files:

- `patch_codex.py` - the production patcher shipped in the VSIX.
- `codex_assets/` - the verified patched Codex files copied into the stock VSIX.
- `stable_version.txt` - the Codex Marketplace version this baseline supports.
- `patcher_version.txt` - the Codex Orbit patcher version written to the marker.

Only promote this folder after the patcher has been test-run against the exact
target Codex VSIX and the generated VSIX passes verification.
