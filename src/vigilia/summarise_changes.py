"""
Orchestrates the full pipeline for summarising changes between two git commits.

Calls the existing commands in sequence: git-patches → assemble-fragments → summarise-fragments.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .assemble_fragments import main as assemble_fragments
from .conf import DEFAULT_MAX_TOKENS, DEFAULT_MODEL_ID
from .extract_patches import main as extract_patches
from .summarise_fragments import main as summarise_fragments


def main(
    base_ref: Annotated[
        str, typer.Argument(help="Base reference (tag, branch, or commit)")
    ] = "HEAD^",
    target: Annotated[str, typer.Argument(help="Target reference")] = "HEAD",
    path_to_repo: Annotated[
        Path, typer.Option("-r", "--repo", help="Path to repository")
    ] = Path("."),
    output_dir: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output",
            help="Output directory for the intermediary files and final summary",
            dir_okay=True,
            file_okay=False,
        ),
    ] = Path("out/"),
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = DEFAULT_MODEL_ID,
    max_tokens: Annotated[
        int,
        typer.Option("-t", "--max-tokens", help="Maximum tokens per fragment"),
    ] = DEFAULT_MAX_TOKENS,
    skip_oversized: Annotated[
        bool,
        typer.Option(
            "--skip-oversized/--include-oversized",
            help="Skip patches that exceed the token limit instead of including them",
        ),
    ] = True,
) -> None:
    """
    Summarise changes between two git commits in one command.

    Runs the full pipeline: extracts patches from git, assembles them into
    token-limited fragments, summarises each fragment via an LLM, then
    consolidates into a final summary.

    Example:
        $ vigilia summarise-changes v1.0.0 main --repo /path/to/repo
    """
    console = Console()

    patches_dir = output_dir / "patches"
    fragments_dir = output_dir / "fragments"
    summaries_dir = output_dir / "summaries"

    console.print(
        f"[bold]Step 1/3:[/bold] Extracting patches from {base_ref}..{target}"
    )
    extract_patches(
        base_ref=base_ref,
        target=target,
        path_to_repo=path_to_repo,
        output=patches_dir,
    )

    console.print("[bold]Step 2/3:[/bold] Assembling fragments")
    assemble_fragments(
        patches_dir=patches_dir,
        prefix="",
        max_tokens_per_fragment=max_tokens,
        output_dir=fragments_dir,
        skip_oversized=skip_oversized,
    )

    console.print("[bold]Step 3/3:[/bold] Summarising fragments")
    summarise_fragments(
        fragments_dir=fragments_dir,
        model=model,
        prefix="fragment",
        output_dir=summaries_dir,
    )
