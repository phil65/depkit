"""Smoke test: the package imports and reports its version."""

from __future__ import annotations

import depkit


def test_package_imports() -> None:
    """The package can be imported and exposes a version string."""
    assert isinstance(depkit.__version__, str)
