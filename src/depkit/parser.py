"""Dependency parsing utilities."""

from __future__ import annotations

import logging
import re
import tomllib
from typing import TYPE_CHECKING

from depkit.exceptions import ScriptError


if TYPE_CHECKING:
    from collections.abc import Iterator

# PEP 723 regex pattern
SCRIPT_REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


logger = logging.getLogger(__name__)


def parse_pep723_deps(content: str) -> Iterator[str]:
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
        filter(lambda m: m.group("type") == "script", re.finditer(SCRIPT_REGEX, content))
    )

    if len(matches) > 1:
        msg = "Multiple script metadata blocks found"
        raise ScriptError(msg)

    if not matches:
        # Fall back to informal format for backwards compatibility
        yield from parse_informal_deps(content)
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


def parse_informal_deps(content: str) -> Iterator[str]:
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
