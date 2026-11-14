"""Scan for and remove empty directories (Optimized for Python 3.15)."""

import logging
import os
import sys
import time
from argparse import ArgumentParser
from argparse import BooleanOptionalAction
from argparse import Namespace
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final
from typing import cast

# PEP 810 (Python 3.15): Explicit lazy imports keep CLI startup instantaneous
# (e.g., for --help, invalid paths, or scans that find zero empty directories).
lazy import csv
lazy import fnmatch
lazy import json
lazy import re
lazy from collections import deque
lazy from collections.abc import Iterable
lazy from concurrent.futures import FIRST_COMPLETED
lazy from concurrent.futures import Future
lazy from concurrent.futures import ThreadPoolExecutor
lazy from concurrent.futures import wait
lazy from itertools import batched
lazy from itertools import chain

from rich.console import Console
lazy from rich.progress import BarColumn
lazy from rich.progress import MofNCompleteColumn
lazy from rich.progress import Progress
lazy from rich.progress import SpinnerColumn
lazy from rich.progress import TimeElapsedColumn
lazy from rich.prompt import Confirm
lazy from rich.table import Table
lazy from rich.traceback import install

console = Console(highlight=False)
logger = logging.getLogger(__name__)

type ConfigMap = frozendict[str, object]

# PEP 814 (Python 3.15): Built-in immutable frozendict for safe default configuration.
# Specify the value type here because frozendict's value type is invariant.
DEFAULT_CONFIG: Final[ConfigMap] = frozendict[str, object](
    include=("*",),
    exclude=("Desktop", "Windows"),
    dry_run=False,
    log_level="INFO",
    log_file="directory_removal_log.txt",
    min_age=0,
)

VALID_LOG_LEVELS: Final = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
UNSAFE_SYSTEM_DIRS: Final = frozenset({
    Path("/home"),
    Path("/Users"),
    Path("/etc"),
    Path("/usr"),
    Path("/var"),
    Path("/System"),
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
})

type ScanError = tuple[str, str]
type BatchResult = tuple[
    list[Path],
    list[Path],
    int,
    int,
    list[ScanError],
]


class RemovalStatus(StrEnum):
    """Report statuses for scanned and cascaded directories."""

    NOT_REMOVED = "Not Removed"
    DRY_RUN = "Dry Run - Not Removed"
    REMOVED = "Removed"
    CASCADED = "Removed (Cascaded Parent)"
    FAILED = "Failed to Remove"


@dataclass(slots=True, frozen=True)
class ScanConfig:
    """Immutable runtime configuration."""

    dirpath: Path
    includes: tuple[str, ...]
    exclusions: tuple[str, ...]
    dry_run: bool
    log_level: str
    log_file: Path
    min_age: int


