#!/usr/bin/env bash
# setup-native-mcp.sh — walk Peter through replacing Zapier MCP with native
# MCP servers for the four services Chef depends on (Monday, Gmail, Slack,
# Calendar).
#
# What this script CAN do automatically:
#   - Verify prerequisites (node, npm, python, jq)
#   - Locate or create claude_desktop_config.json
#   - Generate a config snippet to merge into it
#   - Print a verification command per service
#
# What this script CANNOT do (because OAuth requires a browser):
#   - Grant OAuth permissions on your behalf
#   - Install the MCP server packages globally on your Mac (you decide which
#     specific implementation — there are several per service, and they
#     change quarterly)
#   - Edit claude_desktop_config.json with your credentials
#
# So this is a guided checklist, not a one-button install. After running:
#   1. Pick an MCP server implementation per service from docs/connectors.md
#   2. Run the install command they document (npm install -g, pip install, etc.)
#   3. Paste the credentials into the generated snippet
#   4. Merge the snippet into claude_desktop_config.json
#   5. Restart Claude desktop
#   6. Verify with "what MCP tools do you have for <service>?" in a fresh chat

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
SNIPPET_OUT="$REPO_DIR/.mcp-config-snippet.json"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

step() { printf "\n%b▶ %s%b\n" "$BOLD" "$1" "$RESET"; }
ok()   { printf "%b✓%b %s\n" "$GREEN" "$RESET" "$1"; }
warn() { printf "%b⚠%b %s\n" "$YELLOW" "$RESET" "$1"; }
fail() { printf "%b✗%b %s\n" "$RED" "$RESET" "$1"; }

step "1. Prerequisites"
for cmd in node npm python3 jq; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$cmd: $(command -v "$cmd")"
    else
        fail "$cmd not found — install via Homebrew: brew install $cmd"
    fi
done

step "2. Locate Claude desktop config"
if [ ! -d "$CONFIG_DIR" ]; then
    warn "$CONFIG_DIR does not exist — Claude desktop may not be installed."
    warn "Skipping config-file checks; install Claude desktop and re-run."
else
    ok "Config dir: $CONFIG_DIR"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    warn "$CONFIG_FILE does not exist yet. It will be created the first time"
    warn "you add a server below. (Empty config is fine.)"
else
    ok "Config file: $CONFIG_FILE"
    # Validate it parses
    if ! jq empty "$CONFIG_FILE" >/dev/null 2>&1; then
        fail "$CONFIG_FILE is not valid JSON. Fix it before continuing."
        exit 1
    fi
    if jq -e '.mcpServers.zapier // empty' "$CONFIG_FILE" >/dev/null; then
        warn "Zapier MCP server detected in config. After native servers are"
        warn "verified working, remove the 'zapier' entry from mcpServers."
    fi
fi

step "3. Generating config snippet template"
cat > "$SNIPPET_OUT" <<'JSON'
{
  "mcpServers": {
    "_INSTRUCTIONS": "Replace each server block below with the actual command + args from the MCP server you installed. See docs/connectors.md for current options. Delete this _INSTRUCTIONS key after editing.",

    "monday": {
      "command": "npx",
      "args": ["-y", "REPLACE_WITH_MONDAY_MCP_PACKAGE"],
      "env": {
        "MONDAY_API_TOKEN": "REPLACE_WITH_YOUR_TOKEN"
      }
    },

    "google": {
      "command": "npx",
      "args": ["-y", "REPLACE_WITH_GOOGLE_MCP_PACKAGE"],
      "env": {
        "GOOGLE_OAUTH_CREDENTIALS": "REPLACE_WITH_PATH_TO_OAUTH_JSON"
      },
      "comment": "Most Google MCP servers cover Gmail + Calendar + Drive in one OAuth grant"
    },

    "slack": {
      "command": "npx",
      "args": ["-y", "REPLACE_WITH_SLACK_MCP_PACKAGE"],
      "env": {
        "SLACK_BOT_TOKEN": "REPLACE_WITH_YOUR_TOKEN",
        "SLACK_TEAM_ID": "REPLACE_WITH_YOUR_TEAM_ID"
      }
    }
  }
}
JSON
ok "Snippet template written: $SNIPPET_OUT"

step "4. What you need to do next (manual — OAuth requires a browser)"
cat <<EOF
  a. Open docs/connectors.md and pick an MCP server implementation per
     service. Run their install command(s) (typically: npm install -g <pkg>
     or pip install <pkg>).

  b. Edit $SNIPPET_OUT and fill in the REPLACE_* placeholders with the
     actual package name, command, and credentials per server. Delete the
     "_INSTRUCTIONS" key when done.

  c. Merge the edited snippet into:
       $CONFIG_FILE
     If that file doesn't exist, create it with the snippet's content.
     If it has a "mcpServers" key already, add each new server inside it.

  d. Quit and relaunch Claude desktop (Cmd+Q, then reopen).

  e. Open a new chat and ask: "what MCP tools do you have for monday?"
     Then for gmail, slack, calendar. Each should report tools without going
     through Zapier.

  f. Once all four are working, remove the "zapier" entry from $CONFIG_FILE
     and relaunch Claude desktop one more time. Zapier dependency is now
     fully cut.

EOF

step "5. Fallback while you set this up"
cat <<EOF
  If an in-session Chef hits an MCP gap before native servers are wired up,
  run this for an immediate Monday-only unblock:

    ./bin/chef-snapshot-all.sh

  That writes data/snapshots/chef-everything-latest.json with every managed
  + protocol board, fetched via direct Monday API (no MCP, no Zapier).

EOF

ok "Setup walkthrough complete. See docs/connectors.md for full details."
