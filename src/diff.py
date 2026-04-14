"""Snapshot diffing engine: compares two Monday.com snapshots and reports changes."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def compute_diff(previous: dict, current: dict, config: dict) -> dict:
    """
    Compare two snapshots and produce a structured diff.

    Detects:
    - New items
    - Status changes
    - Date changes
    - Newly overdue items
    - Stalled items (no update in N days)
    - Approaching deadlines
    """
    now = datetime.now(timezone.utc).astimezone()
    stalled_days = config["sync"].get("stalled_threshold_days", 5)
    approaching_days = config["sync"].get("approaching_deadline_days", 7)

    prev_items = _index_items(previous)
    curr_items = _index_items(current)

    new_items = []
    status_changes = []
    date_changes = []
    newly_overdue = []
    stalled = []
    approaching_deadlines = []

    completed_count = 0

    for item_key, curr in curr_items.items():
        prev = prev_items.get(item_key)

        # New item
        if prev is None:
            new_items.append({
                "board": curr["_board_name"],
                "item": curr["name"],
                "group": curr.get("group", ""),
                "assignee": curr.get("assignee", ""),
                "status": curr.get("status", ""),
            })
            continue

        # Status change
        if curr.get("status") != prev.get("status"):
            status_changes.append({
                "board": curr["_board_name"],
                "item": curr["name"],
                "from": prev.get("status", ""),
                "to": curr.get("status", ""),
                "assignee": curr.get("assignee", ""),
            })
            if _is_done(curr.get("status", "")):
                completed_count += 1

        # Date change
        if curr.get("date") and curr.get("date") != prev.get("date"):
            date_changes.append({
                "board": curr["_board_name"],
                "item": curr["name"],
                "from_date": prev.get("date"),
                "to_date": curr.get("date"),
                "assignee": curr.get("assignee", ""),
            })

    # Overdue, stalled, and approaching — scan ALL current items
    for item_key, curr in curr_items.items():
        status = curr.get("status", "")
        if _is_done(status):
            continue

        due_date = _parse_date(curr.get("date"))
        last_updated = _parse_datetime(curr.get("last_updated"))

        # Overdue
        if due_date and due_date.date() < now.date():
            days_overdue = (now.date() - due_date.date()).days
            # Only report if it wasn't already overdue in previous snapshot
            prev = prev_items.get(item_key)
            prev_due = _parse_date(prev.get("date")) if prev else None
            was_already_overdue = prev_due and prev_due.date() < _parse_datetime(
                previous.get("timestamp", now.isoformat())
            ).date() if prev else False

            if not was_already_overdue:
                newly_overdue.append({
                    "board": curr["_board_name"],
                    "item": curr["name"],
                    "due_date": curr["date"],
                    "days_overdue": days_overdue,
                    "assignee": curr.get("assignee", ""),
                })

        # Stalled
        if last_updated:
            days_since_update = (now - last_updated).days
            if days_since_update >= stalled_days:
                stalled.append({
                    "board": curr["_board_name"],
                    "item": curr["name"],
                    "last_updated": curr.get("last_updated", ""),
                    "days_stalled": days_since_update,
                    "assignee": curr.get("assignee", ""),
                })

        # Approaching deadline
        if due_date and due_date.date() >= now.date():
            days_until = (due_date.date() - now.date()).days
            if days_until <= approaching_days:
                approaching_deadlines.append({
                    "board": curr["_board_name"],
                    "item": curr["name"],
                    "due_date": curr["date"],
                    "days_until_due": days_until,
                    "status": status,
                    "assignee": curr.get("assignee", ""),
                })

    # Subitem progress flags
    subitem_risks = _check_subitem_progress(curr_items, now, approaching_days)

    # Summary
    all_overdue = [
        curr for curr in curr_items.values()
        if not _is_done(curr.get("status", ""))
        and _parse_date(curr.get("date"))
        and _parse_date(curr.get("date")).date() < now.date()
    ]

    due_this_week = [
        curr for curr in curr_items.values()
        if not _is_done(curr.get("status", ""))
        and _parse_date(curr.get("date"))
        and 0 <= (_parse_date(curr.get("date")).date() - now.date()).days <= 7
    ]

    return {
        "timestamp": now.isoformat(),
        "compared_to": previous.get("timestamp", ""),
        "changes": {
            "new_items": new_items,
            "status_changes": status_changes,
            "date_changes": date_changes,
            "newly_overdue": newly_overdue,
            "stalled": stalled,
            "approaching_deadlines": approaching_deadlines,
            "subitem_risks": subitem_risks,
        },
        "summary": {
            "total_items_tracked": len(curr_items),
            "overdue_count": len(all_overdue),
            "stalled_count": len(stalled),
            "due_this_week": len(due_this_week),
            "completed_since_last": completed_count,
        },
    }


def _index_items(snapshot: dict) -> dict:
    """Build a flat dict of board_id:item_id -> item for quick lookup."""
    index = {}
    for board_id, board_data in snapshot.get("boards", {}).items():
        board_name = board_data.get("name", board_id)
        for item in board_data.get("items", []):
            key = f"{board_id}:{item['id']}"
            item_copy = dict(item)
            item_copy["_board_name"] = board_name
            item_copy["_board_id"] = board_id
            index[key] = item_copy
    return index


def _is_done(status: str) -> bool:
    """Check if a status label means the item is completed."""
    return status.lower() in ("done", "complete", "completed", "closed") if status else False


def _parse_date(val) -> datetime | None:
    """Try to parse a date string (YYYY-MM-DD or ISO)."""
    if not val:
        return None
    try:
        if "T" in str(val):
            return datetime.fromisoformat(str(val))
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return None


def _parse_datetime(val) -> datetime | None:
    """Parse an ISO datetime string."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _check_subitem_progress(items: dict, now: datetime, approaching_days: int) -> list:
    """Flag parent items where subitem completion rate is low relative to deadline."""
    risks = []
    for item in items.values():
        subitems = item.get("subitems", [])
        if len(subitems) < 2:
            continue

        due_date = _parse_date(item.get("date"))
        if not due_date:
            continue

        days_left = (due_date.date() - now.date()).days
        if days_left > approaching_days or days_left < 0:
            continue

        done_count = 0
        for si in subitems:
            cols = si.get("columns", {})
            for col_data in cols.values():
                text = col_data.get("text", "").lower() if isinstance(col_data, dict) else ""
                if text in ("done", "complete", "completed"):
                    done_count += 1
                    break

        completion_pct = done_count / len(subitems) if subitems else 0
        if completion_pct < 0.5 and days_left <= 3:
            risks.append({
                "board": item.get("_board_name", ""),
                "item": item["name"],
                "subitems_total": len(subitems),
                "subitems_done": done_count,
                "days_until_due": days_left,
                "assignee": item.get("assignee", ""),
            })

    return risks
