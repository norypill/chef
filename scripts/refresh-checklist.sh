#!/usr/bin/env bash
# Print the post-build upload checklist for `make refresh`.
# No Python, no external deps — just bash + sed + find.

set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

printf '\n'
printf '%b── upload checklist ──%b\n' "$BOLD" "$RESET"

# Surface 1: Cowork
printf '%b✅ Cowork:%b drag %bchef.skill%b onto Cowork Settings → Skills\n' \
    "$GREEN" "$RESET" "$BOLD" "$RESET"

# Surface 2: Claude.ai Project — static core + auto-discovered task playbooks
printf '%b📋 Claude.ai Project:%b upload these files (overwrite existing):\n' \
    "$YELLOW" "$RESET"
printf '   • intel/chef.md\n'
printf '   • skills/chef/SKILL.md\n'
find skills/chef/tasks -maxdepth 1 -name '*.md' -type f | sort | while read -r f; do
    printf '   • %s\n' "$f"
done

# Project URL: pull from config.yaml, fall back if missing/unset
if [ ! -f config.yaml ]; then
    printf '%b⚠ config.yaml not found — copy config.example.yaml to config.yaml to set your Project URL.%b\n' \
        "$YELLOW" "$RESET" >&2
    printf '%b🔗 Project URL:%b set claude_project_url in config.yaml\n' \
        "$BLUE" "$RESET"
else
    # Extract: strip key prefix, trailing comments, surrounding double quotes
    url="$(sed -n 's/^claude_project_url:[[:space:]]*//p' config.yaml \
        | head -1 \
        | sed -E 's/[[:space:]]*#.*$//; s/^"(.*)"$/\1/')"
    if [ -n "$url" ]; then
        printf '%b🔗 Project URL:%b %s\n' "$BLUE" "$RESET" "$url"
    else
        printf '%b🔗 Project URL:%b set claude_project_url in config.yaml\n' \
            "$BLUE" "$RESET"
    fi
fi

printf '\n'
printf '%b✅ refresh complete — all three surfaces ready%b\n' "$GREEN" "$RESET"
