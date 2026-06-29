# ⏱ TimeTracker

Automatic time tracking for Windows — records every program and window you use, categorizes activity, and presents interactive stats in your browser.

[中文文档](README.zh-CN.md)

## Features

- **Auto-tracking** — runs in the background, logs foreground window activity by process name and window title
- **Smart classification** — 100+ built-in rules covering development, office, design, browsers, chat, gaming, and media
- **Idle detection** — pauses automatically when you step away, resumes when you're back
- **Video detection** — identifies video players and streaming sites for separate categorization
- **Interactive stats** — donut/bar charts, program rankings, category breakdowns
- **Timeline** — activity log with a zoomable, draggable 24h timeline view
- **System tray** — minimizes to tray with right-click menu
- **Portable** — all data (config, database, icons) stays in the executable's directory

## Quick Start

### Run from source

```bash
pip install -r tracker/requirements.txt
python tracker/main.py
```

### Build portable exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TimeTracker tracker/main.py
```

Run `dist/TimeTracker.exe`. Data files (`config.json`, `tracker.db`, `icons/`) are created automatically next to the exe.

### Download

Grab the latest `TimeTracker.exe` from the [Releases](https://github.com/your-username/your-repo/releases) page, or build it yourself as described above.

## Usage

1. Launch the app — a clock icon 🕐 appears in the system tray
2. It automatically tracks your foreground window activity
3. **Right-click tray icon → Open Stats** to view in your browser
4. **Right-click → Pause/Resume** to temporarily stop tracking
5. **Right-click → Settings** to open `config.json` for rule editing

### Stats page

- **Today / Week / Month** — switch between time ranges
- **By Category / By Program** — toggle donut or bar chart view
- **Drill-down** — click a category to see its programs in detail
- **Timeline** — chronological activity feed
- **⚙ Settings** — edit classification rules directly in-page

## Classification Rules

Rules live in `config.json` under the `rules` array. Each rule:

```json
{
  "process": "chrome.exe",
  "title_pattern": "GitHub|Jira|Stack Overflow",
  "category": "Work"
}
```

- `process` — executable name (case-insensitive)
- `title_pattern` — optional regex on window title (empty = matches all windows)
- `category` — must match a key in `categories` (colours defined there)

Rules are evaluated in order; **title-pattern rules beat process-only rules**, so browsers can be split by what page is open.

You can also edit rules directly from the stats page (⚙ button) without touching `config.json`.

## Project Structure

```
tracker/
├── main.py              # Entry: tray + timer + orchestration
├── config.py            # config.json read/write + defaults
├── storage.py           # SQLite CRUD
├── monitor.py           # Foreground window polling
├── classifier.py        # Rule-based window classification
├── idle_detector.py     # Idle + video detection
├── icon_extractor.py    # Program icon extraction + disk cache
├── stats_html.py        # HTML stats page generator + HTTP server
├── tray.py              # System tray (QSystemTrayIcon)
├── requirements.txt
└── tests/               # pytest suite (17 tests)
```

## Tech Stack

| Component | Choice |
|-----------|--------|
| Runtime | Python 3.13 |
| GUI | PySide6 (Qt for Python) — system tray only |
| Database | SQLite (WAL mode) |
| Charts | Chart.js via local HTTP server |
| Icon extraction | Windows SHGetFileInfo API |
| Packaging | PyInstaller (single-file exe) |

## License

MIT
