# Codex Orbit

**A patch companion for OpenAI's Codex VS Code extension.**

Codex Orbit is a thin wrapper VSIX that downloads the official `openai.chatgpt`
Codex VSIX, applies a verified patch baseline, and installs the patched result.
The wrapper itself does not redistribute the stock Codex extension; patching
happens on the user's machine.

## Current Baseline

- Target extension: `openai.chatgpt`
- Certified Codex version: `26.5609.30741`
- Dynamic patcher: `stable/patch_codex.py` (content-anchored injection)
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
python stable\patch_codex.py openai.chatgpt --version 26.5609.30741 --target-platform win32-x64 --out .tmp\codex-test-patched.vsix --patcher-version dev
```

The patcher is version-agnostic: it injects by content anchor into any
`openai.chatgpt` build and skips anchors that have drifted rather than failing.
`stable_version.txt` records the certified build that `enable()` pins to.

## Release Notes

This repository was rebooted from the previous Orbit wrapper into Codex Orbit.
The old extension target and rollback archive have been removed from the build
path; Codex Orbit now ships a Codex-specific stable patcher and asset baseline.
