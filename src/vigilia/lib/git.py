import sys
from pathlib import Path

import pygit2


def get_patches_from_repo(
    path_to_repo: Path, base_ref: str, target: str
) -> pygit2.Diff:
    """Compute the diff between two git references in a repository.

    >>> diff = get_patches_from_repo(Path("."), "HEAD~5", "HEAD")
    >>> len(list(diff))  # number of changed files
    3
    """
    repo = pygit2.Repository(pygit2.discover_repository(path_to_repo))

    try:
        base = repo.revparse_single(base_ref)
        target_ref = repo.revparse_single(target)
    except KeyError as e:
        sys.exit(f"Error: Could not find ref {e}")

    # Cast to Commit objects for diff
    base_commit = base.peel(pygit2.Commit)
    target_commit = target_ref.peel(pygit2.Commit)

    return repo.diff(base_commit, target_commit)
