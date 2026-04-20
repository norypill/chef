# NORY Chef — Peter's Chief of Staff

**Chef** is Peter's unified **Chief of Staff + Project Manager + Executive Coach**.

This repo is Chef's operational spine: it syncs Monday.com boards, tracks changes over time, maintains institutional intelligence on the team and milestones, and generates daily briefings that tell Peter exactly what decisions he needs to make — and nothing else.

> **Core principle**: Chef does the work. Peter only decides what requires his brain.

See **[intel/chef.md](intel/chef.md)** for the full persona definition.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy config and add your boards:
   ```bash
   cp config.example.yaml config.yaml
   ```

3. Set your Monday.com API token:
   ```bash
   export MONDAY_API_TOKEN="your_token_here"
   ```

## Usage

### Sync Monday.com boards
```bash
./bin/monday-sync.sh
```
Pulls all tracked boards, saves a timestamped snapshot to `data/snapshots/`, rotates `latest.json`/`previous.json`, and computes a diff.

### Generate a briefing
```bash
./bin/generate-briefing.sh
```
Reads latest snapshot, diff, and intel files to produce Chef's briefing in markdown on stdout.

### Cron (8 AM and 4 PM ET)
```
0 8,16 * * * cd ~/pm && MONDAY_API_TOKEN="..." ./bin/monday-sync.sh >> logs/sync.log 2>&1
```

## Project Structure

```
bin/                     Shell entrypoints (sync, briefing)
src/                     Python modules (API client, sync, diff, briefing)
data/snapshots/          Timestamped JSON snapshots
data/diffs/              Computed diffs between snapshots
intel/                   Chef's institutional knowledge
config.example.yaml      Board config template
```

## Intelligence Files

The `intel/` directory contains Chef's manually maintained context:

- **`chef.md`** — Chef's persona, operating rules, escalation, and voice
- `operating-mode.md` — Legacy quick-ref (superseded by chef.md)
- `team-members.md` — Roster with coaching context per person
- `risk-register.md` — Active risks
- `milestone-plans/` — Per-program plans (NYC summer, Boston summer, etc.)

## Architecture

This repo hosts **two delivery channels** for the Chef persona — they coexist and share a single source of truth:

- **`skills/chef/`** — Cowork-installable skill bundled into `chef.skill` by `package.sh`. Contains `SKILL.md` (entry point) and `tasks/` (playbooks like `bow-entry.md`). This is what gets installed on Peter's Mac via Cowork.
- **`src/` + `bin/`** — Standalone Python PM Intelligence tool. Syncs Monday.com boards, computes diffs, generates briefings. Runs on cron, independent of Cowork.

**`intel/chef.md` is the canonical persona doctrine.** Both channels derive from it. When the persona changes, update `intel/chef.md` first, then reconcile `skills/chef/SKILL.md` and any Python-tool copy that references it.

## Install the Cowork skill on a new Mac

```bash
curl -fsSL https://raw.githubusercontent.com/norypill/chef/main/install.sh | bash
```

This clones the repo to `~/chef` (or `$CHEF_DIR`), builds `chef.skill` from `skills/chef/`, and opens it so Cowork can install it. The Python tool under `src/` and `bin/` is left untouched — install it separately if needed (see Setup above).

## Update the Cowork skill

```bash
cd ~/chef && git pull && bash package.sh && open chef.skill
```

Pulls latest, rebuilds the bundle, and re-opens it in Cowork to pick up the new version.
