"""Deterministic YAML output."""

from __future__ import annotations

from typing import Any

import yaml


def render(data: Any) -> str:
    rendered = yaml.safe_dump(
        data,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    # safe_dump appends a trailing newline; strip for cleaner CLI output.
    return rendered.rstrip("\n")
