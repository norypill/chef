"""CLI entrypoint for running a Monday.com sync."""
from __future__ import annotations


import logging
import sys

from .sync import run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    diff = run_sync(config_path)
    summary = diff.get("summary", {})
    if summary:
        print(f"Tracked: {summary.get('total_items_tracked', 0)} items")
        print(f"Overdue: {summary.get('overdue_count', 0)}")
        print(f"Stalled: {summary.get('stalled_count', 0)}")
        print(f"Due this week: {summary.get('due_this_week', 0)}")
        print(f"Completed since last: {summary.get('completed_since_last', 0)}")
    else:
        print("First sync complete — no diff available yet.")


main()
