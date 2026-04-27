"""Monday.com GraphQL API client with pagination and rate limiting."""
from __future__ import annotations


import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)


class BoardNotAccessibleError(Exception):
    """Raised when a board exists in config but Monday returns no rows for it
    (archived, deleted, or permissions revoked)."""

BOARD_QUERY = """
query ($boardId: [ID!]!) {
  boards(ids: $boardId) {
    name
    groups { id title }
    columns { id title type settings_str }
    items_page(limit: 500) {
      cursor
      items {
        id
        name
        group { id title }
        created_at
        updated_at
        column_values {
          id
          text
          value
          type
        }
        subitems {
          id
          name
          column_values {
            id
            text
            value
            type
          }
        }
      }
    }
  }
}
"""

PAGINATION_QUERY = """
query ($boardId: [ID!]!, $cursor: String!) {
  boards(ids: $boardId) {
    items_page(limit: 500, cursor: $cursor) {
      cursor
      items {
        id
        name
        group { id title }
        created_at
        updated_at
        column_values {
          id
          text
          value
          type
        }
        subitems {
          id
          name
          column_values {
            id
            text
            value
            type
          }
        }
      }
    }
  }
}
"""

BOARDS_LIST_QUERY = """
query ($page: Int!, $limit: Int!) {
  boards(page: $page, limit: $limit) {
    id
    name
    state
  }
}
"""