class PathFilter:
    """Precompiled glob and exact-name matcher for fast directory filtering."""

    __slots__ = (
        "_case_fold",
        "exact_exclusions",
        "exc_name_re",
        "exc_path_re",
        "inc_name_re",
        "inc_path_re",
        "include_all",
    )

    _case_fold: bool
    exact_exclusions: frozenset[str]
    exc_name_re: re.Pattern[str] | None
    exc_path_re: re.Pattern[str] | None
    inc_name_re: re.Pattern[str] | None
    inc_path_re: re.Pattern[str] | None
    include_all: bool

    def __init__(
        self,
        includes: tuple[str, ...],
        exclusions: tuple[str, ...],
    ) -> None:
        self._case_fold = os.name == "nt"
        self.include_all = "*" in includes

        if self.include_all:
            self.inc_name_re = None
            self.inc_path_re = None
        else:
            _, self.inc_name_re, self.inc_path_re = self._compile(
                includes,
                split_exact=False,
            )

        (
            self.exact_exclusions,
            self.exc_name_re,
            self.exc_path_re,
        ) = self._compile(exclusions, split_exact=True)

    def _compile(
        self,
        patterns: tuple[str, ...],
        *,
        split_exact: bool,
    ) -> tuple[
        frozenset[str],
        re.Pattern[str] | None,
        re.Pattern[str] | None,
    ]:
        flags = re.IGNORECASE if self._case_fold else 0
        exact: set[str] = set()
        name_globs: list[str] = []
        path_globs: list[str] = []

        for raw in patterns:
            norm = raw.replace("\\", "/")
            has_sep = "/" in norm
            has_meta = any(ch in norm for ch in "*?[")

            if split_exact and not has_sep and not has_meta:
                exact.add(norm.lower() if self._case_fold else norm)
                continue

            translated = fnmatch.translate(norm)
            if not has_sep:
                name_globs.append(translated)
            path_globs.append(translated)

        name_re = re.compile("|".join(name_globs), flags) if name_globs else None
        path_re = re.compile("|".join(path_globs), flags) if path_globs else None
        return frozenset(exact), name_re, path_re

    def is_excluded(self, raw_path: str, name: str) -> bool:
        """Return True if a directory name or path matches any exclusion rule."""
        lookup_name = name.lower() if self._case_fold else name
        if lookup_name in self.exact_exclusions:
            return True
        if self.exc_name_re is not None and self.exc_name_re.match(name) is not None:
            return True
        if self.exc_path_re is not None:
            posix_path = raw_path.replace("\\", "/") if self._case_fold else raw_path
            return self.exc_path_re.match(posix_path) is not None
        return False

    def is_included(self, raw_path: str, name: str) -> bool:
        """Return True if a directory name or path matches any inclusion rule."""
        if self.include_all:
            return True
        if self.inc_name_re is not None and self.inc_name_re.match(name) is not None:
            return True
        if self.inc_path_re is not None:
            posix_path = raw_path.replace("\\", "/") if self._case_fold else raw_path
            return self.inc_path_re.match(posix_path) is not None
        return False


def _extract_str_tuple(value: object, key: str) -> tuple[str, ...]:
    """Validate and narrow a configuration sequence to strings.

    Returns:
        A tuple containing the validated strings.

    Raises:
        TypeError: If the value is not a sequence or contains non-strings.
    """
    if not isinstance(value, (list, tuple)):
        message = f"'{key}' in config must be an array of strings."
        raise TypeError(message)

    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            message = f"All items in '{key}' must be strings."
            raise TypeError(message)
        items.append(item)
    return tuple(items)


def _extract_bool(value: object, key: str) -> bool:
    """Validate a boolean configuration value.

    Returns:
        The validated boolean.

    Raises:
        TypeError: If the value is not a boolean.
    """
    if not isinstance(value, bool):
        message = f"'{key}' in config must be a boolean."
        raise TypeError(message)
    return value


def _extract_str(value: object, key: str) -> str:
    """Validate a string configuration value.

    Returns:
        The validated string.

    Raises:
        TypeError: If the value is not a string.
    """
    if not isinstance(value, str):
        message = f"'{key}' in config must be a string."
        raise TypeError(message)
    return value


def _extract_int(value: object, key: str) -> int:
    """Validate an integer configuration value, excluding booleans.

    Returns:
        The validated integer.

    Raises:
        TypeError: If the value is not an integer or is a boolean.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"'{key}' in config must be an integer."
        raise TypeError(message)
    return value


def _build_parser() -> ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        The configured argument parser.
    """
    parser = ArgumentParser(description="Scan for and remove empty directories.")
    parser.add_argument("dirpath", type=Path, help="Directory path to scan")
    parser.add_argument(
        "--include",
        nargs="+",
        help="Directory names or glob patterns to include in the scan",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="Directory names or glob patterns to exclude (pruned during traversal)",
    )
    parser.add_argument(
        "--dry-run",
        action=BooleanOptionalAction,
        default=None,
        help="Perform a dry run without deleting any directories",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        type=str.upper,
        choices=sorted(VALID_LOG_LEVELS),
        help="Set the logging level",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Set the log file path",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=None,
        help="Minimum age of empty directories to delete, in days",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (JSON)",
    )
    return parser


