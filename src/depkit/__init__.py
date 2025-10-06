"""DepKit: main package.

Tools to manage (uv) environemnts programmatically.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("depkit")
__title__ = "DepKit"

__author__ = "Philipp Temminghoff"
__author_email__ = "philipptemminghoff@googlemail.com"
__copyright__ = "Copyright (c) 2024 Philipp Temminghoff"
__license__ = "MIT"
__url__ = "https://github.com/phil65/depkit"

from depkit.depmanager import DependencyManager
from depkit.exceptions import DependencyError, ScriptError, ImportPathError


__all__ = [
    "DependencyError",
    "DependencyManager",
    "ImportPathError",
    "ScriptError",
    "__version__",
]
