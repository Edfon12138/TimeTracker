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

def get_icon_pixmap(process_name: str, size: int = 28):
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

def _gen_letter(process_name: str, size: int):
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
