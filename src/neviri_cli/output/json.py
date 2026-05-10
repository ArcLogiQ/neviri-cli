"""Deterministic JSON output.

Treated as a public, versioned contract per architecture proposal section 4.6:
keys are sorted, indent is fixed, datetimes serialize via str(). Snapshot tests
guard the schema. Breaking changes require a major version bump.
"""

from __future__ import annotations

import json
from typing import Any


def render(data: Any) -> str:
    return json.dumps(data, sort_keys=True, indent=2, default=str)
