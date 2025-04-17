#!/bin/sh
# Pre-commit hook to increment Poetry patch version and avoid double-bumping

# Exit on error
set -e

# Ensure Poetry is available
command -v poetry >/dev/null 2>&1 || { echo "Poetry not found, aborting commit."; exit 1; }

# Get the current version from pyproject.toml
CURRENT_VERSION=$(poetry version -s)

# Check if pyproject.toml is already staged
if git diff --cached --name-only | grep -q '^pyproject\.toml$'; then
    # Get the staged version of pyproject.toml
    STAGED_VERSION=$(git show :pyproject.toml | grep -E '^version\s*=\s*"' | sed -E 's/.*version\s*=\s*"([^"]+)".*/\1/')
    if [ "$CURRENT_VERSION" = "$STAGED_VERSION" ]; then
        echo "Version $CURRENT_VERSION already staged, skipping patch increment."
        exit 0
    fi
fi

# Run poetry version patch
echo "Incrementing patch version from $CURRENT_VERSION..."
poetry version patch

# Stage the updated pyproject.toml
git add pyproject.toml

# Optionally stage poetry.lock if it exists and was modified
if [ -f poetry.lock ]; then
    git add poetry.lock
fi

echo "Patch version incremented and files staged."
exit 0