def _read_config(path: Path) -> ConfigMap:
    """Read a JSON configuration file.

    Returns:
        The immutable JSON configuration mapping.

    Raises:
        TypeError: If the top-level JSON value is not an object.
    """
    # PEP 686: UTF-8 is the default, but remain explicit for Ruff and clarity.
    with path.open(encoding="utf-8") as file:
        loaded = json.load(
            file,
            object_pairs_hook=frozendict,
            array_hook=tuple,
        )

    if not isinstance(loaded, frozendict):
        message = "Top-level JSON configuration must be an object."
        raise TypeError(message)

    # JSON object keys are strings; individual values are validated when read.
    return cast("ConfigMap", loaded)


def _resolve_scan_config(
    args: Namespace,
    config: ConfigMap,
) -> ScanConfig:
    """Merge CLI arguments with configuration values.

    Returns:
        The resolved runtime configuration.
    """
    includes = tuple(args.include) if args.include is not None else _extract_str_tuple(config["include"], "include")
    exclusions = tuple(args.exclude) if args.exclude is not None else _extract_str_tuple(config["exclude"], "exclude")

    configured_dry_run = _extract_bool(config["dry_run"], "dry_run")
    dry_run = args.dry_run if args.dry_run is not None else configured_dry_run

    configured_log_level = _extract_str(config["log_level"], "log_level")
    log_level = (args.log_level or configured_log_level).upper()

    configured_log_file = _extract_str(config["log_file"], "log_file")
    log_file = (args.log_file or Path(configured_log_file)).resolve()

    configured_min_age = _extract_int(config["min_age"], "min_age")
    min_age = args.min_age if args.min_age is not None else configured_min_age

    return ScanConfig(
        dirpath=args.dirpath.resolve(),
        includes=includes,
        exclusions=exclusions,
        dry_run=dry_run,
        log_level=log_level,
        log_file=log_file,
        min_age=min_age,
    )


def parse_arguments() -> ScanConfig:
    """Parse command-line arguments and merge optional JSON configuration.

    Returns:
        The validated immutable runtime configuration.
    """
    args = _build_parser().parse_args()
    config = DEFAULT_CONFIG

    if args.config is not None:
        if not args.config.is_file():
            console.print(
                f":x: Configuration file not found: {args.config}",
                style="red",
            )
            sys.exit(1)

        try:
            config |= _read_config(args.config)
        except (OSError, ValueError, TypeError) as error:
            console.print(
                f":x: Error reading configuration file: {error}",
                style="red",
            )
            sys.exit(1)

    try:
        cfg = _resolve_scan_config(args, config)
    except TypeError as error:
        console.print(
            f":x: Invalid configuration value: {error}",
            style="red",
        )
        sys.exit(1)

    if cfg.log_level not in VALID_LOG_LEVELS:
        console.print(
            f":x: Invalid log level in config: {cfg.log_level}",
            style="red",
        )
        sys.exit(1)

    if cfg.min_age < 0:
        console.print(":x: --min-age must be 0 or greater.", style="red")
        sys.exit(1)

    return cfg


def is_directory_empty(
    directory: Path,
    out_console: Console = console,
) -> bool:
    """Check whether a directory has zero entries.

    Returns:
        True only when the directory is accessible and contains no entries.
    """
    try:
        with os.scandir(directory) as entries:
            return next(entries, None) is None
    except PermissionError:
        out_console.print(f":lock: Permission denied: {directory}", style="red")
        logger.error("Permission denied when accessing directory: %s", directory)
    except FileNotFoundError:
        out_console.print(f":warning: Directory not found: {directory}", style="red")
        logger.error("Directory not found during check: %s", directory)
    except OSError as error:
        out_console.print(f":x: Error accessing {directory}: {error}", style="red")
        logger.error("Error accessing directory %s: %s", directory, error)
    return False


