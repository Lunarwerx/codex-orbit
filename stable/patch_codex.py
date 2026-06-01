#!/usr/bin/env python
"""Patch the Codex VS Code extension with Codex Orbit task controls.

This first Codex Orbit stable patcher is intentionally baseline-driven: it
replays the verified patched assets from openai.chatgpt 26.5519.32039 instead of
trying to regenerate minified webview patches. That gives the wrapper a solid
Codex target immediately, while keeping the failure mode clear when OpenAI ships
new asset names.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

__version__ = "0.3.1"

DEFAULT_MARKETPLACE_ITEM = "openai.chatgpt"
SUPPORTED_VERSION = "26.5519.32039"
MARKETPLACE_QUERY_URL = (
    "https://marketplace.visualstudio.com/_apis/public/gallery/"
    "extensionquery?api-version=7.2-preview.1"
)
ASSET_ROOT = Path(__file__).resolve().parent / "codex_assets"
LOG_PATH: Path | None = None

PATCHED_FILES = [
    "package.json",
    "out/extension.js",
    "webview/assets/app-main-B4greUYI.js",
    "webview/assets/header-BcIrXCOm-codexpatch.js",
    "webview/assets/history-Dc-JS86K-codexpatch.js",
    "webview/assets/setting-storage-Dtu-rhmp-codexpatch.js",
    "webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js",
]


def log(message: str) -> None:
    line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def marketplace_item_from_target(target: str) -> str | None:
    if target.startswith(("http://", "https://")):
        item = urllib.parse.parse_qs(urllib.parse.urlparse(target).query).get("itemName", [""])[0].strip()
        return item or None
    if "." in target and not any(sep in target for sep in ("/", "\\")) and not target.lower().endswith(".vsix"):
        return target
    return None


def detect_target_platform() -> str | None:
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if sys.platform.startswith("win"):
        return f"win32-{arch}"
    if sys.platform == "darwin":
        return f"darwin-{arch}"
    if sys.platform.startswith("linux"):
        return f"linux-{arch}"
    return None


def download_marketplace_vsix(
    item: str,
    dest_dir: Path,
    version: str | None = None,
    target_platform: str | None = None,
) -> Path:
    target_platform = target_platform or detect_target_platform()
    body = {"filters": [{"criteria": [{"filterType": 7, "value": item}]}], "flags": 403}
    req = urllib.request.Request(
        MARKETPLACE_QUERY_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json;api-version=7.2-preview.1",
            "User-Agent": "codex-orbit-patcher",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
    extension = data["results"][0]["extensions"][0]
    candidates = [v for v in extension["versions"] if not version or v["version"] == version]
    selected = next(
        (v for v in candidates if target_platform and v.get("targetPlatform") == target_platform),
        None,
    )
    if selected is None and target_platform:
        log(f"No {target_platform} VSIX found for {item} {version or 'latest'}; trying platform-neutral package")
    if selected is None:
        selected = next((v for v in candidates if not v.get("targetPlatform")), None)
    if selected is None and candidates:
        selected = candidates[0]
    if selected is None:
        if version:
            raise RuntimeError(f"Version {version} not found for {item}")
        selected = extension["versions"][0] if extension["versions"] else None
        if selected is None:
            raise RuntimeError(f"No versions found for {item}")
    package = next(f for f in selected["files"] if f.get("assetType", "").endswith("VSIXPackage"))
    publisher = extension["publisher"]["publisherName"]
    name = extension["extensionName"]
    selected_platform = selected.get("targetPlatform")
    platform_suffix = f"-{selected_platform}" if selected_platform else ""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{publisher}.{name}-{selected['version']}{platform_suffix}.vsix"
    log(f"Downloading {publisher}.{name} {selected['version']} {selected_platform or 'platform-neutral'} to {dest}")
    urllib.request.urlretrieve(package["source"], dest)
    log(f"Downloaded VSIX size: {dest.stat().st_size} bytes")
    return dest


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_supported_codex(extension_dir: Path) -> dict:
    package_path = extension_dir / "package.json"
    if not package_path.exists():
        raise RuntimeError("Could not find extension/package.json in VSIX")
    manifest = read_json(package_path)
    extension_id = f"{manifest.get('publisher')}.{manifest.get('name')}"
    if extension_id != DEFAULT_MARKETPLACE_ITEM:
        raise RuntimeError(f"Expected {DEFAULT_MARKETPLACE_ITEM}, got {extension_id}")
    version = manifest.get("version")
    if version != SUPPORTED_VERSION:
        raise RuntimeError(
            f"Codex Orbit stable assets support Codex {SUPPORTED_VERSION}; "
            f"target VSIX is {version}. Add a new codex_assets baseline before patching this build."
        )
    return manifest


def copy_patched_assets(extension_dir: Path, patcher_version: str) -> None:
    if not ASSET_ROOT.exists():
        raise RuntimeError(f"Missing bundled Codex assets: {ASSET_ROOT}")
    for rel in PATCHED_FILES:
        src = ASSET_ROOT / rel
        dest = extension_dir / rel
        if not src.exists():
            raise RuntimeError(f"Missing bundled Codex asset: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        log(f"Patched {rel}")
    marker = {
        "tool": "Codex Orbit",
        "patcherVersion": patcher_version,
        "target": DEFAULT_MARKETPLACE_ITEM,
        "targetVersion": SUPPORTED_VERSION,
        "patchedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "asset-baseline",
    }
    (extension_dir / "codex-orbit-patch.json").write_text(
        json.dumps(marker, indent=2) + "\n",
        encoding="utf-8",
    )
    log("Wrote codex-orbit-patch.json marker")


def verify_extension_dir(extension_dir: Path) -> None:
    package = read_json(extension_dir / "package.json")
    command_ids = {cmd.get("command") for cmd in package.get("contributes", {}).get("commands", [])}
    expected_commands = {
        "chatgpt.renameTask",
        "chatgpt.pinTask",
        "chatgpt.unpinTask",
        "chatgpt.starTask",
        "chatgpt.unstarTask",
    }
    missing_commands = sorted(expected_commands - command_ids)
    if missing_commands:
        raise RuntimeError("Missing Codex task commands: " + ", ".join(missing_commands))

    ext_js = (extension_dir / "out" / "extension.js").read_text(encoding="utf-8")
    asset_text = ""
    for rel in [
        "webview/assets/app-main-B4greUYI.js",
        "webview/assets/header-BcIrXCOm-codexpatch.js",
        "webview/assets/history-Dc-JS86K-codexpatch.js",
        "webview/assets/setting-storage-Dtu-rhmp-codexpatch.js",
        "webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js",
    ]:
        asset_text += (extension_dir / rel).read_text(encoding="utf-8", errors="ignore")
    checks = {
        "task context bridge": "codexWithTaskContext" in ext_js and "codex-request-task-context" in asset_text,
        "rename task": "renameChatSessionItem" in ext_js and "chatgpt.renameTask" in ext_js,
        "pin task": "pinChatSessionItem" in ext_js and "chatgpt.pinTask" in ext_js,
        "star task": "starChatSessionItem" in ext_js and "chatgpt.starTask" in ext_js,
        "codex sidebar": "codexOrbitSidebar" in asset_text and "codexOrbitNativeSource" in asset_text,
        "cache-busted assets": "-codexpatch.js" in asset_text,
        "marker": (extension_dir / "codex-orbit-patch.json").exists(),
    }
    for rel in PATCHED_FILES:
        checks[f"file {rel}"] = (extension_dir / rel).exists()
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        raise RuntimeError("Verification failed: " + ", ".join(missing))

    node = shutil.which("node")
    if node:
        log("Running JS syntax checks")
        for rel in [
            "out/extension.js",
            "webview/assets/app-main-B4greUYI.js",
            "webview/assets/header-BcIrXCOm-codexpatch.js",
            "webview/assets/history-Dc-JS86K-codexpatch.js",
            "webview/assets/setting-storage-Dtu-rhmp-codexpatch.js",
            "webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js",
        ]:
            subprocess.check_call([node, "--check", str(extension_dir / rel)])
    log(f"Verification passed ({len(checks)} checks)")


def zip_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(src).as_posix())


def resolve_target(args: argparse.Namespace) -> Path:
    raw = args.target
    raw_path = Path(raw).expanduser()
    if raw_path.exists() or raw_path.suffix.lower() == ".vsix":
        target = raw_path.resolve()
        if not target.exists():
            raise RuntimeError(f"VSIX file not found: {target}")
        log(f"Using local target: {target}")
        return target
    item = marketplace_item_from_target(raw)
    if item is None:
        raise RuntimeError(f"Target does not exist and is not a Marketplace item: {raw}")
    return download_marketplace_vsix(
        item,
        Path(args.download_dir).expanduser().resolve(),
        args.version or None,
        args.target_platform or None,
    )


def main() -> int:
    global LOG_PATH
    parser = argparse.ArgumentParser(description="Patch Codex VSIX with Codex Orbit task controls.")
    parser.add_argument("target", nargs="?", default=DEFAULT_MARKETPLACE_ITEM)
    parser.add_argument("--out", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--target-platform", default="", help="VS Code target platform, e.g. win32-x64.")
    parser.add_argument("--download-dir", default=".")
    parser.add_argument("--log", default="codex-vsix-patch.log")
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download the marketplace VSIX without patching. Prints STOCK_VSIX_PATH: <path>.",
    )
    parser.add_argument(
        "--patcher-version",
        default="dev",
        help="Version string written to codex-orbit-patch.json.",
    )
    args = parser.parse_args()

    LOG_PATH = Path(args.log).expanduser().resolve()
    LOG_PATH.write_text("", encoding="utf-8")
    log(f"Starting Codex VSIX patcher (Codex {SUPPORTED_VERSION}, patcher v{args.patcher_version})")

    target = resolve_target(args)
    if args.download_only:
        print(f"STOCK_VSIX_PATH: {target}", flush=True)
        log(f"Download-only mode - skipping patch. Stock VSIX at: {target}")
        return 0

    builds_dir = Path(__file__).parent / "builds"
    builds_dir.mkdir(exist_ok=True)
    if args.out:
        out = Path(args.out).resolve()
    else:
        n = 1
        while (builds_dir / f"openai-chatgpt-codex-orbit-{n}.vsix").exists():
            n += 1
        out = builds_dir / f"openai-chatgpt-codex-orbit-{n}.vsix"
    log(f"Output VSIX: {out}")

    with tempfile.TemporaryDirectory(prefix="codex-vsix-patch-") as temp:
        root = Path(temp) / "vsix"
        log("Extracting VSIX")
        with zipfile.ZipFile(target) as zf:
            zf.extractall(root)
        extension_dir = root / "extension"
        manifest = assert_supported_codex(extension_dir)
        log(f"Target verified: {manifest.get('displayName')} v{manifest.get('version')}")
        copy_patched_assets(extension_dir, args.patcher_version)
        verify_extension_dir(extension_dir)
        log("Writing patched VSIX")
        zip_dir(root, out)

    log(f"Patched VSIX written: {out}")
    log("Overall status: updated Codex assets")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"Patch run failed: {exc}")
        raise
