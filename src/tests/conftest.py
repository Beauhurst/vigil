"""
Shared pytest configuration and fixtures.
"""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pygit2
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from pytest_mock import MockerFixture

from vigilia.lib.agent import (
    get_fragment_summarisation_agent,
    get_summary_consolidation_agent,
)

# Prevent any accidental real LLM requests during tests
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def git_repo_with_nested_files(tmp_path: Path) -> Path:
    """Create a git repository with nested file structure."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    repo = pygit2.init_repository(repo_path)
    repo.config["user.email"] = "test@example.com"
    repo.config["user.name"] = "Test User"

    # Initial commit
    (repo_path / "hello.txt").write_text("hello\n")
    repo.index.add("hello.txt")
    repo.index.write()
    tree = repo.index.write_tree()
    repo.create_commit(
        "HEAD",
        repo.default_signature,
        repo.default_signature,
        "initial",
        tree,
        [],
    )

    # Second commit with changes including nested files
    (repo_path / "hello.txt").write_text("hello world\n")
    (repo_path / "src").mkdir(parents=True, exist_ok=True)
    (repo_path / "src/nested.py").write_text("print('nested')\n")
    repo.index.add("hello.txt")
    repo.index.add("src/nested.py")
    repo.index.write()
    tree = repo.index.write_tree()
    repo.create_commit(
        "HEAD",
        repo.default_signature,
        repo.default_signature,
        "add changes",
        tree,
        [repo.head.target],
    )

    return repo_path


@pytest.fixture
def auto_confirm() -> Generator[None]:
    """Auto-confirm the prompt to send fragments to LLM."""
    with patch("vigilia.summarise_fragments.Confirm.ask", return_value=True):
        yield


@pytest.fixture
def mock_llm_agents(mocker: MockerFixture) -> None:
    """Mock the LLM agents with TestModel to avoid real API calls."""
    mocker.patch(
        "vigilia.summarise_fragments.get_fragment_summarisation_agent",
        return_value=get_fragment_summarisation_agent(TestModel()),
    )
    mocker.patch(
        "vigilia.summarise_fragments.get_summary_consolidation_agent",
        return_value=get_summary_consolidation_agent(TestModel()),
    )
