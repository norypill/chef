"""
All-boards snapshot CLI — pulls every board Chef tracks (managed_boards from
config + every protocol board discovered) into a single JSON file. Intended
for ad-hoc in-session use when an in-session Chef needs comprehensive Monday
state without going through any MCP layer (Zapier or native).

Difference vs. the cron sync: this writes one consolidated file to a
predictable path (data/snapshots/chef-everything-latest.json) so an
in-session Chef can read it with a single fetch, instead of stitching
together latest.json + protocol-content-*.json.

Usage:
    python3 -m src.all_boards_snapshot_cli                  # uses config.yaml
    python3 -m src.all_boards_snapshot_cli /path/to/config  # custom config
"""
from __future__ import annotations

import logging
import sys
import time
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

OUTPUT_FILENAME = "chef-everything-latest.json"


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    client = MondayClient(config)

    managed = config.get("managed_boards") or config.get("boards") or []
    protocol_cfg = config.get("protocol_boards") or {}
    protocol_prefix = protocol_cfg.get("name_prefix", "[Protocol]")

    snapshot_dir = Path(config["sync"]["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch every managed board (full content)
    logger.info("Fetching %d managed board(s)…", len(managed))
    managed_data = client.fetch_all_boards(managed)

    # 2. Discover and fetch every protocol board (content)
    protocol_data: dict = {}
    if protocol_cfg.get("discover"):
        logger.info("Discovering protocol boards (prefix %r)…", protocol_prefix)
        protocol_list = client.discover_protocol_boards(protocol_prefix)
        for i, b in enumerate(protocol_list):
            try:
                protocol_data[b["id"]] = client.fetch_board(int(b["id"]))
            except Exception:
                logger.exception("Failed to fetch protocol board %s (%s)", b["id"], b.get("name"))
                continue
            if i < len(protocol_list) - 1:
                time.sleep(1.0)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "purpose": "chef-everything-snapshot",
        "managed_boards": managed_data,
        "protocol_boards": protocol_data,
        "managed_requested_count": len(managed),
        "managed_fetched_count": len(managed_data),
        "protocol_fetched_count": len(protocol_data),
    }

    out_path = snapshot_dir / OUTPUT_FILENAME
    _write_json(out_path, snapshot)

    print(f"Snapshot written: {out_path}")
    print(f"  managed: {len(managed_data)}/{len(managed)}")
    print(f"  protocol: {len(protocol_data)}")
    if len(managed_data) < len(managed):
        missing = [b["id"] for b in managed if str(b["id"]) not in managed_data]
        print(f"  ⚠ missing managed boards: {missing}")


main()
