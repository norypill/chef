#!/usr/bin/env bash
# monday-sync.sh — Main sync entrypoint (cron-friendly)
# Pulls Monday.com boards, saves snapshot, computes diff.
#
# Usage:
#   ./bin/monday-sync.sh                  # uses config.yaml in project root
#   ./bin/monday-sync.sh /path/to/config  # custom config path
#
# Cron example (8 AM and 4 PM ET):
#   0 8,16 * * * cd ~/Projects/pill-pm && MONDAY_API_TOKEN="..." ./bin/monday-sync.sh >> logs/sync.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_PATH="${1:-$PROJECT_DIR/config.yaml}"

cd "$PROJECT_DIR"

# Ensure logs dir exists
mkdir -p logs

echo "=== Monday.com Sync — $(date -Iseconds) ==="

# Check for API token
if [ -z "${MONDAY_API_TOKEN:-}" ]; then
    echo "ERROR: MONDAY_API_TOKEN environment variable is not set."
    echo "Set it with: export MONDAY_API_TOKEN=your_token"
    exit 1
fi

# Run sync
python3 -m src.sync_cli "$CONFIG_PATH"

echo "=== Sync complete — $(date -Iseconds) ==="
