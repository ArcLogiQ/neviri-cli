"""Cold-start budget tests (Phase 3 / Story 20).

Two layers:

1. **Determinism layer** (the important one): after ``import neviri_cli.app``
   and after ``app(['--version'])``, certain heavy modules MUST NOT have been
   imported. This pins the lazy-loading contract regardless of CPU speed,
   Python build, or noisy CI runners.

2. **Walltime layer** (best-effort): a generous wall-clock budget on the
   ``--version`` path. Loose enough to survive slow GitHub Actions runners
   but tight enough to catch a regression (e.g. someone re-introducing
   eager imports at the top of ``app.py``).

If a regression is genuine, prefer the determinism layer over the walltime
budget — the walltime test can be relaxed without losing signal as long as
the determinism test holds.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

# Modules that must NOT be imported on the cold ``import neviri_cli.app`` /
# ``neviri --version`` path. If you find yourself wanting to remove one of
# these, you almost certainly need to defer the import behind a function call
# rather than relax this test.
HEAVY_MODULES_FORBIDDEN_AT_IMPORT: tuple[str, ...] = (
    "httpx",
    "keyring",
    "rich.progress",
    "rich.table",
    "respx",
    "neviri_cli.client.base",
    "neviri_cli.client.factory",
    "neviri_cli.commands.app",
    "neviri_cli.commands.auth",
    "neviri_cli.commands.vm",
    "neviri_cli.commands.deploy",
    "neviri_cli.commands.load_balancer",
    "neviri_cli.commands.payment",
)


def _snapshot_modules_after(script: str) -> set[str]:
    """Run ``script`` in a fresh Python process and return ``sys.modules`` keys."""
    full = f"""
import sys
{script}
print('___MODULES___')
print('|'.join(sorted(sys.modules)))
"""
    result = subprocess.run(
        [sys.executable, "-c", full],
        capture_output=True,
        text=True,
        check=True,
        env={
            # Disable telemetry so the test path is identical to a real
            # `--version` invocation in CI.
            "NEVIRI_TELEMETRY": "disable",
            **_passthrough_env(),
        },
    )
    blob = result.stdout.split("___MODULES___", 1)[1].strip()
    return set(blob.split("|"))


def _passthrough_env() -> dict[str, str]:
    """Pass through enough of the parent env that subprocess Python boots."""
    import os

    keys = ("PATH", "PYTHONPATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME")
    return {k: os.environ[k] for k in keys if k in os.environ}


def test_import_app_does_not_pull_heavy_modules() -> None:
    """Importing ``neviri_cli.app`` must not transitively load httpx/keyring/etc."""
    modules = _snapshot_modules_after("import neviri_cli.app")
    leaked = [m for m in HEAVY_MODULES_FORBIDDEN_AT_IMPORT if m in modules]
    assert not leaked, (
        f"Heavy modules leaked into the cold-start path: {leaked}. "
        f"Add them behind a function-local import (see app.py docstring)."
    )


def test_version_does_not_pull_heavy_modules() -> None:
    """Even calling ``app(['--version'])`` must stay on the fast path."""
    modules = _snapshot_modules_after(
        "from neviri_cli.app import app\n"
        "try:\n"
        "    app(['--version'], standalone_mode=False)\n"
        "except SystemExit:\n"
        "    pass\n"
    )
    leaked = [m for m in HEAVY_MODULES_FORBIDDEN_AT_IMPORT if m in modules]
    assert not leaked, (
        f"Heavy modules leaked during --version dispatch: {leaked}. "
        f"The --version path should never need an HTTP client or keyring."
    )


@pytest.mark.parametrize("invocation", ["--version", "-V"])
def test_version_walltime_under_budget(invocation: str) -> None:
    """Loose walltime budget on the ``--version`` path.

    The budget is 1500ms — comfortably above the ~280ms we see on dev
    installs, with headroom for slow GitHub Actions runners and PyInstaller
    binary unpacking. If this trips, run ``python -X importtime`` to find
    what regressed.
    """
    code = (
        "from neviri_cli.app import app\n"
        "try:\n"
        f"    app([{invocation!r}], standalone_mode=False)\n"
        "except SystemExit:\n"
        "    pass\n"
    )
    # Run 3x and take the best (warmest cache) to dampen CI jitter.
    timings = []
    for _ in range(3):
        start = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            env={"NEVIRI_TELEMETRY": "disable", **_passthrough_env()},
        )
        timings.append((time.perf_counter() - start) * 1000)
    best = min(timings)
    assert best < 1500, (
        f"`neviri {invocation}` cold start took {best:.0f}ms — over the 1500ms budget. "
        f"All timings: {[f'{t:.0f}ms' for t in timings]}. "
        f"Profile with `python -X importtime -c 'import neviri_cli.app'`."
    )


def test_lazy_subcommand_registry_is_complete() -> None:
    """Every lazy spec must resolve — guards against a typo'd module path."""
    import importlib

    from neviri_cli.app import _LAZY_COMMANDS, _LAZY_SUBCOMMANDS

    for name, spec in {**_LAZY_SUBCOMMANDS, **_LAZY_COMMANDS}.items():
        modname, _, attr = spec.partition(":")
        module = importlib.import_module(modname)
        assert hasattr(module, attr), (
            f"Lazy spec '{name}' -> '{spec}': module {modname!r} has no attribute {attr!r}"
        )


def test_top_level_help_lists_all_subcommands() -> None:
    """`neviri --help` must show every lazy-mounted subcommand."""
    from neviri_cli.app import _LAZY_COMMANDS, _LAZY_SUBCOMMANDS, app

    runner_result = subprocess.run(
        [sys.executable, "-c", "from neviri_cli.app import app; app(['--help'])"],
        capture_output=True,
        text=True,
        env={"NEVIRI_TELEMETRY": "disable", **_passthrough_env()},
    )
    out = runner_result.stdout + runner_result.stderr
    missing = [name for name in {**_LAZY_SUBCOMMANDS, **_LAZY_COMMANDS} if name not in out]
    assert not missing, f"--help is missing subcommands: {missing}\n\n{out}"
    # Sanity: the runner shouldn't have crashed.
    del app  # silence unused
    _ = json.dumps  # keep stdlib import live for parity with peers
