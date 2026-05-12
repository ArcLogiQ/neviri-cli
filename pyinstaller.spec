# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for `neviri-cli`.

Produces a single-file binary called `neviri` (or `neviri.exe` on Windows)
that wraps the Typer app entry point in ``src/neviri_cli/__main__.py``.

Build locally:

    pyinstaller pyinstaller.spec --clean

The CI workflow in .github/workflows/release.yml runs this on Linux,
macOS (x86_64 and arm64), and Windows on every tag push, attaching the
artefacts to the GitHub Release.

Notes:
- We use one-file mode so users get a single binary; PyInstaller's
  bootloader extracts the bundle to a temp dir on first run, costing
  ~150ms cold-start on top of Python startup. Worth it for distribution.
- `keyring`'s per-platform backends are imported lazily and not detected
  by PyInstaller's static import analysis. Listed as hidden imports.
- `tests`, `mypy`, `respx`, and `pyinstaller` itself are excluded to keep
  the binary smaller. Without these excludes the bundle is ~100MB; with
  them, ~50MB on a typical install.
"""

from PyInstaller.utils.hooks import collect_all

# Collect data files / hidden imports for libraries that use dynamic loading.
typer_datas, typer_binaries, typer_hidden = collect_all("typer")
rich_datas, rich_binaries, rich_hidden = collect_all("rich")


hidden_imports = (
    typer_hidden
    + rich_hidden
    + [
        # keyring loads platform-specific backends at runtime
        "keyring.backends.Windows",
        "keyring.backends.macOS",
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
        # typer's completion class registration (needed for `neviri completion`)
        "typer._completion_classes",
        "typer._completion_shared",
    ]
)


a = Analysis(
    ["src/neviri_cli/__main__.py"],
    pathex=["src"],
    binaries=typer_binaries + rich_binaries,
    datas=typer_datas + rich_datas,
    hiddenimports=hidden_imports,
    excludes=[
        "tests",
        "mypy",
        "respx",
        "PyInstaller",
        # Heavy stdlib modules we don't use
        "tkinter",
        "test",
        "unittest",
        # Notebook / scientific stack pulled in transitively by some envs
        "pandas",
        "numpy",
        "matplotlib",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="neviri",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX reduces size but slows cold start; disabled by default
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # let PyInstaller infer from the running interpreter
    codesign_identity=None,
    entitlements_file=None,
)
