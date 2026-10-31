# CEETEX controls

CEETEX is a terminal-native Ceefax/Teletext-style RSS reader. Type a three-digit page
number at any time to tune to a feed, or use the controls below.

## Keyboard reference

| Key | Action | Where it works |
| --- | --- | --- |
| **0–9** | Dial a three-digit page number (e.g. `101`, `500`) | Anywhere; typing digits focuses the dialler |
| **Up / Down** | Move the highlighted selection | Directory or headline list |
| **Enter** | Open the highlighted directory page or headline | Directory or headline list |
| **Mouse click** | Select a directory page or headline | Directory or headline list |
| **Escape** | Return from an article to its headlines; otherwise return to P100 | Anywhere |
| **Home** | Go straight to P100 (main index) | Anywhere |
| **F1** | Red FastText: **NEWS** (default P101) | Anywhere |
| **F2** | Green FastText: **SPORT** (default P130) | Anywhere |
| **F3** | Yellow FastText: **WEATHER** (default P102) | Anywhere |
| **F4** | Cyan FastText: **TRAVEL** (default P190) | Anywhere |
| **N** | Next numbered subpage | Headline list |
| **P** | Previous numbered subpage | Headline list |
| **A** | Toggle automatic subpage rotation | Anywhere; rotation acts on headline lists |
| **M** | Toggle the classic 40-column view | Anywhere |
| **Ctrl+Left** | Go back in navigation history | Anywhere |
| **Ctrl+Right** | Go forward in navigation history | Anywhere |
| **O** | Open the current article's full URL in the system browser | Article only |
| **R** | Refresh the currently selected RSS feed | Feed page |
| **Q** | Quit CEETEX | Anywhere |

FastText's red, green, yellow and cyan on-screen buttons are also clickable.
They always take you to their configured page, regardless of the currently
selected headline. The colour keys F1–F4 are Teletext navigation shortcuts, not
operating-system function keys: your terminal may require `Fn` for function keys.

## Pages, subpages and history

- **P100** is the directory. Dial `100` or press **Home** to see every channel.
- **P101/1**, **P101/2**, and so on are subpages within a feed. **N** and **P**
  wrap at the last and first subpages. The subpage count depends on the number
  of articles in the feed.
- The default responsive view has **15 headlines per subpage**. Classic mode
  uses **9 headlines per subpage**, a 40-column width and two-line Unicode
  mosaic headings. It approximates Teletext; it is not a broadcast decoder.
- **Escape** returns from an article to the headline list, keeping its selected
  headline. History also records page and subpage changes, so you can navigate
  with **Ctrl+Left / Ctrl+Right**.
- Headline lists are kept in memory for the current session. Returning to a
  previously visited page does not normally download its feed again. Press **R**
  to request fresh data.

## Display indicators

The date and clock update every second. The signal field shows:

| Status | Meaning |
| --- | --- |
| `INDEX` | Main page directory (P100) |
| `TUNING` | An RSS request is in progress |
| `LIVE` | Feed data has just been fetched |
| `CACHED` | Revisited feed data was served from memory |
| `STALE` | The feed snapshot is at least 15 minutes old |
| `OFFLINE/CACHED` | A refresh failed; CEETEX retained an earlier snapshot |
| `NO SIGNAL` | No data is available for the current page |

The clock is your machine's local time; it is not the news provider's timestamp.

## Configuration

### Page directory

Edit `pages.json` next to `ceetex.py`. Each three-digit code maps to a
channel title and an RSS/Atom URL. Page `100` is reserved for the main index.

### FastText destinations

Copy `fasttext.example.json` to `fasttext.json` in the same directory.
Example:

```json
{
  "red": "101",
  "green": "130",
  "yellow": "102",
  "cyan": "190"
}
```

Destinations must refer to valid existing three-digit page IDs. Invalid entries
use the default mapping.

### Startup display preferences

Copy `settings.example.json` to `settings.json`. Example:

```json
{
  "classic_mode": false,
  "auto_subpages": false,
  "rotation_seconds": 10
}
```

`rotation_seconds` accepts values from 2 to 300 seconds. Pressing **M** or
**A** changes that setting for the running session only; it does not overwrite
`settings.json`. Automatic rotation affects headline subpages, not articles
or the directory.

## Configuration location

To place custom channels and settings outside the project checkout, use
your **per-user CEETEX configuration directory**, as reported by:

```sh
python -c "from platformdirs import user_config_dir; print(user_config_dir('ceetex', appauthor=False))"
```

Copy your custom `pages.json`, `fasttext.json` and `settings.json`
there. CEETEX checks this directory first, then falls back to files next to
`ceetex.py`. The bundled `pages.json` is therefore still a usable default.
Invalid user JSON displays a warning and falls back to the bundled file.
Launching from another working directory does not change the lookup order.

## Troubleshooting

If function keys are intercepted by your terminal, click the corresponding
FastText colour on-screen. If a feed shows `NO SIGNAL` or a connection error,
check the URL in `pages.json` and press **R** to retry.