class MondayClient:
    """Wraps the Monday.com GraphQL API with pagination and status label resolution."""

    def __init__(self, config: dict):
        self.api_url = config["monday"]["api_url"]
        token_env = config["monday"]["token_env"]
        self.token = os.environ.get(token_env)
        if not self.token:
            raise RuntimeError(
                f"Monday.com API token not found in environment variable '{token_env}'. "
                f"Set it with: export {token_env}=your_token"
            )
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }
        self._delay = 1.0  # seconds between board fetches for rate limiting
        # Big boards (5k+ items) can take >30s for the first GraphQL response;
        # default to 90s and allow override via config.yaml -> monday.request_timeout
        monday_cfg = config.get("monday", {}) or {}
        self._request_timeout = int(monday_cfg.get("request_timeout", 90))
        self._max_attempts = int(monday_cfg.get("max_attempts", 2))

    def _execute(self, query: str, variables: dict) -> dict:
        """Execute a GraphQL query against Monday.com.

        Retries once on ReadTimeout — Monday's GraphQL is occasionally slow on
        boards with thousands of items. Other failures bubble up immediately.
        """
        payload = json.dumps({"query": query, "variables": variables})
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = requests.post(
                    self.api_url,
                    headers=self.headers,
                    data=payload,
                    timeout=self._request_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if "errors" in data:
                    raise RuntimeError(f"Monday.com API errors: {data['errors']}")
                return data["data"]
            except requests.exceptions.ReadTimeout as e:
                last_exc = e
                if attempt < self._max_attempts:
                    backoff = 2.0 * attempt
                    logger.warning(
                        "Monday read timeout (attempt %d/%d) — retrying after %.1fs",
                        attempt, self._max_attempts, backoff,
                    )
                    time.sleep(backoff)
                else:
                    raise
        # Unreachable — loop either returns or raises
        raise last_exc  # type: ignore[misc]

    def fetch_board(self, board_id: int) -> dict:
        """Fetch a complete board including all items with cursor-based pagination."""
        logger.info("Fetching board %s", board_id)
        data = self._execute(BOARD_QUERY, {"boardId": [str(board_id)]})
        boards_list = data.get("boards") or []
        if not boards_list:
            raise BoardNotAccessibleError(
                f"Board {board_id} returned no data — likely archived, deleted, "
                f"or revoked permissions"
            )
        board = boards_list[0]

        # Build column settings lookup for status label resolution
        column_settings = {}
        for col in board.get("columns", []):
            column_settings[col["id"]] = col

        # Collect all items across pages
        items_page = board["items_page"]
        all_items = list(items_page["items"])
        cursor = items_page["cursor"]

        while cursor:
            logger.info("  Paginating board %s (fetched %d items so far)", board_id, len(all_items))
            page_data = self._execute(
                PAGINATION_QUERY,
                {"boardId": [str(board_id)], "cursor": cursor},
            )
            page = page_data["boards"][0]["items_page"]
            all_items.extend(page["items"])
            cursor = page["cursor"]

        # Resolve status labels
        resolved_items = [
            self._resolve_item(item, column_settings) for item in all_items
        ]

        return {
            "name": board["name"],
            "groups": board.get("groups", []),
            "columns": board.get("columns", []),
            "items": resolved_items,
        }

    def fetch_all_boards(self, board_configs: list[dict]) -> dict:
        """Fetch all configured boards with a delay between each to respect rate limits."""
        boards = {}
        for i, bc in enumerate(board_configs):
            board_id = bc["id"]
            try:
                boards[str(board_id)] = self.fetch_board(board_id)
            except BoardNotAccessibleError as e:
                logger.warning(
                    "Skipping board %s (%s) — not accessible (archived, deleted, or perms "
                    "revoked). Remove from config if intentional. Detail: %s",
                    board_id, bc.get("name", "?"), e,
                )
                continue
            except Exception:
                logger.exception(
                    "Unexpected failure fetching board %s (%s)",
                    board_id, bc.get("name", "?"),
                )
                continue
            # Rate-limit delay between boards (skip after last)
            if i < len(board_configs) - 1:
                time.sleep(self._delay)
        return boards

    def discover_protocol_boards(self, name_prefix: str = "[Protocol]") -> list[dict]:
        """
        Discover all active Monday boards whose name starts with `name_prefix`
        (case-insensitive). Paginates through Monday's board list 100 at a time.
        Returns a list of {"id": str, "name": str}.
        """
        prefix_lower = name_prefix.lower()
        matches: list[dict] = []
        page = 1
        limit = 100
        while True:
            logger.info("Discovering protocol boards — page %d", page)
            data = self._execute(BOARDS_LIST_QUERY, {"page": page, "limit": limit})
            boards = data.get("boards", []) or []
            for b in boards:
                name = b.get("name") or ""
                state = b.get("state") or "active"
                if state != "active":
                    continue
                if name.lower().startswith(prefix_lower):
                    matches.append({"id": str(b["id"]), "name": name})
            if len(boards) < limit:
                break
            page += 1
            time.sleep(self._delay)
        logger.info("Discovered %d protocol board(s) matching prefix %r", len(matches), name_prefix)
        return matches

    # ---- helpers ----

    def _resolve_item(self, item: dict, column_settings: dict) -> dict:
        """Resolve status column indices to human-readable labels."""
        resolved_columns = {}
        status = None
        date_val = None
        assignee = None

        for cv in item.get("column_values", []):
            col_id = cv["id"]
            col_meta = column_settings.get(col_id, {})
            col_type = cv.get("type") or col_meta.get("type", "")
            display_text = cv.get("text", "")

            # Resolve status labels from settings_str
            if col_type == "status" and cv.get("value"):
                display_text = self._resolve_status_label(cv["value"], col_meta)

            resolved_columns[col_id] = {
                "title": col_meta.get("title", col_id),
                "type": col_type,
                "text": display_text,
                "value": cv.get("value"),
            }

            # Extract key fields
            if col_type == "status" and status is None:
                status = display_text
            if col_type in ("date", "date") and date_val is None and display_text:
                date_val = display_text.split(" ")[0] if display_text else None
            if col_type in ("people", "person") and not assignee and display_text:
                assignee = display_text

        # Resolve subitems recursively (no deep column_settings needed)
        subitems = []
        for si in item.get("subitems", []):
            subitems.append({
                "id": si["id"],
                "name": si["name"],
                "columns": {
                    cv["id"]: {"text": cv.get("text", ""), "value": cv.get("value")}
                    for cv in si.get("column_values", [])
                },
            })

        return {
            "id": item["id"],
            "name": item["name"],
            "group": item.get("group", {}).get("title", ""),
            "status": status or "",
            "date": date_val,
            "assignee": assignee or "",
            "created_at": item.get("created_at"),
            "last_updated": item.get("updated_at"),
            "subitems": subitems,
            "raw_columns": resolved_columns,
        }

    @staticmethod
    def _resolve_status_label(raw_value: str, col_meta: dict) -> str:
        """Given a status column's raw JSON value and the column settings, return the label."""
        try:
            val = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            index = val.get("index")
            if index is None:
                return ""
            settings = json.loads(col_meta.get("settings_str", "{}"))
            labels = settings.get("labels", {})
            return labels.get(str(index), f"Unknown({index})")
        except (json.JSONDecodeError, AttributeError, TypeError):
            return str(raw_value)
