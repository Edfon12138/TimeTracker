"""Application entry point: wires monitor, idle, classifier, storage, tray, browser UI."""
import sys, os, subprocess
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg, storage, monitor, idle_detector, classifier, stats_html

class TimeTracker:
    def __init__(self, app):
        self._app = app; self._config = cfg.load_config(); self._paused = False
        db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db")
        storage.init_db(db)
        if self._config.get("retention_days", 90) > 0:
            storage.cleanup_old_data(self._config["retention_days"])
        storage.save_rules_to_db(self._config.get("rules", []))
        self._tray = tray.TrayController(app)
        self._tray.set_callbacks(
            on_open_stats=self._open_stats,
            on_open_settings=self._open_settings,
            on_toggle_pause=self._toggle_pause,
            on_exit=self._shutdown,
        )
        self._tray.show()
        monitor.start_monitor(self._on_activity, self._config.get("min_duration_sec", 5))
        idle_detector.start_idle_detector(on_idle=self._on_idle, on_resume=self._on_resume,
                                          timeout_min=self._config.get("idle_timeout_min", 5))
        self._timer = QTimer(); self._timer.timeout.connect(self._update_tooltip); self._timer.start(60000)
        self._update_tooltip()

    def _on_activity(self, process, window_title, duration, started_at_ts):
        if self._paused or idle_detector.is_idle(): return
        dur = int(duration)
        if dur < self._config.get("min_duration_sec", 5): return
        sd = datetime.fromtimestamp(started_at_ts)
        cat = classifier.classify(process, window_title, self._config.get("rules",[]), self._config.get("defaults",{}))
        storage.insert_activity(process, window_title, cat, sd.strftime("%Y-%m-%d %H:%M:%S"), dur, sd.strftime("%Y-%m-%d"))
        storage.upsert_daily_summary(sd.strftime("%Y-%m-%d"), cat, dur)

    def _on_idle(self): pass
    def _on_resume(self): pass

    def _update_tooltip(self):
        rows = storage.get_daily_summary(datetime.now().strftime("%Y-%m-%d"))
        t = sum(r["total_seconds"] for r in rows)
        sta = "已暂停" if self._paused else "记录中"
        self._tray.update_tooltip(f"{sta} · 今日 {t//3600}h {(t%3600)//60}m")

    def _open_stats(self):
        stats_html.generate()

    def _open_settings(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_path):
            os.startfile(config_path)

    def _toggle_pause(self):
        self._paused = not self._paused; monitor.set_paused(self._paused)
        self._tray.set_recording_state(not self._paused); self._update_tooltip()

    def _shutdown(self):
        monitor.stop_monitor(); idle_detector.stop_idle_detector(); self._app.quit()

def main():
    import ctypes
    h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\TimeTrackerApp")
    if ctypes.windll.kernel32.GetLastError() == 183: return
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    _ = TimeTracker(app); sys.exit(app.exec())

if __name__ == "__main__":
    main()
