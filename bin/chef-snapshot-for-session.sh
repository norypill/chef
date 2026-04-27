#!/usr/bin/env bash
# chef-snapshot-for-session.sh — produce a fresh single-file dump of the 4
# BOW-primary Monday boards so an in-session Chef can read authoritative
# state without going through Zapier MCP (or any other intermediary).
#
# Usage:
#   ./bin/chef-snapshot-for-session.sh
#
# Then in your in-session Chef:
#   "Read data/snapshots/bow-primary-latest.json and continue the BOW playbook."

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Source .env if present so MONDAY_API_TOKEN is auto-exported
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [ -z "${MONDAY_API_TOKEN:-}" ]; then
    echo "ERROR: MONDAY_API_TOKEN not set. Add it to .env or export it." >&2
    exit 1
fi

if [ ! -f config.yaml ]; then
    echo "ERROR: config.yaml not found. Copy config.example.yaml first." >&2
    exit 1
fi

echo "=== BOW snapshot — $(date -Iseconds) ==="
python3 -m src.bow_snapshot_cli
echo "=== Done ==="
echo ""
echo "Tell Chef in-session:"
echo "  \"Read data/snapshots/bow-primary-latest.json and continue the BOW playbook.\""
