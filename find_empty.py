"""Scan for and remove empty directories."""

import logging
import sys
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.traceback import install

install(show_locals=True)
console = Console(highlight=False)




def parse_arguments() -> tuple[Path, set[str]]:
    """Parse command-line arguments."""
    parser = ArgumentParser(description="Scan for empty directories.")
    parser.add_argument("dirpath", type=Path, help="Directory path to scan")
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=["Desktop", "Windows"],
        help="Directories to exclude from the scan",
    )
    args = parser.parse_args()
    return args.dirpath.resolve(), {exclude.lower() for exclude in args.exclude}


def remove_dir(dirpath: Path) -> None:
    """Remove empty directories."""
    try:
        dirpath.rmdir()
        console.print(f":boom: Removing empty directory: {dirpath}", style="yellow")
        # Set up logging only if the directory is removed
        logging.basicConfig(
            filename="directory_removal_log.txt",
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logging.info(f"Removed empty directory: {dirpath}")
    except PermissionError:
        console.print(f":lock: Permission denied: {dirpath}", style="red")
    except OSError as err:
        console.print(f":grimacing: Error removing {dirpath}: {err}", style="red")


def check_empty_and_filter(directory: Path, exclusions: set) -> Path | None:
    """Check if a directory is empty and not in the exclusions list."""
    if directory.name.lower() in exclusions or any(True for _ in directory.iterdir()):
        return None
    return directory


def scan_empty_dirs(dirpath: Path, exclusions: set[str]) -> list[Path]:
    """Scan for empty directories."""
    empty_dirs = []
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(check_empty_and_filter, directory, exclusions): directory
            for directory in dirpath.rglob("*")
            if directory.is_dir()
        }
        for future in as_completed(futures):
            if directory := future.result():
                empty_dirs.append(directory)
    return empty_dirs


def print_results(empty_dirs: list[Path], outfile: Path) -> None:
    """Print the results to the console and write to a file."""
    if not empty_dirs:
        console.print(":eyes: No empty directories found.")
        return

    console.print(f":file_folder: Found [yellow]{len(empty_dirs):,}[/yellow] empty directories.")
    table = Table(title="Empty Directories", show_header=True, header_style="bold magenta")
    table.add_column("Directory", style="cyan")

    for dirpath in empty_dirs:
        table.add_row(str(dirpath))
    console.print(table)

    try:
        if Confirm.ask(
            "\n:thinking_face: Shall I remove the empty directories?",
            default=False,
        ) and Confirm.ask(
            ":worried: Are you sure?",
            default=False,
        ):
            for dirpath in empty_dirs:
                remove_dir(dirpath)
        else:
            console.print(":thumbs_up: No directories were removed.")
    except KeyboardInterrupt:
        console.print(":exclamation: Keyboard interrupt detected...exiting.")
        sys.exit(1)
    else:
        with outfile.open("w", encoding="utf-8") as file:
            file.writelines(f"{directory}\n" for directory in empty_dirs)
        console.print(f":pencil: Results written to: [green]{outfile.resolve()}[/green]\n")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    dirpath, exclusions = parse_arguments()
    if not dirpath.exists():
        console.print("Please include a valid path.", style="bold red")
        sys.exit(1)

    empty_dirs = scan_empty_dirs(dirpath, exclusions)
    outfile = Path(root / "empty_dirs_log.txt")
    print_results(empty_dirs, outfile)
