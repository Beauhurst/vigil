# Run all ci
[group('ci')]
default: lint typecheck format-check test

# Lint with ruff
[group('ci')]
lint:
  uv run ruff check

# Type check with mypy
[group('ci')]
typecheck:
  uv run mypy

# Check formatting with ruff
[group('ci')]
format-check:
  uv run ruff format --check

# Run tests with pytest
[group('ci')]
test:
  uv run pytest

# Get the current version from pyproject.toml
current_version := `uvx bump-my-version show current_version`
_is_current_dev := if current_version =~ '.*dev.*' { 'true' } else { 'false' }

# find if we can bump just the label
# this will fail when pre_label bumping cannot be done (i.e. it's already stable)
# this will succeed but include dev it if is bumping the calver section
_next_pre_label_version := `uvx bump-my-version show --increment pre_label new_version 2>/dev/null || echo 'invalid'`
_can_bump_pre_label := if _next_pre_label_version =~ '.*dev.*|invalid' { 'false' } else { 'true'}

[group('release')]
build:
  uv build --package vigilia --out-dir dist

[group('release')]
pre-release *FLAGS: && build
  #!/usr/bin/env sh
  set -x -e
  if [ '{{_is_current_dev}}' = 'true' ]; then
    # 2024.9.1-dev0 -> 2024.9.1-dev1
    uvx bump-my-version bump pre_release {{FLAGS}}
  else
    # 2024.9.0 -> 2024.9.1-dev0;
    uvx bump-my-version bump num {{FLAGS}}
  fi

[group('release')]
release *FLAGS: && build
  #!/usr/bin/env sh
  set -x -e
  if [ '{{_can_bump_pre_label}}' = 'true' ]; then
    # 2024.9.1-dev0 -> 2024.9.1
    uvx bump-my-version bump pre_label {{FLAGS}}
  else
    # 2024.9.0 -> 2024.9.1
    # or 2024.9.0-dev0 -> 2024.9.1
    uvx bump-my-version bump num --no-commit --no-tag {{FLAGS}}
    uvx bump-my-version bump pre_label --allow-dirty {{FLAGS}}
  fi
