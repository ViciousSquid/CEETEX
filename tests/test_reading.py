"""Bookmark persistence, identity, eviction and corruption tests."""
import json

from ceetex_reading import MAX_BOOKMARKS, MAX_READ_IDS, ReadingState, state_path, story_key


def test_bookmark_and_read_state_survive_restart(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_reading.user_data_dir", lambda *a, **kw: str(tmp_path))
    state = ReadingState.load()
    original = {"id": "story-22", "title": "A title", "link": "https://news.example/a"}
    assert not state.is_read("101", original)
    assert state.mark_read("101", original)
    assert not state.mark_read("101", original)
    assert state.toggle_bookmark("101", {**original, "source_page": "101", "source_name": "NEWS"})
    assert state.save()
    restored = ReadingState.load()
    assert restored.is_read("101", original)
    assert restored.is_read("900", {**original, "source_page": "101"})
    assert restored.is_bookmarked("101", original)
    assert len(restored.bookmarked_entries()) == 1
    assert not restored.toggle_bookmark("900", {**original, "source_page": "101"})
    assert not restored.bookmarks
    assert restored.save()
    assert ReadingState.load().bookmarks == {}


def test_read_and_bookmark_limits():
    state = ReadingState()
    for i in range(MAX_READ_IDS + 200):
        state.mark_read("101", {"id": f"story-{i}"})
    assert len(state.read_ids) == MAX_READ_IDS
    assert not state.is_read("101", {"id": "story-0"})
    for i in range(MAX_BOOKMARKS + 100):
        state.toggle_bookmark("101", {"id": f"saved-{i}", "title": "X"})
    assert len(state.bookmarks) == MAX_BOOKMARKS
    assert state.bookmarked_entries()[0]["id"] == f"saved-{MAX_BOOKMARKS + 99}"


def test_reading_data_corruption_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_reading.user_data_dir", lambda *a, **kw: str(tmp_path))
    state_path().write_text('{invalid', encoding="utf-8")
    assert not ReadingState.load().bookmarks
    state_path().write_text(json.dumps({"version": 1, "read_ids": [1, 2], "bookmarks": {}}))
    assert ReadingState.load().read_ids == []


def test_story_key_uses_original_channel_not_aggregate_page():
    item = {"id": "xyz", "source_page": "101"}
    assert story_key("101", item) == story_key("900", item)
    assert story_key("101", item) != story_key("102", {"id": "xyz"})
