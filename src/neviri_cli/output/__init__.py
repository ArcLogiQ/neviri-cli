"""Output formatters: table / JSON / YAML / tree.

Public API:

    from neviri_cli.output import render, OutputFormat

    print(render(data, fmt="json"))
    print(render(data, fmt="table", no_color=True))

The `OutputFormat` literal type is used by command signatures so Typer/Click
generates a `--output {table,json,yaml}` choice automatically.
"""

from __future__ import annotations

from typing import Any, Literal

from neviri_cli.output import json as _json
from neviri_cli.output import table as _table
from neviri_cli.output import tree as _tree
from neviri_cli.output import yaml as _yaml

OutputFormat = Literal["table", "json", "yaml"]
DEFAULT_FORMAT: OutputFormat = "table"


def render(data: Any, *, fmt: OutputFormat = DEFAULT_FORMAT, no_color: bool = False) -> str:
    """Render `data` in the requested format.

    Tree output is intentionally not selectable here - it's opt-in from
    specific commands via `output.tree.render(...)` directly.
    """
    if fmt == "json":
        return _json.render(data)
    if fmt == "yaml":
        return _yaml.render(data)
    if fmt == "table":
        return _table.render(data, no_color=no_color)
    raise ValueError(f"Unknown output format: {fmt!r}")


__all__ = ["DEFAULT_FORMAT", "OutputFormat", "_json", "_table", "_tree", "_yaml", "render"]
