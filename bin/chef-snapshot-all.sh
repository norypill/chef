#!/usr/bin/env bash
# chef-snapshot-all.sh — produce a single comprehensive JSON of EVERY Monday
# board Chef tracks (managed + protocol). For ad-hoc in-session use when
# you want Chef to have full state without waiting for the next cron tick.
#
# Output: data/snapshots/chef-everything-latest.json
#
# Usage:
#   ./bin/chef-snapshot-all.sh
#
# Then in your in-session Chef:
#   "Read data/snapshots/chef-everything-latest.json — that's the full
#    current state of every board I manage."

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

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

echo "=== Chef everything-snapshot — $(date -Iseconds) ==="
python3 -m src.all_boards_snapshot_cli
echo "=== Done ==="
echo ""
echo "Tell Chef in-session:"
echo "  \"Read data/snapshots/chef-everything-latest.json — that's the full"
echo "   current state of every board I manage.\""