@dataclass(slots=True, frozen=True)
class _DirectoryScan:
    """Results from reading one directory."""

    is_empty: bool
    children: list[Path]
    errors: list[ScanError]


def _scan_entry(
    entry: os.DirEntry[str],
    path_filter: PathFilter,
) -> tuple[Path | None, ScanError | None]:
    """Inspect one directory entry without following directory symlinks.

    Returns:
        A traversable child directory, if any, and an optional error pair.
    """
    try:
        # Uses cached OS d_type / WIN32_FIND_DATA where available.
        if entry.is_dir(follow_symlinks=False) and not path_filter.is_excluded(entry.path, entry.name):
            return Path(entry.path), None
    except OSError as error:
        return None, (
            f":x: Error accessing {entry.path}: {error}",
            f"Error accessing directory entry {entry.path}: {error}",
        )
    return None, None


def _scan_entries(
    entries: Iterable[os.DirEntry[str]],
    path_filter: PathFilter,
    children: list[Path],
    errors: list[ScanError],
) -> bool:
    """Collect child directories from an open directory iterator.

    Returns:
        True if the directory iterator yielded no entries.
    """
    is_empty = True

    for entry in entries:
        is_empty = False
        child, error = _scan_entry(entry, path_filter)
        if child is not None:
            children.append(child)
        if error is not None:
            errors.append(error)

    return is_empty


def _read_directory(
    directory: Path,
    path_filter: PathFilter,
) -> _DirectoryScan:
    """Read one directory and convert access failures into scan errors.

    Returns:
        The directory's empty state, child directories, and accumulated errors.
    """
    is_empty = False
    children: list[Path] = []
    errors: list[ScanError] = []

    try:
        with os.scandir(directory) as entries:
            is_empty = _scan_entries(
                entries,
                path_filter,
                children,
                errors,
            )
    except PermissionError:
        errors.append((
            f":lock: Permission denied: {directory}",
            f"Permission denied when accessing directory: {directory}",
        ))
    except FileNotFoundError:
        errors.append((
            f":warning: Directory not found: {directory}",
            f"Directory not found during scan: {directory}",
        ))
    except OSError as error:
        errors.append((
            f":x: Error accessing {directory}: {error}",
            f"Error accessing directory {directory}: {error}",
        ))

    return _DirectoryScan(is_empty, children, errors)


def _scan_batch(
    roots: tuple[Path, ...],
    root_path: Path,
    path_filter: PathFilter,
    cutoff_mtime: float | None,
    batch_limit: int,
) -> BatchResult:
    """Scan up to ``batch_limit`` directories in a streaming traversal.

    Returns:
        Empty directories, unscanned overflow, scan/discovery counts, and errors.
    """
    queue = deque(roots)
    empty_dirs: list[Path] = []
    errors: list[ScanError] = []
    scanned = 0
    discovered = 0

    while queue and scanned < batch_limit:
        directory = queue.popleft()
        scanned += 1

        result = _read_directory(directory, path_filter)
        queue.extend(result.children)
        discovered += len(result.children)
        errors.extend(result.errors)

        if (
            not result.is_empty
            or directory == root_path
            or not path_filter.is_included(
                str(directory),
                directory.name,
            )
        ):
            continue

        try:
            if cutoff_mtime is not None and directory.stat(follow_symlinks=False).st_mtime > cutoff_mtime:
                continue
        except OSError as error:
            errors.append((
                f":x: Error accessing {directory}: {error}",
                f"Error accessing directory {directory}: {error}",
            ))
            continue

        empty_dirs.append(directory)

    return empty_dirs, list(queue), scanned, discovered, errors


