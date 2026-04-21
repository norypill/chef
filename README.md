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

Running `bash package.sh` now auto-syncs `SKILL.md` with `intel/chef.md`. Single source of truth for Chef's persona is `intel/chef.md` — edit there, rebuild, `SKILL.md` regenerates automatically. The build also validates YAML frontmatter and enforces a 200-line cap on `SKILL.md` so the Cowork entry point stays concise.

## Cron Setup

Chef runs on Peter's Mac via `bin/chef-cron.sh`, which dispatches on a positional arg (`sync` | `brief` | `protocol-refresh`). Every run is gated by `deploy-check.sh` first — if the repo is dirty, off `main`, out of sync with `origin/main`, missing env vars, or missing `config.yaml`, the run aborts and posts a red-line alert to Slack.

### 1. Environment (`.env` at repo root)

Create `~/chef/.env` (not committed — covered by `.gitignore`):

```bash
MONDAY_API_TOKEN=your_monday_personal_token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

`bin/chef-cron.sh` sources this file with `set -a` so both vars are auto-exported to every child process.

### 2. Crontab entries

Run `crontab -e` and add exactly these four lines:

```
45 5 * * 1-5 /Users/nory/chef/bin/chef-cron.sh sync
0 6 * * 1-5 /Users/nory/chef/bin/chef-cron.sh brief
0 9,11,13,15,17,19 * * 1-5 /Users/nory/chef/bin/chef-cron.sh sync
0 23 * * 0 /Users/nory/chef/bin/chef-cron.sh protocol-refresh
```

Schedule rationale:
- 05:45 Mon–Fri: pre-briefing sync to pull fresh board state
- 06:00 Mon–Fri: generate briefing and post to Slack
- 09:00/11:00/13:00/15:00/17:00/19:00 Mon–Fri: hourly-ish resyncs during the workday
- 23:00 Sunday: full protocol-board content refresh for the week ahead

### 3. Manual testing

Run any mode on-demand from the repo root:

```bash
./bin/chef-cron.sh brief
```

Because `deploy-check.sh` requires `branch=main` and a clean tree, feature branches will not pass. Merge (or check out `main`) before testing end-to-end. Logs land in `logs/cron-YYYY-MM-DD.log`, each run header stamped with the current commit SHA.

### 4. Pausing cron

Open the crontab and comment out the lines:

```bash
crontab -e
# prefix each chef line with # to pause, save and quit
```

Uncomment when ready to resume. `crontab -l` confirms active entries.
