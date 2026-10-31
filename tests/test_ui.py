"""Headless terminal interaction tests (run when Textual is installed)."""
import time
from unittest.mock import patch

import pytest

pytest.importorskip("textual")
pytest.importorskip("feedparser")

from ceetex import TeletextApp, STALE_SECONDS
from textual.widgets import ListView


@pytest.fixture(autouse=True)
def isolated_feed_disk_cache(tmp_path, monkeypatch):
    """Ensure headless interaction tests do not share persistent feed state."""
    monkeypatch.setattr(
        "ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path / "cache"),
    )
    monkeypatch.setattr(
        "ceetex_reading.user_data_dir", lambda *a, **kw: str(tmp_path / "reading"),
    )


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
            app.selected_entry = 2
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


@pytest.mark.asyncio
async def test_article_back_and_page_revisit_restore_cache_selection_and_focus():
    calls = []
    def no_fetch(self, page_id, url, request_id):
        calls.append(page_id)

    with patch.object(TeletextApp, "fetch_feed", no_fetch):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(35), "NEWS", app.request_id)
            await pilot.press("n")
            listview = app.query_one("#main_list", ListView)
            listview.index = 3
            await pilot.press("enter")
            assert app.view_mode == "article"
            assert app.selected_entry == 18
            await pilot.press("escape")
            assert app.view_mode == "list"
            assert app.current_subpage == 1
            assert listview.index == 3
            assert listview.has_focus
            assert calls == ["101"]

            await pilot.press("home")
            app.load_page("101")
            assert calls == ["101"]
            assert app._signal() == "CACHED"
            await pilot.press("ctrl+left")
            assert app.current_page_id == "100"


@pytest.mark.asyncio
async def test_failed_article_refresh_keeps_article_visible_offline():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(2), "NEWS", app.request_id)
            app.query_one("#main_list", ListView).index = 1
            await pilot.press("enter")
            assert app.view_mode == "article"
            app.action_refresh()
            app.show_error("101", "OFFLINE", app.request_id)
            assert app.view_mode == "article"
            assert app.selected_entry == 1
            assert app._signal() == "OFFLINE/CACHED"


@pytest.mark.asyncio
async def test_malicious_feed_markups_stay_plain_text_in_views():
    from textual.widgets import Static
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", [{
                "title": "[bold red]FAKE MARKUP[/bold red] &lt;real&gt;",
                "summary": "<p>safe [reverse]text</p><script>INJECT</script>",
                "link": "https://example.org/story",
            }], "FIXTURE", app.request_id)
            await pilot.press("enter")
            assert app.view_mode == "article"
            await pilot.pause()
            # The summary parser must remove embedded scripts but retain
            # literal Rich-formatting strings as ordinary text.
            assert "INJECT" not in str(app.query_one("#article_view", Static).render())


def test_user_configuration_overrides_bundled_files_regardless_of_cwd(tmp_path, monkeypatch):
    import json
    bundle = tmp_path / "bundle"
    user = tmp_path / "user-config"
    other = tmp_path / "other"
    bundle.mkdir()
    user.mkdir()
    other.mkdir()

    (bundle / "pages.json").write_text(json.dumps({
        "100": ["INDEX", ""], "101": ["BUNDLED NEWS", "https://example.org/bundled"],
        "130": ["SPORT", "https://example.org/sport"]}), encoding="utf-8")
    (user / "pages.json").write_text(json.dumps({
        "101": ["USER NEWS", "https://example.org/user"],
        "102": ["LOCAL WEATHER", "https://example.org/weather"],
        "130": ["SPORT", "https://example.org/sport"]}), encoding="utf-8")
    (user / "fasttext.json").write_text('{"red": "102"}', encoding="utf-8")
    (user / "settings.json").write_text(
        '{"classic_mode": true, "auto_subpages": true, "rotation_seconds": 7}', encoding="utf-8")

    monkeypatch.setattr("ceetex.ROOT", bundle)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *a, **kw: str(user))
    monkeypatch.chdir(other)
    app = TeletextApp()
    assert app.pages["101"][0] == "USER NEWS"
    assert app.pages["100"] == ["INDEX", ""]
    assert app.fasttext_pages["red"] == "102"
    assert app.classic_mode and app.auto_rotate and app.rotation_seconds == 7

    (user / "pages.json").write_text("{BROKEN", encoding="utf-8")
    fallback = TeletextApp()
    assert fallback.pages["101"][0] == "BUNDLED NEWS"
    assert fallback.config_warnings
    (user / "pages.json").unlink()
    assert TeletextApp().pages["101"][0] == "BUNDLED NEWS"


