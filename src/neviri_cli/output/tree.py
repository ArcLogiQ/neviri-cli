"""Tree output for nested structures.

Not exposed via the global --output flag (that takes table/json/yaml). Tree is
opt-in: specific commands that produce hierarchical data (e.g. `neviri network
inspect` showing subnets and routes) call this directly.
"""

from __future__ import annotations

import io
from typing import Any

from rich.console import Console
from rich.tree import Tree


def _add(node: Tree, value: Any) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            child = node.add(str(k))
            _add(child, v)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            child = node.add(f"[{i}]")
            _add(child, item)
    else:
        node.add(str(value) if value is not None else "")


def render(data: Any, *, label: str = "root", no_color: bool = False) -> str:
    root = Tree(label)
    _add(root, data)
    buf = io.StringIO()
    console = Console(
        file=buf,
        width=120,
        force_terminal=not no_color,
        no_color=no_color,
        legacy_windows=False,
    )
    console.print(root)
    return buf.getvalue().rstrip("\n")
