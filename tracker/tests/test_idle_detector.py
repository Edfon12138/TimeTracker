"""Tests for idle_detector session tracking (mocked)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import time
import idle_detector

def test_get_idle_sessions_with_completed_sessions():
    idle_detector._idle_sessions = []
    idle_detector._current_session = None
    idle_detector._idle = False

    # Simulate two completed idle sessions
    now = time.time()
    idle_detector._idle_sessions = [
        {"started_at": now - 7200, "ended_at": now - 3600, "duration": 3600, "category": "空闲", "is_video": False, "process": "", "window_title": ""},
        {"started_at": now - 1800, "ended_at": now - 900, "duration": 900, "category": "视频", "is_video": True, "process": "chrome.exe", "window_title": "YouTube"},
    ]
    sessions = idle_detector.get_idle_sessions()
    assert len(sessions) == 2
    assert sessions[0]["category"] == "空闲"
    assert sessions[1]["category"] == "视频"

def test_clear_idle_sessions():
    idle_detector._idle_sessions = [{"test": "data"}]
    idle_detector._current_session = {"test": "current"}
    idle_detector.clear_idle_sessions()
    assert idle_detector._idle_sessions == []
    assert idle_detector._current_session is None