def test_invalid_config_entries_cannot_break_index(tmp_path, monkeypatch):
    import json
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "pages.json").write_text(json.dumps({
        "100": ["INDEX", ""], "101": ["VALID", "https://example.org"],
        "banana": ["BAD", ""], "١٢٣": ["BAD", ""],
        "102": "not-a-channel", "103": ["missing url"]
    }), encoding="utf-8")
    monkeypatch.setattr("ceetex.ROOT", bundle)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *a, **kw: str(tmp_path / "absent"))
    app = TeletextApp()
    assert sorted(app.pages) == ["100", "101", "900", "901"]
    assert len(app.config_warnings) == 4


@pytest.mark.asyncio
async def test_history_can_restore_invalid_page_without_fetch_or_crash():
    calls = []
    def no_fetch(self, page_id, url, request_id):
        calls.append(page_id)

    with patch.object(TeletextApp, "fetch_feed", no_fetch):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("999")
            assert app.view_mode == "error"
            await pilot.press("home")
            assert app.current_page_id == "100"
            await pilot.press("ctrl+left")
            assert app.current_page_id == "999"
            assert app.view_mode == "error"
            await pilot.press("ctrl+right")
            assert app.current_page_id == "100"
            assert calls == []


@pytest.mark.asyncio
async def test_invalid_channel_is_a_real_history_entry():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(3), "NEWS", app.request_id)
            app.load_page("999")
            assert app.view_mode == "error"
            await pilot.press("ctrl+left")
            assert app.current_page_id == "101"
            assert app.view_mode == "list"
            await pilot.press("ctrl+right")
            assert app.current_page_id == "999"
            assert app.view_mode == "error"


@pytest.mark.asyncio
async def test_classic_mode_keeps_highlighted_global_article():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(40), "NEWS", app.request_id)
            await pilot.press("n")
            lst = app.query_one("#main_list", ListView)
            lst.index = 3   # global article 18 on responsive subpage 2
            await pilot.press("m")
            assert app.classic_mode
            assert app.current_subpage == 2
            assert app.selected_entry == 18
            assert lst.index == 0
            await pilot.press("m")
            assert not app.classic_mode
            assert app.current_subpage == 1
            assert lst.index == 3


@pytest.mark.asyncio
async def test_dialled_channel_finishes_with_list_focus():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.feed_cache["101"] = __import__("ceetex").FeedSnapshot(
                fixture_entries(3), time.time(), "NEWS",
            )
            # Let Textual settle the initial ListView focus before typing.
            await pilot.pause()
            assert app.query_one("#main_list", ListView).has_focus
            await pilot.press("1", "0", "1")
            await pilot.pause()
            assert app.current_page_id == "101", (
                app.query_one("#dialer").value,
                app.focused.id if app.focused else None,
                [(x.page_id, x.mode) for x in app.history],
            )
            assert app.query_one("#main_list", ListView).has_focus


@pytest.mark.asyncio
async def test_refresh_keeps_story_identity_when_feed_reorders_or_removes_it():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            items = [
                {"id": f"guid-{i}", "title": f"Story {i}", "summary": "Text"}
                for i in range(3)
            ]
            app.load_page("101")
            app.render_feed("101", items, "NEWS", app.request_id)
            app.query_one("#main_list", ListView).index = 1
            await pilot.press("enter")
            assert app.selected_entry == 1
            app.action_refresh()
            app.render_feed("101", [items[1], items[2], items[0]], "NEWS", app.request_id)
            assert app.view_mode == "article"
            assert app.selected_entry == 0
            app.action_refresh()
            app.render_feed("101", [items[0], items[2]], "NEWS", app.request_id)
            assert app.view_mode == "list"
            assert app.selected_entry == -1


