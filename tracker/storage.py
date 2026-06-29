"""SQLite database: init, CRUD, aggregates, cleanup."""
import sqlite3, os, sys, time, threading
from datetime import datetime, timedelta

_local = threading.local()

def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _db_path():
    return os.path.join(_base_dir(), "tracker.db")

def _get_conn(path=None):
    if path is None:
        # Reuse existing cached connection if available
        if hasattr(_local, "conn") and _local.conn is not None:
            return _local.conn
        path = _db_path()
    cached = hasattr(_local, "conn") and _local.conn is not None
    same_path = cached and getattr(_local, "db_path", None) == path
    if not same_path:
        if cached:
            _local.conn.close()
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        _local.db_path = path
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
