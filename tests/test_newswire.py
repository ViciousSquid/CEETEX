"""Newswire merging: dedupe, ordering, provenance and bound."""
from datetime import datetime, timezone

from ceetex_newswire import MAX_WIRE_ENTRIES, MAX_WIRE_SOURCES, merge_feeds


def test_newest_first_preserves_source_and_deduplicates_urls():
    a = {"id": "first", "title": "First", "link": "https://x.example/1",
         "published": "Sat, 31 Oct 2026 10:00:00 GMT"}
    b = {"id": "second", "title": "Second", "link": "https://x.example/2",
         "published": "Sat, 31 Oct 2026 11:00:00 GMT"}
    merged = merge_feeds([("101", "NEWS", [a, b]), ("300", "WORLD", [a])])
    assert [story["title"] for story in merged] == ["Second", "First"]
    assert merged[0]["source_page"] == "101"
    assert merged[0]["source_name"] == "NEWS"
    assert "source_page" not in a


def test_bounded_feed_merge_and_malformed_entries():
    source_items = [{"id": str(i), "title": str(i)} for i in range(250)]
    sources = [(f"{100+i:03d}", "FEED", source_items + [None]) for i in range(MAX_WIRE_SOURCES + 5)]
    merged = merge_feeds(sources)
    assert len(merged) == MAX_WIRE_ENTRIES
    assert all(story["source_page"] == "100" for story in merged)


def test_iso_dates_sort_before_undated_entries():
    entries = [
        {"id": "none", "title": "Undated"},
        {"id": "a", "title": "A", "published": "2026-10-31T17:00:00+00:00"},
    ]
    assert merge_feeds([("101", "NEWS", entries)])[0]["id"] == "a"
