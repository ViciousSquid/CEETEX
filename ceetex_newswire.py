"""Shared story ordering for the CEETEX newswire (page 900)."""
from __future__ import annotations

from calendar import timegm
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

MAX_WIRE_ENTRIES = 150
MAX_WIRE_SOURCES = 24


def _date_epoch(entry: dict) -> float:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return float(timegm(parsed))
            except (ValueError, TypeError, OverflowError):
                pass
    for key in ("published", "updated"):
        value = entry.get(key)
        if not isinstance(value, str):
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (ValueError, TypeError, OverflowError):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError, OverflowError):
                continue
    return 0.0


def merge_feeds(sources: list[tuple[str, str, list]]) -> list[dict]:
    """Produce a newest-first, deduplicated feed with source attribution.

    Input is (three-digit page number, page title, feed entries). Preserve
    original IDs/links for bookmarking and returning to the source.
    """
    entries = []
    seen = set()
    for page, title, feed_entries in sources[:MAX_WIRE_SOURCES]:
        for entry in feed_entries:
            if not isinstance(entry, dict):
                continue
            copy = dict(entry)
            copy["source_page"] = page
            copy["source_name"] = title
            identity = str(copy.get("link") or f"{page}:{copy.get('id') or copy.get('title', '')}")
            if identity in seen:
                continue
            seen.add(identity)
            entries.append(copy)
    entries.sort(key=_date_epoch, reverse=True)
    return entries[:MAX_WIRE_ENTRIES]
