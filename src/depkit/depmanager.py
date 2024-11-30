from __future__ import annotations

import ast
import importlib
import importlib.metadata
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import TYPE_CHECKING, Self


try:
    from upath import UPath as Path
except (ImportError, ModuleNotFoundError):
    from pathlib import Path

type Command = Sequence[str]

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

# PEP 723 regex pattern
SCRIPT_REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)
logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Error during dependency management."""


class ScriptError(DependencyError):
    """Error related to script loading/processing."""


class ImportPathError(DependencyError):
    """Error related to import path resolution."""


class DependencyManager:
    """Manages global tool dependencies."""

    def __init__(
        self,
        prefer_uv: bool = False,
        requirements: list[str] | None = None,
        extra_paths: list[str] | None = None,
        scripts: list[str] | None = None,
        pip_index_url: str | None = None,
    ) -> None:
        self.prefer_uv = prefer_uv
        self.requirements = requirements or []
        self.extra_paths = extra_paths or []
        self.pip_index_url = pip_index_url
        self._installed: set[str] = set()
        self._is_uv = self._detect_uv_environment()
        self.scripts = scripts or []
        self._scripts_dir = Path(tempfile.mkdtemp(prefix="llmling_scripts_"))
        self._module_map: dict[str, str] = {}  # Maps module names to file paths

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(prefer_uv={self.prefer_uv}, "
            f"requirements={self.requirements}, extra_paths={self.extra_paths}, "
            f"pip_index_url={self.pip_index_url})"
        )

    def __enter__(self) -> Self:
        """Set up dependencies on context entry."""
        import asyncio

        asyncio.run(self.setup())
        return self

    def __exit__(self, *exc: object) -> None:
        """Clean up on context exit."""
        self.cleanup()

    async def __aenter__(self) -> Self:
        """Set up dependencies on async context entry."""
        await self.setup()
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Clean up on async context exit."""
        self.cleanup()

    def _setup_script_modules(self) -> None:
        """Set up importable modules from scripts."""
        if not self.scripts:
            return

        for script_path in self.scripts:
            try:
                # Get content using UPath
                content = Path(script_path).read_text()

                # Extract module name from filename
                module_name = Path(script_path).stem

                # Save to temporary location
                module_file = self._scripts_dir / f"{module_name}.py"
                module_file.write_text(content)

                # Map module name to file
                self._module_map[module_name] = str(module_file)

                # Collect PEP 723 dependencies and add to requirements
                self.requirements.extend(self.parse_pep723_deps(content))

            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to process script %s: %s", script_path, exc)

        # Add scripts directory to Python path
        if self._scripts_dir:
            sys.path.insert(0, str(self._scripts_dir))

    def _validate_script(self, content: str, path: str) -> None:
        """Validate Python script content."""
        try:
            ast.parse(content)
        except SyntaxError as exc:
            msg = f"Invalid Python script {path}: {exc}"
            raise DependencyError(msg) from exc

    def _get_unique_module_name(self, name: str) -> str:
        """Get unique module name."""
        if name not in self._module_map:
            return name
        counter = 1
        while f"{name}_{counter}" in self._module_map:
            counter += 1
        return f"{name}_{counter}"

    def verify_import_path(self, import_path: str) -> None:
        """Verify that an import path matches available modules."""
        module_name = import_path.split(".")[0]
        if module_name not in self._module_map:
            msg = (
                f"Import path {import_path!r} references unknown module. "
                f"Available modules: {', '.join(sorted(self._module_map))}"
            )
            raise DependencyError(msg)

    def parse_pep723_deps(self, content: str) -> Iterator[str]:
        """Parse dependency declarations from Python content according to PEP 723.

        Format:
            # /// script
            # dependencies = [
            #   "requests<3",
            #   "rich",
            # ]
            # requires-python = ">=3.11"
            # ///

        Args:
            content: Python source code content

        Yields:
            Dependency specifications

        Raises:
            ScriptError: If the script metadata is invalid or malformed
        """

        def extract_toml(match: re.Match[str]) -> str:
            """Extract TOML content from comment block."""
            return "".join(
                line[2:] if line.startswith("# ") else line[1:]
                for line in match.group("content").splitlines(keepends=True)
            )

        # Find script metadata blocks
        matches = list(
            filter(
                lambda m: m.group("type") == "script", re.finditer(SCRIPT_REGEX, content)
            )
        )

        if len(matches) > 1:
            msg = "Multiple script metadata blocks found"
            raise ScriptError(msg)

        if not matches:
            # Fall back to informal format for backwards compatibility
            yield from self._parse_informal_deps(content)
            return

        try:
            # Parse TOML content
            toml_content = extract_toml(matches[0])
            metadata = tomllib.loads(toml_content)

            # Handle dependencies
            if deps := metadata.get("dependencies"):
                if not isinstance(deps, list):
                    msg = "dependencies must be a list"
                    raise ScriptError(msg)  # noqa: TRY301
                yield from deps

            # Store Python version requirement if needed
            if python_req := metadata.get("requires-python"):
                if not isinstance(python_req, str):
                    msg = "requires-python must be a string"
                    raise ScriptError(msg)  # noqa: TRY301
                # Could store this for version validation if needed
                logger.debug("Script requires Python %s", python_req)

        except tomllib.TOMLDecodeError as exc:
            msg = f"Invalid TOML in script metadata: {exc}"
            raise ScriptError(msg) from exc
        except Exception as exc:
            msg = f"Error parsing script metadata: {exc}"
            raise ScriptError(msg) from exc

    def _parse_informal_deps(self, content: str) -> Iterator[str]:
        """Parse informal dependency declarations (legacy format).

        Format:
            # Dependencies:
            # requests>=2.28.0
            # pandas~=2.0.0

        Args:
            content: Python source code content

        Yields:
            Dependency specifications
        """
        lines = content.splitlines()
        in_deps = False

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                if stripped == "# Dependencies:":
                    in_deps = True
                    continue

                if in_deps and stripped.startswith("#"):
                    if req := stripped.lstrip("#").strip():
                        yield req
                else:
                    in_deps = False
            else:
                # First non-comment line ends informal deps block
                break

    def collect_file_dependencies(self, path: str | os.PathLike[str]) -> set[str]:
        """Collect dependencies from a Python file."""
        try:
            # Use UTF-8 encoding with error handling
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            return set(self.parse_pep723_deps(content))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to parse dependencies from %s: %s", path, exc)
            return set()

    def scan_for_dependencies(self, directory: str | os.PathLike[str]) -> set[str]:
        """Recursively scan directory for PEP 723 dependencies."""
        all_deps: set[str] = set()
        dir_path = Path(directory)

        # Don't scan site-packages or other system directories
        if "site-packages" in str(dir_path):
            return all_deps

        try:
            for path in dir_path.rglob("*.py"):
                all_deps.update(self.collect_file_dependencies(path))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to scan %s for dependencies: %s", directory, exc)
        return all_deps

    def _detect_uv_environment(self) -> bool:
        """Detect if we're running in a uv environment."""
        try:
            return "UV_VIRTUAL_ENV" in os.environ or bool(shutil.which("uv"))
        except Exception:  # noqa: BLE001
            return False

    def _get_pip_command(self) -> list[str]:
        """Get the appropriate pip command based on environment and settings."""
        if self.prefer_uv or self._is_uv:
            # Check for uv in PATH - will find uv.exe on Windows
            if uv_path := shutil.which("uv"):
                return [str(uv_path), "pip"]
            if self.prefer_uv:
                logger.warning("uv requested but not found, falling back to pip")

        # Use sys.executable for cross-platform compatibility
        # On Windows this will be 'python.exe'
        return [sys.executable, "-m", "pip"]

    def install_requirements(self) -> None:
        """Install missing requirements.

        Raises:
            DependencyError: If installation fails
        """
        if not self.requirements:
            return

        missing = self.check_requirements()
        if not missing:
            return

        logger.info("Installing missing requirements: %s", missing)
        cmd = self._get_pip_command()
        cmd.append("install")

        if self.pip_index_url:
            cmd.extend(["--index-url", self.pip_index_url])

        cmd.extend(missing)

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self._installed.update(missing)
            logger.debug("Package install output:\n%s", result.stdout)

        except subprocess.CalledProcessError as exc:
            msg = f"Failed to install requirements: {exc}\nOutput: {exc.stderr}"
            raise DependencyError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error installing requirements: {exc}"
            raise DependencyError(msg) from exc

    def ensure_importable(self, import_path: str) -> None:
        """Ensure a module can be imported."""
        try:
            module_name = import_path.split(".")[0]
            importlib.import_module(module_name)
        except ImportError as exc:
            installed = {dist.name for dist in importlib.metadata.distributions()}
            msg = (
                f"Module {module_name!r} not found. "
                f"Make sure it's included in global_settings.requirements "
                f"or the module path is in global_settings.extra_paths. "
                f"Currently installed packages: {', '.join(sorted(installed))}"
            )
            raise DependencyError(msg) from exc

    def check_requirements(self) -> list[str]:
        """Check which requirements need to be installed.

        Returns:
            List of requirements that are not yet installed
        """
        missing = []
        for req in self.requirements:
            try:
                # Split requirement into name and version specifier
                name = req.split(">=")[0].split("==")[0].split("<")[0].strip()
                importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(req)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error checking requirement %s: %s", req, exc)
                missing.append(req)
        return missing

    def update_python_path(self) -> None:
        """Add extra paths to Python path.

        Updates sys.path with extra paths from settings, ensuring they exist
        and are absolute paths.

        Logs warnings for invalid paths but doesn't raise exceptions.
        """
        if not self.extra_paths:
            return

        for path in self.extra_paths:
            try:
                # pathlib handles path normalization cross-platform
                abs_path = Path(path).resolve()
                if not abs_path.exists():
                    logger.warning("Path does not exist: %s", path)
                    continue
                # Convert to string in platform's format
                if (str_path := str(abs_path)) not in sys.path:
                    sys.path.append(str_path)
                    logger.debug("Added %s to Python path", str_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to add path %s: %s", path, exc)

    def verify_paths(self, paths: Sequence[str | os.PathLike[str]]) -> None:
        """Verify that paths exist and are accessible.

        Args:
            paths: Sequence of paths to verify

        Raises:
            DependencyError: If any path is invalid or inaccessible
        """
        for path in paths:
            try:
                path_obj = Path(path)
                if not path_obj.exists():
                    msg = f"Path does not exist: {path}"
                    raise DependencyError(msg)  # noqa: TRY301
                if not path_obj.is_dir():
                    msg = f"Path is not a directory: {path}"
                    raise DependencyError(msg)  # noqa: TRY301
            except Exception as exc:
                if isinstance(exc, DependencyError):
                    raise
                msg = f"Invalid path {path}: {exc}"
                raise DependencyError(msg) from exc

    def get_installed_requirements(self) -> list[str]:
        """Get list of requirements that were installed.

        Returns:
            List of installed requirement strings
        """
        return sorted(self._installed)

    def get_python_paths(self) -> list[str]:
        """Get current Python path entries.

        Returns:
            List of paths in sys.path
        """
        return sys.path.copy()

    async def setup(self) -> None:
        """Complete setup of dependencies."""
        try:
            # First set up script modules to collect their dependencies
            self._setup_script_modules()

            # Collect all dependencies (explicit + PEP 723)
            requirements = set(self.requirements)

            # Add PEP 723 requirements from extra paths
            for path in self.extra_paths:
                if Path(path).is_dir():
                    requirements.update(self.scan_for_dependencies(path))

            # Update requirements with all found dependencies
            self.requirements = sorted(requirements)

            # Install requirements
            self.install_requirements()

            # Update Python path
            self.update_python_path()

            # Verify paths exist
            if self.extra_paths:
                self.verify_paths(self.extra_paths)

        except Exception as exc:
            self.cleanup()  # Ensure cleanup on error
            if isinstance(exc, DependencyError):
                raise
            msg = f"Dependency setup failed: {exc}"
            raise DependencyError(msg) from exc

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self._scripts_dir and self._scripts_dir.exists():
            import shutil

            shutil.rmtree(self._scripts_dir)
