"""The shipped integration must parse on the oldest Python we claim to support.

hacs.json declares a minimum of Home Assistant 2024.6, which runs Python 3.12.
Nothing in custom_components/ may use syntax newer than that.

This is not hypothetical: `ruff format` with target-version = "py314" once
rewrote `except (A, B):` into the PEP 758 form `except A, B:`, which is a
SyntaxError on 3.12 and 3.13 - the integration would not have loaded at all.
Neither the test suite nor mypy caught it, because CI runs 3.14.
"""

import ast
from pathlib import Path

import pytest

MIN_PYTHON = (3, 12)
COMPONENT = Path(__file__).resolve().parents[1] / "custom_components"

SOURCES = sorted(COMPONENT.rglob("*.py"))


def test_sources_were_found():
    assert SOURCES, "no integration sources found - the glob is wrong"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_parses_on_minimum_python(path: Path):
    try:
        ast.parse(path.read_text(), filename=str(path), feature_version=MIN_PYTHON)
    except SyntaxError as err:  # pragma: no cover - only on regression
        pytest.fail(
            f"{path.relative_to(COMPONENT.parent)}:{err.lineno} needs newer than "
            f"Python {'.'.join(map(str, MIN_PYTHON))}: {err.msg}"
        )
