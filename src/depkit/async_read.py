from __future__ import annotations

from functools import lru_cache
from itertools import batched
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
    load_parallel: bool = True,
    chunk_size: int = 50,
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
    load_parallel: bool = True,
    chunk_size: int = 50,
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
    load_parallel: bool = True,
    chunk_size: int = 50,
) -> Mapping[str, str | bytes]:
    """Asynchronously read files in a folder matching a pattern.

    Args:
        path: Base directory to read from
        pattern: Glob pattern to match files against (e.g. "**/*.py" for Python files)
        recursive: Whether to search subdirectories
        include_dirs: Whether to include directories in results
        exclude: List of patterns to exclude (uses fnmatch against relative paths)
        max_depth: Maximum directory depth for recursive search
        mode: Read mode ("rt" for text, "rb" for binary)
        encoding: File encoding for text mode
        load_parallel: Whether to load files concurrently
        chunk_size: Number of files to load in parallel when load_parallel=True

    Returns:
        Mapping of relative paths to file contents

    Raises:
        FileNotFoundError: If base path doesn't exist
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
        paths = await fs._glob(str(base_path / pattern), maxdepth=max_depth)
    else:
        paths = await fs._glob(str(base_path / pattern))

    # Collect files to read
    files_to_read: list[tuple[str, str]] = []  # [(rel_path, abs_path), ...]

    for file_path in paths:
        rel_path = os.path.relpath(file_path, str(base_path))  # type: ignore

        # Skip excluded patterns
        if exclude and any(fnmatch(rel_path, pat) for pat in exclude):
            continue

        # Skip directories unless explicitly included
        is_dir = await fs._isdir(file_path)
        if is_dir and not include_dirs:
            continue

        if not is_dir:
            files_to_read.append((rel_path, file_path))  # type: ignore

    if load_parallel:
        # Process files in chunks to avoid too many concurrent operations
        for chunk in batched(files_to_read, chunk_size):
            # Create tasks for this chunk
            tasks = [
                read_path(abs_path, mode=mode, encoding=encoding)
                for rel_path, abs_path in chunk
            ]

            # Execute chunk in parallel
            try:
                contents = await asyncio.gather(*tasks)
                # Map results back to relative paths
                for (rel_path, _), content in zip(chunk, contents, strict=True):
                    result[rel_path] = content  # type: ignore
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to read chunk starting at %s: %s", chunk[0][0], e)
    else:
        # Original sequential reading
        for rel_path, file_path in files_to_read:
            try:
                content = await read_path(file_path, mode=mode, encoding=encoding)
                result[rel_path] = content
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to read %s: %s", rel_path, e)

    return result


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    async def main():
        # Test with current directory
        files = await read_folder(
            ".",
            pattern="**/*.py",
            recursive=True,
            exclude=["__pycache__/*", "*.pyc"],
            max_depth=5,
            load_parallel=True,
        )
        print("\nFound files:")
        pprint(list(files.keys()))

        print("\nFirst file content:")
        first_file = next(iter(files))
        print(f"\n{first_file}:")
        print(files[first_file][:500] + "...")  # Show first 500 chars

    asyncio.run(main())
