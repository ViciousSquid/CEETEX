# CEETEX

#### Ceefax/Teletext engine for modern web feeds

A bridge between today's high-speed data and the low-resolution **Mode 7 Teletext aesthetic**. Customise your RSS channels, dial three-digit pages, and browse the news in a lightweight terminal interface.

![CEETEX screenshot](https://github.com/user-attachments/assets/87f7e7d5-a9a5-43c9-8ad8-e678f49c1465)

## Install and run

Requires Python 3.11 or newer.


~~~sh
python -m pip install -r requirements.txt
python ceetex.py
~~~

Bundled defaults are loaded relative to `ceetex.py`. To override them without editing
the checkout, put custom `pages.json`, `settings.json` and `fasttext.json`
in the OS-specific user configuration directory. Run
`python -c "from platformdirs import user_config_dir; print(user_config_dir('ceetex', appauthor=False))"`
to find it. User overrides take priority; invalid JSON falls back to bundled defaults.

See [the full controls reference](docs/CONTROLS.md) for all key bindings, status indicators and configuration options.

## Using CEETEX

- **Three digits** — dial a channel directly (e.g. `101` for news, `500` for Hacker News).
- **Click a headline / Enter** — read the feed summary.
- **O** — open the current story in your browser.
- **Escape** — return from an article to its headline list; from a list to the main index.
- **Home** — go to index page 100.
- **F1 / F2 / F3 / F4** — red NEWS, green SPORT, yellow WEATHER, cyan TRAVEL FastText links. The four colour buttons are also clickable.
- **N / P** — next or previous numbered subpage. For example, P101/1 and P101/2.
- **A** — toggle subpage auto-rotation (every 10 seconds by default; configurable).
- **M** — toggle an optional centred, **40-character-wide** classic Teletext view, with two-row block-character headings. The default is responsive.
- **Ctrl+Left / Ctrl+Right** — step backwards or forwards through page, subpage, and article history.
- **R** — refresh the current feed.
- **Q** — quit.

The clock updates every second. The signal indicator shows **TUNING**, **LIVE**, **CACHED** (revisited without refetching), **STALE** (older than 15 minutes), **OFFLINE/CACHED** (a refresh failed but earlier data is available), or **NO SIGNAL**.

Subpages show nine headlines in 40-column mode or fifteen in responsive mode. Moving between already loaded pages and returning from an article uses the in-memory feed cache rather than downloading again. Press R to request a new copy.

## Customising channels

Edit `pages.json` to choose channel numbers, titles, and RSS/Atom feed URLs. The entry for page 100 is the built-in directory.

Optionally, copy `fasttext.example.json` to `fasttext.json` and adjust the page numbers:


~~~json
{
  "red": "101",
  "green": "130",
  "yellow": "102",
  "cyan": "190"
}
~~~

FastText destinations must refer to existing three-digit page numbers in `pages.json`. Invalid overrides fall back to the defaults.

## Optional display and rotation defaults

Copy `settings.example.json` to `settings.json` and set your startup preferences:

```json
{
  "classic_mode": false,
  "auto_subpages": false,
  "rotation_seconds": 10
}
```

Rotation intervals between 2 and 300 seconds are supported. The **M** and **A** keys toggle their respective features for the running session; they do not rewrite this file.

40-column classic mode uses Unicode block mosaics to approximate double-height Teletext headings. Terminals cannot actually switch their physical character-cell heights, so this is a visual approximation rather than a broadcast Mode 7 renderer.

## Tests


~~~sh
python -m pip install -r requirements.txt pytest pytest-asyncio
python -m pytest -q
~~~

The tests include pure page-layout logic and headless Textual interaction. GitHub Actions runs these on Linux, macOS, and Windows.

CEETEX is inspired by the UK Ceefax service and similar Teletext systems. This is a modern terminal interpretation, not an implementation of a broadcast decoder.
