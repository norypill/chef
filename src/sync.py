"""Core sync logic: pull Monday.com boards, save snapshots, compute diffs."""
from __future__ import annotations


import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .monday_client import MondayClient
from .diff import compute_diff

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return the YAML config."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_sync(config_path: str = "config.yaml") -> dict:
    """
    Main sync entrypoint:
    1. Load config
    2. Fetch all boards from Monday.com
    3. Save timestamped snapshot
    4. Rotate latest.json -> previous.json
    5. Compute diff against previous snapshot
    6. Save diff
    Returns the diff dict (or empty dict if no previous snapshot).
    """
    config = load_config(config_path)
    client = MondayClient(config)

    now = datetime.now(timezone.utc).astimezone()
    timestamp = now.isoformat()
    file_ts = now.strftime("%Y-%m-%d_%H%M")

    snapshot_dir = Path(config["sync"]["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Fetch all managed boards
    logger.info("Starting sync at %s", timestamp)
    managed_boards_cfg = config.get("managed_boards") or config.get("boards") or []
    logger.info("[phase=fetch] %d managed board(s) configured", len(managed_boards_cfg))
    boards_data = client.fetch_all_boards(managed_boards_cfg)
    logger.info(
        "[phase=fetch] complete — %d/%d boards fetched",
        len(boards_data), len(managed_boards_cfg),
    )

    snapshot = {
        "timestamp": timestamp,
        "boards": boards_data,
    }

    # Discover + cache protocol board list (names only — content is refreshed separately)
    protocol_cfg = config.get("protocol_boards") or {}
    if protocol_cfg.get("discover"):
        prefix = protocol_cfg.get("name_prefix", "[Protocol]")
        try:
            protocol_boards = client.discover_protocol_boards(prefix)
            _write_json(
                snapshot_dir / "protocol-boards.json",
                {"timestamp": timestamp, "name_prefix": prefix, "boards": protocol_boards},
            )
            logger.info("Protocol board list cached (%d boards)", len(protocol_boards))
        except Exception:
            logger.exception("Failed to discover protocol boards — continuing sync")

    # Save timestamped snapshot
    snapshot_path = snapshot_dir / f"{file_ts}.json"
    _write_json(snapshot_path, snapshot)
    logger.info("Snapshot saved: %s", snapshot_path)

    # Rotate latest -> previous
    latest_path = Path("data/latest.json")
    previous_path = Path("data/previous.json")

    has_previous = latest_path.exists()
    if has_previous:
        shutil.copy2(latest_path, previous_path)

    # Write new latest
    _write_json(latest_path, snapshot)

    # Compute diff if we have a previous snapshot. Wrap in try/except so a diff
    # bug never kills a whole sync run — the snapshot itself is already saved.
    diff = {}
    if has_previous:
        logger.info("[phase=diff] computing diff against previous snapshot")
        try:
            previous = _read_json(previous_path)
            diff = compute_diff(previous, snapshot, config)

            # Save diff
            diffs_dir = Path("data/diffs")
            diffs_dir.mkdir(parents=True, exist_ok=True)
            diff_path = diffs_dir / f"{file_ts}_diff.json"
            _write_json(diff_path, diff)

            # Also keep a latest_diff.json for the briefing generator
            _write_json(Path("data/diffs/latest_diff.json"), diff)
            logger.info("[phase=diff] complete — saved %s", diff_path)
        except Exception:
            logger.exception(
                "[phase=diff] FAILED — snapshot is still saved at %s; "
                "brief will run against the previous diff (or empty if first run)",
                snapshot_path,
            )
            diff = {}
    else:
        logger.info("[phase=diff] skipped (no previous snapshot — first run)")

    # Cleanup old snapshots
    try:
        _cleanup_old_snapshots(snapshot_dir, config["sync"].get("keep_snapshots", 30))
    except Exception:
        logger.exception("[phase=cleanup] FAILED — sync still considered successful")

    logger.info("[phase=done] sync complete")
    return diff


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _read_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _cleanup_old_snapshots(snapshot_dir: Path, keep_days: int):
    """Remove snapshots older than keep_days."""
    now = datetime.now(timezone.utc)
    for f in sorted(snapshot_dir.glob("*.json")):
        if f.name == ".gitkeep":
            continue
        age_days = (now.timestamp() - f.stat().st_mtime) / 86400
        if age_days > keep_days:
            logger.info("Removing old snapshot: %s (%.0f days old)", f.name, age_days)
            f.unlink()
