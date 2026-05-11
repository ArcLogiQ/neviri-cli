"""Table output via `rich`.

Accepts:
- list[dict]      -> columns from union of keys (insertion-order)
- dict            -> two-column "Field / Value" table
- list[scalar]    -> single-column "Value" table
- scalar / None   -> stringified

`no_color=True` disables ANSI sequences.
"""

from __future__ import annotations

import io
from typing import Any

from rich.console import Console
from rich.table import Table


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_stringify(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={_stringify(v)}" for k, v in value.items())
    return str(value)


def _columns_from_records(records: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for r in records:
        for k in r.keys():
            seen.setdefault(k, None)
    return list(seen.keys())


def _build_table(data: Any) -> Table:
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        cols = _columns_from_records(data)
        table = Table(show_header=True, header_style="bold")
        for c in cols:
            table.add_column(c)
        for row in data:
            table.add_row(*[_stringify(row.get(c)) for c in cols])
        return table

    if isinstance(data, dict):
        table = Table(show_header=True, header_style="bold")
        table.add_column("Field")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), _stringify(v))
        return table

    if isinstance(data, list):
        table = Table(show_header=True, header_style="bold")
        table.add_column("Value")
        for item in data:
            table.add_row(_stringify(item))
        return table

    table = Table(show_header=False)
    table.add_column("Value")
    table.add_row(_stringify(data))
    return table


def render(data: Any, *, no_color: bool = False) -> str:
    buf = io.StringIO()
    console = Console(
        file=buf,
        width=120,
        force_terminal=not no_color,
        no_color=no_color,
        legacy_windows=False,
    )
    console.print(_build_table(data))
    return buf.getvalue().rstrip("\n")
