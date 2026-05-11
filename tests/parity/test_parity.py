"""Parity test (Story 14): every backend route is either mapped to a CLI
command or explicitly excluded with rationale.

Fails CI when:
  - Backend adds a route that isn't in ROUTE_MAP nor EXCLUDED.
  - A ROUTE_MAP / EXCLUDED entry references a route that no longer exists.
  - A route ends up in both ROUTE_MAP and EXCLUDED (ambiguity).

Refreshing the snapshot:

    python scripts/refresh-openapi-snapshot.py

This re-parses the backend's router source files and updates
``tests/parity/backend_routes.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.parity.route_map import EXCLUDED, ROUTE_MAP

SNAPSHOT_PATH = Path(__file__).parent / "backend_routes.json"


def _load_snapshot() -> set[tuple[str, str]]:
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {(r["method"], r["path"]) for r in data}


@pytest.fixture(scope="module")
def backend_routes() -> set[tuple[str, str]]:
    routes = _load_snapshot()
    assert routes, "backend route snapshot is empty"
    return routes


def _format_routes(routes: set[tuple[str, str]]) -> str:
    return "\n  ".join(f"{m} {p}" for m, p in sorted(routes))


def test_snapshot_is_loadable() -> None:
    """Schema sanity check on backend_routes.json itself."""
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 100, f"suspiciously few backend routes: {len(data)}"
    for r in data:
        assert set(r.keys()) >= {"method", "path"}, r
        assert r["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE"}, r
        assert r["path"].startswith("/api/v1/"), r


def test_no_route_is_in_both_map_and_excluded() -> None:
    """An entry must be in exactly one of ROUTE_MAP / EXCLUDED, not both."""
    overlap = set(ROUTE_MAP.keys()) & set(EXCLUDED.keys())
    if overlap:
        raise AssertionError(
            "These routes appear in BOTH ROUTE_MAP and EXCLUDED:\n  " + _format_routes(overlap)
        )


def test_every_backend_route_is_mapped_or_excluded(
    backend_routes: set[tuple[str, str]],
) -> None:
    """The hard parity guarantee: 100% of backend routes are accounted for."""
    accounted = set(ROUTE_MAP.keys()) | set(EXCLUDED.keys())
    missing = backend_routes - accounted
    if missing:
        raise AssertionError(
            f"\n{len(missing)} backend route(s) are neither mapped to a CLI command "
            f"nor in EXCLUDED:\n  {_format_routes(missing)}\n\n"
            "Either:\n"
            "  (a) Add a CLI command that wraps the route and map it in route_map.py\n"
            "  (b) Add the route to EXCLUDED with a one-line rationale"
        )


def test_no_drift_route_map_to_nonexistent_backend(
    backend_routes: set[tuple[str, str]],
) -> None:
    """Drift detection: a ROUTE_MAP entry must reference a real backend route."""
    stale = set(ROUTE_MAP.keys()) - backend_routes
    if stale:
        raise AssertionError(
            f"\n{len(stale)} ROUTE_MAP entries reference routes that no longer exist "
            f"in backend_routes.json:\n  {_format_routes(stale)}\n\n"
            "Either:\n"
            "  (a) Refresh the snapshot: python scripts/refresh-openapi-snapshot.py\n"
            "  (b) Remove the stale entry if the backend route was intentionally deleted"
        )


def test_no_drift_excluded_to_nonexistent_backend(
    backend_routes: set[tuple[str, str]],
) -> None:
    """Drift detection: an EXCLUDED entry must reference a real backend route too.

    Otherwise dead entries pile up and the file's rationale becomes unreliable.
    """
    stale = set(EXCLUDED.keys()) - backend_routes
    if stale:
        raise AssertionError(
            f"\n{len(stale)} EXCLUDED entries reference routes that no longer exist:\n  "
            + _format_routes(stale)
            + "\n\nRefresh the snapshot or remove the stale entry."
        )


def test_parity_coverage_summary(backend_routes: set[tuple[str, str]]) -> None:
    """Informational: print parity stats. Always passes; useful for CI logs."""
    mapped = len(set(ROUTE_MAP.keys()) & backend_routes)
    excluded = len(set(EXCLUDED.keys()) & backend_routes)
    total = len(backend_routes)
    print(
        f"\nparity: {mapped} mapped + {excluded} excluded = {mapped + excluded}/{total} "
        f"backend routes accounted for"
    )
    # Pin the achievable scope: at least 60% of routes should be mapped to
    # real CLI commands (not just excluded). Drop below = we're not really
    # shipping a CLI.
    assert mapped >= int(total * 0.60), (
        f"only {mapped}/{total} routes are mapped to a CLI command — too many are excluded"
    )
