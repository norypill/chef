#!/usr/bin/env bash
# deploy-check.sh — Pre-flight for chef-cron.sh. Exits 1 with a clear reason on any failure.
#
# Verifies:
#   - Working tree is clean (no uncommitted changes)
#   - Current branch is main
#   - Local main matches origin/main exactly (fetch + SHA compare)
#   - MONDAY_API_TOKEN and SLACK_WEBHOOK_URL are set
#   - config.yaml exists at repo root

set -euo pipefail

cd "$(dirname "$0")"

fail() {
    echo "deploy-check FAILED: $1" >&2
    exit 1
}

# 1. Clean working tree
if [ -n "$(git status --porcelain)" ]; then
    fail "working tree has uncommitted changes — commit or stash before cron runs"
fi

# 2. On branch main
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "main" ]; then
    fail "current branch is '$current_branch'; cron only runs from main"
fi

# 3. Local main matches origin/main
if ! git fetch origin main --quiet; then
    fail "could not fetch origin/main (network or auth issue)"
fi
local_sha="$(git rev-parse main)"
remote_sha="$(git rev-parse origin/main)"
if [ "$local_sha" != "$remote_sha" ]; then
    fail "local main ($local_sha) does not match origin/main ($remote_sha) — pull or push before cron runs"
fi

# 4. Required env vars
: "${MONDAY_API_TOKEN:?deploy-check FAILED: MONDAY_API_TOKEN is not set}"
: "${SLACK_WEBHOOK_URL:?deploy-check FAILED: SLACK_WEBHOOK_URL is not set}"

# 5. config.yaml exists
if [ ! -f config.yaml ]; then
    fail "config.yaml not found at repo root (copy config.example.yaml to config.yaml and edit)"
fi

echo "deploy-check OK  branch=main  sha=$local_sha"
