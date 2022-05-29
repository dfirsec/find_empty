import os
import sys
from pathlib import Path

AUTHOR = "DFIRSec (@pulsecode)"
VERSION = "v0.0.1"
DESCRIPTION = "Find empty directories"

try:
    from tqdm import tqdm
except ImportError:
    sys.exit("\n\033[91m[ERROR]\033[0m Please install tqdm: 'pip install tqdm --user'\n")  # fmt: skip


def main(dirpath):
    """
    Recursively scans a directory for empty directories and writes the results to a text file.

    :param dirpath: The path to the directory you want to scan
    """
    parent = Path(__file__).resolve().parent
    outfile = parent.joinpath("empty_dirs.txt")
    exclude = {"Windows", "Desktop"}
    empty = []
    cnt = 0
    try:
        for root, dirs, files in tqdm(
            os.walk(dirpath, topdown=True),
            desc="\033[33m> Scanning for empty directories\033[0m",
            unit=" files",
        ):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in exclude]
            if not files and not dirs:
                empty.append(root)
                cnt += 1
                #! CAUTION: Uncomment 4 lines below to remove empty dirs
                # try:
                #     Path.rmdir(dirpath)
                # except OSError as e:
                #     print(f'Error: {dirpath} : {e.strerror}')
        if cnt:
            print(f"> Found {cnt:,} emtpy directories.")
            with open(outfile, "w", encoding="utf-8") as fileobj:
                for filepath in empty:
                    fileobj.write(f"{filepath}\n")
            print(f"> Results written to: \033[96m{Path(outfile).resolve()}\033[0m")
        else:
            print("> Found no emtpy directories.")
    except KeyboardInterrupt:
        os.remove(outfile)  # remove unfinished output file
        sys.exit("\033[92m> Script Terminated!\033[0m")


if __name__ == "__main__":
    if len(sys.argv) < 2 or not Path(sys.argv[1]).exists():
        sys.exit("\033[91m[ERROR]\033[0m Please include a valid path.")
    else:
        path = sys.argv[1]

    main(path)
