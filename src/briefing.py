"""
Briefing generator — Chef's daily brief format.

Chef is Peter's unified Chief of Staff + Project Manager + Executive Coach.
Philosophy: Chef does the heavy lifting. Peter only reviews, approves, or makes
decisions that genuinely require him. Every item comes with what Chef already did
or will do, and what Peter's ONE action is.

See intel/chef.md for the full persona definition.
"""
from __future__ import annotations


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
    latest = _read_json(latest_path) if Path(latest_path).exists() else {}
    diff = _read_json(diff_path) if Path(diff_path).exists() else {}
    intel = _load_intel(intel_dir)

    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%A, %B %d, %Y — %I:%M %p")

    sections = []
    sections.append(f"# Daily Brief — {date_str}\n")

    # What Chef already handled
    sections.append(_already_handled_section(diff))

    # Approve / Decide (bare minimum Peter actions)
    sections.append(_approve_decide_section(diff, latest))

    # Today's Play (2-3 things max, pre-broken-down)
    sections.append(_todays_play_section(diff, latest))

    # Team: What Chef is managing for you
    sections.append(_team_management_section(diff, latest, intel))

    # Coaching moment
    sections.append(_coaching_section(diff, latest, intel))

    # Wins (keep momentum)
    sections.append(_wins_section(diff))

    # Dashboard
    sections.append(_dashboard_section(diff))

    return "\n".join(s for s in sections if s)


def _already_handled_section(diff: dict) -> str:
    """Show Peter what Chef already took care of — builds trust and reduces his load."""
    lines = ["## Already Handled For You\n"]
    changes = diff.get("changes", {})
    handled = []

    # If the last sync failed, warn loudly before anything else in this section
    status = _read_sync_status()
    if status is not None and not status.get("ok", True):
        reason = status.get("reason") or "unknown reason"
        ts = status.get("ts") or "unknown time"
        short_reason = (reason[:200].rstrip() + "…") if len(reason) > 200 else reason
        handled.append(
            f"⚠ Last sync failed at {ts} — data may be stale. "
            f"Reason: {short_reason}. Brief may be incomplete."
        )

    # Tracked all boards
    summary = diff.get("summary", {})
    if summary.get("total_items_tracked", 0) > 0:
        handled.append(
            f"Synced and analyzed {summary['total_items_tracked']} items across all boards"
        )

    # Flagged stalled items
    stalled = changes.get("stalled", [])
    if stalled:
        non_peter = [s for s in stalled if "peter" not in s.get("assignee", "").lower()]
        if non_peter:
            handled.append(
                f"Identified {len(non_peter)} stalled item(s) on team boards — "
                f"follow-up messages drafted below"
            )

    # Spotted date changes
    date_changes = changes.get("date_changes", [])
    if date_changes:
        handled.append(
            f"Caught {len(date_changes)} deadline shift(s) — reviewed for impact"
        )

    # Subitem risks
    sub_risks = changes.get("subitem_risks", [])
    if sub_risks:
        handled.append(
            f"Flagged {len(sub_risks)} item(s) where subitem progress is behind schedule"
        )

    # Approaching deadlines triaged
    approaching = changes.get("approaching_deadlines", [])
    if approaching:
        handled.append(
            f"Triaged {len(approaching)} upcoming deadline(s) — prioritized below"
        )

    if not handled:
        handled.append("Ran full board sync — no changes detected since last check")

    for h in handled:
        lines.append(f"- {h}")

    return "\n".join(lines) + "\n"


def _approve_decide_section(diff: dict, latest: dict) -> str:
    """Only things that REQUIRE Peter's brain. Pre-framed as approve/reject/pick-one."""
    lines = ["## Your Call (Need Your Decision)\n"]
    changes = diff.get("changes", {})
    count = 0

    # Severely stalled items — need Peter to unblock
    for item in changes.get("stalled", []):
        if item.get("days_stalled", 0) >= 10:
            count += 1
            assignee = item.get("assignee", "unassigned")
            is_peters = "peter" in assignee.lower()
            lines.append(f"### {count}. {item['item']}")
            lines.append(f"**Stalled {item['days_stalled']} days** — {'yours' if is_peters else f'assigned to {assignee}'}")
            if is_peters:
                lines.append(f"- **Option A**: I'll break it into steps and schedule 15 min for you tomorrow")
                lines.append(f"- **Option B**: Delegate — tell me to whom")
                lines.append(f"- **Option C**: Kill it (it's not happening)")
            else:
                first_name = assignee.split()[0] if assignee != "unassigned" else "the team"
                lines.append(f"- **Option A**: I'll message {first_name} for a status update")
                lines.append(f"- **Option B**: Deprioritize / push deadline")
                lines.append(f"- **Option C**: You handle directly")
            lines.append(f"- *Just reply A, B, or C*\n")

    # Peter's own overdue items
    for item in changes.get("newly_overdue", []):
        if "peter" in item.get("assignee", "").lower():
            count += 1
            lines.append(f"### {count}. {item['item']}")
            lines.append(f"**Overdue by {item['days_overdue']} day(s)**")
            lines.append(f"- **Option A**: I'll reschedule to this week and break it into steps for you")
            lines.append(f"- **Option B**: Delegate — tell me to whom")
            lines.append(f"- **Option C**: Kill it (not worth doing)")
            lines.append(f"- *Just reply A, B, or C*\n")

    if count == 0:
        lines.append("Nothing needs your decision right now. You're clear.\n")

    return "\n".join(lines) + "\n"


