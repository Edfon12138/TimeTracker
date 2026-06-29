# Windows 程序运行时间追踪器 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Windows 桌面应用，后台记录所有前台程序的运行时间，按窗口标题自动分类，通过系统托盘和统计面板查看报告。

**Architecture:** Python + PySide6 + SQLite，事件驱动窗口监控（SetWinEventHook），11 个源文件，系统托盘入口，matplotlib 嵌入统计面板。

**Tech Stack:** Python 3.12+, PySide6, pywin32, matplotlib, sqlite3, PyInstaller

## Global Constraints

- 最小记录阈值: 5 秒
- 空闲超时: 5 分钟（可配置 1-30 分钟）
- 数据保留: 默认 90 天（可配置 30/60/90/180/永久）
- WAL 模式 SQLite，写入重试 3 次
- 单实例运行（互斥锁）
- 深色主题: 底色 `#16181D`，表面 `#1E2027`，强调 `#D4956B`

## File Structure

```
tracker/
├── config.py                 # JSON config read/write
├── storage.py                # SQLite CRUD, aggregates, cleanup
├── classifier.py             # Rule-based window title -> category
├── monitor.py                # SetWinEventHook foreground listener
├── idle_detector.py          # GetLastInputInfo idle detection
├── icon_extractor.py         # SHGetFileInfo -> QIcon cache
├── tray.py                   # QSystemTrayIcon + context menu
├── stats_window.py           # QMainWindow: tabs, toolbar, layout
├── charts.py                 # Matplotlib donut/bar charts
├── classifier_edit.py        # Rule table editor dialog
├── main.py                   # Entry point, wires everything
├── config.json               # Default configuration
├── requirements.txt          # Dependencies
└── tests/
    ├── test_config.py        # 3 tests
    ├── test_storage.py       # 6 tests
    └── test_classifier.py    # 8 tests
```

---

### Task 1: 项目初始化 + config.py

**Files:**
- Create: `tracker/config.py`
- Create: `tracker/config.json`
- Create: `tracker/requirements.txt`
- Create: `tracker/tests/__init__.py`
- Create: `tracker/tests/test_config.py`

**Interfaces:**
- Produces: `load_config() -> dict`, `save_config(cfg: dict)`, `DEFAULT_CONFIG`

- [ ] **Step 1: Create directories**

```bash
mkdir -p tracker/tests
```

- [ ] **Step 2: Create `tracker/requirements.txt`**

```
pywin32>=306
PySide6>=6.7.0
matplotlib>=3.9.0
pytest>=8.0.0
```

- [ ] **Step 3: Create `tracker/config.py`**

```python
"""JSON config file read/write with defaults."""
import json
import os
from copy import deepcopy

DEFAULT_CONFIG = {
    "min_duration_sec": 5,
    "idle_timeout_min": 5,
    "retention_days": 90,
    "autostart": False,
    "export_path": "",
    "categories": {
        "工作": {"color": "#7BA78E"},
        "娱乐": {"color": "#D4956B"},
        "浏览": {"color": "#7B9EC7"},
        "通讯": {"color": "#A78BB5"},
        "系统": {"color": "#6B6B6B"},
        "其他": {"color": "#5A5A5A"},
    },
    "rules": [
        {"process": "Code.exe", "title_pattern": None, "category": "工作"},
        {"process": "devenv.exe", "title_pattern": None, "category": "工作"},
        {"process": "WindowsTerminal.exe", "title_pattern": None, "category": "工作"},
        {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow", "category": "工作"},
        {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili", "category": "娱乐"},
        {"process": "steam.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "WeChat.exe", "title_pattern": None, "category": "通讯"},
        {"process": "QQ.exe", "title_pattern": None, "category": "通讯"},
        {"process": "explorer.exe", "title_pattern": None, "category": "系统"},
    ],
    "defaults": {
        "chrome.exe": "浏览",
        "msedge.exe": "浏览",
        "firefox.exe": "浏览",
    },
}

def _config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return deepcopy(DEFAULT_CONFIG)
    with open(path, "r", encoding="utf-8") as f:
        user = json.load(f)
    merged = deepcopy(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in user:
            merged[key] = user[key]
    return merged

def save_config(config: dict) -> None:
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Create `tracker/config.json`**

Write DEFAULT_CONFIG content as initial config.json.

- [ ] **Step 5: Create `tracker/tests/__init__.py`** (empty file)

- [ ] **Step 6: Create `tracker/tests/test_config.py`**

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config as cfg

def test_default_config_has_required_keys():
    c = cfg.DEFAULT_CONFIG
    assert "min_duration_sec" in c
    assert "categories" in c
    assert "rules" in c

def test_load_config_returns_defaults_when_no_file(monkeypatch):
    monkeypatch.setattr(cfg, "_config_path", lambda: "/nonexistent.json")
    c = cfg.load_config()
    assert c["min_duration_sec"] == 5

def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    p = str(tmp_path / "config.json")
    monkeypatch.setattr(cfg, "_config_path", lambda: p)
    c = cfg.load_config()
    c["min_duration_sec"] = 10
    cfg.save_config(c)
    loaded = cfg.load_config()
    assert loaded["min_duration_sec"] == 10
```

- [ ] **Step 7: Run tests**

```bash
cd tracker && python -m pytest tests/test_config.py -v
```

Expected: 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git add tracker/requirements.txt tracker/config.py tracker/config.json tracker/tests/
git commit -m "feat: add config module and project scaffold"
```

---

### Task 2: storage.py — SQLite 数据层

**Files:**
- Create: `tracker/storage.py`
- Create: `tracker/tests/test_storage.py`

**Interfaces:**
- Consumes: `config.load_config()` (for retention_days)
- Produces: `init_db(db_path)`, `insert_activity(...)`, `upsert_daily_summary(...)`, `get_daily_summary(date)`, `get_range_summary(from, to)`, `get_activity_timeline(date)`, `get_program_stats(from, to)`, `cleanup_old_data(days)`, `load_rules_from_db()`, `save_rules_to_db(rules)`

- [ ] **Step 1: Create `tracker/tests/test_storage.py`**

```python
import os, sqlite3, tempfile, pytest, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import storage

@pytest.fixture
def db():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "test.db")
    storage.init_db(p)
    yield p
    try: os.unlink(p); os.rmdir(d)
    except: pass

