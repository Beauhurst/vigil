"""
Tests for the summarise-fragments CLI command.

Uses pydantic-ai's TestModel to avoid real LLM calls.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.models.test import TestModel

from vigilia.conf import DEFAULT_PATCH_EXT
from vigilia.lib.agent import (
    get_fragment_summarisation_agent,
    get_summary_consolidation_agent,
)
from vigilia.summarise_fragments import (
    consolidate_summaries,
    main as summarise_fragments,
    summarise_fragment,
)


def create_fragment_file(dir: Path, name: str, content: str) -> Path:
    """Create a fragment file in the given directory."""
    path = dir / f"{name}{DEFAULT_PATCH_EXT}"
    path.write_text(content)
    return path


def test_summarise_fragment_includes_fragment_content(mock_llm_agents: None) -> None:
    """Fragment content should be included in the agent call."""
    agent = get_fragment_summarisation_agent(TestModel())

    with capture_run_messages() as messages:
        summarise_fragment(agent, fragment="diff content here", tree=None)

    # The instructions decorator adds content to the request
    assert len(messages) > 0
    # Check that the fragment content appears somewhere in the messages
    all_text = str(messages)
    assert "diff content here" in all_text


def test_summarise_fragment_includes_tree_when_provided(mock_llm_agents: None) -> None:
    """Tree content should be included when provided."""
    agent = get_fragment_summarisation_agent(TestModel())
    tree_content = "root:100\n└── src:100"

    with capture_run_messages() as messages:
        summarise_fragment(agent, fragment="some diff", tree=tree_content)

    all_text = str(messages)
    assert "root:100" in all_text
    assert "src:100" in all_text


def test_consolidate_summaries_includes_all_summaries(mock_llm_agents: None) -> None:
    """All partial summaries should be included in consolidation."""
    agent = get_summary_consolidation_agent(TestModel())
    summaries = ["Summary A content", "Summary B content", "Summary C content"]

    with capture_run_messages() as messages:
        consolidate_summaries(agent, summaries=summaries, tree=None)

    all_text = str(messages)
    assert "Summary A content" in all_text
    assert "Summary B content" in all_text
    assert "Summary C content" in all_text


def test_consolidate_summaries_includes_tree_when_provided(
    mock_llm_agents: None,
) -> None:
    """Tree content should be included in consolidation when provided."""
    agent = get_summary_consolidation_agent(TestModel())
    tree_content = "root:50\n└── lib:50"

    with capture_run_messages() as messages:
        consolidate_summaries(agent, summaries=["summary"], tree=tree_content)

    all_text = str(messages)
    assert "root:50" in all_text


def test_summarise_fragments_creates_output_files(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Command should create summary files in the output directory."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "diff content here")

    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    assert output_dir.exists()
    assert (output_dir / "summary_of_fragment_1.md").exists()
    assert (output_dir / "technical_summary.md").exists()


def test_summarise_fragments_exits_when_no_fragments_found(
    tmp_path: Path, mock_llm_agents: None
) -> None:
    """Command should exit with error when no fragment files match."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        summarise_fragments(
            fragments_dir=fragments_dir,
            output_dir=tmp_path / "summaries",
        )

    assert "No fragments files found" in str(exc_info.value)


def test_summarise_fragments_respects_prefix_filter(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Command should filter fragment files by prefix."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "fragment content")
    create_fragment_file(fragments_dir, "other_0", "other content")

    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
        prefix="fragment",
    )

    # Only fragment_0 should be processed
    assert (output_dir / "summary_of_fragment_1.md").exists()
    assert not (output_dir / "summary_of_fragment_2.md").exists()


def test_summarise_fragments_skips_empty_fragments(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Empty fragments should be skipped without error."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    # One empty, one with content
    create_fragment_file(fragments_dir, "fragment_0", "")
    create_fragment_file(fragments_dir, "fragment_1", "actual content")

    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    # Should have exactly one summary file (for the non-empty fragment)
    summary_files = list(output_dir.glob("summary_of_fragment_*.md"))
    assert len(summary_files) == 1

    # Final summary should exist
    assert (output_dir / "technical_summary.md").exists()


def test_summarise_fragments_caches_intermediate_summaries(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Intermediate summaries should be cached and reused on re-run."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "content")

    # First run
    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    # Modify the cached file to verify it's reused
    (output_dir / "summary_of_fragment_1.md").write_text("cached summary")

    # Second run should use cached file
    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    assert (output_dir / "summary_of_fragment_1.md").read_text() == "cached summary"


def test_summarise_fragments_reads_tree_file(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Command should read tree.txt if present in fragments directory."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "content")
    (fragments_dir / "tree.txt").write_text("root:100\n└── src:100")

    # Should not raise, tree file is optional context
    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    assert (output_dir / "technical_summary.md").exists()


def test_summarise_fragments_consolidates_multiple_summaries(
    tmp_path: Path, auto_confirm: None, mock_llm_agents: None
) -> None:
    """Multiple fragments should be consolidated into a single summary."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "content 1")
    create_fragment_file(fragments_dir, "fragment_1", "content 2")
    create_fragment_file(fragments_dir, "fragment_2", "content 3")

    summarise_fragments(
        fragments_dir=fragments_dir,
        output_dir=output_dir,
    )

    # Should have individual summaries and a consolidated one
    assert (output_dir / "summary_of_fragment_1.md").exists()
    assert (output_dir / "summary_of_fragment_2.md").exists()
    assert (output_dir / "summary_of_fragment_3.md").exists()
    assert (output_dir / "technical_summary.md").exists()


def test_summarise_fragments_cancelled_by_user(
    tmp_path: Path, mock_llm_agents: None
) -> None:
    """Command should exit gracefully when user declines confirmation."""
    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    output_dir = tmp_path / "summaries"

    create_fragment_file(fragments_dir, "fragment_0", "content")

    with patch("vigilia.summarise_fragments.Confirm.ask", return_value=False):
        summarise_fragments(
            fragments_dir=fragments_dir,
            output_dir=output_dir,
        )

    # No output should be created when cancelled
    assert not output_dir.exists() or not (output_dir / "technical_summary.md").exists()
