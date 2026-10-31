import unittest
from ceetex_core import PageState, next_subpage, page_count, subpage_entries, validate_fasttext


class TeletextCoreTests(unittest.TestCase):
    def test_subpage_counts_and_boundaries(self):
        self.assertEqual(page_count(0, 9), 1)
        self.assertEqual(page_count(9, 9), 1)
        self.assertEqual(page_count(10, 9), 2)
        self.assertEqual(page_count(150, 15), 10)
        with self.assertRaises(ValueError):
            page_count(10, 0)

    def test_subpage_contents_keep_global_indexes(self):
        entries = list(range(25))
        self.assertEqual(subpage_entries(entries, 0, 9), list(enumerate(range(9))))
        self.assertEqual(subpage_entries(entries, 2, 9), [(18 + i, 18 + i) for i in range(7)])
        with self.assertRaises(IndexError):
            subpage_entries(entries, 3, 9)

    def test_rotation_wraps_both_directions(self):
        self.assertEqual(next_subpage(2, 3, 1), 0)
        self.assertEqual(next_subpage(0, 3, -1), 2)
        self.assertEqual(next_subpage(1, 3, 1), 2)

    def test_navigation_states_keep_exact_article(self):
        state = PageState("101", "article", 3, 48)
        self.assertEqual(state.subpage, 3)
        self.assertEqual(state.selected_entry, 48)
        self.assertNotEqual(state, PageState("101", "list", 3, 48))

    def test_fasttext_overrides_validate_existing_pages(self):
        pages = {"100": [], "101": [], "102": [], "130": [], "190": [], "500": []}
        defaults = {"red": "101", "green": "130", "yellow": "102", "cyan": "190"}
        result = validate_fasttext({"red": "500", "green": "999", "yellow": 102, "cyan": "١٩٠"}, pages, defaults)
        self.assertEqual(result, {"red": "500", "green": "130", "yellow": "102", "cyan": "190"})


if __name__ == '__main__':
    unittest.main()


def test_mosaic_heading_is_two_rows_and_respects_column_limit():
    from ceetex_core import mosaic_heading
    for text in ("NEWS HEADLINES", "HACKER NEWS", "WEATHER", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", ""):
        lines = mosaic_heading(text, 40).split("\n")
        assert len(lines) == 2
        assert all(len(line) <= 40 for line in lines)
    assert "█" in mosaic_heading("A", 40)


def test_plain_feed_text_removes_markup_scripts_controls_and_ansi():
    from ceetex_core import clean_feed_text
    assert clean_feed_text("&lt;NEWS&gt; [red]Hi[/red]") == "<NEWS> [red]Hi[/red]"
    summary = '<p>Safe &amp; sound <b>[blue]text</b></p><script>NOPE</script><style>HIDE</style><p>More<br>lines</p>'
    assert clean_feed_text(summary, html_content=True) == "Safe & sound [blue]text More lines"
    assert clean_feed_text("ok\x1b[31mred\x1b[0m\u202e\x00") == "okred"
    assert clean_feed_text(None) == ""
    assert clean_feed_text("A < B and C > D") == "A < B and C > D"
