# CEETEX

#### Ceefax/Teletext engine for modern web feeds

A bridge between today's news feeds and the low-resolution **Mode 7 Teletext aesthetic**. Dial three-digit pages, read stories, explore an all-channel newswire, and save articles for later in a keyboard-first terminal interface.

![CEETEX screenshot](https://github.com/user-attachments/assets/87f7e7d5-a9a5-43c9-8ad8-e678f49c1465)

## Install and run

Requires Python 3.11 or newer.

### macOS / Linux (recommended)

From the CEETEX checkout or extracted ZIP directory, create an isolated Python
environment and install the requirements **before** starting the application:

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ceetex.py
~~~

Next time you open Terminal in this directory:

~~~sh
source .venv/bin/activate
python ceetex.py
~~~

Alternatively, install CEETEX itself inside that virtual environment to use the
`ceetex` command from any working directory while the environment is activated:

~~~sh
python -m pip install .
ceetex
~~~

Do not use `sudo pip` or `--break-system-packages`: macOS and Homebrew
Python installations may be externally managed. A virtual environment also
ensures that `python` and `pip` refer to the same installation.

### Windows (PowerShell)

~~~powershell
py -3 -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python ceetex.py
~~~

If `Activate.ps1` is blocked by PowerShell's execution policy, run the
virtual-environment interpreter directly without activating:

~~~powershell
.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.venv\\Scripts\\python.exe ceetex.py
~~~

### Troubleshooting

`ModuleNotFoundError: No module named 'platformdirs'` (or `textual`,
`feedparser` or `rich`) means the dependencies are not installed for the
interpreter launching CEETEX. Activate `.venv`, then rerun
`python -m pip install -r requirements.txt`. You can verify the interpreter
with `python -c "import sys; print(sys.executable)"`.

When running from source, bundled defaults are loaded relative to `ceetex.py`.
Installed distributions carry the default channel directory as a package resource. To override them without editing
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
- **M** — switch between responsive mode and a full **40-column × 25-row** interactive Teletext screen.
- **G / P900** — browse the **Newswire**, which aggregates up to 24 RSS channels and sorts headlines newest first.
- **K / P901** — open your **Bookmarks** page.
- **P902** — built-in Teletext help page and interactive colour/mosaic/reveal demonstration (also works offline).
- **B** — save or remove the article you're reading.
- **V** — reveal concealed source information in classic article pages.
- **H** — HOLD/release automatic Teletext subpage rotation.
- **Ctrl+Left / Ctrl+Right** — step backwards or forwards through page, subpage, and article history.
- **R** — refresh the current feed.
- **Q** — quit.

The clock updates every second. The signal indicator shows **TUNING**, **LIVE**, **CACHED** (revisited without refetching), **STALE** (older than 15 minutes), **OFFLINE/CACHED** (a refresh failed but earlier data is available), or **NO SIGNAL**.

Unread stories have a prominent dot (which flashes in classic mode); already-read stories have a muted marker, and bookmarked stories show a diamond. Opening an article marks it read. The read/unread and bookmark state is saved locally on your computer.

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

Classic mode uses a **40×25 per-character colour grid**, a familiar blue page header, a red/green/yellow/cyan FastText footer, flashing indicators, concealed text reveal, double-row block headings and a two-column index. Mouse clicks and arrow keys work on the classic screen itself. It remains a terminal interpretation: the original broadcast Mode 7 pixels and physical double-height character cells cannot be reproduced exactly in arbitrary terminal fonts.

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

## Your newswire: page 900

Dial **900** or press **G** to see the latest headlines combined from the channels in `pages.json`. Duplicate article URLs are removed, dated items are sorted newest first, and each headline carries its original channel number (for example P101). CEETEX uses cached headlines immediately when available, then refreshes up to 24 source feeds in parallel (maximum three active HTTP fetches). Offline newswire contents therefore depend on which feeds you've previously downloaded. The wire is a reading index, not a replacement for the individual source pages.

## Saved stories: page 901

Press **B** while reading an article to save or remove it. **K** or **901** opens bookmarks from any page. Your saved articles and read/unread identities persist in your OS-specific user data directory, separately from the downloaded RSS cache; no account or external bookmarking service is used.

~~~sh
python -c "from platformdirs import user_data_dir; print(user_data_dir('ceetex', appauthor=False))"
~~~

The `reading.json` file can be backed up or removed while CEETEX is closed. It is limited to 250 saved stories and the 5,000 most recently read IDs. News source attribution is retained when a bookmarked story appears on page 901.

## Classic Teletext keys

The classic screen is navigable with **Up/Down/Enter**, click-to-select headlines and index entries, and the four clickable coloured FastText segments along the bottom. **N/P** steps between numbered headline subpages (or index directory subpages if you configure more than 32 channels). **H** holds automatic subpage rotation, and **V** reveals the concealed source field on article pages. While a feed is being fetched, the interface stays responsive; already cached articles remain accessible.
