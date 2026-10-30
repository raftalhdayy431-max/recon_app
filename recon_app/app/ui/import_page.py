"""صفحة استيراد الملفين وربط الأعمدة."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QBoxLayout, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
                               QAbstractItemView)

from ..loader import FIELDS, RawTable, auto_map, load_table, mapping_problems
from .widgets import DropZone, IconTile, human_size, PageHeader, icon

NONE_TXT = "— غير محدد —"
FIELD_HINTS = {
    "ref": "المفتاح الأقوى للمطابقة",
    "ref2": "اختياري: يُستخدم للبحث عن المرجع",
    "date": "لتقييم فروق التواريخ",
    "amount": "أو استخدم مدين/دائن",
    "debit": "المبلغ المدين",
    "credit": "المبلغ الدائن",
    "currency": "إن غاب يُستخدم الافتراضي",
    "fee": "لتفسير الفروق بالرسوم",
    "party": "يعزز دقة المطابقة الذكية",
    "desc": "قد يحوي رقم الحوالة",
}


class SourceCard(QFrame):
    changed = Signal()

    def __init__(self, side: str, title: str, subtitle: str, accent: str):
        super().__init__()
        self.side = side
        self.setObjectName("Card")
        self.table: Optional[RawTable] = None
        self.path = ""
        self._auto: dict[str, Optional[str]] = {}
        self._building = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(12)
        bar = QLabel(side)
        bar.setFixedSize(40, 40)
        bar.setAlignment(Qt.AlignCenter)
        bar.setStyleSheet(f"background:{accent}; color:#FFFFFF; border-radius:12px; font-weight:800; font-size:13pt;")
        head.addWidget(bar)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("H2")
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        tv.addWidget(t)
        tv.addWidget(s)
        head.addLayout(tv, 1)
        self.badge = QLabel("لم يُحمَّل بعد")
        self.badge.setObjectName("Badge")
        head.addWidget(self.badge)
        lay.addLayout(head)

        self.drop = DropZone("اسحب ملف Excel أو CSV هنا", "أو انقر للاختيار من جهازك — xlsx / xls / csv")
        self.drop.fileChosen.connect(self.load_path)
        lay.addWidget(self.drop)

        # خيارات الورقة والصف
        opts = QGridLayout()
        opts.setHorizontalSpacing(14)
        opts.setVerticalSpacing(12)
        opts.addWidget(QLabel("الورقة:"), 0, 0)
        self.sheet = QComboBox()
        self.sheet.currentIndexChanged.connect(self._reload_sheet)
        opts.addWidget(self.sheet, 0, 1)
        opts.addWidget(QLabel("صف العناوين:"), 0, 2)
        self.hdr = QSpinBox()
        self.hdr.setRange(1, 500)
        self.hdr.setFixedWidth(84)
        self.hdr.setToolTip("رقم الصف الذي يحوي عناوين الأعمدة")
        self.hdr.valueChanged.connect(self._reload_header)
        opts.addWidget(self.hdr, 0, 3)
        opts.addWidget(QLabel("العملة الافتراضية (إن غاب عمود العملة):"), 1, 0, 1, 3)
        self.def_cur = QLineEdit()
        self.def_cur.setPlaceholderText("SAR")
        self.def_cur.setFixedWidth(84)
        opts.addWidget(self.def_cur, 1, 3)
        opts.setColumnStretch(1, 1)
        lay.addLayout(opts)

        # ربط الأعمدة
        self.grid_w = QWidget()
        grid = QGridLayout(self.grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        self.combos: dict[str, QComboBox] = {}
        self.marks: dict[str, QLabel] = {}
        for i, (f, label) in enumerate(FIELDS.items()):
            r, c = divmod(i, 2)
            cell = QVBoxLayout()
            cell.setSpacing(6)
            top = QHBoxLayout()
            lb = QLabel(label)
            lb.setObjectName("H3")
            lb.setStyleSheet("font-size:9.5pt;")
            mk = QLabel("")
            mk.setObjectName("Badge")
            mk.hide()
            top.addWidget(lb)
            top.addWidget(mk)
            top.addStretch(1)
            cb = QComboBox()
            cb.addItem(NONE_TXT)
            cb.currentIndexChanged.connect(lambda _=0, ff=f: self._on_combo(ff))
            cell.addLayout(top)
            cell.addWidget(cb)
            w = QWidget()
            w.setLayout(cell)
            grid.addWidget(w, r, c)
            self.combos[f] = cb
            self.marks[f] = mk
        self.map_sec = self._collapsible("ربط الأعمدة", "تم الاكتشاف تلقائياً — انقر للمراجعة أو التعديل", self.grid_w, False)
        lay.addWidget(self.map_sec)
        self.problem = QLabel("")
        self.problem.setObjectName("Warn")
        self.problem.setWordWrap(True)
        self.problem.hide()
        lay.addWidget(self.problem)

        # معاينة
        self.preview = QTableWidget()
        self.preview.setMinimumHeight(220)
        self.preview.verticalHeader().setDefaultSectionSize(36)
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview.setSelectionMode(QAbstractItemView.NoSelection)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setAlternatingRowColors(True)
        self.preview.setShowGrid(False)
        self.preview.setWordWrap(False)
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.preview.horizontalHeader().setHighlightSections(False)
        lay.addWidget(self._collapsible("معاينة البيانات", "أول الصفوف بعد صف العناوين", self.preview, False))
        lay.addStretch(1)
        self._set_enabled(False)

    @staticmethod
    def _collapsible(title: str, sub: str, body: QWidget, expanded: bool) -> QWidget:
        """قسم قابل للطي (واجهة فقط)."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(10)
        btn = QPushButton()
        btn.setObjectName("Ghost")
        btn.setCheckable(True)
        btn.setChecked(expanded)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("text-align:right; padding:10px 14px;")

        def refresh(on: bool):
            btn.setText(f"{'▾' if on else '◂'}   {title}   ·   {sub}")
            body.setVisible(on)
        btn.toggled.connect(refresh)
        refresh(expanded)
        v.addWidget(btn)
        v.addWidget(body)
        w.btn = btn
        return w

    @staticmethod
    def _section(title: str, sub: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 10, 0, 2)
        a = QLabel(title)
        a.setObjectName("H3")
        b = QLabel(sub)
        b.setObjectName("Muted")
        h.addWidget(a)
        h.addWidget(b)
        h.addStretch(1)
        return w

    def _set_enabled(self, on: bool):
        for w in (self.sheet, self.hdr, self.grid_w):
            w.setEnabled(on)

    # ----------------------------------------------------------- تحميل
    def load_path(self, path: str, sheet: Optional[str] = None, header: Optional[int] = None):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            tbl = load_table(path, sheet, header)
        except Exception as ex:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "تعذّرت قراءة الملف", f"{ex}")
            return
        QApplication.restoreOverrideCursor()
        self.table, self.path = tbl, path
        self._building = True
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.addItems(tbl.sheets)
        self.sheet.setCurrentText(tbl.sheet)
        self.sheet.blockSignals(False)
        self.hdr.blockSignals(True)
        self.hdr.setValue(tbl.header_row)
        self.hdr.blockSignals(False)
        self._fill_combos()
        self._building = False
        self._set_enabled(True)
        self.drop.set_loaded(tbl.name, f"{len(tbl.rows):,} صفاً  ·  {human_size(path)}")
        self.badge.setText(f"{len(tbl.rows):,} عملية")
        self._refresh_preview()
        self._validate()
        # واجهة فقط: يُفتح الربط تلقائياً عند وجود مشكلة، ويُطوى إن سار كل شيء بسلاسة
        self.map_sec.btn.setChecked(not self.problem.isHidden())
        self.changed.emit()

    def _reload_sheet(self):
        if self._building or not self.table:
            return
        self.load_path(self.path, self.sheet.currentText(), None)

    def _reload_header(self):
        if self._building or not self.table:
            return
        self.load_path(self.path, self.sheet.currentText(), self.hdr.value())

    def _fill_combos(self):
        tbl = self.table
        self._auto = auto_map(tbl)
        for f, cb in self.combos.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem(NONE_TXT)
            cb.addItems(tbl.columns)
            col = self._auto.get(f)
            cb.setCurrentText(col if col else NONE_TXT)
            cb.blockSignals(False)
            self._mark(f)

    def _mark(self, f: str):
        mk = self.marks[f]
        cur = self.combos[f].currentText()
        if cur == NONE_TXT:
            mk.hide()
            return
        mk.show()
        if self._auto.get(f) == cur:
            mk.setText("تلقائي ✓")
            mk.setObjectName("BadgeOk")
        else:
            mk.setText("يدوي")
            mk.setObjectName("BadgeWarn")
        mk.style().unpolish(mk)
        mk.style().polish(mk)

    def _on_combo(self, f: str):
        if self._building:
            return
        self._mark(f)
        self._refresh_preview()
        self._validate()
        self.changed.emit()

    def _refresh_preview(self):
        tbl = self.table
        if not tbl:
            return
        rows = tbl.rows[:8]
        self.preview.setColumnCount(len(tbl.columns))
        self.preview.setRowCount(len(rows))
        mapped = {v: k for k, v in self.mapping().items() if v}
        heads = []
        for c in tbl.columns:
            heads.append(f"{c}\n⟵ {FIELDS[mapped[c]]}" if c in mapped else c)
        self.preview.setHorizontalHeaderLabels(heads)
        for i, (_, vals) in enumerate(rows):
            for j, v in enumerate(vals):
                txt = "" if v is None else (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v))
                it = QTableWidgetItem(txt)
                self.preview.setItem(i, j, it)
        self.preview.resizeColumnsToContents()
        for j in range(self.preview.columnCount()):
            self.preview.setColumnWidth(j, min(max(self.preview.columnWidth(j), 90), 220))

    def mapping(self) -> dict[str, Optional[str]]:
        return {f: (None if cb.currentText() == NONE_TXT else cb.currentText()) for f, cb in self.combos.items()}

    def default_currency(self) -> str:
        return self.def_cur.text().strip().upper()

    def problems(self) -> list[str]:
        return mapping_problems(self.mapping()) if self.table else ["لم يتم تحميل الملف."]

    def is_ready(self) -> bool:
        if not self.table:
            return False
        return any(self.mapping().get(f) for f in ("amount", "debit", "credit"))

    def _validate(self):
        probs = self.problems() if self.table else []
        if probs:
            self.problem.setText("  •  ".join(probs))
            self.problem.show()
        else:
            self.problem.hide()