def test_init_db_creates_tables(db):
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "activity_log" in tables
    assert "daily_summary" in tables
    assert "classification_rules" in tables
    conn.close()

def test_insert_and_query_activity(db):
    aid = storage.insert_activity("chrome.exe", "YouTube", "娱乐",
        "2026-06-29 14:30:00", 600, "2026-06-29")
    assert aid > 0
    tl = storage.get_activity_timeline("2026-06-29")
    assert len(tl) == 1
    assert tl[0]["duration"] == 600

def test_daily_summary_upsert(db):
    storage.upsert_daily_summary("2026-06-29", "工作", 3600)
    storage.upsert_daily_summary("2026-06-29", "工作", 600)
    rows = storage.get_daily_summary("2026-06-29")
    w = [r for r in rows if r["category"] == "工作"][0]
    assert w["total_seconds"] == 4200

def test_range_summary(db):
    storage.upsert_daily_summary("2026-06-28", "工作", 1000)
    storage.upsert_daily_summary("2026-06-29", "工作", 2000)
    rows = storage.get_range_summary("2026-06-28", "2026-06-29")
    assert sum(r["total_seconds"] for r in rows if r["category"] == "工作") == 3000

def test_cleanup_old_data(db):
    storage.insert_activity("t.exe", "t", "其他", "2026-03-01 10:00:00", 100, "2026-03-01")
    storage.insert_activity("t.exe", "t", "其他", "2026-06-29 10:00:00", 100, "2026-06-29")
    storage.cleanup_old_data(30)
    assert len(storage.get_activity_timeline("2026-03-01")) == 0
    assert len(storage.get_activity_timeline("2026-06-29")) == 1

def test_program_stats(db):
    storage.insert_activity("Code.exe", "VS", "工作", "2026-06-29 10:00:00", 3600, "2026-06-29")
    storage.insert_activity("Code.exe", "VS", "工作", "2026-06-29 11:00:00", 1800, "2026-06-29")
    progs = storage.get_program_stats("2026-06-29", "2026-06-29")
    c = [p for p in progs if p["process"] == "Code.exe"][0]
    assert c["total_seconds"] == 5400
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd tracker && python -m pytest tests/test_storage.py -v
```

Expected: all FAIL

- [ ] **Step 3: Create `tracker/storage.py`**

```python
"""SQLite database: init, CRUD, aggregates, cleanup."""
import sqlite3, os, time, threading
from datetime import datetime, timedelta

_local = threading.local()

def _db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db")

def _get_conn(path=None):
    if path is None:
        path = _db_path()
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn

