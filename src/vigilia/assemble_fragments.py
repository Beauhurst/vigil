import sys
from collections.abc import Generator, Iterable
from itertools import chain
from pathlib import Path
from typing import Annotated

import rustworkx as rx
import typer
from rich.console import Console
from rich.progress import Progress

from .conf import DEFAULT_MAX_TOKENS, DEFAULT_OUTPUT_DIR, DEFAULT_PATCH_EXT
from .lib.io import find_files, read_files
from .lib.tokens import estimate_tokens
from .lib.tree import (
    NodeData,
    build_patch_tree,
    find_subtrees_with_max_tokens,
    format_tree_ascii,
    get_subtree_leaf_data,
    group_subtrees_into_optimal_fragments,
)


def join_nodes_into_fragment(nodes: Iterable[NodeData]) -> str:
    return "\n\n".join(node["content"] for node in nodes)


def assemble_fragments(
    tree: rx.PyDiGraph[NodeData, None],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    skip_oversized: bool = True,
    console: Console,
) -> Generator[str]:
    """Break a patch tree into token-limited fragments for LLM processing.

    Two-phase approach:
    1. Find the largest subtrees that fit within the limit (coarse grouping)
    2. Greedily pack those subtrees together until we'd exceed the limit

    This keeps related patches together where possible, whilst ensuring each
    fragment is small enough to process in a single LLM call.

    Single patches that exceed max_tokens are included as-is with a warning,
    rather than being truncated or dropped. Truncating diffs mid-way would
    corrupt them, and dropping them silently loses information.
    """
    subtrees = find_subtrees_with_max_tokens(tree, max_tokens=max_tokens)
    subtree_groups = group_subtrees_into_optimal_fragments(
        tree, subtrees=subtrees, max_tokens=max_tokens
    )

    for subtree_group in subtree_groups:
        leaf_nodes = list(
            chain.from_iterable(
                get_subtree_leaf_data(tree, from_node=subtree)
                for subtree in subtree_group
            )
        )

        if len(leaf_nodes) == 1 and leaf_nodes[0]["token_estimate"] > max_tokens:
            # Single patch exceeds token limit
            if skip_oversized:
                console.print(
                    "[yellow]Warning:[/yellow] Single patch "
                    f"'{leaf_nodes[0].get('path', 'root')}' exceeds token limit "
                    f"({leaf_nodes[0]['token_estimate']:,} > {max_tokens:,}). Skipping."
                )
                continue
            else:
                console.print(
                    "[yellow]Warning:[/yellow] Single patch "
                    f"'{leaf_nodes[0].get('path', 'root')}' exceeds token limit "
                    f"({leaf_nodes[0]['token_estimate']:,} > {max_tokens:,}). Including as-is."
                )

        fragment = join_nodes_into_fragment(leaf_nodes)

        yield fragment


def main(
    patches_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory containing patch files",
            exists=True,
            dir_okay=True,
            file_okay=False,
        ),
    ],
    prefix: Annotated[
        str, typer.Option("-p", help="Prefix to filter patch files")
    ] = "",
    ext: Annotated[
        str, typer.Option("-e", help="Patch file extension")
    ] = DEFAULT_PATCH_EXT,
    max_tokens_per_fragment: Annotated[
        int,
        typer.Option(
            "-t", help="Approximate maximum number of tokens to assemble a fragment"
        ),
    ] = DEFAULT_MAX_TOKENS,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file to write summary to (optional)",
            dir_okay=True,
            file_okay=False,
        ),
    ] = DEFAULT_OUTPUT_DIR / "fragments",
    skip_oversized: Annotated[
        bool,
        typer.Option(
            "--skip-oversized/--include-oversized",
            help="Skip patches that exceed the token limit instead of including them",
        ),
    ] = True,
) -> None:
    """Assemble patch files into token-limited fragments for LLM processing."""
    console = Console()

    patch_files = list(find_files(patches_dir, prefix, ext))

    if not patch_files:
        sys.exit(f"Error: No patch files found with prefix '{prefix}' in {patches_dir}")

    console.print(f"Found {len(patch_files)} patch files")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build a tree from patch filenames to group related files together,
    # then break into fragments that fit within the token limit
    patch_tree = build_patch_tree(
        read_files(patch_files), estimate_tokens=estimate_tokens
    )

    # Write tree visualisation for debugging — helps verify grouping logic
    with open(output_dir / "tree.txt", "w") as f:
        f.write(format_tree_ascii(patch_tree, max_depth=5))

    fragments = list(
        assemble_fragments(
            patch_tree,
            max_tokens=max_tokens_per_fragment,
            skip_oversized=skip_oversized,
            console=console,
        )
    )

    with Progress(console=console) as progress:
        task = progress.add_task("Writing fragments...", total=len(fragments))

        for i, fragment in enumerate(fragments):
            with open(output_dir / f"fragment_{i}{ext}", "w") as f:
                f.write(fragment)
            progress.advance(task)

        progress.update(
            task,
            description=f"Writing fragments: [bold green]✓[/bold green] {len(fragments)} files written",
        )
