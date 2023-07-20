"""Find empty directories."""

import os
import sys
from argparse import ArgumentParser
from collections import defaultdict
from operator import itemgetter
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.traceback import install

install(show_locals=True)
console = Console(highlight=False)

PARENT = Path(__file__).resolve().parent
OUTFILE = Path(PARENT / "empty_dirs.txt")


def parse_arguments() -> tuple[str, set]:
    """Parse command-line arguments.

    Returns:
        A tuple containing the directory path and the set of excluded directories.
    """
    parser = ArgumentParser()
    parser.add_argument("dirpath", help="Directory path to scan")
    parser.add_argument(
        "--exclude",
        action="append",
        help="Directories to exclude from the scan",
        default=["Desktop", "Windows"],
    )
    args = parser.parse_args()

    # Normalize the path: remove trailing slashes, convert to lower case, remove leading/trailing spaces
    dirpath = os.path.normpath(args.dirpath).lower().strip()

    exclusions = set(args.exclude)

    return dirpath, exclusions


def remove_dir(dirpath: Path) -> None:
    """Remove empty directories."""
    try:
        dirpath.rmdir()
    except PermissionError:
        console.print(f"[red][ERROR] Permission denied: {dirpath}")
    except OSError as err:
        print(f"Error: {dirpath} : {err.strerror}")


def get_empty_dirs(dirpath: str, exclusions: set) -> None:
    """Recursively scans a source for empty directories.

    Args:
        dirpath (str): Directory path to scan.
        exclusions (set): Set of directories to exclude from scan.
        remove (bool): Remove empty directories.
    """
    empty_dirs_dict = defaultdict(int)
    empty_dirs = []

    with console.status("Scanning for empty directories..."):
        try:
            for root, dirs, files in os.walk(dirpath, topdown=True):
                try:
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in exclusions]
                    if not files and not dirs:
                        top_directory_list = root.split(dirpath, 1)[-1].split(os.sep, 2)
                        if len(top_directory_list) > 1:
                            top_directory = top_directory_list[1]
                            top_directory_path = Path(dirpath) / top_directory
                            empty_dirs_dict[top_directory_path] += 1
                        empty_dirs.append(root)
                except PermissionError:
                    continue
                except Exception:
                    console.print_exception()
        except KeyboardInterrupt:
            console.print(":exclamation: Keyboard interrupt detected...exiting.")
            sys.exit(1)

    if empty_dirs:
        print_results(empty_dirs_dict, empty_dirs)


def print_results(empty_dirs_dict: dict, empty_dirs: list) -> None:
    """Print results to console and write to file."""
    sorted_dirs = sorted(empty_dirs_dict.items(), key=itemgetter(1), reverse=True)
    if not sorted_dirs:
        console.print(":eyes: No empty directories found.")
        return

    console.print(f":file_folder: Found [yellow]{len(empty_dirs):,}[/yellow] empty directories.")

    table = Table(title="Top Directories")
    table.add_column("Directory", style="cyan")
    table.add_column("Empty Subdirectories", style="magenta")

    for directory, count in sorted_dirs[:10]:
        table.add_row(str(directory), str(count))

    console.print(table)

    try:
        ask = Confirm.ask("\n:thinking_face: Shall I remove the empty directories?", default=False)
        if ask:
            confirm = Confirm.ask(":worried: Are you sure?", default=False)
            if confirm:
                for dirpath in empty_dirs:
                    console.print(f"  :boom: Removing empty directory: {dirpath}")
                    remove_dir(Path(dirpath))
            else:
                console.print(":thumbs_up: No directories were removed.")
        else:
            console.print(":thumbs_up: No directories were removed.")
    except KeyboardInterrupt:
        console.print("\n:exclamation: Keyboard interrupt detected...exiting.")
        sys.exit(1)
    else:
        with open(OUTFILE, "w", encoding="utf-8") as fileobj:
            fileobj.writelines(f"{filepath}\n" for filepath in empty_dirs)
            console.print(f":pencil: Results written to: [cyan]{Path(OUTFILE).resolve()}[/cyan]\n")


if __name__ == "__main__":
    dirpath, exclusions = parse_arguments()
    if not Path(dirpath).exists():
        console.print("[red][ERROR] Please include a valid path.")
        sys.exit(1)

    get_empty_dirs(dirpath, exclusions)
