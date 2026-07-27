import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic_ai import Agent
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Confirm

from .conf import DEFAULT_MODEL_ID, DEFAULT_OUTPUT_DIR, DEFAULT_PATCH_EXT
from .lib.agent import (
    FragmentSummarisationDeps,
    SummaryConsolidationDeps,
    get_fragment_summarisation_agent,
    get_summary_consolidation_agent,
)
from .lib.io import find_files, read_files


def summarise_fragment(
    agent: Agent[FragmentSummarisationDeps],
    *,
    fragment: str,
    tree: str | None = None,
) -> str:
    """Summarise a single code diff fragment using the provided agent."""
    result = agent.run_sync(
        "Go!",
        deps=FragmentSummarisationDeps(patch_fragment=fragment, tree=tree),
    )
    return result.output


def consolidate_summaries(
    agent: Agent[SummaryConsolidationDeps],
    *,
    summaries: list[str],
    tree: str | None = None,
) -> str:
    """Consolidate multiple fragment summaries into a single document."""
    result = agent.run_sync(
        "Go!",
        deps=SummaryConsolidationDeps(partial_summaries=summaries, tree=tree),
    )
    return result.output


def main(
    fragments_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory containing fragments files",
            exists=True,
            dir_okay=True,
            file_okay=False,
        ),
    ],
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = DEFAULT_MODEL_ID,
    prefix: Annotated[
        str, typer.Option("-p", help="Prefix to filter fragment files")
    ] = "fragment",
    ext: Annotated[
        str, typer.Option("-e", help="fragment file extension")
    ] = DEFAULT_PATCH_EXT,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file to write summary to (optional)",
            dir_okay=True,
            file_okay=False,
        ),
    ] = DEFAULT_OUTPUT_DIR / "summaries",
) -> None:
    """
    Generate technical summaries from code change fragments.

    Reads fragment files from the specified directory, sends each to an LLM for
    summarisation, then consolidates all partial summaries into a final document.

    Intermediate summaries are cached to disk, so re-running skips already-processed
    fragments. The final output is written to `technical_summary.md` in the output
    directory.

    Example:
        $ vigilia summarise-fragments out/fragments --model anthropic:claude-opus-4-5
    """
    console = Console()

    fragments_files = list(find_files(fragments_dir, prefix, ext))

    if not fragments_files:
        sys.exit(
            f"Error: No fragments files found with prefix '{prefix}' in {fragments_files}"
        )

    console.print(f"Found {len(fragments_files)} patch files")

    output_dir.mkdir(parents=True, exist_ok=True)

    fragments = [content for name, content in read_files(fragments_files)]

    # The tree file provides structural context to the LLM, helping it understand
    # where each fragment fits within the broader set of changes.
    tree: str | None = None
    tree_path = fragments_dir / "tree.txt"
    if tree_path.exists():
        with open(tree_path) as f:
            tree = f.read()

    if not Confirm.ask(
        f"Send {len(fragments)} fragments to {model} for summarisation?"
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    console.print("[yellow]Sending to LLM for summarisation...[/yellow]")

    summaries: list[str] = []

    summarise_fragment_agent = get_fragment_summarisation_agent(model=model)

    with Progress(console=console) as progress:
        task = progress.add_task("Generating summaries", total=len(fragments) + 1)

        for i, fragment in enumerate(fragments, 1):
            if not fragment.strip():
                console.print(f"[yellow]Skipping empty fragment {i}[/yellow]")
                progress.advance(task)
                continue

            # Each fragment's summary is cached to disk. This allows resumption if
            # the process is interrupted, and avoids redundant LLM calls on re-runs.
            summary_of_fragment_filename = output_dir / f"summary_of_fragment_{i}.md"

            if summary_of_fragment_filename.exists():
                with open(summary_of_fragment_filename) as f:
                    summary = f.read()
                progress.update(
                    task,
                    description=f"Summary for fragment {i}/{len(fragments)} exists.",
                )
            else:
                progress.update(
                    task, description=f"Summarising fragment {i}/{len(fragments)}"
                )
                summary = summarise_fragment(
                    summarise_fragment_agent, fragment=fragment, tree=tree
                )

                with open(summary_of_fragment_filename, "w") as f:
                    f.write(summary)

            summaries.append(summary)
            progress.advance(task)

        progress.update(
            task,
            description="Generating final summary, including all fragment summaries",
        )

        # When there are multiple fragments, we consolidate their summaries into a
        # single coherent document. This reduces redundancy and produces a unified
        # view of all changes. A single fragment needs no consolidation.
        if len(summaries) > 1:
            combine_summaries_agent = get_summary_consolidation_agent(model=model)
            combined_summary = consolidate_summaries(
                combine_summaries_agent, summaries=summaries, tree=tree
            )
        else:
            combined_summary = summaries[0]

        final_output_filename = output_dir / "technical_summary.md"
        progress.advance(task)

        with open(final_output_filename, "w") as f:
            f.write(combined_summary)
            progress.update(
                task,
                description=f"[bold green]✓[/bold green] Final summary written to {final_output_filename}",
            )


if __name__ == "__main__":
    typer.run(main)
