# NORY PM Intelligence — Chef

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
