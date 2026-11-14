# Clean Empty Directories

![Python version](https://img.shields.io/badge/python-3.15-blue.svg)

Find empty directories, preview their removal, and delete them after confirmation. The script writes text and CSV reports and can remove eligible parent directories that become empty. It preserves the scan root.

## Prerequisites

- Python 3.15 with support for lazy imports and built-in `frozendict`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for environment and dependency management.

## Installation

Clone the repository:

```console
git clone https://github.com/dfirsec/clean_empty_dirs.git
cd clean_empty_dirs
```

`uv run` handles the environment and installs `rich` on demand. Include `--python 3.15 --with rich` because the script does not yet declare these requirements.

If uv cannot locate or download a compatible Python version, install one and pass its executable path to `uv run --python`.

## Usage

Start with a dry run:

```console
uv run --python 3.15 --with rich clean_empty_dirs.py "path/to/directory" --dry-run
```

Replace the quoted path with the directory to scan. A dry run asks for confirmation and previews deletions without removing directories.

To remove empty directories, omit `--dry-run` and accept both confirmation prompts:

```console
uv run --python 3.15 --with rich clean_empty_dirs.py "path/to/directory"
```

Use `uv run --python 3.15 --with rich clean_empty_dirs.py --help` to display all options.

### Shorter commands with inline metadata

To omit `--python 3.15 --with rich`, first add this metadata at the top of `clean_empty_dirs.py`:

```python
# /// script
# requires-python = ">=3.15"
# dependencies = ["rich"]
# ///
```

After adding that metadata, run:

```console
uv run clean_empty_dirs.py "path/to/directory" --dry-run
```

uv uses these declarations to select Python and install `rich`. See [uv's script documentation](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies).

### Options

- `--include PATTERN [PATTERN ...]`: include directory names or glob patterns.
- `--exclude PATTERN [PATTERN ...]`: prune matching directories during traversal; defaults to `Desktop` and `Windows`.
- `--dry-run` / `--no-dry-run`: enable or disable deletion previews.
- `--min-age DAYS`: set the minimum age of empty directories selected during scanning.
- `--config PATH`: load JSON configuration.
- `--log-level LEVEL`: choose `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `--log-file PATH`: override the default `directory_removal_log.txt` log path.

### Exclude directories

List multiple names or patterns after one `--exclude` option:

```console
uv run --python 3.15 --with rich clean_empty_dirs.py "path/to/directory" --exclude Desktop Windows --dry-run
```

## Output

The script shows scan progress and lists empty directories. If it finds any, it writes these reports in the current working directory after processing finishes:

- `empty_dirs_log.txt`: paths found during scanning.
- `empty_dirs_log.csv`: directory paths and removal statuses, including parents removed after becoming empty.

The script logs events to `directory_removal_log.txt`; use `--log-file` to choose another path. If it finds no empty directories, it prints a message and skips both reports.

## Contributing

Report bugs in an issue or submit a pull request. See [Repository Guidelines](AGENTS.md) for setup, coding conventions, and checks to run before submitting changes.

## License

This project is licensed under the MIT License.
