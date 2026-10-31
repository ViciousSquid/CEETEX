"""CEETEX: RSS displayed as an interactive Teletext service."""
from __future__ import annotations

import html
import json
import re
import textwrap
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
from rich.cells import set_cell_size
from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from ceetex_core import PageState, next_subpage, page_count, subpage_entries, validate_fasttext

ROOT = Path(__file__).resolve().parent
FASTTEXT_DEFAULTS = {"red": "101", "green": "130", "yellow": "102", "cyan": "190"}
FASTTEXT_LABELS = {"red": "NEWS", "green": "SPORT", "yellow": "WEATHER", "cyan": "TRAVEL"}
CLASSIC_WIDTH = 40
CLASSIC_PAGE_SIZE = 9
RESPONSIVE_PAGE_SIZE = 15
AUTO_ROTATE_SECONDS = 10
STALE_SECONDS = 15 * 60

CEETEX_LOGO = """
[b white]█▀▀ █▀▀ █▀▀ ▀█▀ █▀▀ █ █[/b white]
[b white]█   █▀▀ █▀▀  █  █▀▀ ▄▀▄[/b white]
[b white]▀▀▀ ▀▀▀ ▀▀▀  ▀  ▀▀▀ ▀ ▀[/b white]
[reverse][b yellow]  B R O A D C A S T   S E R V I C E  [/b yellow][/reverse]
"""


@dataclass
class FeedSnapshot:
    entries: list
    fetched_at: float
    source: str
    offline: bool = False


