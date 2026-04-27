"""
BOW snapshot CLI — pulls just the 4 BOW-primary Monday boards into a single
JSON file an in-session Chef can read directly, bypassing Zapier MCP entirely.

Use case: in-session Chef hits a Zapier approval gate or any other MCP
hiccup mid-BOW. Peter runs `bin/chef-snapshot-for-session.sh`, then tells
Chef "read data/snapshots/bow-primary-latest.json" — Chef now has fresh
authoritative state for steps 3, 4, 5, and 8 of tasks/bow-entry.md without
any third-party intermediary.

Usage:
    python3 -m src.bow_snapshot_cli                    # uses config.yaml
    python3 -m src.bow_snapshot_cli /path/to/config    # custom config
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .monday_client import MondayClient
from .sync import _write_json, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 4 primary BOW boards per intel/chef.md and skills/chef/tasks/bow-entry.md
BOW_PRIMARY_BOARDS = [
    {"id": 8480912572, "name": "Team's BOW Entry 2026"},
    {"id": 320096424, "name": "Peter's Tasks"},
    {"id": 5106461839, "name": "Peter's Weekly Planning"},
    {"id": 9973608085, "name": "Master Milestones"},
]

OUTPUT_FILENAME = "bow-primary-latest.json"


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    client = MondayClient(config)

    boards = client.fetch_all_boards(BOW_PRIMARY_BOARDS)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "purpose": "bow-session-snapshot",
        "source_boards_requested": [b["id"] for b in BOW_PRIMARY_BOARDS],
        "boards_fetched": list(boards.keys()),
        "boards": boards,
    }

    snapshot_dir = Path(config["sync"]["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_dir / OUTPUT_FILENAME
    _write_json(out_path, snapshot)

    print(f"BOW snapshot written: {out_path}")
    print(f"  boards fetched: {len(boards)}/{len(BOW_PRIMARY_BOARDS)}")
    if len(boards) < len(BOW_PRIMARY_BOARDS):
        missing = [b["id"] for b in BOW_PRIMARY_BOARDS if str(b["id"]) not in boards]
        print(f"  ⚠ missing boards: {missing} — check perms before relying on this snapshot")


main()
