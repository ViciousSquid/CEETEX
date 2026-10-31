"""Headless terminal interaction tests (run when Textual is installed)."""
import time
from unittest.mock import patch

import pytest

pytest.importorskip("textual")
pytest.importorskip("feedparser")

from ceetex import TeletextApp, STALE_SECONDS
from textual.widgets import ListView


def fixture_entries(count=24):
    return [{"title": f"Headline {i} [yellow]", "summary": f"Summary {i}", "link": f"https://example.org/{i}"} for i in range(count)]


@pytest.mark.asyncio
async def test_fasttext_keyboard_and_click():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(90, 30)) as pilot:
            assert len(app.index_mapping) == len(app.pages) - 1  # P100 is the index, not an entry
            await pilot.press("f1")
            assert app.current_page_id == "101"
            await pilot.click("#fasttext_green")
            assert app.current_page_id == "130"
            await pilot.press("home")
            assert app.current_page_id == "100"


@pytest.mark.asyncio
async def test_subpages_classic_and_history_without_reload():
    calls = []
    def no_fetch(self, page_id, url, request_id):
        calls.append((page_id, request_id))

    with patch.object(TeletextApp, "fetch_feed", no_fetch):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(), "Fixtures", app.request_id)
            await pilot.pause()
            await pilot.press("m")
            assert app.classic_mode and app.page_size == 9
            await pilot.press("n")
            assert app.current_subpage == 1
            await pilot.press("n")
            assert app.current_subpage == 2
            await pilot.press("n")
            assert app.current_subpage == 0
            lst = app.query_one("#main_list", ListView)
            lst.index = 2
            await pilot.press("enter")
            assert app.view_mode == "article"
            assert app.selected_entry == 2
            await pilot.press("escape")
            assert app.view_mode == "list"
            assert lst.index == 2
            assert len(calls) == 1
            await pilot.press("ctrl+right")
            assert app.view_mode == "article"
            assert app.selected_entry == 2
            await pilot.press("ctrl+left")
            assert app.view_mode == "list"


@pytest.mark.asyncio
async def test_clock_status_and_stale_error_ignored():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(80, 30)) as pilot:
            app.load_page("101")
            old_id = app.request_id
            app.load_page("500")
            app.render_feed("500", fixture_entries(), "HN", app.request_id)
            app.show_error("101", "STALE ERROR", old_id)
            assert app.current_page_id == "500" and app.view_mode == "list"
            assert app._signal() == "LIVE"
            app.feed_cache["500"].fetched_at = time.time() - STALE_SECONDS - 1
            assert app._signal() == "STALE"
            app.show_error("500", "OFFLINE", app.request_id)
            assert app._signal() == "OFFLINE/CACHED"
            assert app.view_mode == "list"


def test_optional_settings_defaults_and_validation(tmp_path):
    (tmp_path / "settings.json").write_text('{"classic_mode": true, "auto_subpages": true, "rotation_seconds": 4}')
    with patch("ceetex.ROOT", tmp_path):
        app = TeletextApp()
        assert app.classic_mode is True
        assert app.auto_rotate is True
        assert app.rotation_seconds == 4
    (tmp_path / "settings.json").write_text('{"rotation_seconds": -9, "classic_mode": "yes"}')
    with patch("ceetex.ROOT", tmp_path):
        app = TeletextApp()
        assert app.classic_mode is False
        assert app.rotation_seconds == 10


@pytest.mark.asyncio
async def test_every_directory_entry_is_selectable_including_last_column():
    """The old two-column index could only open its left-hand pages."""
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            expected = sorted((p for p in app.pages if p != "100"), key=int)
            assert app.index_mapping == expected
            view = app.query_one("#main_list", ListView)
            assert len(view.children) == len(expected)
            for target in (expected[0], expected[len(expected)//2], expected[-1]):
                view.index = app.index_mapping.index(target)
                view.focus()
                await pilot.press("enter")
                assert app.current_page_id == target
                await pilot.press("home")
                assert app.current_page_id == "100"
                view = app.query_one("#main_list", ListView)
            assert app.query_one("#directory_header").display
            await pilot.press("f1")
            assert not app.query_one("#directory_header").display


@pytest.mark.asyncio
async def test_superseded_requests_cannot_replace_newer_feed_or_error():
    """Callbacks may arrive out of order, including for the same RSS channel."""
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            items = fixture_entries(3)
            app.load_page("101")
            first = app.request_id
            app.load_page("500")
            latest = app.request_id
            app.render_feed("101", items, "OLD", first)
            app.show_error("101", "OLD FAILURE", first)
            assert app.current_page_id == "500"
            assert app.view_mode == "list" or app.fetching
            app.render_feed("500", items, "CURRENT", latest)
            assert app.feed_cache["500"].source == "CURRENT"
            assert app.view_mode == "list"

            app.action_refresh()
            refresh = app.request_id
            app.render_feed("500", fixture_entries(1), "OUTDATED", latest)
            app.show_error("500", "OLD FAILURE", latest)
            assert app.fetching
            assert app.feed_cache["500"].source == "CURRENT"
            app.render_feed("500", fixture_entries(2), "FRESH", refresh)
            assert app.feed_cache["500"].source == "FRESH"

            app.load_page("101")
            pending = app.request_id
            app.load_page("999")
            assert app.current_page_id == "999" and app.view_mode == "error"
            app.render_feed("101", items, "LATE", pending)
            app.show_error("101", "LATE FAILURE", pending)
            assert app.current_page_id == "999" and app.view_mode == "error"
            assert "101" not in app.feed_cache
            await pilot.press("escape")
            assert app.current_page_id == "100"
