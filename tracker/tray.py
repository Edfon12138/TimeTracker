"""System tray icon with SVG clock icon and right-click menu."""
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QAction
from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtSvg import QSvgRenderer

CLOCK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path d="M12.5 7.25a.75.75 0 0 0-1.5 0v5.5c0 .27.144.518.378.651l3.5 2a.75.75 0 0 0 .744-1.302L12.5 12.315V7.25Z"/>
  <path d="M12 1c6.075 0 11 4.925 11 11s-4.925 11-11 11S1 18.075 1 12 5.925 1 12 1ZM2.5 12a9.5 9.5 0 0 0 9.5 9.5 9.5 9.5 0 0 0 9.5-9.5A9.5 9.5 0 0 0 12 2.5 9.5 9.5 0 0 0 2.5 12Z"/>
  {pause}
</svg>"""

PAUSE_SVG = '<path d="M15 8a1 1 0 0 1 1 1v6a1 1 0 1 1-2 0V9a1 1 0 0 1 1-1Z"/>' \
            '<path d="M19 8a1 1 0 0 1 1 1v6a1 1 0 1 1-2 0V9a1 1 0 0 1 1-1Z"/>'


def _make_icon(recording=True):
    svg = CLOCK_SVG.replace("{pause}", "" if recording else PAUSE_SVG)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(32, 32); pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(4, 4, 24, 24))
    p.end()
    return QIcon(pm)


class TrayController:
    def __init__(self, app):
        self._app = app; self._recording = True
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(_make_icon(True))
        self._tray.setToolTip("时间追踪器 · 启动中...")
        self._menu = QMenu()
        self._stats_a = QAction("打开统计面板"); self._menu.addAction(self._stats_a)
        self._settings_a = QAction("设置"); self._menu.addAction(self._settings_a)
        self._menu.addSeparator()
        self._pause_a = QAction("暂停记录"); self._menu.addAction(self._pause_a)
        self._menu.addSeparator()
        self._exit_a = QAction("退出"); self._menu.addAction(self._exit_a)
        self._tray.setContextMenu(self._menu)
        self._cb_open = None; self._cb_settings = None; self._cb_pause = None; self._cb_exit = None
        self._stats_a.triggered.connect(lambda: self._cb_open() if self._cb_open else None)
        self._settings_a.triggered.connect(lambda: self._cb_settings() if self._cb_settings else None)
        self._pause_a.triggered.connect(lambda: self._cb_pause() if self._cb_pause else None)
        self._exit_a.triggered.connect(lambda: (self._cb_exit() if self._cb_exit else None, app.quit()))

    def set_callbacks(self, on_open_stats=None, on_open_settings=None, on_toggle_pause=None, on_exit=None):
        self._cb_open = on_open_stats; self._cb_settings = on_open_settings; self._cb_pause = on_toggle_pause; self._cb_exit = on_exit

    def show(self): self._tray.show()
    def hide(self): self._tray.hide()
    def update_tooltip(self, text): self._tray.setToolTip(f"时间追踪器 · {text}")
    def set_recording_state(self, active):
        self._recording = active
        self._tray.setIcon(_make_icon(active))
        self._pause_a.setText("暂停记录" if active else "恢复记录")
