"""Classification rule editor dialog."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QHeaderView, QMessageBox)
import config as cfg

class ClassifierEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分类规则设置"); self.resize(650, 450)
        self.setStyleSheet("""
            QDialog { background-color:#1E2027; color:#EAE4D9; }
            QTableWidget { background-color:#24262E; color:#EAE4D9;
                gridline-color:#2E3039; border:1px solid #2E3039; }
            QHeaderView::section { background-color:#2E3039; color:#9B958A;
                padding:6px; border:none; font-size:11px; }
            QPushButton { background:#24262E; color:#9B958A; border:1px solid #2E3039;
                padding:6px 14px; border-radius:4px; font-size:11px; }
            QPushButton:hover { color:#EAE4D9; }
            QComboBox { background:#24262E; color:#EAE4D9; border:1px solid #2E3039;
                padding:4px 8px; border-radius:4px; }
        """)
        self._config = cfg.load_config()
        lo = QVBoxLayout(self)
        self._t = QTableWidget(0, 4)
        self._t.setHorizontalHeaderLabels(["进程","标题匹配(正则)","分类",""])
        self._t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._t.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._t.setColumnWidth(3, 60)
        lo.addWidget(self._t)
        bl = QHBoxLayout()
        add = QPushButton("+ 添加规则"); add.clicked.connect(self._add); bl.addWidget(add)
        bl.addStretch()
        sv = QPushButton("保存"); sv.setStyleSheet("background:#D4956B; color:#1A1C21; font-weight:bold;")
        sv.clicked.connect(self._save); bl.addWidget(sv)
        cl = QPushButton("关闭"); cl.clicked.connect(self.reject); bl.addWidget(cl)
        lo.addLayout(bl)
        self._load()

    def _load(self):
        self._t.setRowCount(0); cats = list(self._config["categories"].keys())
        for r in self._config["rules"]:
            row = self._t.rowCount(); self._t.insertRow(row)
            self._t.setItem(row, 0, QTableWidgetItem(r["process"]))
            self._t.setItem(row, 1, QTableWidgetItem(r.get("title_pattern","") or ""))
            cb = QComboBox(); cb.addItems(cats)
            if r["category"] in cats: cb.setCurrentIndex(cats.index(r["category"]))
            self._t.setCellWidget(row, 2, cb)
            db = QPushButton("✕"); db.setFixedSize(40,28)
            db.clicked.connect(lambda _, r=row: self._t.removeRow(r))
            self._t.setCellWidget(row, 3, db)

    def _add(self):
        row = self._t.rowCount(); self._t.insertRow(row)
        self._t.setItem(row, 0, QTableWidgetItem(""))
        self._t.setItem(row, 1, QTableWidgetItem(""))
        cb = QComboBox(); cb.addItems(list(self._config["categories"].keys()))
        self._t.setCellWidget(row, 2, cb)
        db = QPushButton("✕"); db.setFixedSize(40,28)
        db.clicked.connect(lambda _, r=row: self._t.removeRow(r))
        self._t.setCellWidget(row, 3, db)
        self._t.scrollToBottom()

    def _save(self):
        rules = []
        for i in range(self._t.rowCount()):
            p = self._t.item(i, 0); tp = self._t.item(i, 1); cb = self._t.cellWidget(i, 2)
            if not p or not p.text().strip(): continue
            rules.append({"process": p.text().strip(),
                "title_pattern": tp.text().strip() if tp and tp.text().strip() else None,
                "category": cb.currentText() if cb else "其他"})
        self._config["rules"] = rules; cfg.save_config(self._config)
        QMessageBox.information(self, "保存", "分类规则已保存。"); self.accept()
