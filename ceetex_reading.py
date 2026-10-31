"""Persistent personal state for CEETEX: bookmarks and read headlines.

No external service, tracking or account. State lives in the OS user data
directory and is written atomically. Feed-supplied fields are not trusted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile

from platformdirs import user_data_dir

MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_BOOKMARKS = 250
MAX_READ_IDS = 5000
MAX_FIELD_CHARS = 4000
FIELDS = ("id", "guid", "link", "title", "summary", "description", "published", "source_page", "source_name")


def story_key(page_id: str, entry: dict) -> str:
    from ceetex_core import article_identity
    original = str(entry.get("source_page") or page_id)
    return f"{original}|{article_identity(entry)}"


def _safe_entry(entry: dict) -> dict[str, str]:
    return {key: str(entry[key])[:MAX_FIELD_CHARS] for key in FIELDS
            if entry.get(key) is not None}


def state_path() -> Path:
    return Path(user_data_dir("ceetex", appauthor=False)) / "reading.json"


@dataclass
class ReadingState:
    read_ids: list[str] = field(default_factory=list)
    bookmarks: dict[str, dict[str, str]] = field(default_factory=dict)

    def is_read(self, page_id: str, entry: dict) -> bool:
        return story_key(page_id, entry) in self.read_ids

    def is_bookmarked(self, page_id: str, entry: dict) -> bool:
        return story_key(page_id, entry) in self.bookmarks

    def mark_read(self, page_id: str, entry: dict) -> bool:
        key = story_key(page_id, entry)
        if key in self.read_ids:
            return False
        self.read_ids.append(key[:512])
        self.read_ids = self.read_ids[-MAX_READ_IDS:]
        return True

    def toggle_bookmark(self, page_id: str, entry: dict) -> bool:
        key = story_key(page_id, entry)[:512]
        if key in self.bookmarks:
            del self.bookmarks[key]
            return False
        if len(self.bookmarks) >= MAX_BOOKMARKS:
            self.bookmarks.pop(next(iter(self.bookmarks)))
        self.bookmarks[key] = _safe_entry(entry)
        return True

    def bookmarked_entries(self) -> list[dict[str, str]]:
        return list(reversed(list(self.bookmarks.values())))

    def save(self) -> bool:
        payload = json.dumps({
            "version": 1,
            "read_ids": self.read_ids[-MAX_READ_IDS:],
            "bookmarks": self.bookmarks,
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_STATE_BYTES:
            return False
        path = state_path()
        temp_path = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".reading-", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
            os.replace(temp_path, path)
            return True
        except OSError:
            return False
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass

    @classmethod
    def load(cls) -> "ReadingState":
        path = state_path()
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                return cls()
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or doc.get("version") != 1:
                return cls()
            reads = doc.get("read_ids", [])
            bookmarks = doc.get("bookmarks", {})
            if not isinstance(reads, list) or not isinstance(bookmarks, dict):
                return cls()
            if not all(isinstance(key, str) for key in reads):
                return cls()
            clean = {}
            for key, entry in list(bookmarks.items())[-MAX_BOOKMARKS:]:
                if not isinstance(key, str) or not isinstance(entry, dict):
                    continue
                if not all(isinstance(k, str) and isinstance(v, str) for k, v in entry.items()):
                    continue
                clean[key[:512]] = _safe_entry(entry)
            return cls([key[:512] for key in reads[-MAX_READ_IDS:]], clean)
        except (OSError, ValueError, TypeError):
            return cls()