def _todays_play_section(diff: dict, latest: dict) -> str:
    """Max 3 items. Pre-broken into tiny steps. Peter just executes."""
    lines = ["## Today's Play (Your 3 Moves)\n"]
    changes = diff.get("changes", {})

    # Collect candidates: approaching deadlines assigned to Peter, then highest urgency
    peter_urgent = []
    for item in changes.get("approaching_deadlines", []):
        if "peter" in item.get("assignee", "").lower():
            peter_urgent.append(item)

    # Also add Peter's overdue
    for item in _get_all_overdue(latest, "peter"):
        peter_urgent.append({
            "item": item["name"],
            "days_until_due": -(datetime.now(timezone.utc).astimezone().date() - _parse_date_safe(item.get("date")).date()).days if _parse_date_safe(item.get("date")) else -99,
            "status": item.get("status", ""),
            "board": "Peter's Tasks",
            "assignee": "Peter",
        })

    # Sort: most urgent first
    peter_urgent.sort(key=lambda x: x.get("days_until_due", 99))

    # Also include team items Peter needs to review
    team_approaching = [
        item for item in changes.get("approaching_deadlines", [])
        if "peter" not in item.get("assignee", "").lower()
        and item.get("days_until_due", 99) <= 2
    ]

    plays = []
    seen = set()

    for item in peter_urgent[:2]:
        name = item["item"]
        if name in seen:
            continue
        seen.add(name)
        days = item.get("days_until_due", 0)
        if days < 0:
            timing = f"overdue by {abs(days)}d"
        elif days == 0:
            timing = "due TODAY"
        else:
            timing = f"due in {days}d"

        plays.append({
            "name": name,
            "timing": timing,
            "status": item.get("status", "?"),
            "type": "yours",
        })

    for item in team_approaching[:1]:
        name = item["item"]
        if name in seen:
            continue
        seen.add(name)
        plays.append({
            "name": name,
            "timing": f"due in {item['days_until_due']}d",
            "status": item.get("status", "?"),
            "type": "review",
            "assignee": item.get("assignee", "?"),
        })

    if not plays:
        lines.append("No fires today. Use this time for deep work or strategic thinking.\n")
    else:
        for i, play in enumerate(plays[:3], 1):
            lines.append(f"**{i}. {play['name']}** ({play['timing']})")
            if play["type"] == "yours":
                lines.append(f"   - Current status: {play['status']}")
                lines.append(f"   - **Your step**: Open this item and spend 15 min moving it forward")
                lines.append(f"   - I'll update the board once you tell me what you did")
            else:
                lines.append(f"   - Assigned to: {play.get('assignee', '?')}")
                lines.append(f"   - **Your step**: Quick check-in — ask for a 1-line status update")
                lines.append(f"   - I'll follow up if no response by EOD")
            lines.append("")

    return "\n".join(lines) + "\n"


def _team_management_section(diff: dict, latest: dict, intel: dict) -> str:
    """What Chef is actively managing — Peter only intervenes if flagged."""
    lines = ["## Team (What I'm Managing For You)\n"]
    changes = diff.get("changes", {})
    members = _extract_team_members(latest)

    if not members:
        lines.append("*No team data yet — will populate after first full sync.*\n")
        return "\n".join(lines) + "\n"

    for member_name, member_items in sorted(members.items()):
        if "peter" in member_name.lower():
            continue  # Peter's items are in Today's Play

        active = [i for i in member_items if not _is_done(i.get("status", ""))]
        overdue = [
            i for i in member_items
            if i.get("date") and _is_overdue(i["date"]) and not _is_done(i.get("status", ""))
        ]
        stalled_items = [
            s for s in changes.get("stalled", [])
            if member_name.lower() in s.get("assignee", "").lower()
        ]

        first_name = member_name.split()[0]
        lines.append(f"### {member_name}")

        if not overdue and not stalled_items:
            lines.append(f"- **Status**: On track ({len(active)} active items)")
            lines.append(f"- **Your action**: None needed")
        else:
            if overdue:
                lines.append(f"- **{len(overdue)} overdue item(s)**:")
                for oi in overdue[:3]:
                    lines.append(f"  - {oi['name']} (due {oi.get('date', '?')})")
                lines.append(f"- **I'll do**: Message {first_name} for status + revised timeline")

            if stalled_items:
                lines.append(f"- **{len(stalled_items)} stalled item(s)**:")
                for si in stalled_items[:3]:
                    lines.append(f"  - {si['item']} — {si['days_stalled']}d without update")
                lines.append(f"- **I'll do**: Check in with {first_name}, escalate to you only if blocked")

            if overdue or stalled_items:
                lines.append(f"- **Your action**: None unless I escalate")

        lines.append("")

    return "\n".join(lines) + "\n"


