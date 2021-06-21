import os
import sys
from pathlib import Path

__author__ = "DFIRSec (@pulsecode)"
__version__ = "v0.0.1"
__description__ = "Find empty directories"

try:
    from tqdm import tqdm
except ImportError:
    sys.exit("\n\033[91m[ERROR]\033[0m Please install tqdm: 'pip install tqdm --user'\n")


def main(dirpath):
    parent = Path(__file__).resolve().parent
    outfile = parent.joinpath("empty_dirs.txt")
    exclude = {"Windows", "Desktop"}
    empty = []

    try:
        cnt = 0
        for root, dirs, files in tqdm(
            os.walk(dirpath, topdown=True), desc="\033[33m> Scanning for empty directories\033[0m", unit=" files"
        ):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in exclude]
            if len(files) == 0 and len(dirs) == 0:
                empty.append(root)
                cnt += 1
                # # CAUTION: Uncomment 4 lines below to remove empty dirs
                # try:
                #     Path.rmdir(dirpath)
                # except OSError:
                #     continue
        if cnt:
            print(f"> Found {cnt:,} emtpy directories.")
            with open(outfile, "w") as f:
                for p in empty:
                    f.write(p + "\n")
            print(f"> Results written to: \033[96m{Path(outfile).resolve()}\033[0m")
        else:
            print("> Found no emtpy directories.")
    except KeyboardInterrupt:
        os.remove(outfile)  # remove unfinished output file
        sys.exit("\033[92m> Script Terminated!\033[0m")


if __name__ == "__main__":
    if len(sys.argv) < 2 or not Path(sys.argv[1]).exists():
        sys.exit("\n\033[91m[ERROR]\033[0m Please include a valid path.")
    else:
        path = sys.argv[1]

    main(path)
