"""Idle detection using GetLastInputInfo. Tracks idle session start/end + foreground window."""
import ctypes, ctypes.wintypes, threading, time

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]

user32 = ctypes.windll.user32
_idle = False; _timeout_ms = 5 * 60 * 1000; _running = False
_on_idle = None; _on_resume = None
_idle_sessions: list[dict] = []
_current_session: dict | None = None

def _get_idle_ms() -> int:
    lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return ctypes.windll.kernel32.GetTickCount() - lii.dwTime

def _get_foreground_info():
    """Get (process, window_title, is_video) for the current foreground window."""
    try:
        from monitor import get_current_window
    except ImportError:
        return ("", "", False)
    process, title = get_current_window()
    if not process:
        return ("", "", False)
    try:
        from classifier import match_video_keywords
        is_video = match_video_keywords(title)
    except ImportError:
        is_video = False
    return (process, title, is_video)

def _loop():
    global _idle, _current_session
    while _running:
        ms = _get_idle_ms()
        if ms > _timeout_ms and not _idle:
            # Transition: active -> idle
            process, title, is_video = _get_foreground_info()
            category = "视频" if is_video else "空闲"
            _current_session = {
                "started_at": time.time(),
                "ended_at": None,
                "process": process,
                "window_title": title,
                "is_video": is_video,
                "category": category,
            }
            _idle = True
            if _on_idle:
                _on_idle(_current_session)
        elif ms < _timeout_ms and _idle:
            # Transition: idle -> active
            if _current_session is not None:
                _current_session["ended_at"] = time.time()
                _idle_sessions.append(_current_session)
                saved = _current_session
                _current_session = None
                if _on_resume:
                    _on_resume(saved)
            _idle = False
        time.sleep(30)

def start_idle_detector(on_idle, on_resume, timeout_min=5):
    global _on_idle, _on_resume, _timeout_ms, _running, _idle, _idle_sessions, _current_session
    _on_idle = on_idle; _on_resume = on_resume
    _timeout_ms = timeout_min * 60 * 1000
    _idle = False; _running = True; _idle_sessions = []; _current_session = None
    t = threading.Thread(target=_loop, daemon=True); t.start()

def stop_idle_detector():
    global _running; _running = False

def is_idle() -> bool:
    return _idle

def get_idle_sessions() -> list[dict]:
    """Return all completed idle sessions. Each includes started_at, ended_at, duration, etc."""
    result = list(_idle_sessions)
    # Include the current ongoing session if idle
    if _idle and _current_session is not None:
        s = dict(_current_session)
        s["ended_at"] = time.time()
        result.append(s)
    # Add computed duration and filter to today
    today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
    today_end = today_start + 86400
    for s in result:
        s["duration"] = int(s["ended_at"] - s["started_at"])
    return [s for s in result if s["started_at"] >= today_start and s["started_at"] < today_end]

def clear_idle_sessions():
    global _idle_sessions, _current_session
    _idle_sessions = []; _current_session = None
