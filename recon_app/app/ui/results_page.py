"""صفحة النتائج: نظرة عامة + تفاصيل العمليات + لوحة التفسير."""
from __future__ import annotations

import difflib
import html as _html
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QBoxLayout, QCheckBox, QComboBox, QFrame,
                               QGridLayout, QStyle,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSplitter, QStyledItemDelegate, QStyleOptionViewItem,
                               QTableView, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget, QMessageBox, QDialog, QMenu, QProgressBar)

from ..engine import (ALL_STATUSES, BRIDGE_ORDER, MatchRow, ReconResult, STATUS_DIFF, STATUS_DUP,
                      STATUS_MATCHED, STATUS_MISSING_A, STATUS_MISSING_B, STATUS_POSSIBLE,
                      manual_link)
from ..normalize import q2
from .theme import PRIORITY, STATUS, status_colors
from .widgets import DonutChart, HBar, IconTile, KpiCard, PageHeader, StatusChip, add_shadow, icon

ROW_ROLE = Qt.UserRole + 1
STATUS_ICON = {STATUS_MATCHED: 'check', STATUS_DIFF: 'diff', STATUS_POSSIBLE: 'search',
               STATUS_MISSING_B: 'alert', STATUS_MISSING_A: 'alert', STATUS_DUP: 'copy'}


def fm_plain(d) -> str:
    return "" if d is None else f"{q2(Decimal(d)):,.2f}"


def fm(d) -> str:
    """رقم منسّق مع فرض الاتجاه LTR حتى لا تنقلب إشارة السالب في الواجهة العربية."""
    t = fm_plain(d)
    return f"\u202a{t}\u202c" if t else ""


# =============================================================================
class ResultsModel(QAbstractTableModel):
    COLS = ["#", "الحالة", "الأولوية", "المرجع", "العملة", "محاسب", "صرافة", "الفرق", "الثقة", "قرار"]

    def __init__(self):
        super().__init__()
        self.rows: list[MatchRow] = []

    def set_rows(self, rows: list[MatchRow]):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLS[s]
        return None

    def _val(self, r: MatchRow, c: int):
        if c == 0:
            return r.id
        if c == 1:
            return r.status
        if c == 2:
            return r.priority
        if c == 3:
            return r.ref
        if c == 4:
            return r.currency
        if c == 5:
            return r.amt_a
        if c == 6:
            return r.amt_b
        if c == 7:
            return r.diff
        if c == 8:
            return r.confidence
        return {"معتمد": "✔", "مرفوض": "✖"}.get(r.decision, "")

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        r = self.rows[idx.row()]
        c = idx.column()
        if role == ROW_ROLE:
            return r
        v = self._val(r, c)
        if role == Qt.DisplayRole:
            if c in (5, 6, 7):
                return fm(v) if v is not None else "—"
            if c == 8:
                return f"{v}%" if r.status != STATUS_MISSING_A and r.status != STATUS_MISSING_B else "—"
            return "" if v is None else str(v)
        if role == Qt.UserRole:  # للفرز
            if c in (5, 6):
                return float(v) if v is not None else -1e18
            if c == 7:
                return abs(float(v))
            if c == 1:
                from ..engine import STATUS_ORDER
                return STATUS_ORDER[r.status]
            if c == 2:
                return {"عالية": 0, "متوسطة": 1, "منخفضة": 2}.get(r.priority, 3)
            return v if isinstance(v, (int, float)) else str(v)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)
        if role == Qt.ForegroundRole:
            if c == 2:
                return QColor(PRIORITY.get(r.priority, "#667085"))
            if c == 7 and r.diff != 0 and q2(r.diff) != 0:
                return QColor("#D64535")
            if c == 9 and r.decision:
                return QColor("#1F9D55" if r.decision == "معتمد" else "#D64535")
        if role == Qt.ToolTipRole and c == 9 and r.decision:
            return f"قرار المراجع: {r.decision}" + (f" — {r.note}" if r.note else "")
        if role == Qt.FontRole and c in (2, 7, 9):
            from PySide6.QtGui import QFont
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ToolTipRole and c in (1, 3):
            return r.reason_text
        return None

    def row_changed(self, row_obj: MatchRow):
        try:
            i = self.rows.index(row_obj)
        except ValueError:
            return
        self.dataChanged.emit(self.index(i, 0), self.index(i, len(self.COLS) - 1))


class StatusDelegate(QStyledItemDelegate):
    dark = False

    def _line(self, p: QPainter, opt):
        """خط فاصل رفيع أسفل كل صف (واجهة فقط)."""
        p.save()
        p.setPen(QColor("#22393C" if self.dark else "#E3EBEC"))
        y = opt.rect.bottom()
        p.drawLine(opt.rect.left(), y, opt.rect.right(), y)
        p.restore()

    def paint(self, p: QPainter, opt: QStyleOptionViewItem, idx: QModelIndex):
        if idx.column() != 1:
            super().paint(p, opt, idx)
            self._line(p, opt)
            return
        text = idx.data(Qt.DisplayRole)
        main, bg = status_colors(text, self.dark)
        # ارسم خلفية الصف/التحديد أولاً بدون نص ثم الشريحة الملونة فوقها
        base = QStyleOptionViewItem(opt)
        self.initStyleOption(base, idx)
        base.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, base, p, opt.widget)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(4, 6, -4, -6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor(main))
        f = p.font()
        f.setBold(True)
        f.setPointSizeF(8.2)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, text)
        p.restore()
        self._line(p, opt)


class FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.statuses: set[str] = set()
        self.text = ""
        self.priority = ""
        self.only_pending = False
        self.setSortRole(Qt.UserRole)

    def set_filters(self, statuses=None, text=None, priority=None, only_pending=None):
        if statuses is not None:
            self.statuses = statuses
        if text is not None:
            self.text = text.strip().lower()
        if priority is not None:
            self.priority = priority
        if only_pending is not None:
            self.only_pending = only_pending
        self.invalidateFilter()

    def filterAcceptsRow(self, src_row, parent):
        r: MatchRow = self.sourceModel().rows[src_row]
        if self.statuses and r.status not in self.statuses:
            return False
        if self.priority and r.priority != self.priority:
            return False
        if self.only_pending and r.decision:
            return False
        if self.only_pending and r.status == STATUS_MATCHED and r.priority in ("—", ""):
            return False
        if self.text:
            blob = " ".join([r.ref, r.reason_text, r.a.party if r.a else "", r.b.party if r.b else "",
                             r.a.desc if r.a else "", str(r.id), r.currency, fm_plain(r.amt_a), fm_plain(r.amt_b)]).lower()
            if self.text not in blob:
                return False
        return True


# =============================================================================
class RecordCard(QFrame):
    FIELDS = [("row", "الصف"), ("ref", "المرجع"), ("date", "التاريخ"), ("party", "الاسم"),
              ("currency", "العملة"), ("amount", "المبلغ"), ("fee", "الرسوم"), ("desc", "البيان")]

    def __init__(self, title: str, accent: str):
        super().__init__()
        self.setObjectName("CardFlat")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        h = QHBoxLayout()
        bar = QFrame()
        bar.setFixedSize(4, 18)
        bar.setStyleSheet(f"background:{accent}; border-radius:2px;")
        t = QLabel(title)
        t.setObjectName("H3")
        h.addWidget(bar)
        h.addWidget(t)
        h.addStretch(1)
        lay.addLayout(h)
        self.empty = QLabel("لا توجد عملية مقابلة")
        self.empty.setObjectName("Muted")
        lay.addWidget(self.empty)
        self.grid_w = QWidget()
        g = QGridLayout(self.grid_w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(8)
        g.setHorizontalSpacing(14)
        self.vals: dict[str, QLabel] = {}
        for i, (k, lbl) in enumerate(self.FIELDS):
            a = QLabel(lbl)
            a.setObjectName("Muted")
            v = QLabel("")
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(a, i, 0, Qt.AlignTop)
            g.addWidget(v, i, 1)
            self.vals[k] = v
        g.setColumnStretch(1, 1)
        lay.addWidget(self.grid_w)

    def show_record(self, rec, amount_eff: Optional[Decimal], bad: set[str]):
        if rec is None:
            self.grid_w.hide()
            self.empty.show()
            return
        self.empty.hide()
        self.grid_w.show()
        vals = {"row": str(rec.row), "ref": rec.ref or "—",
                "date": rec.date.strftime("%Y-%m-%d") if rec.date else "—",
                "party": rec.party or "—", "currency": rec.currency or "—",
                "amount": fm(rec.amount), "fee": fm(rec.fee) if rec.fee else "—", "desc": rec.desc or "—"}
        for k, lab in self.vals.items():
            lab.setText(vals[k])
            if k in bad:
                lab.setStyleSheet("color:#D64535; font-weight:700;")
            else:
                lab.setStyleSheet("font-weight:600;" if k in ("amount", "ref") else "")


class CompareCard(QFrame):
    """مقارنة مدمجة: الحقل | المحاسب | الصرافة في شبكة واحدة (واجهة فقط)."""
    FIELDS = RecordCard.FIELDS

    def __init__(self):
        super().__init__()
        self.setObjectName("CardFlat")
        g = QGridLayout(self)
        g.setContentsMargins(16, 14, 16, 14)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(7)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        g.addWidget(QLabel(""), 0, 0)
        for col, (t, acc) in enumerate((("ملف المحاسب", "#2563EB"), ("ملف الصرافة", "#E09F3E")), start=1):
            l = QLabel(f"<span style='color:{acc};'>●</span>  {t}")
            l.setObjectName("H3")
            g.addWidget(l, 0, col)
        sep = QFrame()
        sep.setObjectName("HLine")
        g.addWidget(sep, 1, 0, 1, 3)
        self.vals: dict[str, tuple[QLabel, QLabel]] = {}
        for i, (k, lbl) in enumerate(self.FIELDS, start=2):
            a = QLabel(lbl)
            a.setObjectName("Muted")
            va, vb = QLabel(""), QLabel("")
            for v in (va, vb):
                v.setWordWrap(True)
                v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(a, i, 0, Qt.AlignTop)
            g.addWidget(va, i, 1)
            g.addWidget(vb, i, 2)
            self.vals[k] = (va, vb)

    @staticmethod
    def _vals(rec):
        if rec is None:
            return {k: "—" for k, _ in RecordCard.FIELDS}
        return {"row": str(rec.row), "ref": rec.ref or "—",
                "date": rec.date.strftime("%Y-%m-%d") if rec.date else "—",
                "party": rec.party or "—", "currency": rec.currency or "—",
                "amount": fm(rec.amount), "fee": fm(rec.fee) if rec.fee else "—", "desc": rec.desc or "—"}

    @staticmethod
    def _hl(s: str, other: str) -> str:
        """يلوّن الأحرف المختلفة بين نصّين (للمرجع والاسم)."""
        out = []
        for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, s, other).get_opcodes():
            seg = _html.escape(s[i1:i2])
            if tag == "equal" or not seg:
                out.append(seg)
            else:
                out.append(f"<span style='color:#D64535; font-weight:800; background-color:rgba(214,69,53,0.16);'>{seg}</span>")
        return "".join(out)

    def show_records(self, a, b, bad: set[str]):
        vs = (self._vals(a), self._vals(b))
        for side, rec in ((0, a), (1, b)):
            vals = vs[side]
            for k, labs in self.vals.items():
                lab = labs[side]
                if k in ("ref", "party"):
                    lab.setTextFormat(Qt.RichText)
                    mine, other = vals[k], vs[1 - side][k]
                    if a is not None and b is not None and k in bad and mine != other:
                        lab.setText("\u202a" + self._hl(mine, other) + "\u202c")
                    else:
                        lab.setText(_html.escape(mine))
                    lab.setStyleSheet("font-weight:600;" if k == "ref" else "")
                    continue
                lab.setText(vals[k])
                if k in bad:
                    lab.setStyleSheet("color:#D64535; font-weight:700;")
                else:
                    lab.setStyleSheet("font-weight:600;" if k in ("amount", "ref") else "")


