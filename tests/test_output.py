"""Output formatter tests."""

from __future__ import annotations

import json as stdlib_json
from datetime import UTC

import pytest

from neviri_cli.output import DEFAULT_FORMAT, render
from neviri_cli.output import json as json_fmt
from neviri_cli.output import table as table_fmt
from neviri_cli.output import tree as tree_fmt
from neviri_cli.output import yaml as yaml_fmt

# ---------- json ----------


def test_json_keys_are_sorted() -> None:
    data = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    out = json_fmt.render(data)
    parsed = stdlib_json.loads(out)
    assert parsed == data
    # Order in the rendered string: a before b before c
    assert out.find('"a"') < out.find('"b"') < out.find('"c"')


def test_json_renders_lists_of_dicts() -> None:
    data = [{"id": 1}, {"id": 2}]
    out = json_fmt.render(data)
    assert stdlib_json.loads(out) == data


def test_json_default_str_for_unserialisable() -> None:
    from datetime import datetime

    data = {"created": datetime(2026, 1, 1, tzinfo=UTC)}
    out = json_fmt.render(data)
    assert "2026-01-01" in out


def test_json_is_indented_for_human_diff() -> None:
    out = json_fmt.render({"a": 1})
    assert "\n" in out  # multi-line


# ---------- yaml ----------


def test_yaml_keys_are_sorted() -> None:
    out = yaml_fmt.render({"b": 1, "a": 2})
    assert out.index("a:") < out.index("b:")


def test_yaml_block_style_for_lists() -> None:
    out = yaml_fmt.render([{"id": 1}, {"id": 2}])
    # block style uses "-" prefix, not flow "[...]"
    assert out.startswith("-")
    assert "[" not in out.split("\n")[0]


def test_yaml_no_trailing_newline() -> None:
    out = yaml_fmt.render({"a": 1})
    assert not out.endswith("\n")


# ---------- table ----------


def test_table_renders_list_of_dicts_with_headers() -> None:
    out = table_fmt.render([{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}], no_color=True)
    assert "id" in out
    assert "name" in out
    assert "alice" in out
    assert "bob" in out


def test_table_dict_uses_field_value_columns() -> None:
    out = table_fmt.render({"id": 1, "name": "alice"}, no_color=True)
    assert "Field" in out
    assert "Value" in out
    assert "alice" in out


def test_table_handles_scalar() -> None:
    out = table_fmt.render(42, no_color=True)
    assert "42" in out


def test_table_handles_list_of_scalars() -> None:
    out = table_fmt.render(["one", "two"], no_color=True)
    assert "one" in out
    assert "two" in out


def test_table_no_color_strips_ansi() -> None:
    out = table_fmt.render([{"a": 1}], no_color=True)
    # \x1b is the ANSI escape character
    assert "\x1b" not in out


def test_table_unions_keys_across_records() -> None:
    out = table_fmt.render(
        [{"a": 1}, {"a": 2, "b": 3}, {"c": 4}],
        no_color=True,
    )
    # Headers in insertion order across the record union
    assert out.index("a") < out.index("b") < out.index("c")


def test_table_stringifies_none_as_empty() -> None:
    out = table_fmt.render([{"name": None}], no_color=True)
    # The "None" string should NOT be rendered
    assert "None" not in out


def test_table_stringifies_booleans_lowercase() -> None:
    out = table_fmt.render([{"active": True, "deleted": False}], no_color=True)
    assert "true" in out
    assert "false" in out


# ---------- tree ----------


def test_tree_renders_nested_dict() -> None:
    out = tree_fmt.render({"a": {"b": {"c": 1}}}, no_color=True)
    assert "a" in out
    assert "b" in out
    assert "c" in out


def test_tree_renders_lists_with_indices() -> None:
    out = tree_fmt.render([1, 2, 3], no_color=True)
    assert "[0]" in out
    assert "[1]" in out
    assert "[2]" in out


# ---------- dispatch ----------


def test_render_dispatch_json() -> None:
    out = render({"a": 1}, fmt="json")
    assert stdlib_json.loads(out) == {"a": 1}


def test_render_dispatch_yaml() -> None:
    out = render({"a": 1}, fmt="yaml")
    assert "a:" in out


def test_render_dispatch_table() -> None:
    out = render({"a": 1}, fmt="table", no_color=True)
    assert "a" in out


def test_render_dispatch_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown output format"):
        render({}, fmt="xml")  # type: ignore[arg-type]


def test_default_format_is_table() -> None:
    assert DEFAULT_FORMAT == "table"
