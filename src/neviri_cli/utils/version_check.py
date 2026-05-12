"""Version-check + self-update helpers.

Used by ``neviri version [--check] [--upgrade]``. Split out from the
command module so the network + filesystem dance can be tested
independently.

Self-update semantics differ by install method:

- **PyInstaller binary** (``sys.frozen is True``): download the new binary
  for the current OS/arch, write to a side file, and either ``os.replace``
  it (Linux/macOS — kernel allows replacing open files) or spawn a
  detached swap helper (Windows — locks running .exes; standard pattern).
- **pip install** (``sys.frozen is False``): no automatic self-update.
  Print the right ``pip install --upgrade`` invocation and exit.
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx

from neviri_cli.exceptions import NetworkError, UserError

GITHUB_API_LATEST_RELEASE = "https://api.github.com/repos/ArcLogiQ/neviri-cli/releases/latest"


@dataclass(frozen=True)
class LatestRelease:
    tag: str  # "v0.9.0b1"
    version: str  # "0.9.0b1"
    html_url: str  # release page
    assets: dict[str, str]  # asset_name -> download_url


def is_binary_install() -> bool:
    """True when running as a PyInstaller-frozen bundle."""
    return getattr(sys, "frozen", False) is True


def get_current_binary_path() -> Path:
    """Path to the running binary (only meaningful for frozen installs)."""
    return Path(sys.executable).resolve()


def fetch_latest_release(*, timeout: float = 10.0) -> LatestRelease:
    """Query GitHub Releases for the latest release.

    Raises :class:`NetworkError` on transport failure.
    """
    try:
        resp = httpx.get(
            GITHUB_API_LATEST_RELEASE,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.TransportError as exc:
        raise NetworkError(f"could not reach github.com: {exc}") from exc

    if resp.status_code >= 400:
        raise NetworkError(f"github.com returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    tag = cast(str, data.get("tag_name", ""))
    version = tag.removeprefix("v")
    assets = {
        cast(str, a["name"]): cast(str, a["browser_download_url"])
        for a in data.get("assets", [])
        if isinstance(a, dict) and "name" in a and "browser_download_url" in a
    }
    return LatestRelease(
        tag=tag,
        version=version,
        html_url=cast(str, data.get("html_url", "")),
        assets=assets,
    )


def _parse_version(v: str) -> tuple[int, int, int, int, int]:
    """Loose semver-ish parser. Returns a sortable tuple.

    Pre-release ordering: a0 < a1 < b0 < b1 < rc0 < final.
    Pre-release rank: a=0, b=1, rc=2, none=3.
    """
    v = v.removeprefix("v")
    rank = 3  # final by default
    pre_num = 0
    for sep, r in (("rc", 2), ("b", 1), ("a", 0)):
        if sep in v:
            base, _, suffix = v.partition(sep)
            try:
                pre_num = int(suffix)
            except ValueError:
                pre_num = 0
            v = base
            rank = r
            break
    parts = v.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        major = minor = patch = 0
    return (major, minor, patch, rank, pre_num)


def is_newer(latest: str, current: str) -> bool:
    """True if ``latest`` is a strictly higher version than ``current``."""
    return _parse_version(latest) > _parse_version(current)


def asset_name_for_current_platform() -> str:
    """Asset filename matching the running OS + CPU architecture.

    Mirrors the names used in release.yml's binary build matrix.
    Returns the bare name without URL; the caller looks it up in
    :attr:`LatestRelease.assets`.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        return "neviri-linux-x86_64"
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "neviri-macos-arm64"
        return "neviri-macos-x86_64"
    if system == "windows":
        return "neviri-windows-x86_64.exe"
    raise UserError(f"no prebuilt binary published for platform {system}/{machine}")


def download_binary(url: str, dest: Path, *, timeout: float = 60.0) -> None:
    """Stream the binary into ``dest``. Sets executable bit on POSIX."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "application/octet-stream"},
        ) as response:
            if response.status_code >= 400:
                raise NetworkError(f"failed to download {url}: HTTP {response.status_code}")
            with dest.open("wb") as out:
                for chunk in response.iter_bytes(64 * 1024):
                    if chunk:
                        out.write(chunk)
    except httpx.TransportError as exc:
        raise NetworkError(f"download failed: {exc}") from exc

    if os.name != "nt":
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def replace_binary(new_binary: Path, current_binary: Path) -> None:
    """Replace the running binary with ``new_binary``.

    On POSIX: ``os.replace`` works because the kernel keeps the old inode
    alive for the running process and removes it on exit.

    On Windows: the running .exe is locked; we generate a tiny .bat that
    waits, swaps the files, and exits. The current process must exit
    immediately after spawning it.
    """
    if os.name != "nt":
        os.replace(new_binary, current_binary)
        return

    # Windows: write a self-deleting batch helper.
    helper = current_binary.with_suffix(".upgrade.bat")
    # ``ping -n 2 127.0.0.1`` is the classic ~1s wait that works without
    # PowerShell. ``timeout /t 1 /nobreak`` would also work but blocks on
    # input redirection in some shells.
    helper.write_text(
        "@echo off\n"
        "ping -n 2 127.0.0.1 > nul\n"
        f'move /Y "{new_binary}" "{current_binary}" > nul\n'
        f'del "{helper}"\n',
        encoding="utf-8",
    )
    # DETACHED_PROCESS = 0x00000008; CREATE_NEW_PROCESS_GROUP = 0x00000200
    # so the helper survives our exit.
    subprocess.Popen(
        ["cmd", "/c", str(helper)],
        creationflags=0x00000008 | 0x00000200,
        close_fds=True,
    )


def perform_self_update(latest: LatestRelease) -> Path:
    """Download the new binary and swap it in.

    Returns the path to the (now-updated) binary. On Windows, the actual
    swap happens after this process exits — callers should call
    ``raise typer.Exit(0)`` immediately after this returns.

    Raises :class:`UserError` if not running as a frozen bundle.
    """
    if not is_binary_install():
        raise UserError(
            "self-update is only supported for binary installs. "
            "For pip installs, run: pip install --upgrade neviri-cli"
        )

    asset_name = asset_name_for_current_platform()
    if asset_name not in latest.assets:
        raise UserError(
            f"release {latest.tag} doesn't include the asset {asset_name!r}. "
            f"Available: {sorted(latest.assets.keys())}"
        )

    current = get_current_binary_path()
    tmp_dir = Path(tempfile.mkdtemp(prefix="neviri-upgrade-"))
    new_bin = tmp_dir / asset_name
    download_binary(latest.assets[asset_name], new_bin)

    replace_binary(new_bin, current)
    # Best-effort temp cleanup (Windows: the new binary is still in
    # tmp_dir until the helper moves it; skip rmtree there).
    if os.name != "nt":
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return current
