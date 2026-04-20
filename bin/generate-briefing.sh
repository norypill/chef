#!/usr/bin/env bash
# generate-briefing.sh — Generate a PM briefing from latest data
#
# Usage:
#   ./bin/generate-briefing.sh           # outputs markdown to stdout
#   ./bin/generate-briefing.sh > briefing.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

python3 -m src.briefing_cli
