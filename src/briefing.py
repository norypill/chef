"""Briefing generator: produces structured markdown from snapshots, diffs, and intel files."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_briefing(
    latest_path: str = "data/latest.json",
    diff_path: str = "data/diffs/latest_diff.json",
    intel_dir: str = "intel",
) -> str:
    """
    Generate a PM briefing in markdown.

    Reads:
    - latest.json (current board state)
    - latest_diff.json (what changed since last sync)
    - intel/ directory (team notes, risks, milestone plans)

    Returns markdown string.
    """
    latest = _read_json(latest_path) if Path(latest_path).exists() else {}
    diff = _read_json(diff_path) if Path(diff_path).exists() else {}
    intel = _load_intel(intel_dir)

    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%A, %B %d, %Y — %I:%M %p %Z")

    sections = []
    sections.append(f"# PM Briefing — {date_str}\n")

    # Decisions Needed
    sections.append(_decisions_section(diff, latest))

    # This Week's Priorities
    sections.append(_priorities_section(diff, latest))

    # Team Pulse
    sections.append(_team_pulse_section(diff, latest, intel))

    # Risk Watch
    sections.append(_risk_section(diff, intel))

    # Wins
    sections.append(_wins_section(diff))

    # Peter's Task Board
    sections.append(_peter_tasks_section(diff, latest))

    # Summary stats
    sections.append(_stats_section(diff))

    return "\n".join(s for s in sections if s)


def _decisions_section(diff: dict, latest: dict) -> str:
    """Items that need Peter's direct decision — overdue items assigned to him, stalled blockers."""
    lines = ["## Decisions Needed (Only You Can Do These)\n"]
    changes = diff.get("changes", {})

    # Peter's overdue items
    count = 0
    for item in changes.get("newly_overdue", []):
        if "peter" in item.get("assignee", "").lower():
            count += 1
            lines.append(
                f"{count}. **{item['item']}** — overdue by {item['days_overdue']} day(s) "
                f"(Board: {item['board']})"
            )

    # Stalled items that might need unblocking
    for item in changes.get("stalled", []):
        if item.get("days_stalled", 0) >= 10:
            count += 1
            lines.append(
                f"{count}. **{item['item']}** — stalled {item['days_stalled']} days, "
                f"assigned to {item.get('assignee', 'unassigned')} "
                f"(Board: {item['board']}). May need your input."
            )

    if count == 0:
        lines.append("*No decisions needed right now.*\n")

    return "\n".join(lines) + "\n"


def _priorities_section(diff: dict, latest: dict) -> str:
    """Items due this week, sorted by urgency."""
    lines = ["## This Week's Priorities\n"]
    changes = diff.get("changes", {})

    approaching = sorted(
        changes.get("approaching_deadlines", []),
        key=lambda x: x.get("days_until_due", 99),
    )

    if not approaching:
        lines.append("*No items approaching deadline this week.*\n")
    else:
        for item in approaching[:15]:  # Cap at 15
            days = item["days_until_due"]
            urgency = "**TODAY**" if days == 0 else f"in {days}d"
            lines.append(
                f"- [ ] **{item['item']}** — due {urgency}, "
                f"status: {item.get('status', '?')}, "
                f"assigned: {item.get('assignee', 'unassigned')} "
                f"({item['board']})"
            )

    return "\n".join(lines) + "\n"


def _team_pulse_section(diff: dict, latest: dict, intel: dict) -> str:
    """Group items by team member with status overview."""
    lines = ["## Team Pulse\n"]

    team_notes = intel.get("team-members", "")
    members = _extract_team_members(latest)

    if not members:
        lines.append("*No team member data available yet.*\n")
        return "\n".join(lines) + "\n"

    changes = diff.get("changes", {})

    for member_name, member_items in sorted(members.items()):
        lines.append(f"### {member_name}\n")

        # Count statuses
        done = [i for i in member_items if _is_done(i.get("status", ""))]
        overdue_items = [
            i for i in member_items
            if i.get("date") and _is_overdue(i["date"]) and not _is_done(i.get("status", ""))
        ]
        in_progress = [
            i for i in member_items
            if not _is_done(i.get("status", "")) and i.get("status", "").lower() in
            ("working on it", "in progress", "on it")
        ]

        if in_progress:
            lines.append(f"- On track: {len(in_progress)} item(s) in progress")
        if overdue_items:
            for oi in overdue_items[:5]:
                lines.append(f"- **Overdue**: {oi['name']} (due {oi.get('date', '?')})")

        # Check stalled items for this member
        member_stalled = [
            s for s in changes.get("stalled", [])
            if member_name.lower() in s.get("assignee", "").lower()
        ]
        if member_stalled:
            for ms in member_stalled[:3]:
                lines.append(
                    f"- Stalled: {ms['item']} — no update in {ms['days_stalled']} days"
                )

        if not in_progress and not overdue_items and not member_stalled:
            lines.append(f"- {len(done)} completed, no active items flagged")

        lines.append("")

    return "\n".join(lines) + "\n"