def _coaching_section(diff: dict, latest: dict, intel: dict) -> str:
    """One clear exec coaching insight per briefing. Honest, actionable, specific."""
    lines = ["## Coaching Corner\n"]
    changes = diff.get("changes", {})
    summary = diff.get("summary", {})

    observations = []

    # Pattern: too many overdue items
    overdue_count = summary.get("overdue_count", 0)
    if overdue_count >= 5:
        observations.append(
            f"You have {overdue_count} overdue items across boards. "
            f"That's not a time problem — it's a saying-yes problem. "
            f"Pick 3 to actually do this week. Kill or delegate the rest. "
            f"I can draft the delegation messages."
        )

    # Pattern: stalled items piling up
    stalled_count = summary.get("stalled_count", 0)
    if stalled_count >= 5:
        observations.append(
            f"{stalled_count} items are stalled. When things stall, it usually means "
            f"the owner is unclear on what 'done' looks like, or they're waiting on "
            f"something they haven't asked for. I'll audit each one and bring you "
            f"the real blockers."
        )

    # Pattern: lots completed — acknowledge
    completed = summary.get("completed_since_last", 0)
    if completed >= 3:
        observations.append(
            f"{completed} items completed since last sync. That's momentum. "
            f"Protect it — don't add new commitments today. "
            f"Let the team finish what they started."
        )

    # Pattern: approaching deadlines with Not Started status
    not_started_approaching = [
        a for a in changes.get("approaching_deadlines", [])
        if a.get("status", "").lower() in ("not started", "", "stuck")
        and a.get("days_until_due", 99) <= 3
    ]
    if not_started_approaching:
        names = [a["item"] for a in not_started_approaching[:3]]
        observations.append(
            f"{len(not_started_approaching)} item(s) due within 3 days haven't been started: "
            f"{', '.join(names)}. "
            f"Be honest — are these actually going to happen? "
            f"If not, reschedule now rather than letting them become overdue. "
            f"I can move them."
        )

    # Default coaching
    if not observations:
        observations.append(
            "Boards look healthy. Use today to think about what's NOT on the board "
            "but should be. The biggest risks are usually the ones nobody tracked."
        )

    # Pick the most impactful one (first match is prioritized)
    lines.append(f"> {observations[0]}")

    return "\n".join(lines) + "\n"


def _wins_section(diff: dict) -> str:
    """Quick celebration — keep morale up."""
    lines = ["## Wins\n"]
    changes = diff.get("changes", {})

    completed = [
        sc for sc in changes.get("status_changes", [])
        if _is_done(sc.get("to", ""))
    ]

    if not completed:
        lines.append("*No completions since last sync.*\n")
    else:
        for c in completed:
            assignee_note = f" ({c.get('assignee', '')})" if c.get("assignee") else ""
            lines.append(f"- **{c['item']}** — done{assignee_note}")

    return "\n".join(lines) + "\n"


def _dashboard_section(diff: dict) -> str:
    """Quick numbers."""
    summary = diff.get("summary", {})
    if not summary:
        return ""

    return (
        "---\n"
        f"**Dashboard**: {summary.get('total_items_tracked', '?')} tracked | "
        f"{summary.get('overdue_count', 0)} overdue | "
        f"{summary.get('stalled_count', 0)} stalled | "
        f"{summary.get('due_this_week', 0)} due this week | "
        f"{summary.get('completed_since_last', 0)} shipped\n"
        "\n— Chef\n"
    )


# ---- Helpers ----

def _read_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _read_sync_status(path: str = "data/sync-status.json") -> dict | None:
    """Return the last sync status dict, or None if the file is missing/invalid.
    Written by bin/chef-cron.sh on every sync run so the brief can flag staleness."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return _read_json(str(p))
    except (json.JSONDecodeError, OSError):
        return None


def _load_intel(intel_dir: str) -> dict:
    intel = {}
    intel_path = Path(intel_dir)
    if not intel_path.exists():
        return intel
    for md_file in intel_path.rglob("*.md"):
        key = md_file.stem
        intel[key] = md_file.read_text()
    return intel


def _extract_team_members(latest: dict) -> dict:
    members = {}
    for board_data in latest.get("boards", {}).values():
        for item in board_data.get("items", []):
            assignee = item.get("assignee", "").strip()
            if not assignee:
                continue
            members.setdefault(assignee, []).append(item)
    return members


def _get_all_overdue(latest: dict, name_filter: str) -> list:
    results = []
    for board_data in latest.get("boards", {}).values():
        for item in board_data.get("items", []):
            if name_filter.lower() not in item.get("assignee", "").lower():
                continue
            if _is_done(item.get("status", "")):
                continue
            if item.get("date") and _is_overdue(item["date"]):
                results.append(item)
    return results


def _parse_date_safe(val) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_done(status: str) -> bool:
    return status.lower() in ("done", "complete", "completed", "closed") if status else False


def _is_overdue(date_str: str) -> bool:
    try:
        due = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return due.date() < datetime.now().date()
    except (ValueError, TypeError):
        return False
