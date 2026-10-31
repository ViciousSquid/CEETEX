"""Pure page layout and navigation helpers for CEETEX."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class PageState:
    page_id: str
    mode: str = "list"  # index, list, article
    subpage: int = 0  # zero-based
    selected_entry: int = -1  # index into the complete RSS feed


def page_count(item_count: int, page_size: int) -> int:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    return max(1, ceil(item_count / page_size))


def subpage_entries(entries: list, subpage: int, page_size: int) -> list[tuple[int, object]]:
    """Return (global index, entry) pairs for one zero-based subpage."""
    total = page_count(len(entries), page_size)
    if not 0 <= subpage < total:
        raise IndexError("subpage out of range")
    start = subpage * page_size
    return list(enumerate(entries[start:start + page_size], start))


def next_subpage(current: int, total: int, offset: int) -> int:
    if total < 1:
        raise ValueError("total must be positive")
    return (current + offset) % total


def validate_fasttext(config: dict, pages: dict, defaults: dict[str, str]) -> dict[str, str]:
    """Allow only existing 3-digit pages as FastText destinations."""
    result = defaults.copy()
    for colour in defaults:
        candidate = config.get(colour, result[colour])
        if isinstance(candidate, str) and len(candidate) == 3 and candidate.isascii() and candidate.isdigit() and candidate in pages:
            result[colour] = candidate
    return result
