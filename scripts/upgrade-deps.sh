#!/usr/bin/env bash
# Mechanical batch upgrade: refresh the lock against every allowed newer version.
# Callers (the weekly GitHub job, local dry-run) run tests after this script.
set -euo pipefail
cd "$(dirname "$0")/.."
uv lock --upgrade
