"""
CLI for protocol-board content refresh.

Reads the cached protocol-boards.json (discovered during regular sync) and
fetches the full item content for each protocol board, caching results to
data/snapshots/protocol-content-<board_id>.json. Run on Sunday 23:00 via
`bin/chef-cron.sh protocol-refresh`.
"""
from __future__ import annotations


import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .monday_client import MondayClient
from .sync import load_config, _write_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    client = MondayClient(config)

    protocol_cfg = config.get("protocol_boards") or {}
    prefix = protocol_cfg.get("name_prefix", "[Protocol]")

    snapshot_dir = Path(config["sync"]["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    cache_path = snapshot_dir / "protocol-boards.json"

    # Refresh the board list first so we're working from current state
    logger.info("Re-discovering protocol boards before content refresh")
    protocol_boards = client.discover_protocol_boards(prefix)
    now = datetime.now(timezone.utc).astimezone().isoformat()
    _write_json(
        cache_path,
        {"timestamp": now, "name_prefix": prefix, "boards": protocol_boards},
    )

    if not protocol_boards:
        print(f"No protocol boards found matching prefix {prefix!r}. Nothing to refresh.")
        return

    fetched = 0
    for i, b in enumerate(protocol_boards):
        board_id = b["id"]
        try:
            content = client.fetch_board(int(board_id))
        except Exception:
            logger.exception("Failed to refresh protocol board %s (%s)", board_id, b.get("name"))
            continue
        out_path = snapshot_dir / f"protocol-content-{board_id}.json"
        _write_json(
            out_path,
            {"timestamp": now, "board_id": board_id, "content": content},
        )
        fetched += 1
        if i < len(protocol_boards) - 1:
            time.sleep(1.0)

    print(f"Protocol content refresh complete — {fetched}/{len(protocol_boards)} boards cached.")


main()
