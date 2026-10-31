"""Interactive Teletext surface and modern reading workflow tests."""
from unittest.mock import patch

import pytest

from ceetex import TeletextApp
from textual.widgets import ListView


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path / "cache"))
    monkeypatch.setattr("ceetex_reading.user_data_dir", lambda *a, **kw: str(tmp_path / "reading"))


def sample():
    return [
        {"id": "story-A", "title": "World news", "summary": "A brief news story",
         "link": "https://example.org/a", "published": "Sat, 31 Oct 2026 10:00:00 GMT"},
        {"id": "story-B", "title": "Other story", "summary": "More details",
         "link": "https://example.org/b", "published": "Sat, 31 Oct 2026 09:00:00 GMT"},
    ]


@pytest.mark.asyncio
async def test_classic_page_renders_fixed_grid_and_navigation_by_keyboard():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.press("m")
            await pilot.pause()
            screen = app.query_one("#classic_page")
            assert screen.has_focus
            assert screen.render().plain.count("\n") == 24
            assert "P100" in screen.render().plain.splitlines()[0]
            app.classic_click(5, 5)  # first directory item in left column
            assert app.current_page_id == "101"
            app.render_feed("101", sample(), "NEWS", app.request_id)
            assert app.view_mode == "list"
            await pilot.press("down")
            assert app.selected_entry == 1
            await pilot.press("enter")
            assert app.view_mode == "article"
            assert app.selected_entry == 1
            assert app.reading.is_read("101", sample()[1])
            await pilot.press("escape")
            assert app.view_mode == "list"
            assert screen.has_focus


@pytest.mark.asyncio
async def test_bookmark_save_remove_and_restart_across_page_901():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", sample(), "NEWS", app.request_id)
            app.query_one("#main_list", ListView).index = 0
            await pilot.press("enter")
            await pilot.press("b")
            assert app.reading.is_bookmarked("101", sample()[0])
            await pilot.press("k")
            assert app.current_page_id == "901"
            assert len(app.entries) == 1
            assert app.entries[0]["source_page"] == "101"
            app.query_one("#main_list", ListView).index = 0
            await pilot.press("enter")
            await pilot.press("b")
            assert not app.reading.bookmarks
            await pilot.press("escape")
            assert app.view_mode == "list"
            assert not app.entries
        restarted = TeletextApp()
        assert not restarted.reading.bookmarks
        assert restarted.reading.is_read("101", sample()[0])


@pytest.mark.asyncio
async def test_newswire_shows_cached_sources_then_refreshes():
    calls = []
    def fake_wire(self, request_id):
        calls.append(request_id)
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None), patch.object(TeletextApp, "fetch_wire", fake_wire):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", sample(), "NEWS", app.request_id)
            app.load_page("500")
            app.render_feed("500", [{"id": "z", "title": "Tech",
                                     "link": "https://example.org/z",
                                     "published": "Sat, 31 Oct 2026 12:00:00 GMT"}], "TECH", app.request_id)
            await pilot.press("g")
            assert app.current_page_id == "900"
            assert app.view_mode == "list"
            assert [item["source_page"] for item in app.entries] == ["500", "101", "101"]
            assert calls == [app.request_id]
            await pilot.press("r")
            assert len(calls) == 2


@pytest.mark.asyncio
async def test_classic_fasttext_bar_and_reveal_hold_controls():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("m")
            app.classic_click(5, 24)
            assert app.current_page_id == "101"
            app.render_feed("101", sample(), "NEWS", app.request_id)
            app.classic_key("enter")
            assert app.view_mode == "article"
            screen = app.query_one("#classic_page")
            assert "SOURCE:" not in screen.render().plain.splitlines()[6]
            await pilot.press("v")
            assert "SOURCE:" in screen.render().plain.splitlines()[6]
            await pilot.press("h")
            assert app.hold_page
            await pilot.press("h")
            assert not app.hold_page


@pytest.mark.asyncio
async def test_builtin_help_page_902_is_offline_and_reveals_secret():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None), patch.object(TeletextApp, "fetch_wire", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.load_page("902")
            assert app.view_mode == "help"
            assert app.current_page_id == "902"
            await pilot.press("m")
            screen = app.query_one("#classic_page")
            assert "P902" in screen.render().plain.splitlines()[0]
            assert "YOUR NEWS IS YOURS TO KEEP" not in screen.render().plain
            await pilot.press("v")
            assert "YOUR NEWS IS YOURS TO KEEP" in screen.render().plain
            await pilot.press("home")
            assert app.current_page_id == "100"
