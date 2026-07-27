from collections.abc import Generator, Iterable
from pathlib import Path

from rich.progress import Progress


def find_files(dir: Path, prefix: str, ext: str) -> Generator[Path]:
    """Find files in a directory matching a prefix and extension.

    >>> list(find_files(Path("fragments"), "fragment", ".patch.txt"))
    [PosixPath('fragments/fragment_0.patch.txt'), PosixPath('fragments/fragment_1.patch.txt')]

    >>> list(find_files(Path("patches"), "", ".patch"))  # all .patch files
    [PosixPath('patches/foo.patch'), PosixPath('patches/bar.patch')]
    """
    pattern = f"{prefix}*{ext}" if prefix else f"*{ext}"

    yield from dir.glob(pattern=pattern)


def read_files(paths: Iterable[Path]) -> Generator[tuple[str, str]]:
    """Read file contents into a dictionary."""

    paths = list(paths)

    with Progress() as progress:
        task = progress.add_task("Reading files...", total=len(paths))
        for file_path in paths:
            # Read the file content
            file_content = file_path.read_text()

            yield file_path.name, file_content
            progress.advance(task)

        progress.update(
            task,
            description=f"Reading fles: \n[bold green]✓[/bold green] {len(paths)} read",
        )
