"""40 x 25 terminal Teletext character grid.

A Teletext *presentation* model, not a broadcast decoder. Individual cells
carry foreground/background, flash and conceal attributes. Mosaic glyphs use
Unicode braille/blocks to approximate the original 2x3 character graphics.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from rich.text import Text

COLUMNS = 40
ROWS = 25
COLOURS = {
    "black": "#000000", "red": "#ff0000", "green": "#00ff00",
    "yellow": "#ffff00", "blue": "#0000ff", "magenta": "#ff00ff",
    "cyan": "#00ffff", "white": "#ffffff",
}
SIXEL_BRAILLE = (0x01, 0x08, 0x02, 0x10, 0x04, 0x20)


@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    fg: str = "white"
    bg: str = "black"
    flash: bool = False
    conceal: bool = False


def teletext_glyph(character: str) -> str:
    """One visual terminal cell per input codepoint."""
    if not character or character in ("\r", "\n", "\t"):
        return " "
    character = character[0]
    if (unicodedata.category(character).startswith("C")
            or unicodedata.combining(character)
            or unicodedata.east_asian_width(character) in ("W", "F")):
        return "?"
    return character


def mosaic(pattern: int, *, separated: bool = False) -> str:
    """Represent the six 2x3 Teletext mosaic blocks in a single terminal cell.

    Full contiguous mosaics are solid blocks; for partial mosaics, Braille
    preserves all six component pixels within a single text character.
    A genuine broadcast receiver has a different 2x3 block raster.
    """
    if not 0 <= pattern <= 63:
        raise ValueError("mosaic pattern must be between 0 and 63")
    if pattern == 0:
        return " "
    if pattern == 63 and not separated:
        return "█"
    bits = sum(bit for n, bit in enumerate(SIXEL_BRAILLE) if pattern & (1 << n))
    return chr(0x2800 + bits)


class TeletextGrid:
    def __init__(self) -> None:
        self.cells = [[Cell() for _ in range(COLUMNS)] for _ in range(ROWS)]

    def put(
        self, x: int, y: int, character: str, *,
        fg: str = "white", bg: str = "black",
        flash: bool = False, conceal: bool = False,
    ) -> None:
        if fg not in COLOURS or bg not in COLOURS:
            raise ValueError("Unknown Teletext colour")
        if 0 <= x < COLUMNS and 0 <= y < ROWS:
            self.cells[y][x] = Cell(teletext_glyph(character), fg, bg, flash, conceal)

    def write(
        self, x: int, y: int, value: str, *,
        fg: str = "white", bg: str = "black",
        flash: bool = False, conceal: bool = False,
    ) -> None:
        if not 0 <= y < ROWS:
            return
        for i, ch in enumerate(str(value)):
            if x + i >= COLUMNS:
                break
            self.put(x + i, y, ch, fg=fg, bg=bg, flash=flash, conceal=conceal)

    def fill(self, y: int, character: str = " ", *, fg: str = "white", bg: str = "black") -> None:
        self.write(0, y, character * COLUMNS, fg=fg, bg=bg)

    def mosaic(self, x: int, y: int, pattern: int, *, separated: bool = False,
               fg: str = "white", bg: str = "black") -> None:
        self.put(x, y, mosaic(pattern, separated=separated), fg=fg, bg=bg)

    def heading(self, y: int, title: str, *, fg: str = "yellow") -> None:
        from ceetex_core import mosaic_heading
        top, bottom = mosaic_heading(title, COLUMNS).split("\n")
        self.write(0, y, top, fg=fg)
        self.write(0, y + 1, bottom, fg=fg)

    def rich(self, *, reveal: bool = False, flash_on: bool = True) -> Text:
        result = Text(no_wrap=True, overflow="crop")
        for y, row in enumerate(self.cells):
            current_style = None
            chars = []
            for cell in row:
                style = f"{COLOURS[cell.fg]} on {COLOURS[cell.bg]}"
                if current_style is not None and current_style != style:
                    result.append("".join(chars), style=current_style)
                    chars.clear()
                current_style = style
                hidden = (cell.conceal and not reveal) or (cell.flash and not flash_on)
                chars.append(" " if hidden else cell.char)
            if chars:
                result.append("".join(chars), style=current_style)
            if y != ROWS - 1:
                result.append("\n")
        return result

    def plain(self, *, reveal: bool = False, flash_on: bool = True) -> list[str]:
        return [
            "".join(
                " " if (cell.conceal and not reveal) or (cell.flash and not flash_on)
                else cell.char
                for cell in row
            )
            for row in self.cells
        ]


# Broadcast-inspired Mode 7 set-after control codes (0x00–0x1f). The
# terminal glyph mapping is deliberately approximate; styling and mosaic
# composition follow actual Teletext control-byte semantics.
_MODE7_COLOURS = ("black", "red", "green", "yellow",
                  "blue", "magenta", "cyan", "white")


def draw_mode7_row(grid: TeletextGrid, y: int, data: bytes, *, double_bottom: bool = False) -> None:
    """Decode a single Mode 7-style control-code row into coloured cells.

    Alpha/graphics colours, flash/steady, conceal, graphics separation,
    background changes and held mosaic graphics are recognised. Control codes
    occupy a character cell, as they do in broadcast Teletext. Double-height
    data uses two terminal rows to retain the intended vertical footprint.
    """
    fg = "white"
    bg = "black"
    graphics = False
    flashing = False
    concealed = False
    separated = False
    hold = False
    double = False
    last_mosaic = " "
    for x, code in enumerate(data[:COLUMNS]):
        if code < 32:
            # An attribute code uses one screen cell. In held graphics mode,
            # display the last mosaic instead of leaving the cell blank.
            char = last_mosaic if graphics and hold else " "
            grid.put(x, y, char, fg=fg, bg=bg, flash=flashing, conceal=concealed)
            if code <= 7:
                fg = _MODE7_COLOURS[code]
                graphics = False
                concealed = False
            elif code in range(0x10, 0x18):
                fg = _MODE7_COLOURS[code - 0x10]
                graphics = True
                concealed = False
            elif code == 0x08:
                flashing = True
            elif code == 0x09:
                flashing = False
            elif code == 0x0C:
                double = False
            elif code == 0x0D:
                double = True
            elif code == 0x18:
                concealed = True
            elif code == 0x19:
                separated = False
            elif code == 0x1A:
                separated = True
            elif code == 0x1C:
                bg = "black"
            elif code == 0x1D:
                bg = fg
            elif code == 0x1E:
                hold = True
            elif code == 0x1F:
                hold = False
                last_mosaic = " "
            continue
        if graphics and (0x20 <= code <= 0x3F or 0x60 <= code <= 0x7F):
            pattern = (code & 0x1F) | ((code & 0x40) >> 1)
            char = mosaic(pattern, separated=separated)
            if pattern:
                last_mosaic = char
        else:
            char = teletext_glyph(chr(code))
        grid.put(x, y, char, fg=fg, bg=bg, flash=flashing, conceal=concealed)
        if double and y + 1 < ROWS and not double_bottom:
            # A terminal has no character-cell half-height font. Reserve the
            # lower row explicitly; keep the glyph readable on both rows.
            grid.put(x, y + 1, char, fg=fg, bg=bg, flash=flashing, conceal=concealed)
