import feedparser
import textwrap
import re
import webbrowser
import json
import os
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Static, Input, ListView, ListItem
from textual.containers import Container, Horizontal
from textual.binding import Binding
from textual.events import Resize

# BUSY MODE 7 ASCII ART
CEETEX_LOGO = """
 [b white]█▀▀ █▀▀ █▀▀ ▀█▀ █▀▀ █ █[/b white]
 [b white]█   █▀▀ █▀▀  █  █▀▀ ▄▀▄[/b white]
 [b white]▀▀▀ ▀▀▀ ▀▀▀  ▀  ▀▀▀ ▀ ▀[/b white]
 [reverse][b yellow]  B R O A D C A S T   S E R V I C E  [/b yellow][/reverse]
"""

class TeletextApp(App):
    """
    CEETEX ULTIMATE - The 'Busy' Edition.
    Combines classic BBC Ceefax and ITV Teletext elements.
    """
    
    BINDINGS = [
        Binding("escape", "back_to_list", "Index/Back"),
        Binding("o", "open_browser", "Open Link"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        background: #000000;
        color: #ffffff;
    }

    #page_header {
        background: #0000ff;
        color: #ffffff;
        height: 7;
        width: 100%;
        content-align: center top;
    }

    #sub_header {
        background: #000000;
        color: #00ff00;
        height: 1;
        margin: 0 2;
        text-style: bold;
    }

    #teletext_container {
        width: 100%;
        height: 1fr;
        background: #000000;
    }

    ListView {
        background: #000000;
        height: auto;
        border: none;
    }

    ListItem {
        padding: 0;
        background: #000000;
        color: #ffffff;
    }

    ListItem.--highlight {
        background: #0000ff;
        color: #ffff00;
        text-style: bold;
    }

    #ticker_tape {
        background: #0000ff;
        color: #ffffff;
        height: 1;
        width: 100%;
        text-style: bold;
    }

    #fasttext_bar {
        height: 1;
        width: 100%;
        background: #000000;
    }

    Input {
        width: 100%;
        background: #000000;
        color: #ffffff;
        border: none;
        padding: 0 2;
    }

    .hidden { display: none; }
    """

    def __init__(self):
        super().__init__()
        self.pages = self.load_config()
        self.entries = []
        self.current_page_id = "100"
        self.view_mode = "index"

    def load_config(self):
        if os.path.exists("pages.json"):
            try:
                with open("pages.json", "r") as f:
                    return json.load(f)
            except: pass
        return {"100": ["INDEX", ""]}

    def compose(self) -> ComposeResult:
        yield Static("", id="page_header", markup=True)
        yield Static(" P100  CEETEX 1  [white]1/1[/white]  LONDON", id="sub_header", markup=True)
        
        with Container(id="teletext_container"):
            yield ListView(id="main_list")
            yield Static("", id="article_view", classes="hidden", markup=True)
        
        yield Static(" LATEST: LOADING CEETEX NEWS TICKER...", id="ticker_tape", markup=True)
        yield Static(" [b red] NEWS [/b red] [b green] SPORT [/b green] [b yellow] WEATHER [/b yellow] [b cyan] TRAVEL [/b cyan]", id="fasttext_bar", markup=True)
        yield Input(placeholder="P100", id="dialer")

    def on_mount(self) -> None:
        self.query_one("#dialer").focus()
        self.load_page("100")

    def update_header(self, page_id):
        time_str = datetime.now().strftime('%a %d %b %H:%M/%S')
        meta = f"[yellow]Ceetex {page_id}[/yellow] [white]CEETEX 1[/white] [yellow]{time_str}[/yellow]"
        self.query_one("#page_header").update(f"{meta}\n{CEETEX_LOGO}")

    def display_index(self) -> None:
        self.view_mode = "index"
        lst = self.query_one("#main_list")
        lst.clear()
        
        # Add the busy "Sub-Category" headers
        lst.append(ListItem(Static("[b yellow] C4                ITV [/b yellow]")))
        
        sorted_keys = sorted([k for k in self.pages.keys() if k != "100"], key=int)
        mid = (len(sorted_keys) + 1) // 2
        col1 = sorted_keys[:mid]
        col2 = sorted_keys[mid:]

        for i in range(mid):
            p1 = col1[i]
            n1 = self.pages[p1][0].upper()
            line = f" [white]{n1}[/white] {'.' * (20-len(n1))} [cyan]{p1}[/cyan]"
            
            if i < len(col2):
                p2 = col2[i]
                n2 = self.pages[p2][0].upper()
                line += f"  [white]{n2}[/white] {'.' * (18-len(n2))} [cyan]{p2}[/cyan]"
            
            lst.append(ListItem(Static(line, markup=True)))
        
        # Add a fake "advert" at the bottom to fill space
        lst.append(ListItem(Static("")))
        lst.append(ListItem(Static("[reverse][b yellow] FINANCE: GET THE FACTS ON PAGE 200 [/b yellow][/reverse]")))
        
        self.update_header("100")

    def load_page(self, page_id) -> None:
        if page_id == "100":
            self.display_index()
            return

        if page_id not in self.pages: return
        cat, url = self.pages[page_id]
        
        try:
            feed = feedparser.parse(url)
            self.entries = feed.entries
            lst = self.query_one("#main_list")
            lst.clear()
            
            self.update_header(page_id)
            self.query_one("#sub_header").update(f" P{page_id}  CEETEX 1  [white]1/1[/white]  {cat}")
            
            # Update Ticker with the top headline
            if self.entries:
                self.query_one("#ticker_tape").update(f" [b yellow]LATEST:[/b yellow] {self.entries[0].title.upper()}")

            for entry in self.entries[:15]:
                title = textwrap.shorten(entry.title.upper(), width=self.size.width-10, placeholder="...")
                lst.append(ListItem(Static(f" [cyan]█[/cyan] [white]{title}[/white]", markup=True)))
            
            self.view_mode = "list"
            self.query_one("#article_view").add_class("hidden")
            self.query_one("#main_list").remove_class("hidden")
            self.query_one("#main_list").focus()
        except:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.view_mode == "index":
            text = event.item.query_one(Static).renderable
            match = re.findall(r'(\d{3})', str(text))
            if match: self.load_page(match[-1])
        elif self.view_mode == "list":
            idx = self.query_one("#main_list").index
            if idx is not None: self.display_article(self.entries[idx])

    def display_article(self, entry) -> None:
        self.view_mode = "article"
        self.query_one("#main_list").add_class("hidden")
        view = self.query_one("#article_view")
        view.remove_class("hidden")
        
        summary = re.sub('<[^<]+?>', '', entry.get('summary', ''))
        content = (
            f"[b cyan]{entry.title.upper()}[/b cyan]\n\n"
            f"[white]{textwrap.fill(summary, width=self.size.width-10)}[/white]\n\n"
            f"[b yellow]PRESS 'O' FOR FULL STORY | ESC FOR INDEX[/b yellow]"
        )
        view.update(content)

    def action_back_to_list(self) -> None:
        if self.view_mode == "article":
            self.load_page(self.current_page_id)
        else:
            self.load_page("100")

    def action_open_browser(self) -> None:
        if self.view_mode == "article":
            idx = self.query_one("#main_list").index
            webbrowser.open(self.entries[idx].link)

    def on_input_changed(self, event: Input.Changed) -> None:
        if len(event.value) == 3 and event.value.isdigit():
            self.load_page(event.value)
            event.input.value = ""

if __name__ == "__main__":
    app = TeletextApp()
    app.run()