class DetailPanel(QFrame):
    decisionChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self.row: Optional[MatchRow] = None
        self.dark = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        lay.addWidget(self.scroll)
        self.body = QWidget()
        self.body.setObjectName("Plain")
        self.scroll.setWidget(self.body)
        v = QVBoxLayout(self.body)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(14)

        self.placeholder = QLabel("اختر عملية من الجدول\nلعرض التفسير والإجراء المقترح ومراجعتها.")
        self.placeholder.setObjectName("Muted")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setMinimumHeight(240)
        self.placeholder.setWordWrap(True)
        v.addWidget(self.placeholder)

        self.content = QWidget()
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(16)
        top = QHBoxLayout()
        self.chip = StatusChip("")
        top.addWidget(self.chip)
        self.title = QLabel("")
        self.title.setObjectName("H3")
        top.addWidget(self.title)
        top.addStretch(1)
        c.addLayout(top)
        conf = QHBoxLayout()
        self.conf_lbl = QLabel("")
        self.conf_lbl.setObjectName("Muted")
        self.conf_bar = HBar()
        conf.addWidget(self.conf_lbl)
        conf.addWidget(self.conf_bar, 1)
        c.addLayout(conf)

        self.compare = CompareCard()
        c.addWidget(self.compare)

        self.diff_lbl = QLabel("")
        self.diff_lbl.setObjectName("H2")
        c.addWidget(self.diff_lbl)

        c.addWidget(self._h("لماذا هذه النتيجة؟"))
        self.reasons = QLabel("")
        self.reasons.setWordWrap(True)
        self.reasons.setTextFormat(Qt.RichText)
        c.addWidget(self.reasons)
        c.addWidget(self._h("الإجراء المقترح"))
        self.action = QLabel("")
        self.action.setWordWrap(True)
        self.action.setObjectName("Warn")
        c.addWidget(self.action)

        c.addWidget(self._h("قرار المراجع"))
        db = QHBoxLayout()
        self.b_ok = QPushButton("✔  اعتماد")
        self.b_ok.setObjectName("Good")
        self.b_no = QPushButton("✖  رفض")
        self.b_no.setObjectName("Bad")
        self.b_clr = QPushButton("مسح القرار")
        self.b_clr.setObjectName("Ghost")
        db.setSpacing(12)
        for b in (self.b_ok, self.b_no, self.b_clr):
            b.setCursor(Qt.PointingHandCursor)
            db.addWidget(b)
        c.addLayout(db)
        self.note = QLineEdit()
        self.note.setPlaceholderText("ملاحظة المراجع (تُحفظ في التقرير)…")
        self.note.setClearButtonEnabled(True)
        c.addWidget(self.note)
        v.addWidget(self.content)
        v.addStretch(1)
        self.content.hide()

        self.b_ok.clicked.connect(lambda: self._decide("معتمد"))
        self.b_no.clicked.connect(lambda: self._decide("مرفوض"))
        self.b_clr.clicked.connect(lambda: self._decide(""))
        self.note.editingFinished.connect(self._save_note)

    @staticmethod
    def _h(t: str) -> QLabel:
        l = QLabel(t)
        l.setObjectName("H3")
        return l

    def resizeEvent(self, e):
        super().resizeEvent(e)
        pass

    def clear(self):
        self.row = None
        self.content.hide()
        self.placeholder.show()

    def show_row(self, r: MatchRow):
        self.row = r
        self.placeholder.hide()
        self.content.show()
        self.chip.set_status(r.status, self.dark)
        self.title.setText(f"عملية رقم {r.id}  ·  {r.method}")
        col = "#1F9D55" if r.confidence >= 90 else ("#D99100" if r.confidence >= 70 else "#D64535")
        if r.status in (STATUS_MISSING_A, STATUS_MISSING_B):
            self.conf_lbl.setText("لا يوجد مقابل")
            self.conf_bar.set(0)
        else:
            self.conf_lbl.setText(f"الثقة {r.confidence}%")
            self.conf_bar.set(r.confidence, col)
        bad = set()
        if r.a and r.b:
            if r.a.ref_norm != r.b.ref_norm:
                bad.add("ref")
            if "amount" in r.flags or "sign" in r.flags:
                bad.add("amount")
            if "currency" in r.flags:
                bad.add("currency")
            if "date" in r.flags:
                bad.add("date")
            if "party" in r.flags:
                bad.add("party")
        self.compare.show_records(r.a, r.b, bad)
        cur = r.currency
        d = q2(r.diff)
        self.diff_lbl.setText(f"الفرق (محاسب − صرافة):  {fm(d)} {cur}")
        self.diff_lbl.setStyleSheet(f"color: {'#D64535' if d != 0 else '#1F9D55'};")
        self.reasons.setText("<ul style='margin:0; padding-right:16px;'>" +
                             "".join(f"<li style='margin-bottom:4px;'>{x}</li>" for x in r.reasons) + "</ul>")
        self.action.setText(r.action)
        self.note.setText(r.note)
        self._style_decision()

    def _style_decision(self):
        r = self.row
        if not r:
            return
        self.b_ok.setEnabled(r.decision != "معتمد")
        self.b_no.setEnabled(r.decision != "مرفوض")
        self.b_clr.setEnabled(bool(r.decision))

    def _decide(self, d: str):
        if not self.row:
            return
        self.row.decision = d
        self._style_decision()
        self.decisionChanged.emit(self.row)

    def _save_note(self):
        if self.row and self.row.note != self.note.text():
            self.row.note = self.note.text()
            self.decisionChanged.emit(self.row)


