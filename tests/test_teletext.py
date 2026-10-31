"""Pure 40x25 Teletext engine tests: control attributes and visible cells."""
from datetime import datetime

import pytest

from ceetex_teletext import COLUMNS, ROWS, TeletextGrid, mosaic
from ceetex_classic import compose_classic
from ceetex_reading import ReadingState


def test_exact_grid_dimensions_and_cropped_writes():
    g = TeletextGrid()
    g.write(38, 0, "ABCDE", fg="yellow", bg="blue")
    rows = g.plain()
    assert len(rows) == ROWS
    assert all(len(row) == COLUMNS for row in rows)
    assert rows[0].endswith("AB")
    assert g.cells[0][38].fg == "yellow"
    assert g.cells[0][38].bg == "blue"
    g.put(100, 100, "x")
    assert g.plain() == rows


def test_flash_conceal_and_reveal_are_independent():
    g = TeletextGrid()
    g.write(0, 0, "HIDDEN", conceal=True, fg="cyan")
    g.write(0, 1, "FLASH", flash=True, fg="red")
    assert "HIDDEN" not in g.plain()[0]
    assert g.plain(reveal=True)[0].startswith("HIDDEN")
    assert g.plain(flash_on=False)[1].startswith("     ")
    assert g.plain(flash_on=True)[1].startswith("FLASH")
    assert g.rich(reveal=True, flash_on=False).plain.count("\n") == 24


def test_sixel_patterns_and_colour_validation():
    assert mosaic(0) == " "
    assert mosaic(63) == "█"
    assert mosaic(63, separated=True) != "█"
    assert mosaic(1) != mosaic(2)
    assert len({mosaic(i, separated=True) for i in range(64)}) == 64
    with pytest.raises(ValueError):
        mosaic(64)
    with pytest.raises(ValueError):
        TeletextGrid().put(0, 0, "X", fg="orange")


def test_unicode_text_cannot_break_cell_geometry():
    g = TeletextGrid()
    g.write(0, 0, "A中😀B\t")
    assert g.plain()[0].startswith("A??B ")
    assert len(g.plain()[0]) == 40


def test_classic_index_two_columns_click_regions_and_fasttext():
    pages = {f"{i:03d}": [f"CHANNEL {i}", "https://example.org"] for i in range(101, 140)}
    order = sorted(pages)
    frame = compose_classic(
        page_id="100", mode="index", page_title="INDEX",
        pages=pages, index_mapping=order, entries=[], displayed_indices=[],
        current_subpage=0, selected_index=17, reading=ReadingState(),
        fasttext_pages={"red": "101", "green": "102", "yellow": "103", "cyan": "104"},
        now=datetime(2026, 10, 31, 10, 0), index_subpage=0,
    )
    assert len(frame.grid.plain()) == 25
    assert frame.hit_regions[6] == [(0, 20, 1), (20, 40, 17)]
    assert "RED 101" in frame.grid.plain()[24]
    assert frame.grid.cells[24][0].bg == "red"


def test_classic_article_source_reveal_and_bookmark_flag():
    entry = {"id": "a1", "title": "Sample headline", "summary": "<b>Some</b> useful text", "source_page": "101", "source_name": "BBC"}
    frame = compose_classic(
        page_id="900", mode="article", page_title="NEWSWIRE",
        pages={}, index_mapping=[], entries=[entry], displayed_indices=[],
        current_subpage=0, selected_index=0, reading=ReadingState(),
        fasttext_pages={}, now=datetime(2026, 10, 31),
    )
    assert "SOME USEFUL TEXT" not in frame.grid.plain()[7]  # content preserves casing
    assert "Some useful text" in frame.grid.plain()[7]
    assert "SOURCE" not in frame.grid.plain()[6]
    assert "SOURCE: BBC" in frame.grid.plain(reveal=True)[6]


def test_mode7_control_bytes_colour_graphics_hold_and_reveal():
    from ceetex_teletext import draw_mode7_row
    grid = TeletextGrid()
    # Red text, green graphics, held mosaic, separated graphics, conceal.
    draw_mode7_row(grid, 0, bytes([
        0x01, ord("A"), 0x12, 0x7F, 0x1E, 0x1A, 0x18, ord("B"),
    ]))
    assert grid.cells[0][1].char == "A"
    assert grid.cells[0][1].fg == "red"
    assert grid.cells[0][3].fg == "green"
    assert grid.cells[0][3].char == "█"
    assert grid.cells[0][4].char == " "   # HOLD applies after its control cell
    assert grid.cells[0][5].char == "█"   # next control cell displays the held mosaic
    assert grid.cells[0][7].conceal
    assert grid.plain()[0][7] == " "
    assert grid.plain(reveal=True)[0][7] == "B"


def test_mode7_flash_background_and_double_height():
    from ceetex_teletext import draw_mode7_row
    grid = TeletextGrid()
    draw_mode7_row(grid, 2, bytes([0x03, 0x1D, 0x08, ord("X"), 0x09, 0x0D, ord("Y")]))
    assert grid.cells[2][3].bg == "yellow"
    assert grid.cells[2][3].flash
    assert not grid.cells[2][6].flash
    assert grid.cells[3][6].char == "Y"  # explicit lower-row footprint
