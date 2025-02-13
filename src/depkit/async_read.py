from __future__ import annotations

from functools import lru_cache
import logging
import os
from typing import TYPE_CHECKING, Literal, overload


StrPath = str | os.PathLike[str]

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fsspec.asyn import AsyncFileSystem


logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _get_cached_fs(protocol: str) -> AsyncFileSystem:
    """Cached filesystem creation."""
    import fsspec
    from fsspec.asyn import AsyncFileSystem
    from fsspec.implementations.asyn_wrapper import AsyncFileSystemWrapper
    from morefs.asyn_local import AsyncLocalFileSystem

    if protocol in ("", "file"):
        return AsyncLocalFileSystem()

    fs = fsspec.filesystem(protocol, asynchronous=True)
    if not isinstance(fs, AsyncFileSystem):
        fs = AsyncFileSystemWrapper(fs)
    return fs


async def get_async_fs(path: StrPath) -> AsyncFileSystem:
    """Get appropriate async filesystem for path."""
    from upath import UPath

    path_obj = UPath(path)
    return _get_cached_fs(path_obj.protocol)


@overload
async def read_path(
    path: StrPath, mode: Literal["rt"] = "rt", encoding: str = ...
) -> str: ...


@overload
async def read_path(path: StrPath, mode: Literal["rb"], encoding: str = ...) -> bytes: ...


async def read_path(
    path: StrPath,
    mode: Literal["rt", "rb"] = "rt",
    encoding: str = "utf-8",
) -> str | bytes:
    """Read file content asynchronously when possible.

    Args:
        path: Path to read
        mode: Read mode ("rt" for text, "rb" for binary)
        encoding: File encoding for text files

    Returns:
        File content as string or bytes depending on mode
    """
    from upath import UPath

    path_obj = UPath(path)
    fs = await get_async_fs(path_obj)

    f = await fs.open_async(path_obj.path, mode=mode)
    async with f:
        return await f.read()


@overload
async def read_folder(
    path: StrPath,
    *,
    pattern: str = "**/*",
    recursive: bool = True,
    include_dirs: bool = False,
    exclude: list[str] | None = None,
    max_depth: int | None = None,
    mode: Literal["rt"] = "rt",
    encoding: str = "utf-8",
) -> Mapping[str, str]: ...


@overload
async def read_folder(
    path: StrPath,
    *,
    pattern: str = "**/*",
    recursive: bool = True,
    include_dirs: bool = False,
    exclude: list[str] | None = None,
    max_depth: int | None = None,
    mode: Literal["rb"],
    encoding: str = "utf-8",
) -> Mapping[str, bytes]: ...


async def read_folder(
    path: StrPath,
    *,
    pattern: str = "**/*",
    recursive: bool = True,
    include_dirs: bool = False,
    exclude: list[str] | None = None,
    max_depth: int | None = None,
    mode: Literal["rt", "rb"] = "rt",
    encoding: str = "utf-8",
) -> Mapping[str, str | bytes]:
    """Asynchronously read all files in a folder.

    Args:
        path: Base path to read from
        pattern: Glob pattern to filter files
        recursive: Whether to traverse subdirectories
        include_dirs: Whether to include directory paths
        exclude: Patterns to exclude
        max_depth: Optional depth limit
        mode: Read mode ("rt" for text, "rb" for binary)
        encoding: File encoding for text files

    Returns:
        Dict mapping relative paths to their contents
    """
    from fnmatch import fnmatch

    from upath import UPath

    base_path = UPath(path)
    if not base_path.exists():
        msg = f"Path does not exist: {path}"
        raise FileNotFoundError(msg)

    fs = await get_async_fs(base_path)
    result: dict[str, str | bytes] = {}

    # Get all matching paths
    if recursive:
        paths = await fs._find(str(base_path), maxdepth=max_depth)
    else:
        paths = await fs.ls(str(base_path))

    # Filter paths
    for file_path in paths:
        rel_path = os.path.relpath(file_path, str(base_path))

        # Skip excluded patterns
        if exclude and any(fnmatch(rel_path, pat) for pat in exclude):
            continue

        # Skip directories unless explicitly included
        is_dir = await fs._isdir(file_path)
        if is_dir and not include_dirs:
            continue

        # Filter by pattern
        if not fnmatch(rel_path, pattern):
            continue

        try:
            if not is_dir:
                content = await read_path(file_path, mode=mode, encoding=encoding)
                result[rel_path] = content
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to read %s: %s", rel_path, e)
            continue

    return result


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    async def main():
        # Test with current directory
        files = await read_folder(
            ".",
            pattern="*.py",
            recursive=True,
            exclude=["__pycache__/*", "*.pyc"],
            max_depth=2,
        )
        print("\nFound files:")
        pprint(list(files.keys()))

        print("\nFirst file content:")
        first_file = next(iter(files))
        print(f"\n{first_file}:")
        print(files[first_file][:500] + "...")  # Show first 500 chars

    asyncio.run(main())
