"""Compose CEETEX's classic display from a 40x25 Teletext cell grid.

The two-dimensional hit regions keep mouse selection aligned with the exact
characters users see, including both columns of the index.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import textwrap

from ceetex_core import clean_feed_text
from ceetex_teletext import TeletextGrid, draw_mode7_row

INDEX_ROWS = 16
INDEX_PER_PAGE = INDEX_ROWS * 2
HEADLINE_ROWS = tuple(5 + n * 2 for n in range(9))
FASTTEXT_COLOURS = ("red", "green", "yellow", "cyan")


@dataclass
class ClassicPage:
    grid: TeletextGrid
    # row -> (start x, exclusive end x, entry index)
    hit_regions: dict[int, list[tuple[int, int, int]]]


def compose_classic(
    *, page_id: str, mode: str, page_title: str,
    pages: dict, index_mapping: list[str], entries: list,
    displayed_indices: list[int], current_subpage: int,
    selected_index: int, fasttext_pages: dict[str, str],
    reading, reveal: bool = False, now: datetime | None = None,
    index_subpage: int = 0, message: str = "",
    signal: str = "LIVE", hold: bool = False,
) -> ClassicPage:
    grid = TeletextGrid()
    hits: dict[int, list[tuple[int, int, int]]] = {}
    now = now or datetime.now()
    grid.fill(0, " ", fg="yellow", bg="blue")
    grid.write(0, 0, f"P{page_id}", fg="yellow", bg="blue")
    grid.write(5, 0, "CEETEX", fg="white", bg="blue")
    grid.write(18, 0, now.strftime("%d %b %H:%M").upper(), fg="white", bg="blue")
    grid.write(32, 0, signal[:8].ljust(8), fg="green" if signal in ("LIVE", "CACHED") else "yellow", bg="blue")
    grid.write(0, 1, "CEEFAX FOR THE INTERNET", fg="cyan")
    if hold:
        grid.write(35, 1, "HOLD", fg="yellow", flash=True)
    grid.heading(2, page_title[:10], fg="yellow")
    grid.write(0, 4, "━" * 40, fg="blue")

    if mode == "index":
        begin = max(0, index_subpage) * INDEX_PER_PAGE
        for slot, page in enumerate(index_mapping[begin:begin + INDEX_PER_PAGE]):
            column, position = divmod(slot, INDEX_ROWS)
            x = column * 20
            y = 5 + position
            name = clean_feed_text(pages[page][0]).upper()
            label = f"{page} {textwrap.shorten(name, width=15, placeholder='…')}"
            is_selected = begin + slot == selected_index
            grid.write(x, y, (">" if is_selected else " ") + label[:18].ljust(18),
                       fg="yellow" if is_selected else "cyan",
                       bg="blue" if is_selected else "black")
            hits.setdefault(y, []).append((x, x + 20, begin + slot))
        grid.write(0, 22, f"INDEX {index_subpage + 1}/{max(1, (len(index_mapping)+31)//32)}", fg="yellow")
    elif mode == "list":
        if not entries:
            grid.write(1, 8, "SEARCHING PAGE " + page_id if signal == "TUNING" else (
                "NO SAVED STORIES" if page_id == "901" else "NO HEADLINES AVAILABLE"),
                fg="yellow" if signal == "TUNING" else "red")
            if signal == "TUNING":
                grid.write(1, 10, "WAITING FOR SIGNAL", fg="cyan", flash=True)
        for slot, global_index in enumerate(displayed_indices[:9]):
            if global_index >= len(entries):
                break
            entry = entries[global_index]
            row = HEADLINE_ROWS[slot]
            is_selected = global_index == selected_index
            unread = not reading.is_read(page_id, entry)
            book = reading.is_bookmarked(page_id, entry)
            source = str(entry.get("source_page", ""))
            title = clean_feed_text(entry.get("title") or "UNTITLED").upper()
            available = 30 if source else 35
            short = textwrap.shorten(title, width=available, placeholder="…")
            prefix = f"{source} " if source else ""
            line = (">" if is_selected else " ") + ("*" if unread else " ") + prefix + short
            grid.write(0, row, line[:40].ljust(40),
                       fg="yellow" if is_selected else ("white" if unread else "cyan"),
                       bg="blue" if is_selected else "black")
            if unread:
                grid.put(1, row, "●", fg="yellow", flash=True,
                         bg="blue" if is_selected else "black")
            if book:
                grid.write(39, row, "◆", fg="yellow",
                           bg="blue" if is_selected else "black")
            hits.setdefault(row, []).append((0, 40, global_index))
        grid.write(0, 22, f"P{page_id}/{current_subpage+1}  ENTER READ  N/P PAGES", fg="yellow")
    elif mode == "help":
        grid.write(1, 5, "YOUR CEETEX QUICK GUIDE", fg="yellow")
        for y, text in enumerate((
            "100  MAIN DIRECTORY",
            "900  LIVE NEWSWIRE",
            "901  SAVED STORIES",
            "0-9  DIAL THREE DIGITS",
            "F1-4 FASTTEXT  N/P SUBPAGES",
            "UP/DOWN SELECT, ENTER READ",
            "B SAVE STORY  O OPEN WEB",
            "V REVEAL TEXT  H HOLD PAGE",
        ), start=7):
            grid.write(1, y, text, fg="cyan" if y % 2 else "white")
        # A genuine Mode 7 control-code row demonstrates changing per-cell
        # colours, held mosaics and special graphics attributes.
        draw_mode7_row(grid, 17, bytes([0x11, 0x7F, 0x1E, 0x7F, 0x7F,
                                        0x12, 0x7F, 0x7F, 0x1F]))
        grid.write(1, 19, "V REVEALS THE SECRET BELOW:", fg="yellow")
        grid.write(1, 20, "YOUR NEWS IS YOURS TO KEEP", fg="cyan", conceal=True)
        grid.write(0, 22, "CEETEX • MODERN NEWS, CLASSIC FEEL", fg="green")
    elif mode == "article" and 0 <= selected_index < len(entries):
        entry = entries[selected_index]
        heading = clean_feed_text(entry.get("title") or "UNTITLED").upper()
        grid.write(0, 5, textwrap.shorten(heading, width=40, placeholder="…"), fg="yellow")
        origin = clean_feed_text(entry.get("source_name") or page_title)
        grid.write(0, 6, f"SOURCE: {origin}"[:39], fg="cyan", conceal=True)
        body = clean_feed_text(entry.get("summary", entry.get("description", "NO DETAILS")), html_content=True)
        for n, line in enumerate(textwrap.wrap(body, width=38, break_long_words=True)[:15]):
            grid.write(1, 7 + n, line, fg="white")
        flagged = "SAVED" if reading.is_bookmarked(page_id, entry) else "NOT SAVED"
        grid.write(0, 22, f"B BOOKMARK ({flagged})  O WEB", fg="green")
    else:
        grid.write(1, 8, (message or "PAGE NOT AVAILABLE")[:38], fg="red")
        grid.write(1, 10, "ESC INDEX   R RETRY", fg="yellow")

    if mode != "index":
        grid.write(0, 23, "ESC BACK G NEWS K SAVED V REVEAL H HOLD", fg="cyan")
    else:
        grid.write(0, 23, "TYPE PAGE NUMBER   G NEWS  K SAVED", fg="cyan")
    for i, colour in enumerate(FASTTEXT_COLOURS):
        x = i * 10
        grid.write(x, 24, f" {colour.upper()[:3]} {fasttext_pages.get(colour, '---')} ".ljust(10),
                   fg="black" if colour == "yellow" else "white", bg=colour)
    return ClassicPage(grid, hits)
