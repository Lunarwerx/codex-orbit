# Codex Orbit

**A patch companion for OpenAI's Codex VS Code extension.**

Codex Orbit is a thin wrapper VSIX that downloads the official `openai.chatgpt`
Codex VSIX, applies a verified patch baseline, and installs the patched result.
The wrapper itself does not redistribute the stock Codex extension; patching
happens on the user's machine.

## Current Baseline

- Target extension: `openai.chatgpt`
- Verified Codex version: `26.5519.32039`
- Stable patcher: `stable/patch_codex.py`
- Patched asset baseline: `stable/codex_assets/`
- Installed marker: `codex-orbit-patch.json`

## Features

- Rename Codex tasks from the task context menu.
- Pin and unpin tasks.
- Star and unstar tasks.
- Replace Codex's inline recent-task feed with a collapsible right sidebar that
  mirrors only the current workspace's chats.
- Keep the recent-task menu/search/grouping patches from the verified Codex
  baseline.
- Detect whether the installed Codex extension is stock, patched, or behind the
  bundled patcher.

## Build

```powershell
python build.py
```

The build writes a numbered wrapper VSIX to `builds/` and updates
`latest/codex-orbit.vsix`.

For a local smoke build without creating a numbered release artifact:

```powershell
python build.py --out .tmp\codex-orbit-test.vsix
```

## Patch A Stock Codex VSIX

```powershell
python stable\patch_codex.py Potentials\Codex\openai.chatgpt-26.5519.32039.vsix --out .tmp\codex-test-patched.vsix --patcher-version dev
```

The patcher refuses unsupported Codex versions until a new
`stable/codex_assets` baseline is promoted.

## Release Notes

This repository was rebooted from the previous Orbit wrapper into Codex Orbit.
The old extension target and rollback archive have been removed from the build
path; Codex Orbit now ships a Codex-specific stable patcher and asset baseline.
