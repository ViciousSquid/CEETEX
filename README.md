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
- **M** — toggle an optional centred, **40-column × 25-row** classic Teletext viewport, with two-row block-character headings. The default is responsive.
- **Ctrl+Left / Ctrl+Right** — step backwards or forwards through page, subpage, and article history.
- **R** — refresh the current feed.
- **Q** — quit.

The clock updates every second. The signal indicator shows **TUNING**, **LIVE**, **CACHED** (revisited without refetching), **STALE** (older than 15 minutes), **OFFLINE/CACHED** (a refresh failed but earlier data is available), or **NO SIGNAL**.

Subpages show nine headlines in 40-column mode or fifteen in responsive mode. Moving between already loaded pages and returning from an article uses the in-memory feed cache rather than downloading again. Snapshots are also persisted in the OS-specific per-user cache directory, so recently viewed pages can be read after restarting the app—even without a network connection. Press R to revalidate the current feed; conditional HTTP requests reuse unchanged content.

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
  "rotation_seconds": 10,
  "auto_refresh_seconds": 0
}
```

Rotation intervals between 2 and 300 seconds are supported. Set `auto_refresh_seconds` to 0 to disable background refresh (the default), or to 60–3600 seconds to periodically revalidate the currently open feed without blanking cached content. The **M** and **A** keys toggle their respective features for the running session; they do not rewrite this file.

Classic mode uses a 40-column by 25-row viewport when the terminal is large enough and Unicode block mosaics to approximate double-height Teletext headings. Terminals cannot actually switch their physical character-cell heights, so this is a visual approximation rather than a broadcast Mode 7 renderer.

## Tests


~~~sh
python -m pip install -r requirements.txt pytest pytest-asyncio
python -m pytest -q
~~~

The tests include pure page-layout logic, a simulated bounded HTTP transport, persistent cache roundtrips, and headless Textual interaction. GitHub Actions runs these on Linux, macOS, and Windows.

CEETEX is inspired by the UK Ceefax service and similar Teletext systems. This is a modern terminal interpretation, not an implementation of a broadcast decoder.

## Feed reliability and offline cache

CEETEX limits individual feed downloads to 2 MiB, uses a 10-second network socket timeout, and permits at most three simultaneous downloads. This timeout is a socket timeout, not a hard guarantee on total network duration. Feed validators (ETag and Last-Modified) minimise unnecessary transfers, and a failed refresh retains existing content.

The persisted cache is stored in the OS-specific user cache directory. Locate it with:

```sh
python -c "from platformdirs import user_cache_dir; print(user_cache_dir('ceetex', appauthor=False))"
```

You can remove this cache directory while CEETEX is not running to discard downloaded headlines. Cached data is bounded to 300 entries per page, and caches are never treated as executable code. Channel URL changes invalidate old cached snapshots.
