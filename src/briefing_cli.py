"""CLI entrypoint for generating a PM briefing."""
from __future__ import annotations


import sys

from .briefing import generate_briefing


def main():
    latest = sys.argv[1] if len(sys.argv) > 1 else "data/latest.json"
    diff = sys.argv[2] if len(sys.argv) > 2 else "data/diffs/latest_diff.json"
    intel = sys.argv[3] if len(sys.argv) > 3 else "intel"

    briefing = generate_briefing(latest, diff, intel)
    print(briefing)


main()
