#!/usr/bin/env python3
"""Refresh tests/parity/backend_routes.json by parsing the backend's router
source files.

Run from the neviri-cli repo root:

    python scripts/refresh-openapi-snapshot.py

The script doesn't need a running backend - it parses router .py files in
``neviri-backend/`` (sibling repo by default; override via env var
``NEVIRI_BACKEND_PATH``). Output is a sorted list of
``{"method": "GET", "path": "/api/v1/..."}`` tuples that the parity test
compares against the CLI's route_map.

Use cases:
    - Backend ships a new endpoint; run this; commit the updated snapshot;
      add a corresponding entry to ``tests/parity/route_map.py``.
    - Backend renames an endpoint; the diff to the snapshot tells the CLI
      maintainer to update the route map.

Limitations: regex-based, so it misses routes that use:
    - Decorator argument indirection (path stored in a variable)
    - Routes added via ``app.include_router(...)`` with a different prefix
      than the one declared on the ``APIRouter``
    - Routes marked ``include_in_schema=False`` (still extracted - parity
      test treats them like any other route; they can go in EXCLUDED)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

API_V1_PREFIX = "/api/v1"

ROUTE_DECORATOR_RE = re.compile(
    r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']',
    re.MULTILINE,
)
PREFIX_RE = re.compile(
    r'APIRouter\s*\(\s*[^)]*?\bprefix\s*=\s*["\']([^"\']+)["\']',
    re.DOTALL,
)


def extract_routes_from_file(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    prefix_match = PREFIX_RE.search(text)
    router_prefix = prefix_match.group(1) if prefix_match else ""

    routes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in ROUTE_DECORATOR_RE.finditer(text):
        method = m.group(1).upper()
        sub_path = m.group(2)
        full_path = f"{API_V1_PREFIX}{router_prefix}{sub_path}"
        # Normalise trailing slash so /apps and /apps/ aren't treated as two routes.
        # The backend has redirect_slashes=False so they ARE different routes, but
        # they're conceptually the same endpoint; dedupe on (method, normalized).
        normalized = full_path.rstrip("/") or "/"
        if (method, normalized) in seen:
            continue
        seen.add((method, normalized))
        routes.append({"method": method, "path": full_path})
    return routes


def find_backend_routers(backend_path: Path) -> list[Path]:
    routers_dir = backend_path / "app" / "routers"
    if not routers_dir.exists():
        raise SystemExit(
            f"backend routers dir not found at {routers_dir}. "
            "Set NEVIRI_BACKEND_PATH to the neviri-backend repo root."
        )
    return sorted(p for p in routers_dir.rglob("*.py") if p.name != "__init__.py")


def main() -> int:
    here = Path(__file__).resolve().parent.parent  # neviri-cli/
    default_backend = (here / "../neviri-backend").resolve()
    backend_path = Path(os.environ.get("NEVIRI_BACKEND_PATH", default_backend)).resolve()

    print(f"Reading backend routers from: {backend_path}", file=sys.stderr)

    all_routes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for router_file in find_backend_routers(backend_path):
        rel = router_file.relative_to(backend_path)
        file_routes = extract_routes_from_file(router_file)
        for r in file_routes:
            key = (r["method"], r["path"])
            if key in seen:
                continue
            seen.add(key)
            r["source"] = str(rel).replace("\\", "/")
            all_routes.append(r)

    # Sort for deterministic snapshot.
    all_routes.sort(key=lambda r: (r["path"], r["method"]))

    snapshot_path = here / "tests" / "parity" / "backend_routes.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(all_routes, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_routes)} routes to {snapshot_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
