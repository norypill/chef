# PM Intelligence Tool

Local toolset that syncs Monday.com boards, tracks diffs over time, maintains project intelligence, and generates PM briefings.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy config and add your boards:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
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
Reads latest snapshot, diff, and intel files to produce a structured markdown briefing on stdout.

### Cron setup (8 AM and 4 PM ET)
```
0 8,16 * * * cd ~/Projects/pill-pm && MONDAY_API_TOKEN="..." ./bin/monday-sync.sh >> logs/sync.log 2>&1
```

## Project Structure

```
bin/                    Shell entrypoints (sync, briefing)
src/                    Python modules (API client, sync, diff, briefing)
data/snapshots/         Timestamped JSON snapshots
data/diffs/             Computed diffs between snapshots
intel/                  Team roster, risk register, milestone plans
config.example.yaml     Board config template
```

## Intelligence Files

The `intel/` directory contains manually maintained context:
- `team-members.md` — Team roster, capacity, working style notes
- `risk-register.md` — Active risks being watched
- `milestone-plans/` — Reverse-engineered plans per milestone
