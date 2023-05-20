# Find Empty

![Generic badge](https://img.shields.io/badge/python-3.8-blue.svg)

Python script to to recursively scan a directory and find empty directories within it. It generates a list of empty directory paths and writes them to a text file named `empty_dirs.txt`.

## Prerequisites

Python 3.x

## Installation

1. Clone the repository:

```text
git clone https://github.com/dfirsec/find_empty.git
```

2. Navigate to the project directory:

```text
cd find_empty
```

3. Install the required dependencies using poetry:

```text
poetry install
```

## Usage

1. Create the virtual environment

```text
poetry shell
```

2. Run the program

```text
python find_empty.py <Directory path to scan>
```

> Replace \<Directory path to scan> with the path to the directory you want to scan for empty directories.

3. Exit the program when done.

```text
exit
```



### Options

--exclude \<Directory name>: Exclude a specific directory from the scanning process. You can use this option multiple times to exclude multiple directories.

## Output

The program will scan the provided directory and display the progress using a progress bar. Once the scan is complete, it will generate a text file named empty_dirs.txt that contains the paths of all empty directories found during the scan.

If no empty directories are found, the program will display a message indicating that no empty directories were found.

## Example

```text
python find_empty.py /path/to/directory --exclude Desktop --exclude Windows
```

This command will scan the /path/to/directory directory for empty directories, excluding the directories named "Desktop" and "Windows". It will display the progress and generate the empty_dirs.txt file containing the paths of the empty directories.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvement, please create an issue or submit a pull request.

## License

This project is licensed under the MIT License.
