"""Tests for the version_check helpers (GitHub Releases query + self-update)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from neviri_cli.exceptions import NetworkError, UserError
from neviri_cli.utils.version_check import (
    GITHUB_API_LATEST_RELEASE,
    _parse_version,
    asset_name_for_current_platform,
    download_binary,
    fetch_latest_release,
    is_binary_install,
    is_newer,
    perform_self_update,
    replace_binary,
)

# ---------- version comparison ----------


def test_parse_version_handles_dotted() -> None:
    assert _parse_version("1.2.3") == (1, 2, 3, 3, 0)


def test_parse_version_handles_v_prefix() -> None:
    assert _parse_version("v1.2.3") == _parse_version("1.2.3")


def test_parse_version_rank_pre_release() -> None:
    # a < b < rc < final
    assert _parse_version("1.0.0a1")[3] == 0
    assert _parse_version("1.0.0b1")[3] == 1
    assert _parse_version("1.0.0rc1")[3] == 2
    assert _parse_version("1.0.0")[3] == 3


def test_is_newer_simple() -> None:
    assert is_newer("1.0.1", "1.0.0")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("1.0.0", "1.0.1")


def test_is_newer_pre_release_ordering() -> None:
    assert is_newer("0.9.0b1", "0.1.0a1")
    assert is_newer("0.9.0b2", "0.9.0b1")
    assert is_newer("0.9.0rc1", "0.9.0b9")
    assert is_newer("1.0.0", "0.9.0rc1")


def test_is_newer_pre_release_to_final() -> None:
    assert is_newer("0.9.0", "0.9.0b1")
    assert not is_newer("0.9.0b2", "0.9.0")


# ---------- fetch_latest_release ----------


@respx.mock
def test_fetch_latest_release_returns_parsed() -> None:
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/x/y/releases/tag/v1.0.0",
                "assets": [
                    {
                        "name": "neviri-linux-x86_64",
                        "browser_download_url": "https://x/neviri-linux-x86_64",
                    },
                    {
                        "name": "neviri-windows-x86_64.exe",
                        "browser_download_url": "https://x/neviri-windows-x86_64.exe",
                    },
                ],
            },
        )
    )
    rel = fetch_latest_release()
    assert rel.tag == "v1.0.0"
    assert rel.version == "1.0.0"
    assert rel.html_url.endswith("v1.0.0")
    assert rel.assets["neviri-linux-x86_64"].endswith("neviri-linux-x86_64")


@respx.mock
def test_fetch_latest_release_404_raises_network_error() -> None:
    respx.get(GITHUB_API_LATEST_RELEASE).mock(return_value=httpx.Response(404))
    with pytest.raises(NetworkError):
        fetch_latest_release()


@respx.mock
def test_fetch_latest_release_transport_error_raises_network_error() -> None:
    respx.get(GITHUB_API_LATEST_RELEASE).mock(side_effect=httpx.ConnectError("no DNS"))
    with pytest.raises(NetworkError):
        fetch_latest_release()


@respx.mock
def test_fetch_latest_release_handles_malformed_assets() -> None:
    """Defensive: skip asset entries that don't have name + browser_download_url."""
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v1.0.0",
                "assets": [
                    {"name": "ok", "browser_download_url": "u"},
                    {"name": "missing-url"},
                    "not-a-dict",
                ],
            },
        )
    )
    rel = fetch_latest_release()
    assert rel.assets == {"ok": "u"}


# ---------- asset_name_for_current_platform ----------


def test_asset_name_linux() -> None:
    with patch("platform.system", return_value="Linux"):
        assert asset_name_for_current_platform() == "neviri-linux-x86_64"


def test_asset_name_macos_arm() -> None:
    with (
        patch("platform.system", return_value="Darwin"),
        patch("platform.machine", return_value="arm64"),
    ):
        assert asset_name_for_current_platform() == "neviri-macos-arm64"


def test_asset_name_macos_intel() -> None:
    with (
        patch("platform.system", return_value="Darwin"),
        patch("platform.machine", return_value="x86_64"),
    ):
        assert asset_name_for_current_platform() == "neviri-macos-x86_64"


def test_asset_name_windows() -> None:
    with patch("platform.system", return_value="Windows"):
        assert asset_name_for_current_platform() == "neviri-windows-x86_64.exe"


def test_asset_name_unknown_platform_raises() -> None:
    with patch("platform.system", return_value="FreeBSD"):
        with pytest.raises(UserError):
            asset_name_for_current_platform()


# ---------- is_binary_install ----------


def test_is_binary_install_false_when_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    assert not is_binary_install()


def test_is_binary_install_true_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.frozen", True, raising=False)
    assert is_binary_install()


