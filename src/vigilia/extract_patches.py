from pathlib import Path
from typing import Annotated

import typer
from pygit2 import Patch
from rich.console import Console
from rich.progress import Progress

from .conf import DEFAULT_OUTPUT_DIR, DEFAULT_PATCH_EXT
from .lib.git import get_patches_from_repo


def write_patch(patch: Patch, output_dir: Path, ext: str) -> None:
    """Write a single patch to disk with a filename derived from the file path."""
    filename = patch.delta.new_file.path or patch.delta.old_file.path
    safe_name = filename.replace("/", "__") + ext
    output_path = output_dir / safe_name

    patch_text = patch.text
    if patch_text is not None:
        output_path.write_text(patch_text)


def main(
    base_ref: Annotated[
        str, typer.Argument(help="Base reference (tag, branch, or commit)")
    ] = "HEAD^",
    target: Annotated[str, typer.Argument(help="Target reference")] = "HEAD",
    path_to_repo: Annotated[
        Path, typer.Option("-r", "--repo", help="Path to repository ")
    ] = Path("."),
    output: Annotated[
        Path,
        typer.Option(
            "-o",
            help="Output directory",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = DEFAULT_OUTPUT_DIR / "patches",
    ext: Annotated[
        str, typer.Option("-e", help="Patch file extension")
    ] = DEFAULT_PATCH_EXT,
) -> None:
    console = Console()

    output.mkdir(parents=True, exist_ok=True)

    diff = get_patches_from_repo(path_to_repo, base_ref, target)

    console.print(f"Generating patches for {len(diff)} files...")

    with Progress(console=console) as progress:
        task = progress.add_task("Writing patches", total=len(diff))

        for patch in diff:
            if patch is not None:
                write_patch(patch, output, ext)
            progress.advance(task)

    console.print(f"\n[green]Done.[/green] Patches written to {output}/")
