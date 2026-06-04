# Codex Orbit Architecture

Codex Orbit is a VS Code wrapper extension that patches the official
`openai.chatgpt` Codex extension at runtime.

## Runtime Flow

1. The wrapper checks whether `openai.chatgpt` is installed.
2. It reads `codex-orbit-patch.json` from the installed Codex extension to
   decide whether Codex is stock, patched, or outdated.
3. When enabled, it runs `stable/patch_codex.py`.
4. The patcher downloads or receives a stock Codex VSIX, verifies the target
   version, copies the verified files from `stable/codex_assets`, and writes a
   patched VSIX.
5. The wrapper swaps the installed Codex extension with the patched VSIX.

## Current Stable Baseline

- Marketplace item: `openai.chatgpt`
- Supported Codex version: `26.5519.32039`
- Wrapper view ID: `codexOrbit.sidebar`
- Dev-mode setting: `codexOrbit.devMode`
- Latest wrapper artifact: `latest/codex-orbit.vsix`

## Why Asset Baseline Patching

The current Codex patches are stored as verified patched bundle files. The
stable patcher intentionally fails when the stock Codex version does not match
the baseline, which avoids writing incompatible minified assets into a newer
OpenAI release.