class TeletextApp(App):
    BINDINGS = [
        Binding("escape", "back_to_list", "Back/Index"),
        Binding("home", "go_home", "Index"),
        Binding("f1", "fasttext('red')", "News", show=False),
        Binding("f2", "fasttext('green')", "Sport", show=False),
        Binding("f3", "fasttext('yellow')", "Weather", show=False),
        Binding("f4", "fasttext('cyan')", "Travel", show=False),
        Binding("n", "next_subpage", "Next page"),
        Binding("p", "previous_subpage", "Previous page"),
        Binding("a", "toggle_auto_rotate", "Auto subpages"),
        Binding("m", "toggle_classic", "40 columns"),
        Binding("ctrl+left", "history_back", "Back", show=False),
        Binding("ctrl+right", "history_forward", "Forward", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("o", "open_browser", "Open story"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen { background: #000000; color: #ffffff; align: center top; }
    #teletext_screen { width: 100%; height: 100%; background: #000000; }
    #page_header { background: #0000ff; color: #ffffff; height: 7; width: 100%; content-align: center top; }
    #sub_header { background: #000000; color: #00ff00; height: 1; width: 100%; text-style: bold; }
    #teletext_container { width: 100%; height: 1fr; background: #000000; }
    ListView { background: #000000; height: 1fr; border: none; overflow-y: auto; }
    ListItem { padding: 0 1; background: #000000; color: #ffffff; }
    ListItem.--highlight { background: #0000ff; color: #ffff00; text-style: bold; }
    #ticker_tape { background: #0000ff; color: #ffffff; height: 1; width: 100%; text-style: bold; }
    #fasttext_bar { height: 1; width: 100%; layout: horizontal; }
    #fasttext_bar Button { width: 1fr; min-width: 0; height: 1; border: none; padding: 0; text-style: bold; }
    #fasttext_red { background: #aa0000; color: white; }
    #fasttext_green { background: #006600; color: white; }
    #fasttext_yellow { background: #aaaa00; color: black; }
    #fasttext_cyan { background: #008888; color: white; }
    #dialer { width: 100%; height: 1; background: #000000; color: #ffffff; border: none; padding: 0 1; }
    .hidden { display: none; }
    #loading_msg { color: #ffff00; text-style: blink; margin: 2; }
    #article_scroll { height: 1fr; width: 100%; overflow-y: auto; }
    #article_view { padding: 1 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.pages = self.load_config()
        self.fasttext_pages = self.load_fasttext()
        self.feed_cache: dict[str, FeedSnapshot] = {}
        self.entries: list = []
        self.displayed_indices: list[int] = []
        self.index_mapping: list[str | None] = []
        self.current_page_id = "100"
        self.view_mode = "index"
        self.current_subpage = 0
        self.selected_entry = -1
        self.classic_mode = False
        self.auto_rotate = False
        self.next_rotation = time.monotonic() + AUTO_ROTATE_SECONDS
        self.request_id = 0
        self.fetching = False
        self.history: list[PageState] = [PageState("100", "index")]
        self.history_position = 0

    def load_config(self) -> dict:
        path = ROOT / "pages.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("pages.json must be an object")
            return data
        except (OSError, ValueError, TypeError):
            return {"100": ["INDEX", ""]}

    def load_fasttext(self) -> dict[str, str]:
        try:
            overrides = json.loads((ROOT / "fasttext.json").read_text(encoding="utf-8"))
            if not isinstance(overrides, dict):
                overrides = {}
        except (OSError, ValueError):
            overrides = {}
        return validate_fasttext(overrides, self.pages, FASTTEXT_DEFAULTS)

    def compose(self) -> ComposeResult:
        with Container(id="teletext_screen"):
            yield Static("", id="page_header", markup=True)
            yield Static("", id="sub_header", markup=False)
            with Container(id="teletext_container"):
                yield ListView(id="main_list")
                yield Static(" [blink]LOADING DATA...[/blink]", id="loading_msg", classes="hidden")
                with VerticalScroll(id="article_scroll", classes="hidden"):
                    yield Static("", id="article_view", markup=True)
            yield Static(" LATEST: WAITING FOR CEETEX DATA...", id="ticker_tape", markup=True)
            with Horizontal(id="fasttext_bar"):
                for colour, label in FASTTEXT_LABELS.items():
                    yield Button(label, id=f"fasttext_{colour}")
            yield Input(placeholder="P100", id="dialer")

    def on_mount(self) -> None:
        self._apply_width()
        self.query_one("#dialer", Input).focus()
        self.display_index()
        self.set_interval(1.0, self._tick)

    def on_resize(self) -> None:
        self._apply_width()
        if self.view_mode == "index":
            self.display_index()
        elif self.view_mode == "list" and self.current_page_id in self.feed_cache:
            self._render_list()
        elif self.view_mode == "article" and self.current_page_id in self.feed_cache:
            self._render_article()

    def _apply_width(self) -> None:
        try:
            self.query_one("#teletext_screen").styles.width = min(CLASSIC_WIDTH, max(1, self.size.width)) if self.classic_mode else "100%"
        except Exception:
            pass  # Widget may not be mounted during the first resize event.

    @property
    def page_size(self) -> int:
        return CLASSIC_PAGE_SIZE if self.classic_mode else RESPONSIVE_PAGE_SIZE

    @property
    def content_width(self) -> int:
        return max(12, min(CLASSIC_WIDTH if self.classic_mode else self.size.width, max(12, self.size.width)) - 4)

    def _tick(self) -> None:
        self.update_header()
        self._update_sub_header()
        if self.auto_rotate and self.view_mode == "list" and time.monotonic() >= self.next_rotation:
            self.next_rotation = time.monotonic() + AUTO_ROTATE_SECONDS
            self._change_subpage(1, record_history=False)

    def update_header(self) -> None:
        stamp = datetime.now().strftime("%a %d %b %H:%M:%S").upper()
        widget = self.query_one("#page_header", Static)
        prefix = f"[b yellow]CEETEX {self.current_page_id}[/b yellow]  [white]{stamp}[/white]"
        if self.current_page_id == "100":
            widget.update(prefix + "\n" + CEETEX_LOGO)
            widget.styles.height = 7
        else:
            widget.update(prefix)
            widget.styles.height = 1

    def _signal(self) -> str:
        if self.current_page_id == "100":
            return "INDEX"
        if self.fetching:
            return "TUNING"
        snapshot = self.feed_cache.get(self.current_page_id)
        if snapshot is None:
            return "NO SIGNAL"
        if snapshot.offline:
            return "OFFLINE/CACHED"
        return "STALE" if time.time() - snapshot.fetched_at >= STALE_SECONDS else "LIVE"

    def _update_sub_header(self) -> None:
        page = self.current_page_id
        if page == "100":
            label = "MAIN INDEX"
            page_name = "P100"
        else:
            page_name = f"P{page}/{self.current_subpage + 1}"
            label = str(self.pages[page][0]).upper() if page in self.pages else "UNKNOWN"
        status = self._signal()
        if self.classic_mode:
            # Keep control/status metadata inside the actual 40-cell display.
            header = f"{page_name} {label}  {status}"
            header = set_cell_size(header, min(CLASSIC_WIDTH, max(1, self.size.width)))
        else:
            header = f" {page_name}  CEETEX  {label}   SIGNAL: {status}"
        self.query_one("#sub_header", Static).update(header)

    def _toggle_views(self, *, list_view=False, article=False, loading=False) -> None:
        self.query_one("#main_list").set_class(not list_view, "hidden")
        self.query_one("#article_scroll").set_class(not article, "hidden")
        self.query_one("#loading_msg").set_class(not loading, "hidden")
        self.update_header()
        self._update_sub_header()

    def display_index(self) -> None:
        self.view_mode = "index"
        self.current_page_id = "100"
        self.current_subpage = 0
        self.fetching = False
        self.request_id += 1
        self.index_mapping = []
        lst = self.query_one("#main_list", ListView)
        lst.clear()
        lst.append(ListItem(Label("[b yellow] DIRECTORY[/b yellow]", markup=True)))
        self.index_mapping.append(None)
        for page in sorted((p for p in self.pages if p != "100" and p.isdigit()), key=int):
            name = str(self.pages[page][0]).upper()
            label_width = max(5, self.content_width - 6)
            # One selectable item per channel: both columns in the old index
            # previously mapped to only the left-hand page.
            name = textwrap.shorten(name, width=label_width, placeholder="…")
            dots = "." * max(2, label_width - len(name))
            line = f" [white]{escape(name)}[/white] [yellow]{dots}[/yellow] [cyan]{page}[/cyan]"
            lst.append(ListItem(Label(line, markup=True)))
            self.index_mapping.append(page)
        self._toggle_views(list_view=True)

    def _capture_state(self) -> PageState:
        if self.view_mode == "list":
            idx = self.query_one("#main_list", ListView).index
            if idx is not None and idx < len(self.displayed_indices):
                self.selected_entry = self.displayed_indices[idx]
        return PageState(self.current_page_id, self.view_mode, self.current_subpage, self.selected_entry)

    def _navigate(self, state: PageState) -> None:
        current = self._capture_state()
        self.history[self.history_position] = current
        if state != current:
            self.history = self.history[: self.history_position + 1]
            self.history.append(state)
            self.history_position += 1
        self._restore_state(state)

    def _restore_state(self, state: PageState) -> None:
        if state.mode == "index" or state.page_id == "100":
            self.display_index()
            return
        self.current_page_id = state.page_id
        self.current_subpage = state.subpage
        self.selected_entry = state.selected_entry
        self.entries = self.feed_cache[state.page_id].entries if state.page_id in self.feed_cache else []
        self.view_mode = state.mode
        self.next_rotation = time.monotonic() + AUTO_ROTATE_SECONDS
        self.fetching = False
        self.request_id += 1  # invalidate callbacks from older pages/requests
        if not self.entries:
            self._toggle_views(loading=True)
            self.fetching = True
            self._update_sub_header()
            self.fetch_feed(state.page_id, self.pages[state.page_id][1], self.request_id)
        elif state.mode == "article" and 0 <= state.selected_entry < len(self.entries):
            self._render_article()
        else:
            self.view_mode = "list"
            self._render_list()

    def load_page(self, page_id: str) -> None:
        if page_id == "100":
            self._navigate(PageState("100", "index"))
        elif page_id not in self.pages:
            self.show_error(page_id, "PAGE DOES NOT EXIST")
        else:
            self._navigate(PageState(page_id))

    @work(thread=True)
    def fetch_feed(self, page_id: str, url: str, request_id: int) -> None:
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                self.call_from_thread(self.show_error, page_id, "NO DATA RECEIVED ON THIS CHANNEL", request_id)
                return
            entries = list(feed.entries)
            source = str(feed.feed.get("title", self.pages[page_id][0]))
            self.call_from_thread(self.render_feed, page_id, entries, source, request_id)
        except Exception as exc:
            self.call_from_thread(self.show_error, page_id, f"CONNECTION ERROR: {exc}", request_id)

    def render_feed(self, page_id: str, entries: list, source: str, request_id: int) -> None:
        if page_id != self.current_page_id or request_id != self.request_id:
            return
        self.feed_cache[page_id] = FeedSnapshot(entries, time.time(), source)
        self.entries = entries
        self.fetching = False
        if self.view_mode == "article" and 0 <= self.selected_entry < len(entries):
            self._render_article()
        else:
            self.view_mode = "list"
            self.current_subpage = min(self.current_subpage, page_count(len(entries), self.page_size) - 1)
            self._render_list()

    def _render_list(self) -> None:
        self.view_mode = "list"
        snapshot = self.feed_cache.get(self.current_page_id)
        if snapshot is None:
            return
        self.entries = snapshot.entries
        total = page_count(len(self.entries), self.page_size)
        self.current_subpage = min(self.current_subpage, total - 1)
        lst = self.query_one("#main_list", ListView)
        lst.clear()
        self.displayed_indices = []
        latest = escape(html.unescape(str(self.entries[0].get("title", "UNTITLED"))).upper())
        self.query_one("#ticker_tape", Static).update(f" [b yellow]LATEST:[/b yellow] {latest}")
        for global_idx, entry in subpage_entries(self.entries, self.current_subpage, self.page_size):
            title = html.unescape(str(entry.get("title", "UNTITLED"))).upper()
            title = textwrap.shorten(title, width=self.content_width, placeholder="…")
            lst.append(ListItem(Label(f"[cyan]█[/cyan] [white]{escape(title)}[/white]", markup=True)))
            self.displayed_indices.append(global_idx)
        self._toggle_views(list_view=True)
        if self.selected_entry in self.displayed_indices:
            lst.index = self.displayed_indices.index(self.selected_entry)
        elif self.displayed_indices:
            lst.index = 0
        lst.focus()

    def _render_article(self) -> None:
        if not (0 <= self.selected_entry < len(self.entries)):
            self.view_mode = "list"
            self._render_list()
            return
        self.view_mode = "article"
        entry = self.entries[self.selected_entry]
        title = html.unescape(str(entry.get("title", "UNTITLED"))).upper()
        summary = str(entry.get("summary", entry.get("description", "NO DETAILS PROVIDED.")))
        summary = html.unescape(re.sub(r"<[^>]*>", "", summary))
        width = self.content_width
        title = textwrap.fill(title, width=width)
        summary = textwrap.fill(summary, width=width)
        view = self.query_one("#article_view", Static)
        view.update(f"[b cyan]{escape(title)}[/b cyan]\n\n[white]{escape(summary)}[/white]\n\n[b yellow]O: FULL STORY   ESC: BACK[/b yellow]")
        self._toggle_views(article=True)

    def show_error(self, page_id: str, message: str, request_id: int | None = None) -> None:
        if request_id is not None and (request_id != self.request_id or page_id != self.current_page_id):
            return
        self.fetching = False
        cached = self.feed_cache.get(page_id)
        if cached is not None:
            cached.offline = True
            self.entries = cached.entries
            self._render_list()
            return
        self.view_mode = "error"
        self.query_one("#article_view", Static).update(
            f"\n[b red]{escape(message)}[/b red]\n\nCHECK SIGNAL AND RETRY (R)\nESC: INDEX"
        )
        self._toggle_views(article=True)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#main_list", ListView).index
        if idx is None:
            return
        if self.view_mode == "index":
            if 0 <= idx < len(self.index_mapping) and self.index_mapping[idx]:
                self.load_page(self.index_mapping[idx])
        elif self.view_mode == "list" and 0 <= idx < len(self.displayed_indices):
            selected = self.displayed_indices[idx]
            self.selected_entry = selected
            self._navigate(PageState(self.current_page_id, "article", self.current_subpage, selected))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("fasttext_"):
            self.action_fasttext(event.button.id.removeprefix("fasttext_"))

    def action_fasttext(self, colour: str) -> None:
        target = self.fasttext_pages.get(colour)
        if target:
            self.load_page(target)

    def _change_subpage(self, offset: int, *, record_history: bool = True) -> None:
        if self.view_mode != "list" or not self.entries:
            return
        total = page_count(len(self.entries), self.page_size)
        if total <= 1:
            return
        subpage = next_subpage(self.current_subpage, total, offset)
        state = PageState(self.current_page_id, "list", subpage)
        if record_history:
            self._navigate(state)
        else:
            self.current_subpage = subpage
            self.selected_entry = -1
            self.history[self.history_position] = state
            self._render_list()

    def action_next_subpage(self) -> None:
        self._change_subpage(1)

    def action_previous_subpage(self) -> None:
        self._change_subpage(-1)

    def action_toggle_auto_rotate(self) -> None:
        self.auto_rotate = not self.auto_rotate
        self.next_rotation = time.monotonic() + AUTO_ROTATE_SECONDS
        self.notify("AUTO SUBPAGES ON" if self.auto_rotate else "AUTO SUBPAGES OFF")

    def action_toggle_classic(self) -> None:
        self.classic_mode = not self.classic_mode
        self._apply_width()
        if self.view_mode == "index":
            self.display_index()
        elif self.view_mode == "list":
            # Keep the same article visible even though the page size changes.
            if self.selected_entry >= 0:
                self.current_subpage = self.selected_entry // self.page_size
            self._render_list()
        elif self.view_mode == "article":
            self._render_article()
        self.notify("40-COLUMN MODE" if self.classic_mode else "RESPONSIVE MODE")

    def action_history_back(self) -> None:
        if self.history_position > 0:
            self.history[self.history_position] = self._capture_state()
            self.history_position -= 1
            self._restore_state(self.history[self.history_position])

    def action_history_forward(self) -> None:
        if self.history_position + 1 < len(self.history):
            self.history[self.history_position] = self._capture_state()
            self.history_position += 1
            self._restore_state(self.history[self.history_position])

    def action_back_to_list(self) -> None:
        if self.view_mode == "article":
            if self.history_position > 0 and self.history[self.history_position - 1].page_id == self.current_page_id and self.history[self.history_position - 1].mode == "list":
                self.action_history_back()
            else:
                self._navigate(PageState(self.current_page_id, "list", self.current_subpage, self.selected_entry))
        else:
            self.load_page("100")
        self._clear_dialer()

    def action_go_home(self) -> None:
        self.load_page("100")
        self._clear_dialer()

    def action_refresh(self) -> None:
        if self.current_page_id == "100" or self.current_page_id not in self.pages:
            return
        self.request_id += 1
        self.fetching = True
        self._toggle_views(loading=True)
        self.fetch_feed(self.current_page_id, self.pages[self.current_page_id][1], self.request_id)

    def action_open_browser(self) -> None:
        if self.view_mode != "article" or not (0 <= self.selected_entry < len(self.entries)):
            return
        url = str(self.entries[self.selected_entry].get("link", ""))
        if urlparse(url).scheme in ("http", "https"):
            webbrowser.open(url)

    def on_key(self, event) -> None:
        if event.character and event.character.isascii() and event.character.isdigit():
            dialer = self.query_one("#dialer", Input)
            if not dialer.has_focus:
                dialer.focus()
                dialer.value += event.character
                event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "dialer":
            return
        value = event.value
        if len(value) == 3 and value.isascii() and value.isdigit():
            self.load_page(value)
            self.call_after_refresh(self._clear_dialer)
        elif len(value) >= 3:
            self._clear_dialer()

    def _clear_dialer(self) -> None:
        dialer = self.query_one("#dialer", Input)
        dialer.value = ""
        dialer.focus()


if __name__ == "__main__":
    TeletextApp().run()
