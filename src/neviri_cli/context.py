"""Per-invocation runtime context.

Carries global flag values (`--output`, `--no-color`, `--debug`, `--profile`)
from the Typer root callback down to individual command implementations.
Stored on `typer.Context.obj` so commands access it via `ctx.obj`.
"""

from __future__ import annotations

from dataclasses import dataclass

from neviri_cli.output import DEFAULT_FORMAT, OutputFormat


@dataclass
class CLIContext:
    output: OutputFormat = DEFAULT_FORMAT
    no_color: bool = False
    debug: bool = False
    profile: str = "default"
