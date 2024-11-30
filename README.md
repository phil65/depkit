# DepKit

[![PyPI License](https://img.shields.io/pypi/l/depkit.svg)](https://pypi.org/project/depkit/)
[![Package status](https://img.shields.io/pypi/status/depkit.svg)](https://pypi.org/project/depkit/)
[![Daily downloads](https://img.shields.io/pypi/dd/depkit.svg)](https://pypi.org/project/depkit/)
[![Weekly downloads](https://img.shields.io/pypi/dw/depkit.svg)](https://pypi.org/project/depkit/)
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
[![Github commits this week](https://img.shields.io/github/commit-activity/w/phil65/depkit)](https://github.com/phil65/depkit)
[![Github commits this month](https://img.shields.io/github/commit-activity/m/phil65/depkit)](https://github.com/phil65/depkit)
[![Github commits this year](https://img.shields.io/github/commit-activity/y/phil65/depkit)](https://github.com/phil65/depkit)
[![Package status](https://codecov.io/gh/phil65/depkit/branch/main/graph/badge.svg)](https://codecov.io/gh/phil65/depkit/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyUp](https://pyup.io/repos/github/phil65/depkit/shield.svg)](https://pyup.io/repos/github/phil65/depkit/)

# DependencyManager

A flexible Python dependency manager that handles runtime dependencies and script imports.

## Quick Start

```python
from depkit import DependencyManager

# Simple usage
manager = DependencyManager(requirements=["requests>=2.31.0"])
manager.install()
import requests
# ... do your work ...
manager.uninstall()  # optional cleanup
```

## Recommended Usage (Context Managers)

```python
# Synchronous
with DependencyManager(requirements=["requests"]) as manager:
    import requests
    # ... do your work ...
    # cleanup happens automatically

# Asynchronous
async with DependencyManager(requirements=["requests"]) as manager:
    import requests
    # ... do your work ...
    # cleanup happens automatically
```

## Features

- Simple install/uninstall methods for quick usage
- Context managers for proper resource management
- PEP 723 dependency declaration support
- Support for both pip and uv package managers
- Custom pip index URL support
- Temporary script importing
- Path management for imports

## Installation

```bash
pip install depkit
```

## Basic Usage

The DependencyManager supports both synchronous and asynchronous context managers:

### Async Usage
```python
from depkit import DependencyManager

async with DependencyManager(
    requirements=["requests>=2.31.0", "pandas"],
    prefer_uv=True
) as manager:
    import requests
    import pandas
```

### Sync Usage
```python
from depkit import DependencyManager

with DependencyManager(
    requirements=["requests>=2.31.0", "pandas"],
    prefer_uv=True
) as manager:
    import requests
    import pandas
```

## Working with Scripts

The DependencyManager can handle scripts with PEP 723 dependency declarations:

```python
# example_script.py
# /// script
# dependencies = [
#   "requests>=2.31.0",
#   "pandas>=2.0.0"
# ]
# requires-python = ">=3.12"
# ///

import requests
import pandas as pd
```

Load and use the script:

```python
async with DependencyManager(
    scripts=["path/to/example_script.py"],
    extra_paths=["."]  # Add paths to Python's import path
) as manager:
    # Script's dependencies are installed automatically
    from example_script import some_function
```

## Configuration Options

```python
DependencyManager(
    prefer_uv: bool = False,          # Prefer uv over pip if available
    requirements: list[str] = None,   # List of PEP 508 requirement specifiers
    extra_paths: list[str] = None,    # Additional Python import paths
    scripts: list[str] = None,        # Scripts to load and process
    pip_index_url: str = None,        # Custom PyPI index URL
)
```

## Features in Detail

### UV Integration

The manager automatically detects and can use uv for faster package installation:

```python
manager = DependencyManager(prefer_uv=True)
```

### Custom Package Index

Specify a custom PyPI index:

```python
manager = DependencyManager(
    requirements=["private-package>=1.0.0"],
    pip_index_url="https://private.pypi.org/simple"
)
```

### Path Management

Add custom import paths:

```python
manager = DependencyManager(
    extra_paths=[
        "./src",
        "./lib",
    ]
)
```

### Error Handling

```python
from depkit import DependencyError

try:
    async with DependencyManager(requirements=["nonexistent-package"]):
        pass
except DependencyError as e:
    print(f"Dependency management failed: {e}")
```

## Best Practices

1. Use as a context manager to ensure proper cleanup
2. Specify exact version requirements when possible
3. Use PEP 723 for script dependencies
4. Handle DependencyError exceptions appropriately
5. Consider using uv in production for better performance

## Limitations

- Requires Python 3.12 or higher
- Some features may not work on all platforms
- UV support requires uv to be installed separately
