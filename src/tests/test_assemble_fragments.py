"""
Tests for the assemble-fragments CLI command.

Focuses on end-to-end command behaviour. Tree construction and subtree
finding logic are tested in test_tree.py.
"""

from pathlib import Path

import pytest

from vigilia.assemble_fragments import main as assemble_fragments
from vigilia.conf import DEFAULT_PATCH_EXT


def create_patch_file(dir: Path, name: str, content: str) -> Path:
    """Create a patch file in the given directory."""
    path = dir / f"{name}{DEFAULT_PATCH_EXT}"
    path.write_text(content)
    return path


def test_assemble_fragments_creates_output_files(tmp_path: Path) -> None:
    """Command should create fragment files in the output directory."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    create_patch_file(patches_dir, "src__foo", "patch content foo")
    create_patch_file(patches_dir, "src__bar", "patch content bar")

    assemble_fragments(patches_dir=patches_dir, output_dir=output_dir)

    assert output_dir.exists()

    fragment_files = list(output_dir.glob(f"fragment_*{DEFAULT_PATCH_EXT}"))
    assert len(fragment_files) >= 1

    # All patch content should appear in fragments
    all_content = "".join(f.read_text() for f in fragment_files)
    assert "patch content foo" in all_content
    assert "patch content bar" in all_content


def test_assemble_fragments_creates_tree_visualisation(tmp_path: Path) -> None:
    """Command should write a tree.txt file for debugging."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    create_patch_file(patches_dir, "src__lib__utils", "content")

    assemble_fragments(patches_dir=patches_dir, output_dir=output_dir)

    tree_file = output_dir / "tree.txt"
    assert tree_file.exists()

    tree_content = tree_file.read_text()
    assert "root" in tree_content
    assert "src" in tree_content


def test_assemble_fragments_exits_when_no_patches_found(tmp_path: Path) -> None:
    """Command should exit with error when no patch files match."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        assemble_fragments(patches_dir=patches_dir, output_dir=tmp_path / "fragments")

    assert "No patch files found" in str(exc_info.value)


def test_assemble_fragments_respects_prefix_filter(tmp_path: Path) -> None:
    """Command should filter patch files by prefix."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    create_patch_file(patches_dir, "feature__foo", "feature content")
    create_patch_file(patches_dir, "bugfix__bar", "bugfix content")

    assemble_fragments(patches_dir=patches_dir, output_dir=output_dir, prefix="feature")

    fragment_files = list(output_dir.glob(f"fragment_*{DEFAULT_PATCH_EXT}"))
    all_content = "".join(f.read_text() for f in fragment_files)

    assert "feature content" in all_content
    assert "bugfix content" not in all_content


def test_assemble_fragments_skip_oversized_excludes_large_patches(
    tmp_path: Path,
) -> None:
    """With skip_oversized=True, patches exceeding the limit should be excluded."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    create_patch_file(patches_dir, "small", "x" * 10)
    create_patch_file(patches_dir, "huge", "y" * 10000)

    assemble_fragments(
        patches_dir=patches_dir, output_dir=output_dir, max_tokens_per_fragment=100
    )

    fragment_files = list(output_dir.glob(f"fragment_*{DEFAULT_PATCH_EXT}"))
    all_content = "".join(f.read_text() for f in fragment_files)

    assert "x" * 10 in all_content
    assert "y" * 10000 not in all_content


def test_assemble_fragments_include_oversized_keeps_large_patches(
    tmp_path: Path,
) -> None:
    """With skip_oversized=False, patches exceeding the limit should be included."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    create_patch_file(patches_dir, "small", "x" * 10)
    create_patch_file(patches_dir, "huge", "y" * 10000)

    assemble_fragments(
        patches_dir=patches_dir,
        output_dir=output_dir,
        max_tokens_per_fragment=100,
        skip_oversized=False,
    )

    fragment_files = list(output_dir.glob(f"fragment_*{DEFAULT_PATCH_EXT}"))
    all_content = "".join(f.read_text() for f in fragment_files)

    assert "x" * 10 in all_content
    assert "y" * 10000 in all_content


def test_assemble_fragments_splits_into_multiple_fragments(tmp_path: Path) -> None:
    """Large sets of patches should be split into multiple fragment files."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    output_dir = tmp_path / "fragments"

    # Create patches that won't all fit in one fragment
    for i in range(10):
        create_patch_file(patches_dir, f"file_{i}", f"content {i} " * 100)

    assemble_fragments(
        patches_dir=patches_dir, output_dir=output_dir, max_tokens_per_fragment=500
    )

    fragment_files = list(output_dir.glob(f"fragment_*{DEFAULT_PATCH_EXT}"))
    assert len(fragment_files) > 1
