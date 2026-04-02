import feedparser
import textwrap
import re
import html
import webbrowser
import json
import os
from datetime import datetime
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Static, Input, ListView, ListItem, Label
from textual.containers import Container
from textual.binding import Binding

CEETEX_LOGO = """
 [b white]█▀▀ █▀▀ █▀▀ ▀█▀ █▀▀ █ █[/b white]
 [b white]█   █▀▀ █▀▀  █  █▀▀ ▄▀▄[/b white]
 [b white]▀▀▀ ▀▀▀ ▀▀▀  ▀  ▀▀▀ ▀ ▀[/b white]
 [reverse][b yellow]  B R O A D C A S T   S E R V I C E  [/b yellow][/reverse]
"""

class TeletextApp(App):
    """CEETEX ULTIMATE - Enhanced & Stabilized Edition."""
    
    BINDINGS = [
        Binding("escape", "back_to_list", "Index/Back"),
        Binding("home", "go_home", "Home"),
        Binding("o", "open_browser", "Open Link"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen { background: #000000; color: #ffffff; }
    #page_header { background: #0000ff; color: #ffffff; height: 7; width: 100%; content-align: center top; }
    #sub_header { background: #000000; color: #00ff00; height: 1; margin: 0 2; text-style: bold; }
    #teletext_container { width: 100%; height: 1fr; background: #000000; }
    ListView { background: #000000; height: 1fr; border: none; overflow-y: scroll; }
    ListItem { padding: 0 1; background: #000000; color: #ffffff; }
    ListItem.--highlight { background: #0000ff; color: #ffff00; text-style: bold; }
    #ticker_tape { background: #0000ff; color: #ffffff; height: 1; width: 100%; text-style: bold; }
    #fasttext_bar { height: 1; width: 100%; background: #000000; }
    Input { width: 100%; height: 1; background: #000000; color: #ffffff; border: none; padding: 0 2; }
    .hidden { display: none; }
    #loading_msg { color: #ffff00; text-style: blink; margin: 2; }
    #article_view { padding: 1 2; }
    """

    def __init__(self):
        super().__init__()
        self.pages = self.load_config()
        self.entries = []
        self.current_page_id = "100"
        self.view_mode = "index"
        self.index_mapping = [] 

    def load_config(self):
        if os.path.exists("pages.json"):
            try:
                with open("pages.json", "r") as f:
                    return json.load(f)
            except Exception as e:
                self.notify(f"Config error: {e}", severity="error")
        return {"100": ["INDEX", ""]}

    def compose(self) -> ComposeResult:
        yield Static("", id="page_header", markup=True)
        yield Static(" P100  CEETEX 1  [white]1/1[/white]  LONDON", id="sub_header", markup=True)
        
        with Container(id="teletext_container"):
            yield ListView(id="main_list")
            yield Static(" [blink]LOADING DATA...[/blink]", id="loading_msg", markup=True, classes="hidden")
            yield Static("", id="article_view", classes="hidden", markup=True)
        
        yield Static(" LATEST: WAITING FOR CEETEX DATA...", id="ticker_tape", markup=True)
        yield Static(" [b red] NEWS [/b red] [b green] SPORT [/b green] [b yellow] WEATHER [/b yellow] [b cyan] TRAVEL [/b cyan]", id="fasttext_bar", markup=True)
        yield Input(placeholder="P100", id="dialer")

    def on_mount(self) -> None:
        self.query_one("#dialer").focus()
        self.load_page("100")

    def update_header(self, page_id: str) -> None:
        """Updates the header with the logo only on the main index (P100)."""
        time_str = datetime.now().strftime('%a %d %b %H:%M/%S')
        meta = f"[yellow]Ceetex {page_id}[/yellow] [white]CEETEX 1[/white] [yellow]{time_str}[/yellow]"
        header_widget = self.query_one("#page_header")

        if page_id == "100":
            header_widget.update(f"{meta}\n{CEETEX_LOGO}")
            header_widget.styles.height = 7
        else:
            header_widget.update(meta)
            header_widget.styles.height = 1

    def action_go_home(self) -> None:
        """Action triggered by the Home key to return to P100."""
        self.load_page("100")
        self.query_one("#dialer").value = ""
        self.query_one("#dialer").focus()

    def display_index(self) -> None:
        self.view_mode = "index"
        self.current_page_id = "100"
        self.index_mapping = []
        
        lst = self.query_one("#main_list")
        lst.clear()
        self._toggle_views(show_list=True)
        
        lst.append(ListItem(Label("[b yellow] DIRECTORY                  [/b yellow]", markup=True)))
        
        sorted_keys = sorted([k for k in self.pages.keys() if k != "100"], key=int)
        mid = (len(sorted_keys) + 1) // 2
        col1 = sorted_keys[:mid]
        col2 = sorted_keys[mid:]

        for i in range(mid):
            p1 = col1[i]
            n1 = self.pages[p1][0].upper()
            left_dots = "." * max(2, 22 - len(n1))
            line = f" [white]{n1}[/white] {left_dots} [cyan]{p1}[/cyan]"
            
            if i < len(col2):
                p2 = col2[i]
                n2 = self.pages[p2][0].upper()
                right_dots = "." * max(2, 22 - len(n2))
                line += f"     [white]{n2}[/white] {right_dots} [cyan]{p2}[/cyan]"
            
            lst.append(ListItem(Label(line, markup=True)))
            self.index_mapping.append(p1) 
        
        lst.append(ListItem(Label("")))
        lst.append(ListItem(Label("[reverse][b yellow] FINANCE: GET THE FACTS ON PAGE 200 [/b yellow][/reverse]", markup=True)))
        
        self.update_header("100")
        self.query_one("#sub_header").update(" P100  CEETEX 1  [white]1/1[/white]  MAIN INDEX")

    def load_page(self, page_id: str) -> None:
        if page_id == "100":
            self.display_index()
            return

        if page_id not in self.pages:
            self.show_error(page_id, "PAGE DOES NOT EXIST")
            return

        self.current_page_id = page_id
        cat, url = self.pages[page_id]
        
        self.update_header(page_id)
        self.query_one("#sub_header").update(f" P{page_id}  CEETEX 1  [white]1/1[/white]  {cat}")
        
        self._toggle_views(show_loading=True)
        self.fetch_feed(page_id, url)

    @work(thread=True)
    def fetch_feed(self, page_id: str, url: str) -> None:
        try:
            feed = feedparser.parse(url)
            self.call_from_thread(self.render_feed, page_id, feed)
        except Exception as e:
            self.call_from_thread(self.show_error, page_id, f"CONNECTION ERROR: {str(e)}")

    def render_feed(self, page_id: str, feed) -> None:
        if self.current_page_id != page_id:
            return

        if not feed.entries:
            self.show_error(page_id, "NO DATA RECEIVED ON THIS CHANNEL")
            return

        self.entries = feed.entries
        lst = self.query_one("#main_list")
        lst.clear()

        safe_ticker_title = html.unescape(self.entries[0].title.upper())
        self.query_one("#ticker_tape").update(f" [b yellow]LATEST:[/b yellow] {safe_ticker_title}")

        for entry in self.entries[:15]:
            clean_title = html.unescape(entry.get("title", "UNTITLED")).upper()
            title = textwrap.shorten(clean_title, width=self.size.width - 10, placeholder="...")
            lst.append(ListItem(Label(f" [cyan]█[/cyan] [white]{title}[/white]", markup=True)))
        
        self.view_mode = "list"
        self._toggle_views(show_list=True)
        lst.focus()

    def show_error(self, page_id: str, message: str) -> None:
        self.view_mode = "error"
        view = self.query_one("#article_view")
        content = f"\n\n[b red] {message} [/b red]\n\n[white] PLEASE CHECK SIGNAL AND TRY AGAIN[/white]\n\n[b yellow] ESC FOR INDEX[/b yellow]"
        view.update(content)
        self._toggle_views(show_article=True)

    def _toggle_views(self, show_list=False, show_article=False, show_loading=False):
        self.query_one("#main_list").set_class(not show_list, "hidden")
        self.query_one("#article_view").set_class(not show_article, "hidden")
        self.query_one("#loading_msg").set_class(not show_loading, "hidden")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#main_list").index
        if idx is None: return

        if self.view_mode == "index":
            adjusted_idx = idx - 1 
            if 0 <= adjusted_idx < len(self.index_mapping):
                self.load_page(self.index_mapping[adjusted_idx])
        elif self.view_mode == "list":
            self.display_article(self.entries[idx])

    def display_article(self, entry) -> None:
        self.view_mode = "article"
        view = self.query_one("#article_view")
        
        raw_summary = entry.get('summary', entry.get('description', 'NO DETAILS PROVIDED.'))
        clean_summary = html.unescape(re.sub('<[^<]+?>', '', raw_summary))
        clean_title = html.unescape(entry.get('title', 'UNTITLED')).upper()

        content = (
            f"[b cyan]{clean_title}[/b cyan]\n\n"
            f"[white]{textwrap.fill(clean_summary, width=self.size.width-10)}[/white]\n\n"
            f"[b yellow]PRESS 'O' FOR FULL STORY | ESC FOR INDEX[/b yellow]"
        )
        view.update(content)
        self._toggle_views(show_article=True)

    def action_back_to_list(self) -> None:
        if self.view_mode in ("article", "error"):
            self.load_page(self.current_page_id)
        else:
            self.load_page("100")
        self.query_one("#dialer").value = ""
        self.query_one("#dialer").focus()

    def action_open_browser(self) -> None:
        if self.view_mode == "article":
            idx = self.query_one("#main_list").index
            link = self.entries[idx].get("link")
            if link:
                webbrowser.open(link)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handles 3-digit dialing and clears input correctly."""
        val = event.value
        if len(val) == 3:
            if val.isdigit():
                self.load_page(val)
                # We defer clearing to ensure the value is processed
                self.call_after_refresh(self._clear_dialer)
            else:
                # If non-digits are entered, clear immediately
                self._clear_dialer()

    def _clear_dialer(self) -> None:
        dialer = self.query_one("#dialer")
        dialer.value = ""
        # Keep focus so the user can type again immediately
        dialer.focus()

if __name__ == "__main__":
    app = TeletextApp()
    app.run()