#!/usr/bin/env bash
# chef-cron.sh — Cron entrypoint for Chef's recurring runs.
#
# Usage:
#   bin/chef-cron.sh sync              # pull managed boards, compute diff
#   bin/chef-cron.sh brief             # generate briefing, post to Slack
#   bin/chef-cron.sh protocol-refresh  # fetch all protocol-board content
#
# Runs deploy-check.sh first. On any failure (deploy-check or the run itself),
# posts a red-line alert to $SLACK_WEBHOOK_URL and exits non-zero.

set -euo pipefail

STAGE="init"
MODE="${1:-}"

REPO_DIR="${HOME}/chef"
cd "$REPO_DIR"

# --- .env (sourced with auto-export so variables are exposed to child processes) ---
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# --- logging setup: per-day log file, SHA-stamped run header ---
mkdir -p logs
LOG_FILE="logs/cron-$(date +%Y-%m-%d).log"
COMMIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
RUN_TS="$(date -Iseconds)"

{
    echo ""
    echo "=========================================================="
    echo "Run: mode=${MODE:-<none>}  ts=${RUN_TS}  sha=${COMMIT_SHA}"
    echo "=========================================================="
} >> "$LOG_FILE"

# Mirror all subsequent stdout/stderr into the log while still printing to stdout
exec > >(tee -a "$LOG_FILE") 2>&1

post_slack() {
    local text="$1"
    if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
        echo "WARN: SLACK_WEBHOOK_URL not set — skipping Slack post"
        return 0
    fi
    # Escape via jq so multi-line markdown survives JSON encoding
    local payload
    payload="$(printf '%s' "$text" | jq -Rs '{text: .}')"
    curl -fsS -X POST -H 'Content-Type: application/json' \
        --data "$payload" "$SLACK_WEBHOOK_URL" >/dev/null || true
}

write_sync_status() {
    # Write data/sync-status.json so briefing.py can warn when data is stale.
    # args: $1 = ok ("true"|"false"), $2 = reason (string, may be empty)
    local ok="$1"
    local reason="$2"
    mkdir -p data
    jq -n \
        --argjson ok "$ok" \
        --arg ts "$(date -Iseconds)" \
        --arg reason "$reason" \
        '{ok: $ok, ts: $ts, reason: $reason}' \
        > data/sync-status.json
}

on_failure() {
    local exit_code=$?
    local err_snip="${LAST_ERR:-see ${LOG_FILE}}"
    # Keep the LAST 2000 chars — actual errors live at the end of the log,
    # not the start. Slack message stays under its size limit.
    err_snip="$(printf '%s' "$err_snip" | tail -c 2000)"
    # If sync was the failing stage, mark the status file so briefing.py can warn
    if [ "$STAGE" = "sync" ]; then
        write_sync_status false "$err_snip"
    fi
    local msg
    msg=$(printf '🚨 CHEF FAILURE: %s — %s\nsha=%s  mode=%s  ts=%s\nfull log: %s' \
        "$STAGE" "$err_snip" "$COMMIT_SHA" "${MODE:-<none>}" "$RUN_TS" "$LOG_FILE")
    echo "$msg"
    post_slack "$msg"
    exit "$exit_code"
}
trap on_failure ERR

run_capture() {
    # Runs "$@" and stashes combined output into LAST_ERR for the failure alert
    local tmp
    tmp="$(mktemp)"
    if ! "$@" >"$tmp" 2>&1; then
        LAST_ERR="$(cat "$tmp")"
        cat "$tmp"
        rm -f "$tmp"
        return 1
    fi
    cat "$tmp"
    rm -f "$tmp"
}

# --- Pre-flight: deploy-check must pass ---
STAGE="deploy-check"
echo "[${STAGE}] running…"
run_capture ./deploy-check.sh

# --- Dispatch on mode ---
case "$MODE" in
    sync)
        STAGE="sync"
        echo "[${STAGE}] pulling managed boards…"
        run_capture ./bin/monday-sync.sh
        # Reaching here means run_capture succeeded (failure would have tripped ERR trap)
        write_sync_status true ""
        ;;

    brief)
        STAGE="brief"
        echo "[${STAGE}] generating briefing…"
        BRIEF_FILE="$(mktemp)"
        if ! ./bin/generate-briefing.sh >"$BRIEF_FILE" 2>&1; then
            LAST_ERR="$(cat "$BRIEF_FILE")"
            rm -f "$BRIEF_FILE"
            false  # trip the ERR trap
        fi
        cat "$BRIEF_FILE"

        STAGE="brief-post"
        echo "[${STAGE}] posting briefing to Slack…"
        BRIEF_TEXT="$(cat "$BRIEF_FILE")"
        rm -f "$BRIEF_FILE"
        post_slack "$BRIEF_TEXT"
        ;;

    protocol-refresh)
        STAGE="protocol-refresh"
        echo "[${STAGE}] refreshing protocol-board content…"
        run_capture python3 -m src.protocol_refresh_cli
        ;;

    "")
        STAGE="args"
        LAST_ERR="missing mode arg; expected one of: sync | brief | protocol-refresh"
        echo "ERROR: $LAST_ERR"
        false
        ;;

    *)
        STAGE="args"
        LAST_ERR="unknown mode '$MODE'; expected one of: sync | brief | protocol-refresh"
        echo "ERROR: $LAST_ERR"
        false
        ;;
esac

echo "[${STAGE}] complete — $(date -Iseconds)"
