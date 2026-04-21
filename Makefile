.PHONY: refresh

# `make refresh` — single command to keep all three chef surfaces in sync:
#   1. Cowork (chef.skill bundle)
#   2. Claude.ai Project (loose file uploads — manual step, checklist printed)
#   3. Python cron (this repo on Peter's Mac)
#
# Pulls main, rebuilds the bundle (with SKILL.md auto-sync + validation),
# opens Finder at the repo root, and prints a scannable upload checklist.
refresh:
	@echo "▶ refreshing chef…"
	@git pull --ff-only origin main || { \
	    echo "✗ git pull --ff-only failed — main is not fast-forwardable. Resolve locally (stash/commit/merge) and retry." >&2; \
	    exit 1; \
	}
	@bash package.sh
	@open "$$(pwd)" 2>/dev/null || true
	@bash scripts/refresh-checklist.sh
