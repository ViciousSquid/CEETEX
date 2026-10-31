"""Persistent RSS cache: atomic writes, invalidation, and hostile files."""
from pathlib import Path

from ceetex_cache import load_feed, save_feed, MAX_CACHE_BYTES


def test_persist_and_restore_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path))
    entries = [{"id": "guid-1", "title": "A", "summary": "Details", "link": "https://x.test/1"}]
    assert save_feed("101", entries, 100.0, "BBC", "https://example.org/rss", '"v1"')
    result = load_feed("101")
    assert result is not None
    assert result.entries == entries
    assert result.fetched_at == 100.0
    assert result.etag == '"v1"'
    assert result.url == "https://example.org/rss"


def test_corrupt_or_oversized_cache_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path))
    path = tmp_path / "101.json"
    path.write_text("{INVALID", encoding="utf-8")
    assert load_feed("101") is None
    path.write_bytes(b"x" * (MAX_CACHE_BYTES + 1))
    assert load_feed("101") is None


def test_cache_limits_entries_and_omits_unknown_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path))
    items = [{"id": str(i), "title": "X", "not_for_cache": "secret"} for i in range(500)]
    assert save_feed("500", items, 123, "HN", "https://example.org/rss")
    restored = load_feed("500")
    assert len(restored.entries) == 300
    assert "not_for_cache" not in restored.entries[0]


def test_cache_rejects_path_traversal(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr("ceetex_cache.user_cache_dir", lambda *a, **kw: str(tmp_path))
    with pytest.raises(ValueError):
        load_feed("../")
    with pytest.raises(ValueError):
        save_feed("../../etc", [], 0, "", "https://example.org/feed")