class ReviewDialog(QDialog):
    """وضع المراجعة السريعة: عملية واحدة بكامل الشاشة مع اختصارات (واجهة فقط)."""

    def __init__(self, rows: list, dark: bool, on_change, parent=None):
        super().__init__(parent)
        self.setWindowTitle("المراجعة السريعة")
        self.resize(820, 860)
        self.rows = rows
        self.i = 0
        self.on_change = on_change
        self._prev: dict[int, str] = {r.id: r.decision for r in rows}
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(12)
        top = QHBoxLayout()
        t = QLabel("المراجعة السريعة")
        t.setObjectName("H2")
        self.pos = QLabel("")
        self.pos.setObjectName("Badge")
        top.addWidget(t)
        top.addStretch(1)
        top.addWidget(self.pos)
        v.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        v.addWidget(self.bar)
        self.panel = DetailPanel()
        self.panel.dark = dark
        self.panel.decisionChanged.connect(self._decided)
        v.addWidget(self.panel, 1)
        self.done_lbl = QLabel("اكتملت المراجعة — لا توجد عمليات أخرى بانتظار قرارك.")
        self.done_lbl.setObjectName("BadgeOk")
        self.done_lbl.setAlignment(Qt.AlignCenter)
        self.done_lbl.hide()
        v.addWidget(self.done_lbl)
        nav = QHBoxLayout()
        self.b_prev = QPushButton("السابق  (→)")
        self.b_prev.setObjectName("Ghost")
        self.b_next = QPushButton("التالي  (←)")
        self.b_next.setObjectName("Ghost")
        close = QPushButton("إغلاق  (Esc)")
        hint = QLabel("A اعتماد   ·   R رفض   ·   ← → تنقّل")
        hint.setObjectName("Muted")
        for b in (self.b_prev, self.b_next, close):
            b.setCursor(Qt.PointingHandCursor)
        nav.addWidget(self.b_prev)
        nav.addWidget(self.b_next)
        nav.addWidget(hint, 1, Qt.AlignCenter)
        nav.addWidget(close)
        v.addLayout(nav)
        self.b_prev.clicked.connect(lambda: self.go(self.i - 1))
        self.b_next.clicked.connect(lambda: self.go(self.i + 1))
        close.clicked.connect(self.accept)
        for key, fn in (("A", lambda: self._press(self.panel.b_ok)), ("R", lambda: self._press(self.panel.b_no)),
                        ("Left", lambda: self.go(self.i + 1)), ("Right", lambda: self.go(self.i - 1))):
            QShortcut(QKeySequence(key), self, activated=fn)
        self.go(0)

    @staticmethod
    def _press(btn):
        if btn.isEnabled():
            btn.click()

    def go(self, i: int):
        if not self.rows:
            return
        self.i = max(0, min(len(self.rows) - 1, i))
        self.panel.show_row(self.rows[self.i])
        self._refresh()

    def _refresh(self):
        n = len(self.rows)
        left = sum(1 for r in self.rows if not r.decision)
        self.pos.setText(f"عملية {self.i + 1} من {n}   ·   متبقٍّ {left}")
        self.bar.setMaximum(max(n, 1))
        self.bar.setValue(n - left)
        self.b_prev.setEnabled(self.i > 0)
        self.b_next.setEnabled(self.i < n - 1)
        self.done_lbl.setVisible(left == 0)

    def _decided(self, row):
        self.on_change(row)
        changed = row.decision != self._prev.get(row.id, "")
        self._prev[row.id] = row.decision
        self._refresh()
        if changed and row.decision and row is self.rows[self.i]:
            nxt = next((k for k in range(self.i + 1, len(self.rows)) if not self.rows[k].decision), None)
            if nxt is None:
                nxt = next((k for k in range(0, self.i) if not self.rows[k].decision), None)
            if nxt is not None:
                QTimer.singleShot(160, lambda k=nxt: self.go(k))