class ImportPage(QWidget):
    startRequested = Signal()
    reloadLastRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 22)
        outer.setSpacing(10)

        chips = QWidget()
        chips.setObjectName("Plain")
        ch = QHBoxLayout(chips)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(10)
        for i, t in enumerate(("١  استيراد الملفين", "٢  ضبط القواعد", "٣  مراجعة النتائج وتصدير التقرير")):
            c = QLabel(t)
            c.setObjectName("HeroChip")
            ch.addWidget(c)
            if i < 2:
                ar = QLabel("◂")
                ar.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
                ch.addWidget(ar)
        ch.addStretch(1)
        self.header = PageHeader("استيراد الملفات",
                                 "حمّل ملف المحاسب وملف الصرافة. يكتشف البرنامج صف العناوين والأعمدة تلقائياً، ويمكنك تعديلها قبل البدء.",
                                 "import", chips)
        outer.addWidget(self.header)

        self.last_bar = QFrame()
        self.last_bar.setObjectName("ActionBar")
        lb = QHBoxLayout(self.last_bar)
        lb.setContentsMargins(18, 10, 14, 10)
        lb.setSpacing(12)
        lb.addWidget(IconTile("files", "#0D9488", 36))
        self.last_txt = QLabel("")
        self.last_txt.setStyleSheet("background: transparent;")
        lb.addWidget(self.last_txt, 1)
        self.btn_last = QPushButton("إعادة تحميل الملفين")
        self.btn_last.setCursor(Qt.PointingHandCursor)
        self.btn_last.clicked.connect(self.reloadLastRequested.emit)
        lb.addWidget(self.btn_last)
        self.last_bar.hide()
        outer.addWidget(self.last_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        row = QHBoxLayout(inner)
        row.setContentsMargins(0, 14, 10, 10)
        row.setSpacing(24)
        self._row = row
        self.card_a = SourceCard("A", "ملف المحاسب المالي", "كشف الحساب / دفتر الأستاذ", "#2563EB")
        self.card_b = SourceCard("B", "ملف الصرافة", "كشف الحوالات الصادر من الصرافة", "#E09F3E")
        row.addWidget(self.card_a, 1, Qt.AlignTop)
        row.addWidget(self.card_b, 1, Qt.AlignTop)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        bar_frame = QFrame()
        bar_frame.setObjectName("ActionBar")
        bar = QHBoxLayout(bar_frame)
        bar.setContentsMargins(22, 16, 18, 16)
        bar.setSpacing(14)
        self.status = QLabel("حمّل الملفين للمتابعة.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        bar.addWidget(self.status, 1)
        self.btn_sample = QPushButton("تجربة ببيانات نموذجية")
        self.btn_sample.setObjectName("Ghost")
        self.btn_sample.setCursor(Qt.PointingHandCursor)
        self.btn_sample.setToolTip("يولّد ملفين تجريبيين ويحمّلهما للتجربة الفورية")
        bar.addWidget(self.btn_sample)
        self.btn_start = QPushButton("  بدء المطابقة")
        self.btn_start.setIcon(icon("bolt", "#FFFFFF", 18))
        self.btn_start.setObjectName("Primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.startRequested.emit)
        bar.addWidget(self.btn_start)
        outer.addSpacing(6)
        outer.addWidget(bar_frame)

        self.card_a.changed.connect(self._update)
        self.card_b.changed.connect(self._update)

    def set_last_run(self, text):
        """شريط «آخر مطابقة» (عرض فقط)."""
        self.last_txt.setText(text or "")
        self.last_bar.setVisible(bool(text))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # عند ضيق الصفحة تُرتَّب البطاقتان فوق بعضهما بدل جنباً إلى جنب
        want = QBoxLayout.TopToBottom if self.width() < 1180 else QBoxLayout.LeftToRight
        if self._row.direction() != want:
            self._row.setDirection(want)

    def _update(self):
        ra, rb = self.card_a.is_ready(), self.card_b.is_ready()
        self.btn_start.setEnabled(ra and rb)
        if ra and rb:
            self.status.setText("الملفان جاهزان ✔  — راجع القواعد من الشريط الجانبي أو ابدأ مباشرة.")
        elif self.card_a.table and self.card_b.table:
            self.status.setText("أكمل ربط عمود المبلغ (أو مدين/دائن) في كلا الملفين.")
        else:
            self.status.setText("حمّل الملفين للمتابعة.")
