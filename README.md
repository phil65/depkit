# DepKit

[![PyPI License](https://img.shields.io/pypi/l/depkit.svg)](https://pypi.org/project/depkit/)
[![Package status](https://img.shields.io/pypi/status/depkit.svg)](https://pypi.org/project/depkit/)
[![Monthly downloads](https://img.shields.io/pypi/dm/depkit.svg)](https://pypi.org/project/depkit/)
[![Distribution format](https://img.shields.io/pypi/format/depkit.svg)](https://pypi.org/project/depkit/)
[![Wheel availability](https://img.shields.io/pypi/wheel/depkit.svg)](https://pypi.org/project/depkit/)
[![Python version](https://img.shields.io/pypi/pyversions/depkit.svg)](https://pypi.org/project/depkit/)
[![Implementation](https://img.shields.io/pypi/implementation/depkit.svg)](https://pypi.org/project/depkit/)
[![Releases](https://img.shields.io/github/downloads/phil65/depkit/total.svg)](https://github.com/phil65/depkit/releases)
[![Github Contributors](https://img.shields.io/github/contributors/phil65/depkit)](https://github.com/phil65/depkit/graphs/contributors)
[![Github Discussions](https://img.shields.io/github/discussions/phil65/depkit)](https://github.com/phil65/depkit/discussions)
[![Github Forks](https://img.shields.io/github/forks/phil65/depkit)](https://github.com/phil65/depkit/forks)
[![Github Issues](https://img.shields.io/github/issues/phil65/depkit)](https://github.com/phil65/depkit/issues)
[![Github Issues](https://img.shields.io/github/issues-pr/phil65/depkit)](https://github.com/phil65/depkit/pulls)
[![Github Watchers](https://img.shields.io/github/watchers/phil65/depkit)](https://github.com/phil65/depkit/watchers)
[![Github Stars](https://img.shields.io/github/stars/phil65/depkit)](https://github.com/phil65/depkit/stars)
[![Github Repository size](https://img.shields.io/github/repo-size/phil65/depkit)](https://github.com/phil65/depkit)
[![Github last commit](https://img.shields.io/github/last-commit/phil65/depkit)](https://github.com/phil65/depkit/commits)
[![Github release date](https://img.shields.io/github/release-date/phil65/depkit)](https://github.com/phil65/depkit/releases)
[![Github language count](https://img.shields.io/github/languages/count/phil65/depkit)](https://github.com/phil65/depkit)
[![Github commits this month](https://img.shields.io/github/commit-activity/m/phil65/depkit)](https://github.com/phil65/depkit)
[![Package status](https://codecov.io/gh/phil65/depkit/branch/main/graph/badge.svg)](https://codecov.io/gh/phil65/depkit/)
[![PyUp](https://pyup.io/repos/github/phil65/depkit/shield.svg)](https://pyup.io/repos/github/phil65/depkit/)

Install Python packages at runtime, programmatically.

DepKit's `DependencyManager` makes sure a set of requirements is available in the current
virtual environment before your code imports them. Requirements can be listed explicitly,
read from [PEP 723](https://peps.python.org/pep-0723/) inline script metadata, or collected
from the `.py` files in extra import paths. Packages are installed with `pip` or `uv pip`.

Documentation: <https://phil65.github.io/depkit/>

## Installation

```bash
pip install depkit
# or
uv add depkit
```

## Quick start

```python
from depkit import DependencyManager

with DependencyManager(requirements=["requests>=2.31.0"]) as manager:
    import requests

    print(manager.get_installed_requirements())
```

Requirements that are already installed are skipped; missing ones are installed on entry.
The async variant works the same way:

```python
async with DependencyManager(requirements=["requests"], prefer_uv=True) as manager:
    import requests
```

Without a context manager, call `install()` and (optionally) `uninstall()` yourself:

```python
manager = DependencyManager(requirements=["requests"])
manager.install()
import requests

manager.uninstall()  # removes temporary files
```

## Features

- Sync and async context managers, or plain `install()` / `uninstall()`
- PEP 723 inline script metadata: dependencies and `requires-python` checks
- Scripts listed in `scripts` become importable modules (by file stem)
- `extra_paths` are added to `sys.path` and scanned for PEP 723 dependencies
- Uses `uv pip` when uv is available (on PATH or in a uv environment), otherwise `python -m pip`
- Custom package index via `pip_index_url`
- Refuses to install outside a virtual environment unless `force_install=True`

## Working with scripts

Given a script with PEP 723 metadata:

```python
# example_script.py
# /// script
# dependencies = [
#   "requests>=2.31.0",
# ]
# requires-python = ">=3.13"
# ///

import requests


def fetch(url: str) -> int:
    return requests.get(url).status_code
```

DepKit installs its dependencies and makes it importable:

```python
with DependencyManager(scripts=["path/to/example_script.py"]) as manager:
    from example_script import fetch
```

You can also install a single requirement or a script's dependencies directly:

```python
manager = DependencyManager()
manager.install_dependency("rich>=13")
manager.install_script("path/to/example_script.py")
```

## Configuration

```python
DependencyManager(
    requirements=None,  # list of PEP 508 requirement strings
    prefer_uv=False,  # prefer `uv pip` (warns if uv is not found)
    extra_paths=None,  # directories added to sys.path and scanned for PEP 723 deps
    scripts=None,  # PEP 723 scripts to load as importable modules
    pip_index_url=None,  # custom package index URL
    force_install=False,  # allow installing outside a virtual environment
)
```

## Error handling

All errors derive from `DependencyError` (`ScriptError` for invalid script metadata):

```python
from depkit import DependencyError, DependencyManager

try:
    with DependencyManager(requirements=["nonexistent-package-xyz"]):
        pass
except DependencyError as e:
    print(f"Dependency management failed: {e}")
```

## Limitations

- Requires Python 3.13 or newer.
- Already-installed packages are detected by name only; version specifiers of installed
  packages are not re-checked.
- Changes to `sys.path` made via `extra_paths` are not undone on cleanup.
- uv support requires `uv` to be installed separately.
