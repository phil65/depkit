from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from depkit.depmanager import DependencyManager, ScriptError


if TYPE_CHECKING:
    from pathlib import Path


# Test data
SCRIPT_WITH_DEPS = """\
# /// script
# dependencies = [
#   "requests>=2.31.0",
#   "pandas>=2.0.0"
# ]
# requires-python = ">=3.12"
# ///

import requests
import pandas as pd
"""

SCRIPT_SINGLE_DEP = """\
# /// script
# dependencies = ["requests>=2.31.0"]
# ///
"""

SCRIPT_SINGLE_DEP_2 = """\
# /// script
# dependencies = ["pandas>=2.0.0"]
# ///
"""

INVALID_TOML = """\
# /// script
# dependencies = ["incomplete
# ///
"""

MULTIPLE_BLOCKS = """\
# /// script
# dependencies = ["pkg1"]
# ///

# /// script
# dependencies = ["pkg2"]
# ///
"""

PYTHON_VERSION_REQ = """\
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""


class TestPEP723Dependencies:
    def test_parse_deps(self) -> None:
        """Test parsing of PEP 723 dependencies."""
        manager = DependencyManager()
        deps = list(manager.parse_pep723_deps(SCRIPT_WITH_DEPS))
        assert deps == ["requests>=2.31.0", "pandas>=2.0.0"]

    def test_scan_directory(self, tmp_path: Path) -> None:
        """Test scanning directory for PEP 723 dependencies."""
        # Create test files
        file1 = tmp_path / "test1.py"
        file1.write_text(SCRIPT_SINGLE_DEP)

        file2 = tmp_path / "test2.py"
        file2.write_text(SCRIPT_SINGLE_DEP_2)

        manager = DependencyManager(extra_paths=[str(tmp_path)])
        deps = manager.scan_for_dependencies(tmp_path)
        assert deps == {"requests>=2.31.0", "pandas>=2.0.0"}

    def test_invalid_toml(self) -> None:
        """Test handling of invalid TOML in script metadata."""
        manager = DependencyManager()
        with pytest.raises(ScriptError, match="Invalid TOML"):
            list(manager.parse_pep723_deps(INVALID_TOML))

    def test_multiple_metadata_blocks(self) -> None:
        """Test handling of multiple script metadata blocks."""
        manager = DependencyManager()
        with pytest.raises(ScriptError, match="Multiple script metadata blocks"):
            list(manager.parse_pep723_deps(MULTIPLE_BLOCKS))

    def test_python_version_requirement(self) -> None:
        """Test parsing of Python version requirements."""
        manager = DependencyManager()
        deps = list(manager.parse_pep723_deps(PYTHON_VERSION_REQ))
        assert deps == ["requests"]

    def test_no_deps_block(self) -> None:
        """Test file without dependency block."""
        content = "print('hello')"
        manager = DependencyManager()
        deps = list(manager.parse_pep723_deps(content))
        assert not deps