def _risk_section(diff: dict, intel: dict) -> str:
    """Active risks from diff + intel risk register."""
    lines = ["## Risk Watch\n"]
    changes = diff.get("changes", {})

    # Subitem progress risks
    for risk in changes.get("subitem_risks", []):
        lines.append(
            f"- **{risk['item']}** — only {risk['subitems_done']}/{risk['subitems_total']} "
            f"subitems done, {risk['days_until_due']}d until deadline "
            f"({risk.get('assignee', 'unassigned')})"
        )

    # Heavily stalled items
    severe_stalled = [s for s in changes.get("stalled", []) if s.get("days_stalled", 0) >= 10]
    for s in severe_stalled[:5]:
        lines.append(
            f"- {s['item']} — stalled {s['days_stalled']} days ({s.get('assignee', '?')})"
        )

    # Pull from risk register intel file
    risk_register = intel.get("risk-register", "")
    if risk_register:
        lines.append("")
        lines.append("### From Risk Register\n")
        lines.append(risk_register.strip())

    if len(lines) == 1:
        lines.append("*No active risks flagged.*\n")

    return "\n".join(lines) + "\n"


def _wins_section(diff: dict) -> str:
    """Items completed since last sync."""
    lines = ["## Wins Since Last Briefing\n"]
    changes = diff.get("changes", {})

    completed = [
        sc for sc in changes.get("status_changes", [])
        if _is_done(sc.get("to", ""))
    ]

    if not completed:
        lines.append("*No completions since last sync.*\n")
    else:
        for c in completed:
            lines.append(f"- **{c['item']}** — marked {c['to']} ({c['board']})")

    return "\n".join(lines) + "\n"


def _peter_tasks_section(diff: dict, latest: dict) -> str:
    """Peter's personal task board items needing attention."""
    lines = ["## Your Task Board\n"]

    # Find Peter's Tasks board
    peter_board = None
    for board_id, board_data in latest.get("boards", {}).items():
        if "peter" in board_data.get("name", "").lower() and "task" in board_data.get("name", "").lower():
            peter_board = board_data
            break

    if not peter_board:
        lines.append("*Peter's Tasks board not found in latest snapshot.*\n")
        return "\n".join(lines) + "\n"

    attention_items = []
    for item in peter_board.get("items", []):
        if _is_done(item.get("status", "")):
            continue
        date = item.get("date")
        if date and _is_overdue(date):
            from datetime import datetime as dt
            try:
                due = dt.strptime(date.strip(), "%Y-%m-%d")
                days = (dt.now() - due).days
                attention_items.append((days, f"- [ ] **{item['name']}** — overdue by {days} day(s)"))
            except ValueError:
                attention_items.append((0, f"- [ ] **{item['name']}** — overdue"))
        elif date:
            attention_items.append((-1, f"- [ ] **{item['name']}** — due {date}, status: {item.get('status', '?')}"))

    attention_items.sort(key=lambda x: x[0], reverse=True)

    if not attention_items:
        lines.append("*All clear on your board.*\n")
    else:
        count = len(attention_items)
        lines[0] = f"## Your Task Board ({count} item(s) need attention)\n"
        for _, line in attention_items[:10]:
            lines.append(line)

    return "\n".join(lines) + "\n"


def _stats_section(diff: dict) -> str:
    """Summary statistics footer."""
    summary = diff.get("summary", {})
    if not summary:
        return ""

    return (
        "---\n"
        f"*Tracking {summary.get('total_items_tracked', '?')} items | "
        f"{summary.get('overdue_count', 0)} overdue | "
        f"{summary.get('stalled_count', 0)} stalled | "
        f"{summary.get('due_this_week', 0)} due this week | "
        f"{summary.get('completed_since_last', 0)} completed since last sync*\n"
    )


# ---- Helpers ----

def _read_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _load_intel(intel_dir: str) -> dict:
    """Load all .md files from intel/ into a dict keyed by filename (no extension)."""
    intel = {}
    intel_path = Path(intel_dir)
    if not intel_path.exists():
        return intel
    for md_file in intel_path.rglob("*.md"):
        key = md_file.stem
        intel[key] = md_file.read_text()
    return intel


def _extract_team_members(latest: dict) -> dict:
    """Group items by assignee across all boards."""
    members = {}
    for board_data in latest.get("boards", {}).values():
        for item in board_data.get("items", []):
            assignee = item.get("assignee", "").strip()
            if not assignee:
                continue
            members.setdefault(assignee, []).append(item)
    return members


def _is_done(status: str) -> bool:
    return status.lower() in ("done", "complete", "completed", "closed") if status else False


def _is_overdue(date_str: str) -> bool:
    from datetime import datetime as dt
    try:
        due = dt.strptime(date_str.strip(), "%Y-%m-%d")
        return due.date() < dt.now().date()
    except (ValueError, TypeError):
        return False
