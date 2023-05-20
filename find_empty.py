"""Find empty directories."""

import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from tqdm import tqdm


def main(dirpath: str, exclusions: set) -> None:
    """Recursively scans a source for empty directories.

    Args:
        dirpath (str): Directory path to scan.
        exclusions (set): Set of directories to exclude from scan.
    """
    parent = Path(__file__).resolve().parent
    outfile = parent.joinpath("empty_dirs.txt")
    empty = []
    counter = 0

    for root, dirs, files in tqdm(
        os.walk(dirpath, topdown=True),
        desc="\033[33m> Scanning for empty directories\033[0m",
        unit=" files",
    ):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in exclusions]
        if not files and not dirs:
            empty.append(root)
            counter += 1
            #! CAUTION: Uncomment 4 lines below to remove empty dirs
            # try:
            #     Path.rmdir(dirpath)
            # except OSError as e:
            #     print(f'Error: {dirpath} : {e.strerror}')

    if counter:
        print(f"> Found {counter:,} empty directories.")
        with open(outfile, "w", encoding="utf-8") as fileobj:
            fileobj.writelines(f"{filepath}\n" for filepath in empty)
        print(f"> Results written to: \033[96m{Path(outfile).resolve()}\033[0m")
    else:
        print("> Found no empty directories.")


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
    dirpath = args.dirpath
    exclusions = set(args.exclude)
    return dirpath, exclusions


if __name__ == "__main__":
    dirpath, exclusions = parse_arguments()
    if not Path(dirpath).exists():
        sys.exit("\033[91m[ERROR]\033[0m Please include a valid path.")

    main(dirpath, exclusions)