# ---------- download_binary ----------


@respx.mock
def test_download_binary_writes_file(tmp_path: Path) -> None:
    payload = b"PK\x03\x04fake-binary"
    respx.get("https://x.test/neviri").mock(return_value=httpx.Response(200, content=payload))
    dest = tmp_path / "neviri-linux-x86_64"
    download_binary("https://x.test/neviri", dest)
    assert dest.read_bytes() == payload


@respx.mock
def test_download_binary_404_raises(tmp_path: Path) -> None:
    respx.get("https://x.test/missing").mock(return_value=httpx.Response(404))
    with pytest.raises(NetworkError):
        download_binary("https://x.test/missing", tmp_path / "out")


@respx.mock
def test_download_binary_creates_parent_dirs(tmp_path: Path) -> None:
    respx.get("https://x.test/n").mock(return_value=httpx.Response(200, content=b"hi"))
    dest = tmp_path / "deep" / "nested" / "neviri"
    download_binary("https://x.test/n", dest)
    assert dest.exists()


# ---------- replace_binary (POSIX path; Windows path tested via mock) ----------


def test_replace_binary_posix_uses_os_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("os.name", "posix")
    src = tmp_path / "new"
    src.write_bytes(b"new")
    dst = tmp_path / "current"
    dst.write_bytes(b"old")

    replace_binary(src, dst)
    assert dst.read_bytes() == b"new"
    assert not src.exists()


def test_replace_binary_windows_spawns_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("os.name", "nt")
    src = tmp_path / "new.exe"
    src.write_bytes(b"new")
    dst = tmp_path / "current.exe"
    dst.write_bytes(b"old")

    with patch("neviri_cli.utils.version_check.subprocess.Popen") as popen:
        replace_binary(src, dst)
    # The helper batch file was created next to the current binary
    helper = dst.with_suffix(".upgrade.bat")
    assert helper.exists()
    content = helper.read_text()
    assert "move /Y" in content
    assert str(src) in content
    assert str(dst) in content
    popen.assert_called_once()


# ---------- perform_self_update ----------


def test_perform_self_update_requires_binary_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    from neviri_cli.utils.version_check import LatestRelease

    rel = LatestRelease(tag="v1.0.0", version="1.0.0", html_url="", assets={})
    with pytest.raises(UserError, match="self-update is only supported for binary"):
        perform_self_update(rel)


def test_perform_self_update_missing_asset_for_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    from neviri_cli.utils.version_check import LatestRelease

    rel = LatestRelease(
        tag="v1.0.0", version="1.0.0", html_url="", assets={"some-other-asset": "u"}
    )
    with pytest.raises(UserError, match="doesn't include the asset"):
        perform_self_update(rel)


@respx.mock
@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX-only os.replace path")
def test_perform_self_update_happy_path_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full upgrade flow on a POSIX runner — exercises the os.replace branch."""
    fake_current = tmp_path / "neviri"
    fake_current.write_bytes(b"old")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_current))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    payload = b"\x7fELFnew-binary"
    respx.get("https://x.test/neviri-linux-x86_64").mock(
        return_value=httpx.Response(200, content=payload)
    )

    from neviri_cli.utils.version_check import LatestRelease

    rel = LatestRelease(
        tag="v1.0.0",
        version="1.0.0",
        html_url="",
        assets={"neviri-linux-x86_64": "https://x.test/neviri-linux-x86_64"},
    )
    result_path = perform_self_update(rel)
    assert result_path == fake_current.resolve()
    assert fake_current.read_bytes() == payload


@respx.mock
@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows-only helper-batch path")
def test_perform_self_update_happy_path_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full upgrade flow on a Windows runner — exercises the .bat helper branch.

    cmd.exe isn't run in the test; subprocess.Popen is patched out. We
    verify the helper batch was written next to the binary and that Popen
    would have been called.
    """
    fake_current = tmp_path / "neviri.exe"
    fake_current.write_bytes(b"old")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_current))
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    payload = b"MZnew-binary"
    respx.get("https://x.test/neviri-windows-x86_64.exe").mock(
        return_value=httpx.Response(200, content=payload)
    )

    from neviri_cli.utils.version_check import LatestRelease

    rel = LatestRelease(
        tag="v1.0.0",
        version="1.0.0",
        html_url="",
        assets={
            "neviri-windows-x86_64.exe": "https://x.test/neviri-windows-x86_64.exe",
        },
    )
    with patch("neviri_cli.utils.version_check.subprocess.Popen") as popen:
        result_path = perform_self_update(rel)

    assert result_path == fake_current.resolve()
    helper = fake_current.with_suffix(".upgrade.bat")
    assert helper.exists()
    popen.assert_called_once()
