"""Optional bounded on-disk RSS snapshot cache, independent of Textual."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir

MAX_CACHE_BYTES = 4 * 1024 * 1024
MAX_CACHE_ITEMS = 300
MAX_FIELD_CHARS = 16_000
ENTRY_FIELDS = ("id", "guid", "link", "title", "summary", "description", "published")


@dataclass(frozen=True)
class CachedFeed:
    entries: list[dict[str, str]]
    fetched_at: float
    source: str
    url: str
    etag: str | None
    last_modified: str | None


def _path(page_id: str) -> Path:
    if not (isinstance(page_id, str) and len(page_id) == 3
            and page_id.isascii() and page_id.isdigit() and page_id != "100"):
        raise ValueError("Invalid cache page ID")
    return Path(user_cache_dir("ceetex", appauthor=False)) / f"{page_id}.json"


def save_feed(
    page_id: str, entries: list, fetched_at: float, source: str,
    url: str, etag: str | None = None, last_modified: str | None = None,
) -> bool:
    """Write a bounded, JSON-only feed snapshot atomically.

    Returns False for cache permission failures and excessive data: the live
    feed remains usable even if persistent caching is unavailable.
    """
    path = _path(page_id)
    compact = [
        {key: str(entry[key])[:MAX_FIELD_CHARS] for key in ENTRY_FIELDS if entry.get(key) is not None}
        for entry in entries[:MAX_CACHE_ITEMS]
    ]
    payload = {
        "version": 1,
        "fetched_at": float(fetched_at),
        "source": str(source)[:MAX_FIELD_CHARS],
        "url": url,
        "etag": etag,
        "last_modified": last_modified,
        "entries": compact,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_CACHE_BYTES:
        return False
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".ceetex-", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        os.replace(tmp, path)
        return True
    except OSError:
        return False
    finally:
        if tmp is not None:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass


def load_feed(page_id: str) -> CachedFeed | None:
    """Ignore missing, corrupt, or incompatible cached snapshots."""
    path = _path(page_id)
    try:
        if path.stat().st_size > MAX_CACHE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            return None
        entries = data["entries"]
        if not isinstance(entries, list) or not entries or len(entries) > MAX_CACHE_ITEMS:
            return None
        if not all(
            isinstance(entry, dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in entry.items())
            for entry in entries
        ):
            return None
        timestamp = data["fetched_at"]
        source = data["source"]
        url = data["url"]
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            return None
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or timestamp < 0:
            return None
        if not isinstance(source, str):
            return None
        etag, last_modified = data.get("etag"), data.get("last_modified")
        if not all(item is None or isinstance(item, str) for item in (etag, last_modified)):
            return None
        return CachedFeed(entries, float(timestamp), source, url, etag, last_modified)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None
