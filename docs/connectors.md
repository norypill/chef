# Connectors — How Chef talks to the outside world

Chef needs read/write access to four services to run the BOW playbook end-to-end:

| Service | What Chef does there | BOW step |
|---|---|---|
| **Monday.com** | Pull task/milestone state, post weekly entry | 2, 3, 4, 5, 7, 10 |
| **Gmail** | 10-day digest, draft replies | 6 |
| **Slack** | 10-day digest (dynamic channels), DM Peter the brief | 6 |
| **Google Calendar** | PTO/holiday pre-flight, capacity check | 1, 8 |

There are three ways to wire each service into an in-session Chef. **Native MCP is the recommended path.** Zapier should be a last resort, not the default.

---

## Why not Zapier

Zapier MCP is convenient (one auth flow for everything) but in practice it has been the binding constraint:

- Per-tool approval gates that reset mid-session, breaking long-running playbooks like BOW
- Single point of failure — when Zapier hiccups, every connector goes down at once
- Adds latency (extra hop) and ongoing subscription cost
- Approval scopes have to be re-granted whenever Zapier's UI changes

The cron toolchain in `src/` proves you don't need Zapier for Monday — `monday_client.py` calls Monday's GraphQL API directly with a personal token. The same pattern (direct HTTP / native MCP) works for the other three services.

---

## Recommended setup: native MCP servers

Native MCP servers run locally and connect each service directly. One-time setup per service, but no third-party hop and no shared failure mode.

The ecosystem for these is moving fast. The canonical sources to check for current install commands are:

- **Anthropic's reference servers** — `github.com/modelcontextprotocol/servers` (official + community-maintained adapters; check the README for what's currently shipped)
- **Each vendor's own developer docs** — Monday, Google, Slack all publish their own MCP integrations as they ship them; their docs are the source of truth for auth setup
- **`smithery.ai` / `mcp.so`** — community MCP server registries

For each service, the install pattern looks roughly like:

1. Install the MCP server (npm package, pip install, or standalone binary)
2. Configure auth (OAuth flow, API token, or service-account JSON depending on vendor)
3. Add the server to `~/Library/Application Support/Claude/claude_desktop_config.json` under `mcpServers`
4. Restart Claude desktop

After each new server is added, verify with: in a fresh Claude desktop chat, ask "what MCP tools do you have for <service>?" — you should see the relevant tools listed without going through Zapier.

### Suggested install order

1. **Monday first** — it's the most-used service in BOW (touched in 6 of 10 steps). Highest leverage from removing the Zapier dependency.
2. **Google Calendar second** — needed for step 1 pre-flight. Native Google MCP servers handle Calendar + Gmail together via the same OAuth grant, so this often gets you Gmail at the same time.
3. **Slack last** — most flexible (Slack also has a webhook path that already works for the cron's brief-posting; in-session reads are the only piece needing MCP).

---

## Fallback: the snapshot bridge

For the case where the in-session Chef hits a connector failure mid-BOW (Zapier approval gate, MCP server not yet installed for a service, network hiccup), there's a no-MCP-required escape hatch:

```bash
./bin/chef-snapshot-for-session.sh
```

This runs `src/bow_snapshot_cli.py`, which uses the same direct Monday API path the cron uses, fetches the 4 BOW-primary boards, and writes the result to `data/snapshots/bow-primary-latest.json`. Then tell the in-session Chef:

> "Read `data/snapshots/bow-primary-latest.json` and continue the BOW playbook."

Chef now has authoritative state for steps 3, 4, 5, and 8 with zero Zapier involvement.

This is **not** a substitute for native MCP — it only covers Monday, and it's a manual step. But it unblocks BOW immediately when something else is broken.

---

## What still requires manual handoff today

Even with native MCP installed for everything, two BOW steps will likely remain partially manual until Anthropic or the relevant vendor closes the gap:

- **Step 6 dynamic Slack channel selection** — needs read access to channel listings; some Slack MCP servers limit this depending on the app's OAuth scopes
- **Step 10 board writes** — explicit approval is required by the playbook anyway; the constraint is intentional, not a tooling gap

Document any new failure modes you discover in this file so future Chef runs can avoid the same trap.
