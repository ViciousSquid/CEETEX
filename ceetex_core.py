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


# Two terminal rows of half-block Unicode glyphs approximate the original
# Mode 7 double-height presentation without changing terminal font metrics.
_MOSAIC_FONT = {
    "0": ("###", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", "###"),
    "2": ("##.", "..#", ".#.", "###"),
    "3": ("##.", "..#", ".##", "##."),
    "4": ("#.#", "#.#", "###", "..#"),
    "5": ("###", "#..", "##.", "..#"),
    "6": (".##", "#..", "###", "###"),
    "7": ("###", "..#", ".#.", ".#."),
    "8": ("###", "#.#", "###", "###"),
    "9": ("###", "#.#", "###", "..#"),
    "A": (".#.", "#.#", "###", "#.#"),
    "B": ("##.", "#.#", "##.", "##."),
    "C": (".##", "#..", "#..", ".##"),
    "D": ("##.", "#.#", "#.#", "##."),
    "E": ("###", "##.", "#..", "###"),
    "F": ("###", "##.", "#..", "#.."),
    "G": (".##", "#..", "#.#", ".##"),
    "H": ("#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", "###"),
    "J": ("..#", "..#", "#.#", ".#."),
    "K": ("#.#", "##.", "##.", "#.#"),
    "L": ("#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "###", "#.#"),
    "N": ("#.#", "##.", ".##", "#.#"),
    "O": ("###", "#.#", "#.#", "###"),
    "P": ("##.", "#.#", "##.", "#.."),
    "Q": ("###", "#.#", "###", "..#"),
    "R": ("##.", "#.#", "##.", "#.#"),
    "S": (".##", "#..", ".#.", "##."),
    "T": ("###", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "###"),
    "V": ("#.#", "#.#", "#.#", ".#."),
    "W": ("#.#", "#.#", "###", "###"),
    "X": ("#.#", ".#.", ".#.", "#.#"),
    "Y": ("#.#", ".#.", ".#.", ".#."),
    "Z": ("###", "..#", ".#.", "###"),
    " ": ("...", "...", "...", "..."),
}


def mosaic_heading(title: str, width: int = 40) -> str:
    """Render a two-row Teletext-like heading using half-block glyphs.

    Real broadcast Teletext doubled the physical cell height; terminals cannot,
    so two rows of half-height bitmap mosaics approximate the effect.
    """
    rows = ["", ""]
    max_letters = max(0, (width + 1) // 4)
    for letter in title.upper()[:max_letters]:
        bitmap = _MOSAIC_FONT.get(letter, _MOSAIC_FONT[" "])
        for y in range(2):
            if rows[y]:
                rows[y] += " "
            for x in range(3):
                top = bitmap[y * 2][x] == "#"
                bottom = bitmap[y * 2 + 1][x] == "#"
                rows[y] += ("█" if top and bottom else "▀" if top else "▄" if bottom else " ")
    return "\n".join(rows)


def clean_feed_text(value: object, *, html_content: bool = False) -> str:
    """Convert untrusted RSS text to terminal-safe plain text.

    HTML summaries retain meaningful text but discard markup, scripts, styles,
    terminal escape/control sequences and invisible formatting characters.
    Rendering code must still Rich-escape the returned text.
    """
    import html
    import re
    from html.parser import HTMLParser

    class _SummaryHTML(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.fragments = []
            self.ignored = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.ignored.append(tag)
            elif not self.ignored and tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3"):
                self.fragments.append(" ")

        def handle_endtag(self, tag):
            if self.ignored:
                if tag == self.ignored[-1]:
                    self.ignored.pop()
            elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3"):
                self.fragments.append(" ")

        def handle_data(self, data):
            if not self.ignored:
                self.fragments.append(data)

    raw = str(value) if value is not None else ""
    # Remove escape sequences before collapsing control characters.
    raw = re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~])?", "", raw)
    if html_content:
        parser = _SummaryHTML()
        parser.feed(raw)
        parser.close()
        raw = " ".join(parser.fragments)
    raw = html.unescape(raw)
    return " ".join("".join(c for c in raw if c.isprintable() or c.isspace()).split())
