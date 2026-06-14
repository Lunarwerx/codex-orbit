# Codex Orbit Architecture

Codex Orbit is a VS Code wrapper extension that patches the official
`openai.chatgpt` Codex extension at runtime.

## Runtime Flow

1. The wrapper checks whether `openai.chatgpt` is installed.
2. It reads `codex-orbit-patch.json` from the installed Codex extension to
   decide whether Codex is stock, patched, or outdated.
3. When enabled, it runs `stable/patch_codex.py`.
4. The patcher downloads or receives a stock Codex VSIX and injects the Codex
   Orbit sidebar (plus the host-channel, live-status, and workspace-`<meta>`
   hooks) by CONTENT ANCHOR — appending/splicing into the relevant minified
   chunks — then writes a patched VSIX. Drifted anchors are skipped, never fatal.
5. The wrapper swaps the installed Codex extension with the patched VSIX.

## Current Stable Baseline

- Marketplace item: `openai.chatgpt`
- Certified Codex version: `26.5609.30741`
- Wrapper view ID: `codexOrbit.sidebar`
- Dev-mode setting: `codexOrbit.devMode`
- Latest wrapper artifact: `latest/codex-orbit.vsix`

## Why Dynamic, Content-Anchored Patching

Codex Orbit injects by locating stable content anchors in Codex's minified
bundle, not by replaying a stored asset baseline. A Codex update therefore does
not automatically break the patch: anchors are matched by content, and a drifted
anchor is skipped (its feature degrades) rather than crashing the whole patch.
`stable_version.txt` records the build the patcher was last test-run against, and
`enable()` pins the install to it so users always get a verified baseline — but
the patcher itself has no version gate and will patch any `openai.chatgpt` build.
