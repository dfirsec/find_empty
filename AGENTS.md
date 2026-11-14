# Repository Guidelines

## Project Structure & Module Organization

`clean_empty_dirs.py` contains the CLI, configuration validation, path filtering, concurrent scanning, directory removal, and report generation. `README.md` documents setup and usage. There are currently no separate source packages, assets, test directory, or dependency manifest in the working tree.

## Build, Test, and Development Commands

Use `uv run` to manage the environment and dependencies. The source requires Python 3.15 features, including lazy imports and `frozendict`. Specify the interpreter and `rich` dependency explicitly until the script declares them in inline metadata.

- `uv run --python 3.15 --with rich clean_empty_dirs.py --help`: inspect CLI options.
- `uv run --python 3.15 --with rich clean_empty_dirs.py "path/to/sandbox" --dry-run`: preview removal in a disposable directory tree; confirmation prompts still appear.
- `uv run --python 3.15 python -m py_compile clean_empty_dirs.py`: check syntax.

No build step is required. See `README.md` for the inline metadata needed to use the shorter `uv run clean_empty_dirs.py` command.

## Coding Style & Naming Conventions

Follow the existing four-space indentation, type annotations, double-quoted strings, and function docstrings. Use `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Preserve immutable configuration and explicit UTF-8 file handling. No formatter or linter configuration is currently present. Markdown uses LF line endings.

## Testing Guidelines

No automated suite or coverage threshold is configured. For new behavior, add focused tests under `tests/test_*.py`; standard-library `unittest` avoids another dependency. Once tests exist, run `uv run --python 3.15 --with rich python -m unittest discover -s tests`. Cover filtering, invalid configuration, dry-run behavior, and removal boundaries. Use temporary directories for filesystem tests and verify that populated directories and the scan root survive.

## Commit & Pull Request Guidelines

Recent commits use short subjects such as `Updated Version` and `Updated/Optimized`; no formal convention is evident. Prefer specific imperative subjects, such as `Fix exclusion matching on Windows`. PRs should explain the behavior change, link relevant issues, and list validation commands and results. Include sample CLI output when reporting changes to user-visible behavior.

## Filesystem Safety

Preserve confirmation prompts, system-directory checks, and scan-root boundaries. Exercise deletion only in disposable fixtures. Keep generated reports, logs, and local environments out of commits. Preserve unrelated working-tree changes.
