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