def init_db(db_path=None):
    conn = _get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process TEXT NOT NULL,
            window_title TEXT NOT NULL,
            category TEXT DEFAULT '其他',
            started_at DATETIME NOT NULL,
            duration INTEGER NOT NULL,
            date TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_log(date);
        CREATE INDEX IF NOT EXISTS idx_activity_cat ON activity_log(category, date);
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT NOT NULL, category TEXT NOT NULL,
            total_seconds INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, category)
        );
        CREATE TABLE IF NOT EXISTS classification_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process TEXT NOT NULL, title_pattern TEXT,
            category TEXT NOT NULL, is_user_added INTEGER DEFAULT 0
        );
    """)

def insert_activity(process, window_title, category, started_at, duration, date):
    conn = _get_conn()
    for i in range(3):
        try:
            c = conn.execute(
                "INSERT INTO activity_log (process,window_title,category,started_at,duration,date) VALUES (?,?,?,?,?,?)",
                (process, window_title, category, started_at, duration, date)
            )
            conn.commit()
            return c.lastrowid
        except sqlite3.OperationalError:
            if i == 2: raise
            time.sleep(0.1)

def upsert_daily_summary(date, category, seconds):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO daily_summary (date,category,total_seconds) VALUES (?,?,?) "
        "ON CONFLICT(date,category) DO UPDATE SET total_seconds = total_seconds + ?",
        (date, category, seconds, seconds)
    )
    conn.commit()

def get_daily_summary(date):
    return [dict(r) for r in _get_conn().execute(
        "SELECT category,total_seconds FROM daily_summary WHERE date=? ORDER BY total_seconds DESC", (date,)).fetchall()]

def get_range_summary(date_from, date_to):
    return [dict(r) for r in _get_conn().execute(
        "SELECT category,SUM(total_seconds) as total_seconds FROM daily_summary "
        "WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY total_seconds DESC",
        (date_from, date_to)).fetchall()]

def get_activity_timeline(date):
    return [dict(r) for r in _get_conn().execute(
        "SELECT id,process,window_title,category,started_at,duration FROM activity_log "
        "WHERE date=? ORDER BY started_at", (date,)).fetchall()]

def get_program_stats(date_from, date_to):
    return [dict(r) for r in _get_conn().execute(
        "SELECT process,SUM(duration) as total_seconds FROM activity_log "
        "WHERE date BETWEEN ? AND ? GROUP BY process ORDER BY total_seconds DESC",
        (date_from, date_to)).fetchall()]

def cleanup_old_data(retention_days):
    if retention_days <= 0: return
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    _get_conn().execute("DELETE FROM activity_log WHERE date < ?", (cutoff,))
    _get_conn().commit()

def load_rules_from_db():
    return [dict(r) for r in _get_conn().execute(
        "SELECT process,title_pattern,category,is_user_added FROM classification_rules").fetchall()]

def save_rules_to_db(rules):
    conn = _get_conn()
    conn.execute("DELETE FROM classification_rules")
    for r in rules:
        conn.execute(
            "INSERT INTO classification_rules (process,title_pattern,category,is_user_added) VALUES (?,?,?,?)",
            (r.get("process",""), r.get("title_pattern"), r.get("category","其他"), r.get("is_user_added",0)))
    conn.commit()
```

- [ ] **Step 4: Run tests**

```bash
cd tracker && python -m pytest tests/test_storage.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracker/storage.py tracker/tests/test_storage.py
git commit -m "feat: add storage module with SQLite data layer"
```

---

### Task 3: classifier.py — 自动分类器

**Files:**
- Create: `tracker/classifier.py`
- Create: `tracker/tests/test_classifier.py`

**Interfaces:**
- Consumes: config rules + defaults
- Produces: `classify(process, window_title, rules, defaults) -> str`

- [ ] **Step 1: Create `tracker/tests/test_classifier.py`**

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import classifier

RULES = [
    {"process": "Code.exe", "title_pattern": None, "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow", "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili", "category": "娱乐"},
    {"process": "WeChat.exe", "title_pattern": None, "category": "通讯"},
]
DEFAULTS = {"chrome.exe": "浏览", "msedge.exe": "浏览"}

def test_exact_process_match():
    assert classifier.classify("Code.exe", "x", RULES, DEFAULTS) == "工作"

def test_title_pattern_match_wins():
    assert classifier.classify("chrome.exe", "GitHub PR review", RULES, DEFAULTS) == "工作"

def test_title_no_match_falls_to_default():
    assert classifier.classify("chrome.exe", "Some random site", RULES, DEFAULTS) == "浏览"

def test_default_only():
    assert classifier.classify("msedge.exe", "x", RULES, DEFAULTS) == "浏览"

def test_unknown_process():
    assert classifier.classify("unknown.exe", "x", RULES, DEFAULTS) == "其他"

def test_title_priority_over_process():
    rules = [
        {"process": "chrome.exe", "title_pattern": None, "category": "浏览"},
        {"process": "chrome.exe", "title_pattern": "GitHub", "category": "工作"},
    ]
    assert classifier.classify("chrome.exe", "GitHub test", rules, {}) == "工作"
    assert classifier.classify("chrome.exe", "random", rules, {}) == "浏览"

def test_case_insensitive():
    assert classifier.classify("CODE.EXE", "x", RULES, DEFAULTS) == "工作"

def test_extract_domain():
    d = classifier.extract_domain_from_title("GitHub - Google Chrome")
    assert d is not None
```

- [ ] **Step 2: Run to verify failures**

```bash
cd tracker && python -m pytest tests/test_classifier.py -v
```

Expected: all FAIL

- [ ] **Step 3: Create `tracker/classifier.py`**

```python
"""Rule-based classification of windows into activity categories."""
import re

def classify(process: str, window_title: str, rules: list[dict], defaults: dict) -> str:
    """
    Priority:
    1. Rule with matching process AND title_pattern regex
    2. Rule with matching process only
    3. defaults[process_lower]
    4. '其他'
    """
    pl = process.lower()
    tl = window_title.lower()
    title_match = None
    process_match = None

    for r in rules:
        if r["process"].lower() != pl:
            continue
        tp = r.get("title_pattern")
        if tp:
            if re.search(tp.lower(), tl):
                title_match = r["category"]
        elif process_match is None:
            process_match = r["category"]

    if title_match:
        return title_match
    if process_match:
        return process_match
    if pl in defaults:
        return defaults[pl]
    return "其他"

def extract_domain_from_title(window_title: str) -> str | None:
    for sep in [" — ", " · ", " - ", " | ", " – "]:
        if sep in window_title:
            parts = window_title.split(sep)
            if parts[0].strip():
                return parts[0].strip()
    return None
```

- [ ] **Step 4: Run tests**

```bash
cd tracker && python -m pytest tests/test_classifier.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracker/classifier.py tracker/tests/test_classifier.py
git commit -m "feat: add classifier with rule-based window-to-category matching"
```

---

### Task 4: idle_detector.py — 空闲检测

**Files:**
- Create: `tracker/idle_detector.py`

**Interfaces:**
- `start_idle_detector(on_idle, on_resume, timeout_min)`
- `stop_idle_detector()`
- `is_idle() -> bool`

- [ ] **Step 1: Create `tracker/idle_detector.py`**

```python
"""Idle detection using GetLastInputInfo. Polls every 30s."""
import ctypes, ctypes.wintypes, threading, time

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]

user32 = ctypes.windll.user32
_idle = False; _timeout_ms = 5 * 60 * 1000; _running = False; _on_idle = None; _on_resume = None

def _get_idle_ms() -> int:
    lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return ctypes.windll.kernel32.GetTickCount() - lii.dwTime

def _loop():
    global _idle
    while _running:
        ms = _get_idle_ms()
        if ms > _timeout_ms and not _idle:
            _idle = True
            if _on_idle: _on_idle()
        elif ms < _timeout_ms and _idle:
            _idle = False
            if _on_resume: _on_resume()
        time.sleep(30)

def start_idle_detector(on_idle, on_resume, timeout_min=5):
    global _on_idle, _on_resume, _timeout_ms, _running, _idle
    _on_idle = on_idle; _on_resume = on_resume
    _timeout_ms = timeout_min * 60 * 1000
    _idle = False; _running = True
    t = threading.Thread(target=_loop, daemon=True); t.start()

def stop_idle_detector():
    global _running; _running = False

def is_idle() -> bool:
    return _idle
```

- [ ] **Step 2: Commit**

```bash
git add tracker/idle_detector.py
git commit -m "feat: add idle detector using GetLastInputInfo"
```

---

### Task 5: monitor.py — 窗口监控引擎

**Files:**
- Create: `tracker/monitor.py`

**Interfaces:**
- `start_monitor(callback, min_duration_sec)`
- `stop_monitor()`
- `set_paused(bool)`

- [ ] **Step 1: Create `tracker/monitor.py`**

```python
"""Foreground window monitor via SetWinEventHook (event-driven)."""
import ctypes, ctypes.wintypes, threading, time

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

user32 = ctypes.windll.user32; kernel32 = ctypes.windll.kernel32; psapi = ctypes.windll.psapi

WinEventProc = ctypes.WINFUNCTYPE(None, ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND, ctypes.wintypes.LONG, ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD, ctypes.wintypes.DWORD)

_current = {"process": None, "window_title": None, "started_at": None}
_callback = None; _hook = None; _paused = False; _running = False; _lock = threading.Lock(); _min_dur = 5

def _get_process_name(hwnd):
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value: return ""
    h = kernel32.OpenProcess(0x0400|0x0010, False, pid.value)
    if not h: return ""
    buf = ctypes.create_unicode_buffer(260)
    sz = ctypes.wintypes.DWORD(260)
    if psapi.GetModuleBaseNameW(h, None, buf, sz):
        kernel32.CloseHandle(h); return buf.value
    kernel32.CloseHandle(h)
    return ""

def _get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if not length: return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

@WinEventProc
def _win_event_proc(hook, event, hwnd, id_obj, id_child, event_thread, event_time):
    global _current
    if id_obj != 0 or id_child != 0 or hwnd == 0: return
    now = time.time()
    with _lock:
        if _paused: return
        if _current["process"] and _current["started_at"]:
            dur = now - _current["started_at"]
            if dur >= _min_dur and _callback:
                _callback(_current["process"], _current["window_title"], dur, _current["started_at"])
        p = _get_process_name(hwnd); t = _get_window_title(hwnd)
        if p and t:
            _current["process"] = p; _current["window_title"] = t; _current["started_at"] = now

def start_monitor(callback, min_duration_sec=5):
    global _callback, _hook, _running, _min_dur
    _callback = callback; _min_dur = min_duration_sec; _running = True
    _hook = user32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
        0, _win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)

def stop_monitor():
    global _hook, _running
    _running = False
    if _hook: user32.UnhookWinEvent(_hook); _hook = None

def set_paused(paused):
    global _paused
    with _lock: _paused = paused

def is_running():
    return _running
```

- [ ] **Step 2: Commit**

```bash
git add tracker/monitor.py
git commit -m "feat: add foreground window monitor with SetWinEventHook"
```

---

### Task 6: icon_extractor.py — 程序图标提取

**Files:**
- Create: `tracker/icon_extractor.py`

**Interfaces:**
- `get_icon_pixmap(process_name, size=28) -> QPixmap`
- `get_icon_color(process_name) -> str`

- [ ] **Step 1: Create `tracker/icon_extractor.py`**

```python
"""Extract program icons from .exe via SHGetFileInfo, with fallback letter icons."""
import ctypes, ctypes.wintypes, os, hashlib
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import Qt

SHGFI_ICON = 0x000000100; SHGFI_SMALLICON = 0x000000001; MAX_PATH = 260

FALLBACK_COLORS = {
    "code.exe": "#007ACC", "devenv.exe": "#5C2D91", "chrome.exe": "#E8833A",
    "msedge.exe": "#1A73E8", "firefox.exe": "#FF7139", "wechat.exe": "#2DC100",
    "qq.exe": "#12B7F5", "steam.exe": "#0E6B2E", "explorer.exe": "#F0C94A",
    "windowsterminal.exe": "#2F7B9E", "notepad++.exe": "#80C846",
    "taskmgr.exe": "#8E8E8E", "spotify.exe": "#1DB954",
}

_icon_cache = {}; _color_cache = {}

def _find_exe_path(process_name: str) -> str | None:
    pn = process_name.lower()
    known = {
        "code.exe": os.path.join(os.environ.get("LOCALAPPDATA",""), "Programs","Microsoft VS Code","Code.exe"),
        "chrome.exe": os.path.join(os.environ.get("ProgramFiles","C:\\Program Files"),"Google","Chrome","Application","chrome.exe"),
        "msedge.exe": os.path.join(os.environ.get("ProgramFiles(x86)","C:\\Program Files (x86)"),"Microsoft","Edge","Application","msedge.exe"),
    }
    if pn in known and os.path.exists(known[pn]):
        return known[pn]
    return None

class _SHFILEINFO(ctypes.Structure):
    _fields_ = [("hIcon", ctypes.wintypes.HANDLE), ("iIcon", ctypes.c_int),
                ("dwAttributes", ctypes.wintypes.DWORD),
                ("szDisplayName", ctypes.c_wchar * MAX_PATH),
                ("szTypeName", ctypes.c_wchar * 80)]

def get_icon_pixmap(process_name: str, size: int = 28) -> QPixmap:
    key = f"{process_name.lower()}:{size}"
    if key in _icon_cache:
        return _icon_cache[key] if _icon_cache[key] else None
    exe = _find_exe_path(process_name)
    if not exe:
        pm = _gen_letter(process_name, size)
        _icon_cache[key] = pm; return pm
    shfi = _SHFILEINFO()
    r = ctypes.windll.shell32.SHGetFileInfoW(exe, 0, ctypes.byref(shfi), ctypes.sizeof(shfi), SHGFI_ICON|SHGFI_SMALLICON)
    if r and shfi.hIcon:
        pm = QPixmap.fromHICON(shfi.hIcon)
        if not pm.isNull():
            pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ctypes.windll.user32.DestroyIcon(shfi.hIcon)
            _icon_cache[key] = pm; return pm
        ctypes.windll.user32.DestroyIcon(shfi.hIcon)
    pm = _gen_letter(process_name, size)
    _icon_cache[key] = pm; return pm

def get_icon_color(process_name: str) -> str:
    key = process_name.lower()
    if key in _color_cache: return _color_cache[key]
    if key in FALLBACK_COLORS:
        _color_cache[key] = FALLBACK_COLORS[key]; return FALLBACK_COLORS[key]
    h = int(hashlib.md5(key.encode()).hexdigest()[:6], 16) % 0xFFFFFF
    r, g, b = (h>>16)&0xFF, (h>>8)&0xFF, h&0xFF
    if (r*299+g*587+b*114)/1000 < 80: r = min(255, r+100); g = min(255, g+100); b = min(255, b+100)
    c = f"#{r:02X}{g:02X}{b:02X}"
    _color_cache[key] = c; return c

def _gen_letter(process_name: str, size: int) -> QPixmap:
    color = QColor(get_icon_color(process_name))
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(color); p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, size*0.18, size*0.18)
    letter = (os.path.splitext(process_name)[0] or "?")[0].upper()
    p.setPen(QColor(255,255,255))
    p.setFont(QFont("Segoe UI", int(size*0.5), QFont.Bold))
    p.drawText(0, 0, size, size, Qt.AlignCenter, letter)
    p.end(); return pm

def clear_cache():
    _icon_cache.clear(); _color_cache.clear()
```

- [ ] **Step 2: Commit**

```bash
git add tracker/icon_extractor.py
git commit -m "feat: add icon extractor with SHGetFileInfo and fallback letter icons"
```

---

### Task 7: tray.py — 系统托盘

**Files:**
- Create: `tracker/tray.py`

**Interfaces:**
- `TrayController(app)` class with `show()`, `update_tooltip(text)`, `set_recording_state(active)`, `set_callbacks(on_open_stats, on_toggle_pause, on_exit)`

- [ ] **Step 1: Create `tracker/tray.py`**

```python
"""System tray icon with clock-style icon and right-click menu."""
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QAction
from PySide6.QtCore import Qt

def _make_icon(recording=True):
    pm = QPixmap(32, 32); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    c = 16; r = 14
    p.setPen(QPen(QColor("#EAE4D9"), 2)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(c-r, c-r, r*2, r*2)
    p.setPen(QPen(QColor("#EAE4D9"), 2.5)); p.drawLine(c, c, c+5, c-5)
    p.setPen(QPen(QColor("#D4956B"), 2)); p.drawLine(c, c, c, c-9)
    p.setBrush(QColor("#D4956B")); p.setPen(Qt.NoPen)
    p.drawEllipse(c-2, c-2, 4, 4)
    if not recording:
        p.setPen(QPen(QColor("#E85D75"), 2.5))
        p.drawLine(c-10, c-8, c-10, c+8); p.drawLine(c+10, c-8, c+10, c+8)
    p.end(); return QIcon(pm)

class TrayController:
    def __init__(self, app):
        self._app = app; self._recording = True
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(_make_icon(True))
        self._tray.setToolTip("时间追踪器 · 启动中...")
        self._menu = QMenu()
        self._stats_a = QAction("打开统计面板"); self._menu.addAction(self._stats_a)
        self._menu.addSeparator()
        self._pause_a = QAction("暂停记录"); self._menu.addAction(self._pause_a)
        self._menu.addSeparator()
        self._exit_a = QAction("退出"); self._menu.addAction(self._exit_a)
        self._tray.setContextMenu(self._menu)
        self._cb_open = None; self._cb_pause = None; self._cb_exit = None
        self._stats_a.triggered.connect(lambda: self._cb_open() if self._cb_open else None)
        self._pause_a.triggered.connect(lambda: self._cb_pause() if self._cb_pause else None)
        self._exit_a.triggered.connect(lambda: (self._cb_exit() if self._cb_exit else None, app.quit()))

    def set_callbacks(self, on_open_stats=None, on_toggle_pause=None, on_exit=None):
        self._cb_open = on_open_stats; self._cb_pause = on_toggle_pause; self._cb_exit = on_exit

    def show(self): self._tray.show()
    def hide(self): self._tray.hide()
    def update_tooltip(self, text): self._tray.setToolTip(f"时间追踪器 · {text}")
    def set_recording_state(self, active):
        self._recording = active
        self._tray.setIcon(_make_icon(active))
        self._pause_a.setText("暂停记录" if active else "恢复记录")
```

- [ ] **Step 2: Commit**

```bash
git add tracker/tray.py
git commit -m "feat: add system tray controller with icon and menu"
```

---

### Task 8: charts.py — Matplotlib 图表工厂

**Files:**
- Create: `tracker/charts.py`

**Interfaces:**
- `create_donut_chart(data, center_total, center_label) -> Figure`
- `create_bar_chart(data) -> Figure`

- [ ] **Step 1: Create `tracker/charts.py`**

```python
"""Matplotlib chart factory for donut (pie) and horizontal bar charts."""
import matplotlib; matplotlib.use("QtAgg")
from matplotlib.figure import Figure

BG = "#1E2027"; TXT = "#9B958A"; MUTED = "#5E5A54"; BORDER = "#2E3039"

def create_donut_chart(data: list[dict], center_total: str = "", center_label: str = ""):
    fig = Figure(figsize=(2.7, 2.7), facecolor=BG)
    ax = fig.add_subplot(111); ax.set_facecolor(BG)
    vals = [d["value"] for d in data]; colors = [d["color"] for d in data]
    total = sum(vals)
    if total == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", color=TXT, fontsize=12)
        ax.set_xlim(-1,1); ax.set_ylim(-1,1); ax.axis("off"); return fig
    wedges, _ = ax.pie(vals, labels=None, colors=colors, startangle=90,
        counterclock=False, wedgeprops={"width": 0.35, "edgecolor": BG, "linewidth": 2})
    ax.text(0, 0.05, center_total, ha="center", va="center",
        fontsize=18, fontweight="bold", color="#EAE4D9", fontfamily="monospace")
    ax.text(0, -0.22, center_label, ha="center", va="center", fontsize=9, color=MUTED)
    ax.axis("equal"); fig.tight_layout(pad=0.5)
    for i, w in enumerate(wedges):
        w.highlight_key = data[i].get("highlight_key", data[i]["label"])
    return fig

def create_bar_chart(data: list[dict]):
    n = len(data)
    fig = Figure(figsize=(2.8, max(2.5, n*0.45)), facecolor=BG)
    ax = fig.add_subplot(111); ax.set_facecolor(BG)
    labels = [d["label"] for d in data]; vals = [d["value"] for d in data]
    colors = [d["color"] for d in data]; mx = max(vals) if vals else 1
    bars = ax.barh(range(n), vals, height=0.6, color=colors, zorder=2)
    for i, (b, v) in enumerate(zip(bars, vals)):
        b.highlight_key = data[i].get("highlight_key", data[i]["label"])
        pct = v / mx * 100
        txt = f"{v//3600}h {(v%3600)//60}m" if v >= 3600 else f"{v//60}m"
        if pct > 40:
            ax.text(v-mx*0.02, b.get_y()+b.get_height()/2, txt, ha="right", va="center",
                    fontsize=9, color="white", fontweight="bold", fontfamily="monospace")
        else:
            ax.text(v+mx*0.01, b.get_y()+b.get_height()/2, txt, ha="left", va="center",
                    fontsize=9, color=TXT, fontfamily="monospace")
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=9, color=TXT)
    ax.set_xlim(0, mx*1.18)
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BORDER)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8)
    ax.xaxis.grid(True, color=BORDER, alpha=0.3, zorder=1)
    ax.set_axisbelow(True); fig.tight_layout(pad=0.5)
    return fig
```

- [ ] **Step 2: Commit**

```bash
git add tracker/charts.py
git commit -m "feat: add matplotlib chart factory for donut and bar charts"
```

---

### Task 9: stats_window.py — 统计面板

**Files:**
- Create: `tracker/stats_window.py`

**Interfaces:**
- `StatsWindow(QMainWindow)` — the main statistics panel

- [ ] **Step 1: Create `tracker/stats_window.py`**

```python
"""Statistics panel main window: tabs, toolbar, charts, breakdown, timeline."""
from datetime import datetime, timedelta, date as dt_date
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QDateEdit, QFrame,
    QButtonGroup, QFileDialog,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon, QColor, QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import storage, charts, icon_extractor, classifier as clf, config as cfg

DARK = """
QMainWindow { background-color: #1E2027; }
QWidget { background-color: #1E2027; color: #EAE4D9; }
QTabBar::tab { background:#1E2027; color:#9B958A; padding:10px 18px; border:none; border-bottom:2px solid transparent; font-size:12px; }
QTabBar::tab:selected { color:#D4956B; border-bottom:2px solid #D4956B; }
QPushButton { background:#24262E; color:#9B958A; border:1px solid #2E3039; padding:6px 14px; border-radius:4px; font-size:11px; }
QPushButton:hover { color:#EAE4D9; }
QPushButton:checked { background:#D4956B; color:#1A1C21; border-color:#D4956B; }
QListWidget { background:#1E2027; border:none; }
QListWidget::item { padding:6px 10px; border-radius:4px; }
QListWidget::item:hover { background:#2C2E36; }
QDateEdit { background:#16181D; color:#EAE4D9; border:1px solid #2E3039; padding:4px 8px; border-radius:4px; }
QFrame#sep { background:#2E3039; max-height:1px; }
"""

class StatsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("时间统计"); self.setStyleSheet(DARK)
        self.resize(820, 720); self.setMinimumSize(700, 550)
        self._time_range = "today"; self._view_mode = "category"
        self._chart_type = "donut"; self._drill_cat = None
        self._custom_from = dt_date.today(); self._custom_to = dt_date.today()
        self._build_ui(); self.refresh()

    def _build_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        lo = QVBoxLayout(c); lo.setContentsMargins(20,16,20,16); lo.setSpacing(12)

        # Tabs
        tl = QHBoxLayout()
        self._bar = QTabBar()
        for t in ["今日","本周","本月","自定义"]: self._bar.addTab(t)
        self._bar.currentChanged.connect(self._on_tab)
        tl.addWidget(self._bar); tl.addStretch()
        s = QPushButton("⚙"); s.setFixedSize(36,36); s.clicked.connect(self._open_settings)
        tl.addWidget(s); lo.addLayout(tl)

        # Custom date row
        self._cw = QWidget()
        h = QHBoxLayout(self._cw); h.setContentsMargins(0,0,0,0)
        self._df = QDateEdit(QDate.currentDate().addMonths(-1)); self._df.setCalendarPopup(True)
        self._dt = QDateEdit(QDate.currentDate()); self._dt.setCalendarPopup(True)
        h.addWidget(QLabel("从")); h.addWidget(self._df); h.addWidget(QLabel("到")); h.addWidget(self._dt)
        a = QPushButton("应用"); a.clicked.connect(self._on_apply); h.addWidget(a); h.addStretch()
        self._cw.hide(); lo.addWidget(self._cw)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(QLabel("视图"))
        self._vg = QButtonGroup(self)
        for i, t in enumerate(["按分类","按程序"]):
            b = QPushButton(t); b.setCheckable(True); b.setChecked(i==0)
            self._vg.addButton(b, i)
        self._vg.buttonClicked.connect(self._on_view)
        tb.addWidget(self._vg.button(0)); tb.addWidget(self._vg.button(1))
        tb.addSpacing(16); tb.addWidget(QLabel("图表"))
        self._cg = QButtonGroup(self)
        for i, t in enumerate(["饼图","柱状图"]):
            b = QPushButton(t); b.setCheckable(True); b.setChecked(i==0)
            self._cg.addButton(b, i)
        self._cg.buttonClicked.connect(self._on_chart)
        tb.addWidget(self._cg.button(0)); tb.addWidget(self._cg.button(1))
        tb.addStretch()
        self._bc = QLabel(""); self._bc.setStyleSheet("color:#D4956B; font-size:11px;"); self._bc.hide()
        tb.addWidget(self._bc); lo.addLayout(tb)

        sp = QFrame(); sp.setObjectName("sep"); lo.addWidget(sp)

        # Chart + breakdown
        sp2 = QSplitter(Qt.Horizontal)
        self._chart_w = QWidget(); self._chart_w.setFixedWidth(280)
        self._chart_lo = QVBoxLayout(self._chart_w); self._canvas = None
        sp2.addWidget(self._chart_w)
        self._bl = QListWidget()
        self._bl.itemClicked.connect(self._on_click)
        sp2.addWidget(self._bl)
        sp2.setStretchFactor(0,1); sp2.setStretchFactor(1,2)
        lo.addWidget(sp2, 1)

        # Timeline
        lo.addWidget(QLabel("时间线"))
        self._tl = QListWidget(); self._tl.setMaximumHeight(200)
        lo.addWidget(self._tl)

        # Export
        el = QHBoxLayout(); el.addStretch()
        csv = QPushButton("导出 CSV"); csv.clicked.connect(self._export)
        el.addWidget(csv); lo.addLayout(el)

    def _get_range(self):
        t = dt_date.today()
        if self._time_range == "today": return t.isoformat(), t.isoformat()
        if self._time_range == "week":
            m = t - timedelta(days=t.weekday()); return m.isoformat(), t.isoformat()
        if self._time_range == "month":
            return t.replace(day=1).isoformat(), t.isoformat()
        return self._custom_from.isoformat(), self._custom_to.isoformat()

    def _on_tab(self, i):
        self._time_range = ["today","week","month","custom"][i]
        self._cw.setVisible(self._time_range=="custom"); self._drill_cat = None; self.refresh()

    def _on_apply(self):
        self._custom_from = self._df.date().toPython(); self._custom_to = self._dt.date().toPython()
        self._drill_cat = None; self.refresh()

    def _on_view(self, b):
        self._view_mode = "category" if self._vg.id(b)==0 else "program"
        self._drill_cat = None; self.refresh()

    def _on_chart(self, b):
        self._chart_type = "donut" if self._cg.id(b)==0 else "bar"; self.refresh()

    def _on_click(self, item):
        d = item.data(Qt.UserRole)
        if not d: return
        if self._view_mode=="category" and not self._drill_cat and d.get("type")=="category":
            self._drill_cat = d["label"]
            self._bc.setText(f"← 返回全部 | {self._drill_cat}"); self._bc.show(); self.refresh()

    def _open_settings(self):
        from classifier_edit import ClassifierEditDialog
        ClassifierEditDialog(self).exec(); self.refresh()

    def refresh(self):
        self._update_chart(); self._update_breakdown(); self._update_timeline()

    def _update_chart(self):
        if self._canvas:
            self._chart_lo.removeWidget(self._canvas); self._canvas.deleteLater(); self._canvas = None
        df, dt = self._get_range(); items = self._build_data(df, dt)
        cfg_ = cfg.load_config()
        if self._chart_type == "donut":
            t = sum(d["value"] for d in items)
            fig = charts.create_donut_chart(items, f"{t//3600}h {(t%3600)//60}m",
                {"today":"今日用时","week":"本周用时","month":"本月用时"}.get(self._time_range,"用时"))
        else:
            fig = charts.create_bar_chart(items)
        self._canvas = FigureCanvasQTAgg(fig); self._chart_lo.addWidget(self._canvas)

    def _update_breakdown(self):
        self._bl.clear(); df, dt = self._get_range(); items = self._build_data(df, dt)
        total = sum(d["value"] for d in items)
        for d in items:
            pct = round(d["value"]/total*100) if total else 0
            secs = d["value"]; txt = f"{secs//3600}h {(secs%3600)//60}m" if secs>=3600 else f"{secs//60}m"
            item = QListWidgetItem(f"  {d['label']}    {txt}    {pct}%")
            item.setData(Qt.UserRole, d)
            pm = icon_extractor.get_icon_pixmap(d.get("icon_name",d["label"]), 24)
            if pm: item.setIcon(QIcon(pm))
            self._bl.addItem(item)

    def _update_timeline(self):
        self._tl.clear()
        df, dt = self._get_range()
        if self._time_range!="today": return
        for row in storage.get_activity_timeline(df):
            d = dict(row)
            s = d["duration"]; ds = f"{s//3600}h {(s%3600)//60}m" if s>=3600 else f"{s//60}m"
            txt = f"  {d['started_at'][11:16]}  {d['process']}  {d['window_title'][:35]}  {ds}  [{d['category']}]"
            item = QListWidgetItem(txt)
            pm = icon_extractor.get_icon_pixmap(d["process"], 20)
            if pm: item.setIcon(QIcon(pm))
            self._tl.addItem(item)

    def _build_data(self, df, dt):
        conf = cfg.load_config()
        cm = {c: conf["categories"].get(c,{}).get("color","#5A5A5A") for c in conf["categories"]}
        if self._view_mode=="category" and not self._drill_cat:
            rows = storage.get_range_summary(df, dt)
            return [{"label":r["category"],"value":r["total_seconds"],
                     "color":cm.get(r["category"],"#5A5A5A"),"highlight_key":r["category"],"type":"category"}
                    for r in rows]
        else:
            rows = storage.get_program_stats(df, dt)
            return [{"label":r["process"],"value":r["total_seconds"],
                     "color":icon_extractor.get_icon_color(r["process"]),
                     "highlight_key":r["process"],"icon_name":r["process"],"type":"program"}
                    for r in rows]

    def _export(self):
        import csv
        p, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "", "CSV (*.csv)")
        if not p: return
        df, dt = self._get_range()
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["进程","窗口标题","分类","开始时间","时长(秒)","日期"])
            for r in storage.get_activity_timeline(df):
                w.writerow([r["process"],r["window_title"],r["category"],r["started_at"],r["duration"],r.get("date","")])
```

- [ ] **Step 2: Commit**

```bash
git add tracker/stats_window.py
git commit -m "feat: add statistics panel with chart, breakdown, and timeline"
```

---

### Task 10: classifier_edit.py — 分类规则编辑器

**Files:**
- Create: `tracker/classifier_edit.py`

**Interfaces:**
- `ClassifierEditDialog(QDialog)` — modal dialog

- [ ] **Step 1: Create `tracker/classifier_edit.py`**

```python
"""Classification rule editor dialog."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QHeaderView, QMessageBox)
import config as cfg

class ClassifierEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分类规则设置"); self.resize(650, 450)
        self.setStyleSheet("""
            QDialog { background-color:#1E2027; color:#EAE4D9; }
            QTableWidget { background-color:#24262E; color:#EAE4D9;
                gridline-color:#2E3039; border:1px solid #2E3039; }
            QHeaderView::section { background-color:#2E3039; color:#9B958A;
                padding:6px; border:none; font-size:11px; }
            QPushButton { background:#24262E; color:#9B958A; border:1px solid #2E3039;
                padding:6px 14px; border-radius:4px; font-size:11px; }
            QPushButton:hover { color:#EAE4D9; }
            QComboBox { background:#24262E; color:#EAE4D9; border:1px solid #2E3039;
                padding:4px 8px; border-radius:4px; }
        """)
        self._config = cfg.load_config()
        lo = QVBoxLayout(self)
        self._t = QTableWidget(0, 4)
        self._t.setHorizontalHeaderLabels(["进程","标题匹配(正则)","分类",""])
        self._t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._t.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._t.setColumnWidth(3, 60)
        lo.addWidget(self._t)
        bl = QHBoxLayout()
        add = QPushButton("+ 添加规则"); add.clicked.connect(self._add); bl.addWidget(add)
        bl.addStretch()
        sv = QPushButton("保存"); sv.setStyleSheet("background:#D4956B; color:#1A1C21; font-weight:bold;")
        sv.clicked.connect(self._save); bl.addWidget(sv)
        cl = QPushButton("关闭"); cl.clicked.connect(self.reject); bl.addWidget(cl)
        lo.addLayout(bl)
        self._load()

    def _load(self):
        self._t.setRowCount(0); cats = list(self._config["categories"].keys())
        for r in self._config["rules"]:
            row = self._t.rowCount(); self._t.insertRow(row)
            self._t.setItem(row, 0, QTableWidgetItem(r["process"]))
            self._t.setItem(row, 1, QTableWidgetItem(r.get("title_pattern","") or ""))
            cb = QComboBox(); cb.addItems(cats)
            if r["category"] in cats: cb.setCurrentIndex(cats.index(r["category"]))
            self._t.setCellWidget(row, 2, cb)
            db = QPushButton("✕"); db.setFixedSize(40,28)
            db.clicked.connect(lambda _, r=row: self._t.removeRow(r))
            self._t.setCellWidget(row, 3, db)

    def _add(self):
        row = self._t.rowCount(); self._t.insertRow(row)
        self._t.setItem(row, 0, QTableWidgetItem(""))
        self._t.setItem(row, 1, QTableWidgetItem(""))
        cb = QComboBox(); cb.addItems(list(self._config["categories"].keys()))
        self._t.setCellWidget(row, 2, cb)
        db = QPushButton("✕"); db.setFixedSize(40,28)
        db.clicked.connect(lambda _, r=row: self._t.removeRow(r))
        self._t.setCellWidget(row, 3, db)
        self._t.scrollToBottom()

    def _save(self):
        rules = []
        for i in range(self._t.rowCount()):
            p = self._t.item(i, 0); tp = self._t.item(i, 1); cb = self._t.cellWidget(i, 2)
            if not p or not p.text().strip(): continue
            rules.append({"process": p.text().strip(),
                "title_pattern": tp.text().strip() if tp and tp.text().strip() else None,
                "category": cb.currentText() if cb else "其他"})
        self._config["rules"] = rules; cfg.save_config(self._config)
        QMessageBox.information(self, "保存", "分类规则已保存。"); self.accept()
```

- [ ] **Step 2: Commit**

```bash
git add tracker/classifier_edit.py
git commit -m "feat: add classification rule editor dialog"
```

---

### Task 11: main.py — 入口 + 整合

**Files:**
- Create: `tracker/main.py`

- [ ] **Step 1: Create `tracker/main.py`**

```python
"""Application entry point: wires monitor, idle, classifier, storage, tray, UI."""
import sys, os, time
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg, storage, monitor, idle_detector, classifier, tray
from stats_window import StatsWindow

class TimeTracker:
    def __init__(self, app):
        self._app = app; self._cfg = cfg.load_config(); self._stats = None; self._paused = False
        db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db")
        storage.init_db(db)
        if self._cfg.get("retention_days", 90) > 0:
            storage.cleanup_old_data(self._cfg["retention_days"])
        storage.save_rules_to_db(self._cfg.get("rules", []))
        self._tray = tray.TrayController(app)
        self._tray.set_callbacks(on_open_stats=self._open_stats, on_toggle_pause=self._toggle_pause, on_exit=self._shutdown)
        self._tray.show()
        monitor.start_monitor(self._on_activity, self._cfg.get("min_duration_sec", 5))
        idle_detector.start_idle_detector(on_idle=self._on_idle, on_resume=self._on_resume,
                                          timeout_min=self._cfg.get("idle_timeout_min", 5))
        self._timer = QTimer(); self._timer.timeout.connect(self._update_tooltip); self._timer.start(60000)
        self._update_tooltip()

    def _on_activity(self, process, window_title, duration, started_at_ts):
        if self._paused or idle_detector.is_idle(): return
        dur = int(duration)
        if dur < self._cfg.get("min_duration_sec", 5): return
        sd = datetime.fromtimestamp(started_at_ts)
        cat = classifier.classify(process, window_title, self._cfg.get("rules",[]), self._cfg.get("defaults",{}))
        storage.insert_activity(process, window_title, cat, sd.strftime("%Y-%m-%d %H:%M:%S"), dur, sd.strftime("%Y-%m-%d"))
        storage.upsert_daily_summary(sd.strftime("%Y-%m-%d"), cat, dur)

    def _on_idle(self): pass
    def _on_resume(self): pass

    def _update_tooltip(self):
        rows = storage.get_daily_summary(datetime.now().strftime("%Y-%m-%d"))
        t = sum(r["total_seconds"] for r in rows)
        sta = "已暂停" if self._paused else "记录中"
        self._tray.update_tooltip(f"{sta} · 今日 {t//3600}h {(t%3600)//60}m")

    def _open_stats(self):
        if not self._stats: self._stats = StatsWindow()
        self._stats.show(); self._stats.raise_(); self._stats.activateWindow()

    def _toggle_pause(self):
        self._paused = not self._paused; monitor.set_paused(self._paused)
        self._tray.set_recording_state(not self._paused); self._update_tooltip()

    def _shutdown(self):
        monitor.stop_monitor(); idle_detector.stop_idle_detector(); self._app.quit()

def main():
    import ctypes
    h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\TimeTrackerApp")
    if ctypes.windll.kernel32.GetLastError() == 183: return  # already running
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    _ = TimeTracker(app); sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add tracker/main.py
git commit -m "feat: add main entry point wiring all modules"
```

---

### Task 12: 手动集成验证

- [ ] **Step 1: 安装所有依赖**

```bash
cd tracker && pip install -r requirements.txt
```

- [ ] **Step 2: 运行全部单元测试**

```bash
cd tracker && python -m pytest tests/ -v
```

Expected: 17 tests PASS (3 config + 6 storage + 8 classifier)

- [ ] **Step 3: 启动应用手动测试**

```bash
cd tracker && python main.py
```

验证检查清单:
- [ ] 系统托盘图标显示，右键有菜单
- [ ] 切换窗口 -> 数据库写入 activity_log
- [ ] 打开统计面板 -> 显示今日数据
- [ ] 切换按分类/按程序 -> 图表和列表更新
- [ ] 切换饼图/柱状图 -> 正常显示
- [ ] 分类下钻 -> 点击展开程序明细
- [ ] 导出 CSV -> 文件内容正确

- [ ] **Step 4: Commit**

```bash
git add tracker/__init__.py
git commit -m "chore: finalize tracker package"
```

---

### Task 13: PyInstaller 打包

**Files:**
- Create: `tracker/build.spec`

- [ ] **Step 1: Install PyInstaller and build**

```bash
pip install pyinstaller
cd tracker
pyinstaller --onefile --windowed --name TimeTracker --add-data "config.json;." main.py
```

- [ ] **Step 2: Test the exe**

```bash
dist/TimeTracker.exe
```

- [ ] **Step 3: Commit build artifacts**

```bash
git add tracker/build.spec
git commit -m "chore: add PyInstaller build spec"
```
