"""صفحة قواعد المطابقة (قابلة للحفظ كقالب JSON للاتفاق مع العميل)."""
from __future__ import annotations

import json
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ..engine import Settings

SIGN_MODES = [("auto", "تلقائي (يكتشف البرنامج)"), ("same", "نفس الاتجاه في الملفين"),
              ("opposite", "معكوس (مدين عند أحدهما = دائن عند الآخر)"), ("ignore", "تجاهل الإشارة (القيمة المطلقة)")]

PRESETS = {
    "متوازن (الافتراضي)": Settings(),
    "صارم": Settings(amount_tol=Decimal("0.00"), date_tol_days=0, fuzzy_days=2, possible_pct=0.005,
                     auto_accept=0.97, min_possible=0.75),
    "مرن": Settings(amount_tol=Decimal("1.00"), date_tol_days=7, fuzzy_days=10, possible_pct=0.05,
                    auto_accept=0.88, min_possible=0.50),
}


from .widgets import PageHeader


class RulesPage(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 20)
        outer.setSpacing(10)
        self.header = PageHeader("قواعد المطابقة",
                                 "القواعد المتفق عليها مع العميل. احفظها كقالب JSON لإعادة استخدامها أو اعتمادها رسمياً.", "rules")
        outer.addWidget(self.header)

        pr_frame = QFrame()
        pr_frame.setObjectName("ActionBar")
        pr = QHBoxLayout(pr_frame)
        pr.setContentsMargins(22, 14, 18, 14)
        pr.setSpacing(12)
        lbl_preset = QLabel("إعداد جاهز:")
        lbl_preset.setObjectName("H3")
        pr.addWidget(lbl_preset)
        for name in PRESETS:
            b = QPushButton(name)
            b.setObjectName("Chip")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.apply(PRESETS[n]))
            pr.addWidget(b)
        pr.addStretch(1)
        bs = QPushButton("حفظ القواعد كقالب…")
        bs.setObjectName("Ghost")
        bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self.save_file)
        bl = QPushButton("تحميل قالب…")
        bl.setObjectName("Ghost")
        bl.setCursor(Qt.PointingHandCursor)
        bl.clicked.connect(self.load_file)
        pr.addWidget(bl)
        pr.addWidget(bs)
        outer.addSpacing(8)
        outer.addWidget(pr_frame)
        outer.addSpacing(2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 8, 10, 8)
        v.setSpacing(22)

        # ---- المبالغ والتواريخ
        card1, g1 = self._card("المبالغ والتواريخ والإشارات")
        self.amount_tol = QDoubleSpinBox()
        self.amount_tol.setDecimals(2)
        self.amount_tol.setRange(0, 100000)
        self.amount_tol.setSingleStep(0.5)
        self._row(g1, 0, "تسامح المبلغ", self.amount_tol,
                  "أقصى فرق يُعتبر مطابقاً (مثلاً 0.01 لتجاهل فروق التقريب).")
        self.date_tol = QSpinBox()
        self.date_tol.setRange(0, 90)
        self.date_tol.setSuffix(" يوم")
        self._row(g1, 1, "تسامح التاريخ", self.date_tol,
                  "عند تطابق المرجع: أكبر فرق تاريخ لا يُعتبر اختلافاً.")
        self.sign_mode = QComboBox()
        for k, label in SIGN_MODES:
            self.sign_mode.addItem(label, k)
        self._row(g1, 2, "اتجاه الإشارات", self.sign_mode,
                  "كثيراً ما يسجّل المحاسب العملية مدينة والصرافة دائنة. الوضع التلقائي يتعرف على ذلك.")
        self.strict_cur = QCheckBox("اعتبار اختلاف العملة فرقاً")
        self._row(g1, 3, "العملات", self.strict_cur, "يمنع مطابقة عمليتين بعملتين مختلفتين في المطابقة الذكية.")
        v.addWidget(card1)

        # ---- المطابقة الذكية
        card2, g2 = self._card("المطابقة الذكية للعمليات بلا مرجع مشترك")
        self.use_fuzzy = QCheckBox("تفعيل المطابقة الذكية")
        self._row(g2, 0, "التفعيل", self.use_fuzzy, "تطابق بالمبلغ والتاريخ والاسم عندما يغيب المرجع أو يختلف.")
        self.fuzzy_days = QSpinBox()
        self.fuzzy_days.setRange(0, 90)
        self.fuzzy_days.setSuffix(" يوم")
        self._row(g2, 1, "نافذة التاريخ", self.fuzzy_days, "أقصى فرق تاريخ لاعتبار عمليتين مرشحتين.")
        self.pct = QDoubleSpinBox()
        self.pct.setRange(0, 50)
        self.pct.setDecimals(1)
        self.pct.setSuffix(" %")
        self._row(g2, 2, "أقصى فرق مبلغ محتمل", self.pct, "نسبة الفرق التي يُسمح بها للمطابقة المحتملة (عمولات/أسعار صرف).")
        self.auto_accept = QSpinBox()
        self.auto_accept.setRange(50, 100)
        self.auto_accept.setSuffix(" %")
        self._row(g2, 3, "حد القبول التلقائي", self.auto_accept,
                  "أي مطابقة ذكية بثقة أعلى من هذا الحد (وبلا فروقات) تُعتبر «متطابقة»؛ وما دونه «محتملة» للمراجعة.")
        self.min_possible = QSpinBox()
        self.min_possible.setRange(30, 100)
        self.min_possible.setSuffix(" %")
        self._row(g2, 4, "أدنى ثقة للاقتراح", self.min_possible, "المطابقات الأقل من هذه الثقة لا تُقترح أصلاً.")
        self.use_desc = QCheckBox("البحث عن رقم الحوالة داخل البيان/السند")
        self._row(g2, 5, "المرجع داخل البيان", self.use_desc, "يربط عمليات مرجعها مكتوب ضمن النص الحر.")
        self.check_party = QCheckBox("تنبيه عند اختلاف اسم الطرف")
        self._row(g2, 6, "فحص الأسماء", self.check_party, "يضيف تنبيهاً للمراجعة دون تغيير حالة المطابقة.")
        v.addWidget(card2)

        card3, g3 = self._card("التكرار")
        self.dups = QCheckBox("كشف العمليات المكررة داخل الملف الواحد")
        self._row(g3, 0, "كشف التكرار", self.dups, "عملية بنفس المرجع/المبلغ/التاريخ مسجلة أكثر من مرة.")
        v.addWidget(card3)
        v.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self.apply(Settings())
        for w in (self.amount_tol, self.pct):
            w.valueChanged.connect(lambda *_: self.changed.emit())
        for w in (self.date_tol, self.fuzzy_days, self.auto_accept, self.min_possible):
            w.valueChanged.connect(lambda *_: self.changed.emit())
        self.sign_mode.currentIndexChanged.connect(lambda *_: self.changed.emit())
        for w in (self.strict_cur, self.use_fuzzy, self.use_desc, self.check_party, self.dups):
            w.toggled.connect(lambda *_: self.changed.emit())

    # ------------------------------------------------------------------
    def _card(self, title: str):
        f = QFrame()
        f.setObjectName("Card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(30, 26, 30, 26)
        lay.setSpacing(16)
        t = QLabel(title)
        t.setObjectName("H2")
        lay.addWidget(t)
        g = QGridLayout()
        g.setHorizontalSpacing(28)
        g.setVerticalSpacing(16)
        g.setColumnStretch(2, 1)
        lay.addLayout(g)
        return f, g

    @staticmethod
    def _row(g: QGridLayout, r: int, label: str, widget: QWidget, hint: str):
        lb = QLabel(label)
        lb.setObjectName("H3")
        lb.setMinimumWidth(170)
        widget.setMinimumWidth(230)
        widget.setToolTip(hint)
        h = QLabel(hint)
        h.setObjectName("Muted")
        h.setWordWrap(True)
        row = r * 2          # كل بند في صف زوجي، والفاصل الرفيع في الصف الفردي الذي قبله
        if r > 0:
            sep = QFrame()
            sep.setObjectName("HLine")
            g.addWidget(sep, row - 1, 0, 1, 3)
        g.addWidget(lb, row, 0, Qt.AlignVCenter)
        g.addWidget(widget, row, 1, Qt.AlignVCenter)
        g.addWidget(h, row, 2, Qt.AlignVCenter)

    def settings(self) -> Settings:
        return Settings(
            amount_tol=Decimal(str(round(self.amount_tol.value(), 2))),
            date_tol_days=self.date_tol.value(), fuzzy_days=self.fuzzy_days.value(),
            possible_pct=self.pct.value() / 100.0, name_threshold=0.80,
            sign_mode=self.sign_mode.currentData(), strict_currency=self.strict_cur.isChecked(),
            use_fuzzy=self.use_fuzzy.isChecked(), use_desc_ref=self.use_desc.isChecked(),
            check_party=self.check_party.isChecked(), auto_accept=self.auto_accept.value() / 100.0,
            min_possible=self.min_possible.value() / 100.0, detect_duplicates=self.dups.isChecked())

    def apply(self, s: Settings):
        self.amount_tol.setValue(float(s.amount_tol))
        self.date_tol.setValue(s.date_tol_days)
        self.fuzzy_days.setValue(s.fuzzy_days)
        self.pct.setValue(s.possible_pct * 100)
        i = self.sign_mode.findData(s.sign_mode)
        self.sign_mode.setCurrentIndex(max(i, 0))
        self.strict_cur.setChecked(s.strict_currency)
        self.use_fuzzy.setChecked(s.use_fuzzy)
        self.use_desc.setChecked(s.use_desc_ref)
        self.check_party.setChecked(s.check_party)
        self.auto_accept.setValue(int(round(s.auto_accept * 100)))
        self.min_possible.setValue(int(round(s.min_possible * 100)))
        self.dups.setChecked(s.detect_duplicates)

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ قواعد المطابقة", "قواعد_المطابقة.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.settings().to_dict(), f, ensure_ascii=False, indent=2)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "تحميل قواعد المطابقة", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self.apply(Settings.from_dict(json.load(f)))
        except Exception as ex:  # noqa: BLE001
            QMessageBox.warning(self, "ملف غير صالح", str(ex))
