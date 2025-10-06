from __future__ import annotations

from importlib.metadata import version

__version__ = version("depkit")

from depkit.depmanager import DependencyManager
from depkit.exceptions import (
    DependencyError,
    ScriptError,
    ImportPathError,
)


__all__ = [
    "__version__","DependencyError", "DependencyManager", "ImportPathError", "ScriptError"]