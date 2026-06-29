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
