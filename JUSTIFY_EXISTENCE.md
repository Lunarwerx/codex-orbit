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
