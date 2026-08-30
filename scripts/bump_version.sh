#!/usr/bin/env bash
# Bumps legendarr's version in lockstep across the root pyproject.toml and every
# workspace member (src/backend, src/web, src/bootstrap), then re-locks uv.lock.
set -euo pipefail

part="${1:?usage: scripts/bump_version.sh <major|minor|patch>}"

uv version --bump "$part"
new_version="$(uv version --short)"

for pkg in legendarr-backend legendarr-web legendarr-bootstrap; do
    uv version "$new_version" --package "$pkg"
done

echo "Bumped to $new_version"
