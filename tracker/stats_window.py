"""Statistics panel main window: tabs, toolbar, charts, breakdown, timeline."""
from datetime import datetime, timedelta, date as dt_date
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QDateEdit, QFrame,
    QButtonGroup, QFileDialog,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import storage, charts, icon_extractor, config as cfg

DARK = """
QMainWindow { background-color: #1E2027; }
QWidget { background-color: #1E2027; color: #EAE4D9; }
QTabBar::tab { background:#1E2027; color:#9B958A; padding:10px 18px; border:none; border-bottom:2px solid transparent; font-size:12px; }
QTabBar::tab:selected { color:#D4956B; border-bottom:2px solid #D4956B; }
QPushButton { background:#24262E; color:#9B958A; border:1px solid #2E3039; padding:6px 14px; border-radius:4px; font-size:11px; }
QPushButton:hover { color:#EAE4D9; }
QPushButton:checked { background:#D4956B; color:#1A1C21; border-color:#D4956B; }
QListWidget { background:#1E2027; border:none; }
QListWidget::item { padding:6px 10px; border-radius:4px; }
QListWidget::item:hover { background:#2C2E36; }
QDateEdit { background:#16181D; color:#EAE4D9; border:1px solid #2E3039; padding:4px 8px; border-radius:4px; }
QFrame#sep { background:#2E3039; max-height:1px; }
"""

class StatsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("时间统计"); self.setStyleSheet(DARK)
        self.resize(820, 720); self.setMinimumSize(700, 550)
        self._time_range = "today"; self._view_mode = "category"
        self._chart_type = "donut"; self._drill_cat = None
        self._custom_from = dt_date.today(); self._custom_to = dt_date.today()
        self._build_ui(); self.refresh()

    def _build_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        lo = QVBoxLayout(c); lo.setContentsMargins(20,16,20,16); lo.setSpacing(12)
        tl = QHBoxLayout()
        self._bar = QTabBar()
        for t in ["今日","本周","本月","自定义"]: self._bar.addTab(t)
        self._bar.currentChanged.connect(self._on_tab)
        tl.addWidget(self._bar); tl.addStretch()
        s = QPushButton("⚙"); s.setFixedSize(36,36); s.clicked.connect(self._open_settings)
        tl.addWidget(s); lo.addLayout(tl)
        self._cw = QWidget()
        h = QHBoxLayout(self._cw); h.setContentsMargins(0,0,0,0)
        self._df = QDateEdit(QDate.currentDate().addMonths(-1)); self._df.setCalendarPopup(True)
        self._dt = QDateEdit(QDate.currentDate()); self._dt.setCalendarPopup(True)
        h.addWidget(QLabel("从")); h.addWidget(self._df); h.addWidget(QLabel("到")); h.addWidget(self._dt)
        a = QPushButton("应用"); a.clicked.connect(self._on_apply); h.addWidget(a); h.addStretch()
        self._cw.hide(); lo.addWidget(self._cw)
        tb = QHBoxLayout()
        tb.addWidget(QLabel("视图"))
        self._vg = QButtonGroup(self)
        for i, t in enumerate(["按分类","按程序"]):
            b = QPushButton(t); b.setCheckable(True); b.setChecked(i==0)
            self._vg.addButton(b, i)
        self._vg.buttonClicked.connect(self._on_view)
        tb.addWidget(self._vg.button(0)); tb.addWidget(self._vg.button(1))
        tb.addSpacing(16); tb.addWidget(QLabel("图表"))
        self._cg = QButtonGroup(self)
        for i, t in enumerate(["饼图","柱状图"]):
            b = QPushButton(t); b.setCheckable(True); b.setChecked(i==0)
            self._cg.addButton(b, i)
        self._cg.buttonClicked.connect(self._on_chart)
        tb.addWidget(self._cg.button(0)); tb.addWidget(self._cg.button(1))
        tb.addStretch()
        self._bc = QLabel(""); self._bc.setStyleSheet("color:#D4956B; font-size:11px;"); self._bc.hide()
        tb.addWidget(self._bc); lo.addLayout(tb)
        sp = QFrame(); sp.setObjectName("sep"); lo.addWidget(sp)
        sp2 = QSplitter(Qt.Horizontal)
        self._chart_w = QWidget(); self._chart_w.setFixedWidth(280)
        self._chart_lo = QVBoxLayout(self._chart_w); self._canvas = None
        sp2.addWidget(self._chart_w)
        self._bl = QListWidget()
        self._bl.itemClicked.connect(self._on_click)
        sp2.addWidget(self._bl)
        sp2.setStretchFactor(0,1); sp2.setStretchFactor(1,2)
        lo.addWidget(sp2, 1)
        lo.addWidget(QLabel("时间线"))
        self._tl = QListWidget(); self._tl.setMaximumHeight(200)
        lo.addWidget(self._tl)
        el = QHBoxLayout(); el.addStretch()
        csv = QPushButton("导出 CSV"); csv.clicked.connect(self._export)
        el.addWidget(csv); lo.addLayout(el)
        self._bl.setStyleSheet("QListWidget::item { padding:8px 12px; margin:2px 0; }")

    def _get_range(self):
        t = dt_date.today()
        if self._time_range == "today": return t.isoformat(), t.isoformat()
        if self._time_range == "week":
            m = t - timedelta(days=t.weekday()); return m.isoformat(), t.isoformat()
        if self._time_range == "month":
            return t.replace(day=1).isoformat(), t.isoformat()
        return self._custom_from.isoformat(), self._custom_to.isoformat()

    def _on_tab(self, i):
        self._time_range = ["today","week","month","custom"][i]
        self._cw.setVisible(self._time_range=="custom"); self._drill_cat = None; self.refresh()

    def _on_apply(self):
        self._custom_from = self._df.date().toPython(); self._custom_to = self._dt.date().toPython()
        self._drill_cat = None; self.refresh()

    def _on_view(self, b):
        self._view_mode = "category" if self._vg.id(b)==0 else "program"
        self._drill_cat = None; self.refresh()

    def _on_chart(self, b):
        self._chart_type = "donut" if self._cg.id(b)==0 else "bar"; self.refresh()

    def _on_click(self, item):
        d = item.data(Qt.UserRole)
        if not d: return
        if self._view_mode=="category" and not self._drill_cat and d.get("type")=="category":
            self._drill_cat = d["label"]
            self._bc.setText(f"← 返回全部 | {self._drill_cat}"); self._bc.show(); self.refresh()

    def _open_settings(self):
        from classifier_edit import ClassifierEditDialog
        ClassifierEditDialog(self).exec(); self.refresh()

    def refresh(self):
        self._update_chart(); self._update_breakdown(); self._update_timeline()

    def _update_chart(self):
        if self._canvas:
            self._chart_lo.removeWidget(self._canvas); self._canvas.deleteLater(); self._canvas = None
        df, dt = self._get_range(); items = self._build_data(df, dt)
        if self._chart_type == "donut":
            t = sum(d["value"] for d in items)
            fig = charts.create_donut_chart(items, f"{t//3600}h {(t%3600)//60}m",
                {"today":"今日用时","week":"本周用时","month":"本月用时"}.get(self._time_range,"用时"))
        else:
            fig = charts.create_bar_chart(items)
        self._canvas = FigureCanvasQTAgg(fig); self._chart_lo.addWidget(self._canvas)

    def _update_breakdown(self):
        self._bl.clear(); df, dt = self._get_range(); items = self._build_data(df, dt)
        total = sum(d["value"] for d in items)
        for d in items:
            pct = round(d["value"]/total*100) if total else 0
            s = d["value"]; txt = f"{s//3600}h {(s%3600)//60}m" if s>=3600 else f"{s//60}m"
            item = QListWidgetItem(f"  {d['label']}    {txt}    {pct}%")
            item.setData(Qt.UserRole, d)
            pm = icon_extractor.get_icon_pixmap(d.get("icon_name",d["label"]), 24)
            if pm: item.setIcon(QIcon(pm))
            self._bl.addItem(item)

    def _update_timeline(self):
        self._tl.clear()
        df, dt = self._get_range()
        if self._time_range!="today": return
        for row in storage.get_activity_timeline(df):
            d = dict(row)
            s = d["duration"]; ds = f"{s//3600}h {(s%3600)//60}m" if s>=3600 else f"{s//60}m"
            txt = f"  {d['started_at'][11:16]}  {d['process']}  {d['window_title'][:35]}  {ds}  [{d['category']}]"
            item = QListWidgetItem(txt)
            pm = icon_extractor.get_icon_pixmap(d["process"], 20)
            if pm: item.setIcon(QIcon(pm))
            self._tl.addItem(item)

    def _build_data(self, df, dt):
        conf = cfg.load_config()
        cm = {c: conf["categories"].get(c,{}).get("color","#5A5A5A") for c in conf["categories"]}
        if self._view_mode=="category" and not self._drill_cat:
            rows = storage.get_range_summary(df, dt)
            return [{"label":r["category"],"value":r["total_seconds"],
                     "color":cm.get(r["category"],"#5A5A5A"),"highlight_key":r["category"],"type":"category"}
                    for r in rows]
        else:
            rows = storage.get_program_stats(df, dt)
            return [{"label":r["process"],"value":r["total_seconds"],
                     "color":icon_extractor.get_icon_color(r["process"]),
                     "highlight_key":r["process"],"icon_name":r["process"],"type":"program"}
                    for r in rows]

    def _export(self):
        import csv
        p, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "", "CSV (*.csv)")
        if not p: return
        df, dt = self._get_range()
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["进程","窗口标题","分类","开始时间","时长(秒)","日期"])
            for r in storage.get_activity_timeline(df):
                w.writerow([r["process"],r["window_title"],r["category"],r["started_at"],r["duration"],r.get("date","")])