@pytest.mark.asyncio
async def test_304_revalidation_preserves_open_story_and_clears_offline_flag():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(2), "NEWS", app.request_id, '"old"')
            app.query_one("#main_list", ListView).index = 1
            await pilot.press("enter")
            app.feed_cache["101"].offline = True
            app.action_refresh()
            app.revalidate_feed("101", app.request_id, '"new"', None)
            assert app.view_mode == "article"
            assert app.selected_entry == 1
            assert not app.feed_cache["101"].offline
            assert app.feed_cache["101"].etag == '"new"'
            assert app._signal() == "CACHED"


def test_invalid_feed_url_ignored_with_warning(tmp_path, monkeypatch):
    import json
    (tmp_path / "pages.json").write_text(json.dumps({
        "101": ["NEWS", "https://example.org/rss"],
        "102": ["LOCAL", "file:///etc/passwd"],
        "103": ["BROKEN", "javascript:alert(1)"],
    }))
    monkeypatch.setattr("ceetex.ROOT", tmp_path)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *a, **kw: str(tmp_path / "absent"))
    app = TeletextApp()
    assert sorted(app.pages) == ["100", "101", "900", "901"]
    assert any("invalid feed URL" in msg for msg in app.config_warnings)
    assert all(page in app.pages for page in app.fasttext_pages.values())


def test_invalid_settings_generate_warnings(tmp_path, monkeypatch):
    (tmp_path / "settings.json").write_text(
        '{"auto_subpages": "yes", "classic_mode": 1, "rotation_seconds": -20}'
    )
    monkeypatch.setattr("ceetex.ROOT", tmp_path)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *a, **kw: str(tmp_path / "absent"))
    app = TeletextApp()
    assert len([w for w in app.config_warnings if "settings.json" in w]) == 3
    assert not app.classic_mode and not app.auto_rotate
    assert app.rotation_seconds == 10


@pytest.mark.asyncio
async def test_classic_viewport_is_40_by_25_cells_when_terminal_allows():
    with patch.object(TeletextApp, "fetch_feed", lambda *_: None):
        app = TeletextApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.press("m")
            await pilot.pause()
            frame = app.query_one("#teletext_screen")
            assert frame.size.width == 40
            assert frame.size.height == 25
            await pilot.press("m")
            await pilot.pause()
            assert frame.size.width == 100
            assert frame.size.height == 35


@pytest.mark.asyncio
async def test_persisted_feed_restores_without_fetch_after_app_restart():
    calls = []
    def no_fetch(self, page_id, url, request_id):
        calls.append(page_id)

    with patch.object(TeletextApp, "fetch_feed", no_fetch):
        first = TeletextApp()
        async with first.run_test():
            first.load_page("500")
            first.render_feed("500", fixture_entries(3), "HN", first.request_id)
        second = TeletextApp()
        async with second.run_test():
            second.load_page("500")
            assert second.view_mode == "list"
            assert second.entries[0]["title"].startswith("Headline")
            assert second._signal() == "CACHED"
        assert calls == ["500"]


@pytest.mark.asyncio
async def test_auto_refresh_is_opt_in_and_does_not_blank_open_article():
    calls = []
    def no_fetch(self, page_id, url, request_id):
        calls.append(page_id)
    with patch.object(TeletextApp, "fetch_feed", no_fetch):
        app = TeletextApp()
        async with app.run_test() as pilot:
            app.load_page("101")
            app.render_feed("101", fixture_entries(3), "NEWS", app.request_id)
            app.query_one("#main_list", ListView).index = 1
            await pilot.press("enter")
            assert app.view_mode == "article"
            assert not app.auto_refresh_seconds
            app.auto_refresh_seconds = 60
            app.next_auto_refresh = 0
            app._tick()
            assert app.fetching
            assert app.view_mode == "article"
            assert app.query_one("#article_scroll").display
            app._tick()
            assert calls == ["101", "101"]


def test_auto_refresh_settings_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex.ROOT", tmp_path)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *a, **kw: str(tmp_path / "absent"))
    (tmp_path / "settings.json").write_text('{"auto_refresh_seconds": 120}')
    assert TeletextApp().auto_refresh_seconds == 120
    (tmp_path / "settings.json").write_text('{"auto_refresh_seconds": 2}')
    app = TeletextApp()
    assert app.auto_refresh_seconds == 0
    assert any("auto_refresh_seconds" in w for w in app.config_warnings)