def scan_empty_dirs(
    dirpath: Path,
    path_filter: PathFilter,
    min_age: int,
) -> list[Path]:
    """Concurrently scan and prune the directory tree in one streaming pass.

    Returns:
        Empty directories sorted deepest-first for safe removal.
    """
    cutoff_mtime = time.time() - min_age * 86_400 if min_age > 0 else None
    max_workers = min(32, (os.process_cpu_count() or 1) + 4)
    empty_batches: list[list[Path]] = []
    total_discovered = 1
    total_scanned = 0

    with (
        Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress,
        ThreadPoolExecutor(max_workers=max_workers) as executor,
    ):
        task = progress.add_task(
            "[cyan]Scanning directories...",
            total=total_discovered,
        )
        # Start with batch_limit=1 so top-level subtrees immediately fan out.
        pending: set[Future[BatchResult]] = {
            executor.submit(
                _scan_batch,
                (dirpath,),
                dirpath,
                path_filter,
                cutoff_mtime,
                1,
            )
        }

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                found, overflow, scanned, discovered, errors = future.result()
                if found:
                    empty_batches.append(found)

                for error in errors:
                    progress.console.print(error[0], style="red")
                    logger.error("%s", error[1])

                total_discovered += discovered
                total_scanned += scanned

                if overflow:
                    fan_out = len(pending) < max_workers
                    for chunk in batched(
                        overflow,
                        1 if fan_out else 32,
                        strict=False,
                    ):
                        pending.add(
                            executor.submit(
                                _scan_batch,
                                chunk,
                                dirpath,
                                path_filter,
                                cutoff_mtime,
                                16 if fan_out else 64,
                            )
                        )

                progress.update(
                    task,
                    completed=total_scanned,
                    total=total_discovered,
                )

    empty_dirs = list(chain.from_iterable(empty_batches))
    empty_dirs.sort(key=lambda directory: len(directory.parts), reverse=True)
    return empty_dirs


def remove_dir_with_parents(
    dirpath: Path,
    path_filter: PathFilter,
    root_path: Path,
    dry_run: bool,
    removed_set: set[Path],
) -> tuple[RemovalStatus, list[Path]]:
    """Remove an empty directory and newly emptied eligible parents.

    Returns:
        The directory's removal status and any cascaded parent directories.
    """
    if dry_run:
        console.print(
            f":boom: [Dry Run] Would remove empty directory: {dirpath}",
            style="yellow",
        )
        logger.info("[Dry Run] Would remove empty directory: %s", dirpath)
        return RemovalStatus.DRY_RUN, []

    if dirpath in removed_set:
        return RemovalStatus.REMOVED, []

    try:
        dirpath.rmdir()
    except PermissionError:
        console.print(f":lock: Permission denied: {dirpath}", style="red")
        logger.error("Permission denied when removing directory: %s", dirpath)
        return RemovalStatus.FAILED, []
    except OSError as error:
        console.print(
            f":grimacing: Error removing {dirpath}: {error}",
            style="red",
        )
        logger.error("Error removing directory %s: %s", dirpath, error)
        return RemovalStatus.FAILED, []

    removed_set.add(dirpath)
    console.print(
        f":boom: Removed empty directory: {dirpath}",
        style="yellow",
    )
    logger.info("Removed empty directory: %s", dirpath)

    # Climb iteratively to avoid RecursionError on deeply nested trees.
    cascaded: list[Path] = []
    current = dirpath

    while True:
        parent = current.parent
        if (
            parent in {current, root_path}
            or parent in removed_set
            or path_filter.is_excluded(str(parent), parent.name)
            or not path_filter.is_included(str(parent), parent.name)
            or not is_directory_empty(parent)
        ):
            break

        try:
            parent.rmdir()
        except OSError as error:
            console.print(
                f":grimacing: Error removing {parent}: {error}",
                style="red",
            )
            logger.error(
                "Error removing parent directory %s: %s",
                parent,
                error,
            )
            break

        removed_set.add(parent)
        cascaded.append(parent)
        console.print(
            f":boom: Removed newly empty parent: {parent}",
            style="yellow",
        )
        logger.info("Removed newly empty parent directory: %s", parent)
        current = parent

    return RemovalStatus.REMOVED, cascaded


