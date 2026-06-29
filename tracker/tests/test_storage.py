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
