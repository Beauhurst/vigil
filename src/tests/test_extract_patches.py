"""
Tests for the extract_patches module.

Uses a real git repository created in a temp directory to verify patch extraction
works end-to-end.
"""

from pathlib import Path

from vigilia.extract_patches import main as extract_patches


def test_extract_patches_extracts_patches_to_output_dir(
    git_repo_with_nested_files: Path, tmp_path: Path
) -> None:
    """The extract_patches command should write patch files for each changed file."""
    output_dir = tmp_path / "patches"

    extract_patches(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output=output_dir,
        ext=".patch",
    )

    patch_files = list(output_dir.glob("*.patch"))
    assert len(patch_files) == 2

    filenames = {p.name for p in patch_files}
    assert "hello.txt.patch" in filenames
    assert "src__nested.py.patch" in filenames


def test_extract_patches_creates_output_dir_if_missing(
    git_repo_with_nested_files: Path, tmp_path: Path
) -> None:
    """Output directory should be created if it doesn't exist."""
    output_dir = tmp_path / "deeply" / "nested" / "output"
    assert not output_dir.exists()

    extract_patches(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output=output_dir,
        ext=".patch",
    )

    assert output_dir.exists()
    assert len(list(output_dir.glob("*.patch"))) == 2


def test_extract_patches_respects_custom_extension(
    git_repo_with_nested_files: Path, tmp_path: Path
) -> None:
    """Custom file extensions should be applied to output files."""
    output_dir = tmp_path / "patches"

    extract_patches(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output=output_dir,
        ext=".diff",
    )

    assert len(list(output_dir.glob("*.diff"))) == 2
    assert len(list(output_dir.glob("*.patch"))) == 0


def test_patch_content_contains_diff(
    git_repo_with_nested_files: Path, tmp_path: Path
) -> None:
    """Patch files should contain actual diff content."""
    output_dir = tmp_path / "patches"

    extract_patches(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output=output_dir,
        ext=".patch",
    )

    hello_patch = output_dir / "hello.txt.patch"
    content = hello_patch.read_text()

    assert "-hello" in content
    assert "+hello world" in content


def test_nested_paths_are_flattened(
    git_repo_with_nested_files: Path, tmp_path: Path
) -> None:
    """Slashes in file paths should be replaced with double underscores."""
    output_dir = tmp_path / "patches"

    extract_patches(
        base_ref="HEAD^",
        target="HEAD",
        path_to_repo=git_repo_with_nested_files,
        output=output_dir,
        ext=".patch",
    )

    nested_patch = output_dir / "src__nested.py.patch"
    assert nested_patch.exists()

    content = nested_patch.read_text()
    assert "nested" in content
