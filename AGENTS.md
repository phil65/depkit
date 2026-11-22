# AGENTS.md

## Overview

DepKit installs Python package requirements at runtime into the current (virtual)
environment, using `pip` or `uv pip`. Requirements come from an explicit list, from
PEP 723 `# /// script` blocks in scripts, or from `.py` files found in extra import paths.
Scripts can be made importable as modules for the lifetime of a `DependencyManager`.
Small library, no CLI, Python >= 3.13.

## Architecture

All code lives in `src/depkit/`:

- `depmanager.py`: `DependencyManager`, the only real public class. Sync/async context
  manager (`setup()` / `async_setup()` on enter, `cleanup()` on exit), plus
  `install()` / `uninstall()` aliases and `install_dependency()` / `install_script()`.
  Setup flow: `_setup_script_modules()` (parse PEP 723 metadata of `scripts`, check
  `requires-python`, copy each script into a temp dir keyed by file stem, prepend that dir to
  `sys.path`) -> scan `extra_paths` dirs for PEP 723 deps -> `_setup_requirements()`
  (find missing ones, check venv, install, extend `sys.path`, verify paths).
- `parser.py`: PEP 723 parsing (`parse_script_metadata` -> `ScriptMetadata`,
  `parse_pep723_deps`, `check_python_version` via `packaging`).
- `utils.py`: stateless helpers: pip/uv command detection (`detect_uv`, `get_pip_command`),
  `check_requirements` (presence check via `importlib.metadata`), `install_requirements`
  (`subprocess.run`), directory scanning (sync via `upath.UPath.rglob`, async via
  `upathtools.read_folder`), `in_virtualenv` / `get_venv_info`, `verify_paths`.
- `exceptions.py`: `DependencyError` (base), `ScriptError`, `ImportPathError`.
- `log.py`: `get_logger` helper (modules mostly use `logging.getLogger(__name__)` directly).
- `__init__.py`: exports `DependencyManager` and the exceptions, `__version__` from metadata.

Paths are handled with `upath.UPath` (imported as `Path`), so fsspec URLs work for scripts.

## Where to look

| Task | File |
| --- | --- |
| Change install/setup/cleanup behaviour | `src/depkit/depmanager.py` |
| PEP 723 parsing, Python version checks | `src/depkit/parser.py` |
| pip/uv invocation, requirement checks, venv detection | `src/depkit/utils.py` |
| Public exports | `src/depkit/__init__.py` |
| Tests | `tests/test_depmanager.py`, `tests/test_pep723.py`, `tests/test_utils.py`, fixtures in `tests/conftest.py` |
| CI | `.github/workflows/build.yml`, `.github/workflows/documentation.yml` |
| Task runner | `duties.py` |

## Commands

```bash
uv sync --all-extras                  # setup (default groups: dev, lint, docs)
uv run pytest                         # tests (testpaths = ["tests/"])
uv run ruff check . && uv run ruff format --check .
uv run ty check                       # type check (src only, warnings fail)
uv run deptry src                     # undeclared/unused dependencies
uv run mkdocs-mknodes build           # docs build (same as CI)
uv build
```

`duties.py` wraps these: `duty test`, `duty lint`, `duty lint_check`, `duty build`,
`duty serve`, `duty clean`, `duty update`, `duty version <bump>`. Pre-commit hooks (`.pre-commit-config.yaml`) run ruff,
tombi, ty and pytest.

## Conventions

- Python 3.13+ syntax (`type` aliases, `Self`, walrus, `X | Y`), `from __future__ import annotations`.
- Ruff with a broad rule set, line length 100, preview formatting (also formats Markdown code
  blocks in README).
- Google-style docstrings without types in `Args` (see `.github/copilot-instructions.md`).
- Errors are wrapped into `DependencyError` subclasses with `raise ... from exc`.
- Tests use pytest with `asyncio_mode = "auto"`; installs are mocked (`mock_subprocess`
  fixture), tests must stay offline and must not touch the real environment.

## Pitfalls

- Copier-managed project (`.copier-answers.yml`, template `copier-phil65`). Workflows,
  `duties.py`, `.pre-commit-config.yaml` and most of `pyproject.toml` are template-owned; add
  dependencies below the `# Only add below (Copier)` markers.
- `check_requirements()` only checks that a distribution with the parsed name is installed; it
  ignores version specifiers, and names with extras or other operators (`~=`, `!=`) are not
  parsed and are reinstalled every time.
- Installing requires a virtual environment (or conda/uv/venv-backed Jupyter) unless
  `force_install=True`; otherwise `DependencyError`.
- Script modules are keyed by file stem; two scripts with the same stem raise `DependencyError`.
  Invalid scripts in `scripts` only log a warning.
- `extra_paths` are appended to `sys.path` and never removed by `cleanup()`; the scripts temp dir
  is removed but stays in `sys.path`.
- `ty check` runs in CI and warnings fail it; prefer targeted `# ty: ignore[rule]`.
