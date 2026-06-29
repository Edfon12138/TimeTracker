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
