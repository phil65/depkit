from __future__ import annotations

import importlib
import importlib.metadata
import os
import subprocess
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest

from depkit.depmanager import DependencyError, DependencyManager


if TYPE_CHECKING:
    from pathlib import Path


class TestPEP723Dependencies:
    def test_parse_deps(self) -> None:
        content = """# Dependencies:
        #   requests>=2.31.0
        #   pandas>=2.0.0

        import requests
        import pandas as pd
        """
        manager = DependencyManager()
        deps = list(manager.parse_pep723_deps(content))
        assert deps == ["requests>=2.31.0", "pandas>=2.0.0"]

    def test_no_deps(self) -> None:
        content = """import sys
        print('hello')
        """
        manager = DependencyManager()
        deps = list(manager.parse_pep723_deps(content))
        assert not deps

    def test_scan_directory(self, tmp_path: Path) -> None:
        # Create test files
        file1 = tmp_path / "test1.py"
        file1.write_text("""
        # Dependencies:
        #   requests>=2.31.0
        """)

        file2 = tmp_path / "test2.py"
        file2.write_text("""
        # Dependencies:
        #   pandas>=2.0.0
        """)

        manager = DependencyManager(extra_paths=[str(tmp_path)])
        deps = manager.scan_for_dependencies(tmp_path)
        assert deps == {"requests>=2.31.0", "pandas>=2.0.0"}

    @pytest.mark.asyncio
    async def test_setup_with_nonexistent_script(self) -> None:
        """Test setup with nonexistent script."""
        async with DependencyManager(scripts=["/nonexistent/script.py"]) as manager:
            # Should handle missing script gracefully
            assert not manager.requirements

    @pytest.mark.asyncio
    async def test_setup_with_pip_error(
        self,
        mock_subprocess: mock.MagicMock,
        mock_importlib: mock.MagicMock,
    ) -> None:
        """Test setup with pip installation error."""
        # Set up conditions for pip install to be triggered:
        # 1. Package not found check should fail
        mock_importlib.side_effect = importlib.metadata.PackageNotFoundError()
        # 2. Pip install should fail
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, [], stderr="Error")

        # Pass some requirements that need to be installed

        with pytest.raises(DependencyError, match="Failed to install requirements"):
            async with DependencyManager(requirements=["some-package>=1.0.0"]):
                pass


class TestDependencyManager:
    @pytest.mark.asyncio
    async def test_setup(
        self,
        settings: dict[str, Any],
        mock_subprocess: mock.MagicMock,
        mock_importlib: mock.MagicMock,
    ) -> None:
        """Test complete setup."""
        mock_importlib.side_effect = importlib.metadata.PackageNotFoundError()

        async with DependencyManager(**settings) as manager:
            assert manager._installed
            mock_subprocess.assert_called_once()

    def test_detect_uv_environment(self) -> None:
        """Test UV environment detection."""
        manager = DependencyManager()

        # Test UV_VIRTUAL_ENV detection
        with mock.patch.dict(os.environ, {"UV_VIRTUAL_ENV": "/some/path"}):
            assert manager._detect_uv_environment()

        # Test UV in PATH
        with mock.patch("shutil.which", return_value="/path/to/uv"):
            assert manager._detect_uv_environment()

        # Test no UV
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            assert not manager._detect_uv_environment()

    @pytest.mark.asyncio
    async def test_setup_with_invalid_script(self, tmp_path: Path) -> None:
        """Test setup with invalid Python script."""
        script = tmp_path / "invalid.py"
        script.write_text("This is not valid Python!", encoding="utf-8")
        async with DependencyManager(scripts=[str(script)]) as manager:
            # Should handle invalid script gracefully
            assert not manager.requirements

    @pytest.mark.asyncio
    async def test_cleanup(self, tmp_path: Path) -> None:
        """Test cleanup of temporary files."""
        script = tmp_path / "test.py"
        script.write_text("print('test')", encoding="utf-8")

        manager = DependencyManager(scripts=[str(script)])
        scripts_dir = manager._scripts_dir

        assert scripts_dir.exists()
        manager.cleanup()
        assert not scripts_dir.exists()

    @pytest.mark.asyncio
    async def test_setup_with_scripts(self, tmp_path: Path) -> None:
        """Test setup with script loading."""
        script = tmp_path / "test.py"
        text = "# Dependencies:\n#   requests>=2.0.0\n\nimport requests\n"
        script.write_text(text, encoding="utf-8")
        async with DependencyManager(
            scripts=[str(script)],
            requirements=["pandas"],
        ) as manager:
            assert "requests>=2.0.0" in manager.requirements
            assert "pandas" in manager.requirements
