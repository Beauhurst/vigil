"""
Tests for the summarise_changes CLI command.

Integration tests covering the full pipeline from git diff to final summary.
Uses the git_repo_with_nested_files fixture and mocks the LLM agents.
"""

from pathlib import Path

from vigilia.summarise_changes import main as summarise_changes


def test_summarise_changes_full_pipeline(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """The full pipeline should produce a technical summary from a git diff."""
    output_dir = tmp_path / "output"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=output_dir,
    )

    assert (output_dir / "summaries" / "technical_summary.md").exists()


def test_summarise_changes_creates_intermediate_artifacts(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """Pipeline should create patches, fragments, and summaries directories."""
    output_dir = tmp_path / "output"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=output_dir,
    )

    assert (output_dir / "patches").exists()
    assert (output_dir / "fragments").exists()
    assert (output_dir / "summaries").exists()


def test_summarise_changes_extracts_patches_for_changed_files(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """Patches should be extracted for each file changed in the diff."""
    output_dir = tmp_path / "output"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=output_dir,
    )

    patches_dir = output_dir / "patches"
    patch_files = list(patches_dir.glob("*.patch"))

    assert len(patch_files) == 2

    filenames = {p.name for p in patch_files}
    assert "hello.txt.patch" in filenames
    assert "src__nested.py.patch" in filenames


def test_summarise_changes_creates_tree_visualisation(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """A tree.txt file should be created in the fragments directory."""
    output_dir = tmp_path / "output"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=output_dir,
    )

    tree_file = output_dir / "fragments" / "tree.txt"
    assert tree_file.exists()

    content = tree_file.read_text()
    assert "root" in content


def test_summarise_changes_creates_fragment_summaries(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """Individual fragment summaries should be created before consolidation."""
    output_dir = tmp_path / "output"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=output_dir,
    )

    summaries_dir = output_dir / "summaries"
    summary_files = list(summaries_dir.glob("summary_of_fragment_*.md"))

    assert len(summary_files) >= 1


def test_summarise_changes_with_custom_output_dir(
    mock_llm_agents: None,
    git_repo_with_nested_files: Path,
    tmp_path: Path,
    auto_confirm: None,
) -> None:
    """Custom output directory should be respected."""
    custom_dir = tmp_path / "custom" / "nested" / "path"

    summarise_changes(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output_dir=custom_dir,
    )

    assert custom_dir.exists()
    assert (custom_dir / "summaries" / "technical_summary.md").exists()
