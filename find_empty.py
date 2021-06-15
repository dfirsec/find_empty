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


def main(path):
    parent = Path(__file__).resolve().parent
    outfile = parent.joinpath("empty_dirs.txt")
    exclude = {"Windows", "Desktop"}

    f = open(outfile, "w")
    try:
        cnt = 0
        for root, dirs, files in tqdm(
            os.walk(path, topdown=True), desc="\033[33m> Scanning for empty directories\033[0m", unit=" files"
        ):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in exclude]
            if len(files) == 0 and len(dirs) == 0:
                cnt += 1
                f.write(root + "\n")
                # # CAUTION: Uncomment 4 lines below to remove empty dirs
                # try:
                #     os.rmdir(dirpath)
                # except OSError:
                #     continue
        f.close()
        if cnt:
            print(f"> Found {cnt:,} emtpy directories.")
            print(f"> Results written to: \033[96m{os.path.abspath(outfile)}\033[0m")
        else:
            print("> Found no emtpy directories.")
    except KeyboardInterrupt:
        os.remove(outfile)  # remove unfinished output file
        sys.exit("\033[92m> Script Terminated!\033[0m")
    finally:
        f.close()


if __name__ == "__main__":
    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        sys.exit("\n\033[91m[ERROR]\033[0m Please include a valid path.")
    else:
        path = sys.argv[1]

    main(path)
