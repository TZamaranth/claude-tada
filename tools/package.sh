#!/bin/bash
# Builds the downloadable release zip from the committed tree.
# Usage: bash tools/package.sh   ->  dist/tada-v<version>.zip
# The version comes from .claude-plugin/plugin.json, so bump it there first.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -n "$(git status --porcelain)" ]; then
  echo "package.sh: commit your changes first; the zip is built from HEAD" >&2
  exit 1
fi

VERSION="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' .claude-plugin/plugin.json)"
if [ -z "$VERSION" ]; then
  echo "package.sh: no version found in .claude-plugin/plugin.json" >&2
  exit 1
fi

mkdir -p dist
OUTPUT="dist/tada-v$VERSION.zip"
git archive --format=zip --prefix=tada/ -o "$OUTPUT" HEAD
echo "$OUTPUT"