def remove_confirmed_dirs(
    empty_dirs: list[Path],
    path_filter: PathFilter,
    root_path: Path,
    dry_run: bool,
) -> list[tuple[Path, RemovalStatus]]:
    """Prompt for confirmation, remove directories, and collect report rows.

    Returns:
        Directory/status pairs for both requested and cascaded removals.
    """
    if not (
        Confirm.ask(
            "\n:thinking_face: Shall I remove the empty directories?",
            default=False,
        )
        and Confirm.ask(":worried: Are you sure?", default=False)
    ):
        console.print(":thumbs_up: No directories were removed.")
        return [(directory, RemovalStatus.NOT_REMOVED) for directory in empty_dirs]

    report_rows: list[tuple[Path, RemovalStatus]] = []
    removed_set: set[Path] = set()

    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Deleting directories...",
            total=len(empty_dirs),
        )
        for dirpath in empty_dirs:
            status, cascaded = remove_dir_with_parents(
                dirpath,
                path_filter,
                root_path,
                dry_run,
                removed_set,
            )
            report_rows.append((dirpath, status))
            report_rows.extend((parent, RemovalStatus.CASCADED) for parent in cascaded)
            progress.advance(task)

    return report_rows


def process_results(
    empty_dirs: list[Path],
    outfile: Path,
    path_filter: PathFilter,
    root_path: Path,
    dry_run: bool,
) -> None:
    """Display found directories, handle interactive removal, and write reports."""
    if not empty_dirs:
        console.print(":eyes: No empty directories found.")
        return

    console.print(f":file_folder: Found [yellow]{len(empty_dirs):,}[/yellow] empty directories.")
    table = Table(
        title="Empty Directories",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Directory", style="cyan")
    for dirpath in empty_dirs:
        table.add_row(str(dirpath))
    console.print(table)

    try:
        report_rows = remove_confirmed_dirs(
            empty_dirs,
            path_filter,
            root_path,
            dry_run,
        )
    except KeyboardInterrupt:
        console.print("\n:exclamation: Keyboard interrupt detected...exiting.")
        sys.exit(1)

    outfile.write_text(
        "".join(f"{directory}\n" for directory in empty_dirs),
        encoding="utf-8",
    )
    console.print(f":pencil: Results written to: [green]{outfile}[/green]\n")

    csv_file = outfile.with_suffix(".csv")
    with csv_file.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(("Directory", "Status"))
        writer.writerows((str(path), status) for path, status in report_rows)
    console.print(f":page_facing_up: Detailed report written to: [green]{csv_file}[/green]\n")


def is_unsafe_target(dirpath: Path) -> bool:
    """Return True if ``dirpath`` is a filesystem root or critical OS directory."""
    if dirpath == Path(dirpath.anchor):
        return True
    return any(dirpath == path.resolve() for path in UNSAFE_SYSTEM_DIRS if path.exists())


def main() -> None:
    """Run the command-line application."""
    install(show_locals=True)
    cfg = parse_arguments()

    if not cfg.dirpath.is_dir():
        console.print(
            "Please provide an existing directory path.",
            style="bold red",
        )
        sys.exit(1)

    if is_unsafe_target(cfg.dirpath):
        console.print(
            "Cannot run this script on critical system directories.",
            style="bold red",
        )
        sys.exit(1)

    logging.basicConfig(
        filename=str(cfg.log_file),
        level=getattr(logging, cfg.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
    )

    path_filter = PathFilter(cfg.includes, cfg.exclusions)
    empty_dirs = scan_empty_dirs(
        cfg.dirpath,
        path_filter,
        cfg.min_age,
    )
    outfile = Path("empty_dirs_log.txt").resolve()
    process_results(
        empty_dirs,
        outfile,
        path_filter,
        cfg.dirpath,
        cfg.dry_run,
    )


if __name__ == "__main__":
    main()
