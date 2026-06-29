"""Extract program icons from .exe via SHGetFileInfo, with fallback letter icons.
Png cache saved to icons/ directory next to config/db for portable reuse."""
import ctypes, ctypes.wintypes, os, hashlib, sys, base64
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QByteArray, QBuffer, QIODevice

SHGFI_ICON = 0x000000100; SHGFI_SMALLICON = 0x000000001; MAX_PATH = 260

FALLBACK_COLORS = {
    "code.exe": "#007ACC", "devenv.exe": "#5C2D91", "chrome.exe": "#E8833A",
    "msedge.exe": "#1A73E8", "firefox.exe": "#FF7139", "wechat.exe": "#2DC100",
    "qq.exe": "#12B7F5", "steam.exe": "#0E6B2E", "explorer.exe": "#F0C94A",
    "windowsterminal.exe": "#2F7B9E", "notepad++.exe": "#80C846",
    "taskmgr.exe": "#8E8E8E", "spotify.exe": "#1DB954",
}

_icon_cache = {}; _color_cache = {}


def _base_dir() -> str:
    """Portable base dir: exe dir when frozen, else script dir."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _icon_cache_dir() -> str:
    """icons/ directory next to config/db; created lazily."""
    d = os.path.join(_base_dir(), "icons")
    os.makedirs(d, exist_ok=True)
    return d


def _cached_icon_path(process_name: str) -> str:
    return os.path.join(_icon_cache_dir(), f"{process_name.lower()}.png")

def _find_exe_path(process_name: str) -> str | None:
    pn = process_name.lower()
    known = {
        "code.exe": os.path.join(os.environ.get("LOCALAPPDATA",""), "Programs","Microsoft VS Code","Code.exe"),
        "chrome.exe": os.path.join(os.environ.get("ProgramFiles","C:\\Program Files"),"Google","Chrome","Application","chrome.exe"),
        "msedge.exe": os.path.join(os.environ.get("ProgramFiles(x86)","C:\\Program Files (x86)"),"Microsoft","Edge","Application","msedge.exe"),
    }
    if pn in known and os.path.exists(known[pn]):
        return known[pn]
    # Search PATH directories
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for d in path_dirs:
        d = d.strip('"')
        if not d: continue
        candidate = os.path.join(d, process_name)
        if os.path.isfile(candidate):
            return candidate
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
        img = QImage.fromHICON(shfi.hIcon)
        if not img.isNull():
            pm = QPixmap.fromImage(img).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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


def get_icon_uri(process_name: str, size: int = 20) -> str | None:
    """Return a data URI (png) for the given process.

    Checks disk cache first (icons/<process>.png), then extracts via
    SHGetFileInfo and caches the result so subsequent lookups are instant.
    Returns None when extraction fails (caller falls back to letter SVG).
    """
    name = process_name.lower()
    cache_path = _cached_icon_path(name)

    # 1. Disk cache hit — read and return
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        except Exception:
            pass  # corrupted file; re-extract

    # 2. Extract icon via Qt / SHGetFileInfo
    pm = get_icon_pixmap(name, size)
    if pm is None or pm.isNull():
        return None

    # 3. Serialise to PNG bytes
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    png_bytes = bytes(ba)

    # 4. Save to disk cache (best-effort)
    try:
        with open(cache_path, "wb") as f:
            f.write(png_bytes)
    except Exception:
        pass

    return f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"


def clear_cache():
    _icon_cache.clear(); _color_cache.clear()