# =============================================================================
class ResultsPage(QWidget):
    exportRequested = Signal()
    newRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.res: Optional[ReconResult] = None
        self.dark = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 18)
        outer.setSpacing(12)

        self.header = PageHeader("نتائج المطابقة", "", "chart")
        self.sub = self.header.sub
        self.btn_new = QPushButton("مطابقة جديدة")
        self.btn_new.setObjectName("HeroBtn")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.setToolTip("العودة إلى صفحة الاستيراد لبدء مطابقة جديدة")
        self.btn_new.clicked.connect(self.newRequested.emit)
        self.btn_export = QPushButton("  تصدير تقرير Excel")
        self.btn_export.setIcon(icon("export", "#0B6F66", 18))
        self.btn_export.setObjectName("HeroSolid")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.clicked.connect(self.exportRequested.emit)
        self.header.add_action(self.btn_new)
        self.header.add_action(self.btn_export)
        outer.addWidget(self.header)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self._build_overview()
        self._build_details()

    # ------------------------------------------------------------------ نظرة عامة
    def _build_overview(self):
        w = QWidget()
        w.setObjectName("Page")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 18, 10, 12)
        v.setSpacing(22)

        self.insight = QFrame()
        self.insight.setObjectName("Card")
        il = QHBoxLayout(self.insight)
        il.setContentsMargins(22, 16, 22, 16)
        il.setSpacing(16)
        il.addWidget(IconTile("bolt", "#0D9488", 52))
        itv = QVBoxLayout()
        itv.setSpacing(2)
        it = QLabel("ابدأ من هنا")
        it.setObjectName("H3")
        self.insight_txt = QLabel("")
        self.insight_txt.setWordWrap(True)
        self.insight_txt.setStyleSheet("background: transparent;")
        itv.addWidget(it)
        itv.addWidget(self.insight_txt)
        il.addLayout(itv, 1)
        self.btn_review = QPushButton("  ابدأ مراجعة الأهم")
        self.btn_review.setObjectName("Primary")
        self.btn_review.setIcon(icon("bolt", "#FFFFFF", 18))
        self.btn_review.setCursor(Qt.PointingHandCursor)
        self.btn_review.setToolTip("يعرض العمليات المنتظرة قراراً واحدة تلو الأخرى، مرتبة بالأهم أولاً")
        self.btn_review.clicked.connect(self.start_review)
        il.addWidget(self.btn_review)
        add_shadow(self.insight, 22, 4, 22)
        v.addWidget(self.insight)

        self._grid1 = QGridLayout()
        self._grid1.setSpacing(18)
        self.k_a = KpiCard("عمليات المحاسب", "#2563EB", icon_kind="files")
        self.k_b = KpiCard("عمليات الصرافة", "#E09F3E", icon_kind="files")
        self.k_rate = KpiCard("نسبة التطابق", "#1F9D55", icon_kind="percent")
        self.k_rev = KpiCard("تحتاج مراجعة", "#D64535", icon_kind="alert")
        self._kpis1 = [self.k_a, self.k_b, self.k_rate, self.k_rev]
        v.addLayout(self._grid1)

        self._grid2 = QGridLayout()
        self._grid2.setSpacing(18)
        self.status_cards: dict[str, KpiCard] = {}
        for s in ALL_STATUSES:
            k = KpiCard(s, STATUS[s][0], clickable=True, icon_kind=STATUS_ICON.get(s, 'check'))
            k.clicked.connect(lambda ss=s: self.focus_status(ss))
            k.setToolTip("انقر لعرض هذه الحالة في تفاصيل العمليات")
            self.status_cards[s] = k
        self._kpis2 = list(self.status_cards.values())
        v.addLayout(self._grid2)
        self._cols1 = self._cols2 = 0
        self._reflow_kpis(4, 6)

        row3 = QHBoxLayout()
        row3.setSpacing(22)
        left = QFrame()
        left.setObjectName("Card")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(24, 22, 24, 22)
        lv.setSpacing(12)
        t = QLabel("توزيع النتائج")
        t.setObjectName("H2")
        lv.addWidget(t)
        self.donut = DonutChart()
        lv.addWidget(self.donut, 1)
        self.legend = QVBoxLayout()
        self.legend.setSpacing(8)
        lv.addLayout(self.legend)
        left.setMaximumWidth(400)
        left.setMinimumHeight(0)
        row3.addWidget(left)

        right = QFrame()
        right.setObjectName("Card")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(24, 22, 24, 22)
        rv.setSpacing(12)
        hh = QHBoxLayout()
        t2 = QLabel("الفروقات المالية وتحليلها")
        t2.setObjectName("H2")
        hh.addWidget(t2)
        hh.addStretch(1)
        self.integrity = QLabel("")
        self.integrity.setObjectName("BadgeOk")
        hh.addWidget(self.integrity)
        rv.addLayout(hh)
        self.rel_note = QLabel("")
        self.rel_note.setObjectName("Muted")
        self.rel_note.setWordWrap(True)
        rv.addWidget(self.rel_note)
        self.fin = QTableWidget()
        self.fin.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fin.setSelectionMode(QAbstractItemView.NoSelection)
        self.fin.verticalHeader().setVisible(False)
        self.fin.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.fin.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.fin.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rv.addWidget(self.fin, 1)
        self.warn = QLabel("")
        self.warn.setObjectName("Warn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        rv.addWidget(self.warn)
        row3.addWidget(right, 1)
        v.addLayout(row3, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(w)
        self.tabs.addTab(scroll, "نظرة عامة")

    def _build_details(self):
        w = QWidget()
        w.setObjectName("Page")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 18, 0, 0)
        v.setSpacing(14)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.chips: dict[str, QPushButton] = {}
        for s in ALL_STATUSES:
            b = QPushButton(s)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.toggled.connect(self._filters_changed)
            self.chips[s] = b
            bar.addWidget(b)
        bar.addStretch(1)
        v.addLayout(bar)
        bar2 = QHBoxLayout()
        bar2.setSpacing(14)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  ابحث بالمرجع أو الاسم أو المبلغ أو السبب…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filters_changed)
        bar2.addWidget(self.search, 1)
        self.prio = QComboBox()
        self.prio.addItems(["كل الأولويات", "عالية", "متوسطة", "منخفضة"])
        self.prio.currentIndexChanged.connect(self._filters_changed)
        bar2.addWidget(self.prio)
        self.pending = QCheckBox("غير المقرَّرة فقط")
        self.pending.toggled.connect(self._filters_changed)
        bar2.addWidget(self.pending)
        v.addLayout(bar2)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(12)
        self.model = ResultsModel()
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(52)
        self.view.setShowGrid(False)
        self.view.horizontalHeader().setHighlightSections(False)
        self.delegate = StatusDelegate()
        self.view.setItemDelegate(self.delegate)
        hdr = self.view.horizontalHeader()
        hdr.setMinimumSectionSize(44)
        hdr.setStretchLastSection(False)
        for i, (mode, wd) in enumerate([(QHeaderView.Fixed, 44), (QHeaderView.Fixed, 140), (QHeaderView.Fixed, 86),
                                        (QHeaderView.ResizeToContents, 0), (QHeaderView.Fixed, 54), (QHeaderView.Fixed, 104),
                                        (QHeaderView.Fixed, 104), (QHeaderView.Fixed, 104), (QHeaderView.Fixed, 54),
                                        (QHeaderView.Fixed, 44)]):
            hdr.setSectionResizeMode(i, mode)
            if wd:
                self.view.setColumnWidth(i, wd)
        self.view.setTextElideMode(Qt.ElideMiddle)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setColumnHidden(8, True)   # الثقة تظهر في لوحة التفاصيل
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setStyleSheet("QTableView { font-size: 9.5pt; } QTableView::item { padding: 4px 6px; }")
        self.view.selectionModel().selectionChanged.connect(self._sel_changed)
        lv.addWidget(self.view, 1)
        foot = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("Muted")
        foot.addWidget(self.count_lbl, 1)
        self.btn_link = QPushButton("🔗  ربط يدوي بين المحدَّدتين")
        self.btn_link.setEnabled(False)
        self.btn_link.setCursor(Qt.PointingHandCursor)
        self.btn_link.setToolTip("حدّد عملية «مفقودة في الصرافة» وعملية «مفقودة في ملف المحاسب» (Ctrl+نقر) ثم اربطهما.")
        self.btn_link.clicked.connect(self._manual_link)
        foot.addWidget(self.btn_link)
        self.btn_bulk = QPushButton("إجراءات جماعية  ▾")
        self.btn_bulk.setCursor(Qt.PointingHandCursor)
        self.btn_bulk.setToolTip("اعتماد أو رفض عدة عمليات دفعة واحدة")
        menu = QMenu(self.btn_bulk)
        for label, kind in (("اعتماد المحدّد", "ok_sel"), ("رفض المحدّد", "no_sel"), ("مسح قرارات المحدّد", "clr_sel"),
                            ("اعتماد كل المتطابقة بثقة ٩٥٪ فأكثر", "ok_conf")):
            menu.addAction(label, lambda k=kind: self._bulk(k))
        self.btn_bulk.setMenu(menu)
        foot.addWidget(self.btn_bulk)
        self.btn_panel = QPushButton("◨  إخفاء اللوحة")
        self.btn_panel.setObjectName("Ghost")
        self.btn_panel.setCheckable(True)
        self.btn_panel.setChecked(True)
        self.btn_panel.setCursor(Qt.PointingHandCursor)
        self.btn_panel.setToolTip("إظهار/إخفاء لوحة تفاصيل العملية لتوسيع الجدول")
        foot.addWidget(self.btn_panel)
        lv.addLayout(foot)
        split.addWidget(left)
        self.detail = DetailPanel()
        self.detail.decisionChanged.connect(self.model.row_changed)
        self.detail.decisionChanged.connect(lambda *_: self._filters_changed())
        split.addWidget(self.detail)
        self.btn_panel.toggled.connect(self._toggle_panel)
        self.detail.setMinimumWidth(400)
        left.setMinimumWidth(600)
        split.setSizes([820, 400])
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        v.addWidget(split, 1)
        self.tabs.addTab(w, "تفاصيل العمليات")

    def _toggle_panel(self, on: bool):
        self.detail.setVisible(on)
        self.btn_panel.setText("◨  إخفاء اللوحة" if on else "◧  إظهار اللوحة")

    # ------------------------------------------------------------------ مراجعة سريعة وإجراءات جماعية
    def _review_queue(self) -> list:
        prio = {"عالية": 0, "متوسطة": 1, "منخفضة": 2}
        rows = [r for r in (self.res.rows if self.res else []) if r.status != STATUS_MATCHED and not r.decision]
        return sorted(rows, key=lambda r: (prio.get(r.priority, 3), r.id))

    def _update_insight(self):
        if not self.res:
            return
        res = self.res
        need = self._review_queue()
        high = sum(1 for r in need if r.priority == "عالية")
        txt = f"تمت مطابقة {res.match_rate * 100:.1f}% من العمليات تلقائياً."
        if need:
            txt += f"  بقي {len(need):,} عملية تنتظر قرارك، منها {high:,} بأولوية عالية."
        else:
            txt += "  لا توجد عمليات بانتظار قرارك — يمكنك تصدير التقرير."
        self.insight_txt.setText(txt)
        self.btn_review.setEnabled(bool(need))

    def _after_decision(self, row):
        self.model.row_changed(row)
        self._filters_changed()
        self._update_insight()

    def start_review(self):
        queue = self._review_queue()
        if not queue:
            return
        dlg = ReviewDialog(queue, self.dark, self._after_decision, self)
        dlg.exec()
        self._update_insight()
        self.detail.clear()

    def _bulk(self, kind: str):
        if not self.res:
            return
        if kind.endswith("_sel"):
            rows = self._selected_rows()
        else:
            rows = [r for r in self.res.rows if not r.decision and r.confidence >= 95
                    and r.status in (STATUS_MATCHED, STATUS_POSSIBLE)]
        if not rows:
            QMessageBox.information(self, "لا توجد عمليات", "لا توجد عمليات مطابقة لهذا الإجراء.")
            return
        value = {"ok_sel": "معتمد", "ok_conf": "معتمد", "no_sel": "مرفوض", "clr_sel": ""}[kind]
        verb = {"معتمد": "اعتماد", "مرفوض": "رفض", "": "مسح قرار"}[value]
        if QMessageBox.question(self, "تأكيد", f"سيتم {verb} {len(rows):,} عملية. هل تريد المتابعة؟") != QMessageBox.Yes:
            return
        for r in rows:
            r.decision = value
        self.model.set_rows(self.res.rows)
        self._filters_changed()
        self._update_insight()
        self.detail.clear()

    # ------------------------------------------------------------------ استجابة للحجم
    @staticmethod
    def _reflow(grid: QGridLayout, widgets: list, cols: int):
        for w in widgets:
            grid.removeWidget(w)
        for i, w in enumerate(widgets):
            grid.addWidget(w, i // cols, i % cols)
        for c in range(len(widgets)):
            grid.setColumnStretch(c, 1 if c < cols else 0)

    def _reflow_kpis(self, cols1: int, cols2: int):
        if cols1 != self._cols1:
            self._cols1 = cols1
            self._reflow(self._grid1, self._kpis1, cols1)
        if cols2 != self._cols2:
            self._cols2 = cols2
            self._reflow(self._grid2, self._kpis2, cols2)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w = self.width()
        self._reflow_kpis(4 if w >= 800 else 2, 6 if w >= 1100 else 3)

    # ------------------------------------------------------------------ منطق
    def set_dark(self, dark: bool):
        self.dark = dark
        self.donut.dark = dark
        self.delegate.dark = dark
        self.detail.dark = dark
        self.view.viewport().update()
        self.donut.update()
        if self.detail.row:
            self.detail.show_row(self.detail.row)
        if self.res:
            self._fill_legend()

    def show_result(self, res: ReconResult, names: tuple[str, str]):
        self.res = res
        self.sub.setText(f"{names[0]}  ⟷  {names[1]}")
        self.model.set_rows(res.rows)
        self.detail.clear()
        self.refresh_overview()
        self._filters_changed()
        self.tabs.setCurrentIndex(0)

    def refresh_overview(self):
        res = self.res
        if not res:
            return
        c = res.counts
        self.k_a.set(f"{res.count_a:,}", "عملية في ملف المحاسب")
        self.k_b.set(f"{res.count_b:,}", "عملية في ملف الصرافة")
        self.k_rate.set(f"{res.match_rate * 100:.1f}%", f"{c[STATUS_MATCHED]:,} عملية متطابقة")
        need = sum(1 for r in res.rows if r.status != STATUS_MATCHED)
        high = sum(1 for r in res.rows if r.priority == "عالية")
        self.k_rev.set(f"{need:,}", f"منها {high:,} بأولوية عالية")
        for s, k in self.status_cards.items():
            k.set(f"{c[s]:,}", "انقر للتصفية")
        self._fill_legend()
        self._fill_financial()
        self._update_insight()
        self.rel_note.setText("ℹ  " + res.rel_note)
        ok = all(v == 0 for v in res.integrity.values())
        self.integrity.setText("✔ التحقق الحسابي مغلق" if ok else "✖ خلل في التحقق الحسابي")
        self.integrity.setObjectName("BadgeOk" if ok else "BadgeBad")
        self.integrity.style().unpolish(self.integrity)
        self.integrity.style().polish(self.integrity)
        if res.warnings:
            self.warn.setText("\n".join("• " + w for w in res.warnings))
            self.warn.show()
        else:
            self.warn.hide()

    def _fill_legend(self):
        res = self.res
        while self.legend.count():
            it = self.legend.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        data = [(s, res.counts[s], STATUS[s][0]) for s in ALL_STATUSES]
        self.donut.set_data(data, f"{res.match_rate * 100:.0f}%", "نسبة التطابق")
        for s, n, col in data:
            r = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{col};")
            r.addWidget(dot)
            r.addWidget(QLabel(s))
            r.addStretch(1)
            nn = QLabel(f"{n:,}")
            nn.setStyleSheet("font-weight:700;")
            r.addWidget(nn)
            wdg = QWidget()
            wdg.setLayout(r)
            self.legend.addWidget(wdg)

    def _fill_financial(self):
        res = self.res
        curs = res.currencies or [""]
        cats = [c for c in BRIDGE_ORDER if any(c in res.bridge.get(cur, {}) for cur in curs)]
        lines: list[tuple[str, str, list[str]]] = []
        lines.append(("إجمالي ملف المحاسب", "total", [fm(res.total_a.get(c, 0)) for c in curs]))
        lines.append(("إجمالي ملف الصرافة", "total", [fm(res.total_b.get(c, 0)) for c in curs]))
        lines.append(("الفرق الصافي (محاسب − صرافة)", "net", [fm(res.net_diff(c)) for c in curs]))
        lines.append(("تحليل الفرق حسب السبب", "head", [""] * len(curs)))
        for cat in cats:
            lines.append((cat, "item", [fm(res.bridge.get(c, {}).get(cat, 0)) for c in curs]))
        lines.append(("مجموع الأسباب", "net", [fm(sum(res.bridge.get(c, {}).values(), Decimal(0))) for c in curs]))
        self.fin.clear()
        self.fin.setRowCount(len(lines))
        self.fin.setColumnCount(len(curs) + 1)
        self.fin.setHorizontalHeaderLabels(["البند"] + [c or "غير محدد" for c in curs])
        self.fin.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for j in range(1, len(curs) + 1):
            self.fin.horizontalHeader().setSectionResizeMode(j, QHeaderView.ResizeToContents)
        for i, (label, kind, vals) in enumerate(lines):
            it = QTableWidgetItem(label)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if kind in ("net", "head"):
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            if kind == "head":
                it.setBackground(QColor("#2A3A5E" if self.dark else "#E8EEF8"))
            self.fin.setItem(i, 0, it)
            for j, v in enumerate(vals):
                vi = QTableWidgetItem(v)
                vi.setTextAlignment(Qt.AlignCenter)
                if kind == "head":
                    vi.setBackground(QColor("#2A3A5E" if self.dark else "#E8EEF8"))
                if kind == "net":
                    f = vi.font()
                    f.setBold(True)
                    vi.setFont(f)
                if v.strip("\u202a\u202c").startswith("-") and v.strip("\u202a\u202c") != "-0.00":
                    vi.setForeground(QColor("#D64535"))
                self.fin.setItem(i, j + 1, vi)
            self.fin.setRowHeight(i, 40)
        # واجهة فقط: ارتفاع الجدول يناسب محتواه دون أشرطة تمرير داخلية
        self.fin.setFixedHeight(self.fin.horizontalHeader().height() + 40 * self.fin.rowCount() + 6)

    def focus_status(self, status: str):
        for s, b in self.chips.items():
            b.blockSignals(True)
            b.setChecked(s == status)
            b.blockSignals(False)
        self._filters_changed()
        self.tabs.setCurrentIndex(1)

    def _filters_changed(self, *_):
        sel = {s for s, b in self.chips.items() if b.isChecked()}
        prio = self.prio.currentText() if self.prio.currentIndex() > 0 else ""
        self.proxy.set_filters(sel, self.search.text(), prio, self.pending.isChecked())
        n = self.proxy.rowCount()
        total = len(self.model.rows)
        self.count_lbl.setText(f"عرض {n:,} من {total:,} عملية")

    def _selected_rows(self) -> list[MatchRow]:
        return [self.proxy.data(i, ROW_ROLE) for i in self.view.selectionModel().selectedRows()]

    def _sel_changed(self, *_):
        rows = self._selected_rows()
        if len(rows) == 1:
            self.detail.show_row(rows[0])
        elif not rows:
            self.detail.clear()
        stats = sorted(r.status for r in rows)
        self.btn_link.setEnabled(len(rows) == 2 and stats == sorted([STATUS_MISSING_B, STATUS_MISSING_A]))

    def _manual_link(self):
        rows = self._selected_rows()
        ra = next((r for r in rows if r.status == STATUS_MISSING_B), None)
        rb = next((r for r in rows if r.status == STATUS_MISSING_A), None)
        if not (ra and rb):
            return
        try:
            new = manual_link(self.res, ra, rb)
        except ValueError as ex:
            QMessageBox.warning(self, "تعذّر الربط", str(ex))
            return
        self.model.set_rows(self.res.rows)
        self.refresh_overview()
        self._filters_changed()
        self.view.clearSelection()
        for i in range(self.proxy.rowCount()):
            if self.proxy.data(self.proxy.index(i, 0), ROW_ROLE) is new:
                self.view.selectRow(i)
                break
