"""النافذة الرئيسية: الشريط الجانبي، الصفحات، المعالجة في خيط خلفي، التصدير."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPropertyAnimation, QSettings, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, APP_VERSION
from ..engine import Settings, reconcile
from ..exporter import export_report
from ..loader import build_records
from .import_page import ImportPage
from .results_page import ResultsPage
from .rules_page import RulesPage
from .theme import DARK, LIGHT, build_qss
from .widgets import icon


class ReconWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object, list)
    failed = Signal(str)

    def __init__(self, ta, ma, ca, tb, mb, cb, settings: Settings):
        super().__init__()
        self.args = (ta, ma, ca, tb, mb, cb, settings)

    def run(self):
        try:
            ta, ma, ca, tb, mb, cb, st = self.args
            self.progress.emit(2, "قراءة وتطبيع ملف المحاسب")
            ra, sa = build_records(ta, ma, "A", ca)
            self.progress.emit(4, "قراءة وتطبيع ملف الصرافة")
            rb, sb = build_records(tb, mb, "B", cb)
            if not ra or not rb:
                raise ValueError("لا توجد عمليات صالحة في أحد الملفين. تحقق من ربط عمود المبلغ وصف العناوين.")
            res = reconcile(ra, rb, st, progress=lambda p, m: self.progress.emit(p, m))
            self.done.emit(res, sa + sb)
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            self.failed.emit(str(ex))


class ProgressDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setObjectName("Root")
        self.setMinimumWidth(500)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(30, 26, 30, 26)
        v.setSpacing(12)
        head = QHBoxLayout()
        t = QLabel("جارٍ المطابقة…")
        t.setObjectName("H2")
        self.pct = QLabel("0%")
        self.pct.setObjectName("Pct")
        head.addWidget(t)
        head.addStretch(1)
        head.addWidget(self.pct)
        self.msg = QLabel("")
        self.msg.setObjectName("Muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        note = QLabel("قد يستغرق ذلك لحظات حسب حجم الملفين — يرجى عدم إغلاق البرنامج.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addLayout(head)
        v.addWidget(self.msg)
        v.addWidget(self.bar)
        v.addWidget(note)

    def update_progress(self, p: int, m: str):
        self.bar.setValue(p)
        self.pct.setText(f"{p}%")
        self.msg.setText(m)


class MainWindow(QMainWindow):
    SIDE_W = 248          # عرض الشريط الجانبي الموسّع
    SIDE_W_COMPACT = 84   # عرضه عند ضيق النافذة
    COMPACT_BELOW = 0     # 0 = لا وضع مدمج: يبقى الشريط الجانبي بشكله المعتاد دائماً

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  —  {APP_VERSION}")
        self.setWindowIcon(QIcon(self._logo_pixmap(128)))
        self.resize(1500, 920)
        self.setMinimumSize(1100, 700)
        self.qs = QSettings("ReconPro", "Reconciliation")
        self.dark = self.qs.value("dark", False, type=bool)
        self.worker: Optional[ReconWorker] = None
        self.res = None
        self.skipped: list = []
        self._ready = False
        self._compact = False
        self._anim = None

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ---- الشريط الجانبي
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(self.SIDE_W)
        self.side = side
        sv = QVBoxLayout(side)
        sv.setContentsMargins(18, 26, 18, 18)
        sv.setSpacing(8)
        self.side_lay = sv

        self.brand_box = QWidget()
        self.brand_box.setObjectName("BrandBox")
        self.brand_row = QHBoxLayout(self.brand_box)
        self.brand_row.setContentsMargins(10, 10, 10, 10)
        self.brand_row.setSpacing(12)
        self.logo = QLabel()
        self.logo.setFixedSize(42, 42)
        self.logo.setPixmap(self._logo_pixmap(42))
        self.brand_row.addWidget(self.logo)
        self.brand_txt = QWidget()
        self.brand_txt.setObjectName("Plain")
        bt = QVBoxLayout(self.brand_txt)
        bt.setContentsMargins(0, 0, 0, 0)
        bt.setSpacing(0)
        brand = QLabel("المطابقة والتسوية")
        brand.setObjectName("Brand")
        sub = QLabel("مطابقة ذكية بين المحاسب والصرافة")
        sub.setObjectName("BrandSub")
        sub.setWordWrap(True)
        bt.addWidget(brand)
        bt.addWidget(sub)
        self.brand_row.addWidget(self.brand_txt, 1)
        sv.addWidget(self.brand_box)
        sv.addSpacing(14)
        line1 = QFrame()
        line1.setObjectName("SideLine")
        sv.addWidget(line1)
        sv.addSpacing(8)
        self.side_section = QLabel("خطوات العمل")
        self.side_section.setObjectName("SideSection")
        sv.addWidget(self.side_section)
        self._nav_full = ["استيراد الملفات", "قواعد المطابقة", "النتائج والتقارير"]
        self._nav_short = ["", "", ""]
        self._nav_tips = ["استيراد ملفي المحاسب والصرافة وربط الأعمدة", "ضبط قواعد وتسامحات المطابقة",
                          "عرض النتائج ومراجعتها وتصدير التقرير"]
        self.nav: list[QPushButton] = []
        for i, t in enumerate(self._nav_full):
            b = QPushButton(t)
            b.setObjectName("Nav")
            b.setIcon(icon(("import", "rules", "chart")[i], "#FFFFFF", 22))
            b.setIconSize(QSize(22, 22))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(self._nav_tips[i])
            b.clicked.connect(lambda _=False, k=i: self.go(k))
            sv.addWidget(b)
            self.nav.append(b)
        sv.addStretch(1)
        line2 = QFrame()
        line2.setObjectName("SideLine")
        sv.addWidget(line2)
        sv.addSpacing(4)
        self.theme_btn = QPushButton("")
        self.theme_btn.setObjectName("Nav")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("التبديل بين الوضع الفاتح والداكن")
        self.theme_btn.clicked.connect(self.toggle_theme)
        sv.addWidget(self.theme_btn)
        self.foot = QLabel(f"الإصدار {APP_VERSION}")
        self.foot.setObjectName("SideFoot")
        sv.addWidget(self.foot)
        h.addWidget(side)

        # ---- الصفحات
        self.stack = QStackedWidget()
        self.p_import = ImportPage()
        self.p_rules = RulesPage()
        self.p_results = ResultsPage()
        for p in (self.p_import, self.p_rules, self.p_results):
            self.stack.addWidget(p)
        h.addWidget(self.stack, 1)

        self.p_import.startRequested.connect(self.start)
        self.p_import.btn_sample.clicked.connect(self.load_sample)
        self.p_import.card_a.changed.connect(self._refresh_last_run)
        self.p_import.card_b.changed.connect(self._refresh_last_run)
        self.p_results.exportRequested.connect(self.export)
        self.p_results.newRequested.connect(lambda: self.go(0))
        self.p_rules.changed.connect(self.save_rules)
        self.nav[2].setEnabled(False)
        self.nav[2].setToolTip("شغّل المطابقة أولاً لتظهر النتائج هنا")
        self.p_import.btn_start.setToolTip("بدء المطابقة  (Ctrl+Enter)")
        self.p_results.btn_export.setToolTip("تصدير تقرير Excel  (Ctrl+E)")

        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.p_import.btn_start.click())

        self.p_import.reloadLastRequested.connect(self.reload_last)
        self.setAcceptDrops(True)
        self.overlay = QLabel("أفلت الملفات هنا\nالأول لملف المحاسب والثاني لملف الصرافة", self.stack)
        self.overlay.setObjectName("DropOverlay")
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.hide()

        self.load_rules()
        self.apply_theme()
        self.go(0)
        self._refresh_last_run()
        self.statusBar().showMessage("جاهز")
        self._ready = True
        self._set_compact(self.width() < self.COMPACT_BELOW)

    # --------------------------------------------------------------- سحب وإفلات في أي مكان
    _EXT = (".xlsx", ".xlsm", ".xls", ".csv")

    def _drop_files(self, e) -> list[str]:
        if not e.mimeData().hasUrls():
            return []
        fs = [u.toLocalFile() for u in e.mimeData().urls()]
        return [f for f in fs if f.lower().endswith(self._EXT)]

    def dragEnterEvent(self, e):
        if self._drop_files(e):
            e.acceptProposedAction()
            self.overlay.setGeometry(self.stack.rect().adjusted(14, 14, -14, -14))
            self.overlay.show()
            self.overlay.raise_()

    def dragLeaveEvent(self, e):
        self.overlay.hide()

    def dropEvent(self, e):
        self.overlay.hide()
        files = self._drop_files(e)
        if not files:
            return
        e.acceptProposedAction()
        self.go(0)
        ca, cb = self.p_import.card_a, self.p_import.card_b
        if len(files) >= 2:
            ca.load_path(files[0])
            cb.load_path(files[1])
            return
        f = files[0]
        if ca.table is None:
            ca.load_path(f)
        elif cb.table is None:
            cb.load_path(f)
        else:
            box = QMessageBox(self)
            box.setWindowTitle("أي ملف تستبدل؟")
            box.setText("الملفان محمّلان. اختر الملف الذي تريد استبداله بالملف الجديد.")
            a = box.addButton("ملف المحاسب", QMessageBox.AcceptRole)
            b = box.addButton("ملف الصرافة", QMessageBox.AcceptRole)
            box.addButton("إلغاء", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is a:
                ca.load_path(f)
            elif box.clickedButton() is b:
                cb.load_path(f)

    # --------------------------------------------------------------- آخر مطابقة
    def _remember_last_run(self, res):
        ca, cb = self.p_import.card_a, self.p_import.card_b
        self.qs.setValue("last_run", json.dumps({
            "a": ca.path, "b": cb.path, "sa": ca.sheet.currentText(), "sb": cb.sheet.currentText(),
            "ha": ca.hdr.value(), "hb": cb.hdr.value(), "time": f"{datetime.now():%Y-%m-%d %H:%M}",
            "rate": f"{res.match_rate * 100:.1f}", "na": ca.table.name, "nb": cb.table.name}))

    def _last_run(self):
        try:
            d = json.loads(self.qs.value("last_run", "") or "{}")
        except (ValueError, TypeError):
            return None
        return d if d and Path(d.get("a", "")).exists() and Path(d.get("b", "")).exists() else None

    def _refresh_last_run(self):
        d = self._last_run()
        ca, cb = self.p_import.card_a, self.p_import.card_b
        if d and ca.table is None and cb.table is None:
            self.p_import.set_last_run(f"آخر مطابقة: {d['time']}  ·  {d['na']}  ⟷  {d['nb']}  ·  تطابق {d['rate']}%")
        else:
            self.p_import.set_last_run(None)

    def reload_last(self):
        d = self._last_run()
        if not d:
            return
        ca, cb = self.p_import.card_a, self.p_import.card_b
        ca.load_path(d["a"], d.get("sa") or None, d.get("ha"))
        cb.load_path(d["b"], d.get("sb") or None, d.get("hb"))
        self._refresh_last_run()

    # --------------------------------------------------------------- تنقل/سمة
    def go(self, i: int):
        changed = i != self.stack.currentIndex()
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.nav):
            b.setChecked(k == i)
        if changed and self.isVisible():
            self._fade_in(self.stack.currentWidget())

    def _fade_in(self, w: QWidget):
        """ظهور تدريجي قصير للصفحة عند التنقل (تجميلي فقط)."""
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        self._anim = anim
        anim.start()

    # --------------------------------------------------------------- استجابة للحجم
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._ready:
            self._set_compact(self.width() < self.COMPACT_BELOW)

    def _set_compact(self, compact: bool):
        if compact == self._compact:
            return
        self._compact = compact
        self.side.setFixedWidth(self.SIDE_W_COMPACT if compact else self.SIDE_W)
        m = 12 if compact else 16
        self.side_lay.setContentsMargins(m, 22, m, 16)
        self.brand_row.setContentsMargins(9 if compact else 10, 10, 9 if compact else 10, 10)
        for w in (self.brand_txt, self.side_section, self.foot):
            w.setVisible(not compact)
        for k, b in enumerate(self.nav):
            b.setText(self._nav_short[k] if compact else self._nav_full[k])
            b.setProperty("compact", compact)
            b.style().unpolish(b)
            b.style().polish(b)
        self.theme_btn.setProperty("compact", compact)
        self.theme_btn.style().unpolish(self.theme_btn)
        self.theme_btn.style().polish(self.theme_btn)
        self._update_theme_btn()

    @staticmethod
    def _icon_dir() -> Path:
        from PySide6.QtCore import QStandardPaths
        d = Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation)) / "recon_ui"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _check_icon() -> str:
        """أيقونة علامة ✓ بيضاء تُرسم مرة واحدة وتُستخدم في مربعات الاختيار."""
        from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
        f = MainWindow._icon_dir() / "check.png"
        if not f.exists():
            pm = QPixmap(40, 40)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("white"), 5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(10, 21, 17, 28)
            p.drawLine(17, 28, 30, 12)
            p.end()
            pm.save(str(f))
        return f.as_posix()

    @staticmethod
    def _arrow_icons() -> dict:
        """أسهم صغيرة (لأسفل/لأعلى) للقوائم المنسدلة وحقول الأرقام ومؤشر الفرز."""
        from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
        out = {}
        for key, pts in (("down", ((11, 16), (20, 25), (29, 16))), ("up", ((11, 25), (20, 16), (29, 25)))):
            f = MainWindow._icon_dir() / f"arrow_{key}.png"
            if not f.exists():
                pm = QPixmap(40, 40)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                pen = QPen(QColor("#8A94A6"), 4.5)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                p.setPen(pen)
                p.drawLine(*pts[0], *pts[1])
                p.drawLine(*pts[1], *pts[2])
                p.end()
                pm.save(str(f))
            out[key] = f.as_posix()
        return out

    @staticmethod
    def _logo_pixmap(size: int):
        """شعار البرنامج (مربع مستدير بتدرّج أزرق وسهمان متقابلان) يُرسم برمجياً."""
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
        n = 160
        pm = QPixmap(n, n)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, n, n)
        g.setColorAt(0, QColor("#FFFFFF"))
        g.setColorAt(1, QColor("#DDF4F0"))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 0, n, n), 36, 36)
        pen = QPen(QColor("#0D9488"), 12)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawLine(38, 60, 122, 60)
        p.drawLine(122, 60, 100, 38)
        p.drawLine(122, 60, 100, 82)
        p.drawLine(122, 100, 38, 100)
        p.drawLine(38, 100, 60, 78)
        p.drawLine(38, 100, 60, 122)
        p.end()
        return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _update_theme_btn(self):
        if self._compact:
            self.theme_btn.setText("")
        else:
            self.theme_btn.setText("  الوضع الفاتح" if self.dark else "  الوضع الداكن")
        self.theme_btn.setIcon(icon("sun" if self.dark else "moon", "#FFFFFF", 20))
        self.theme_btn.setIconSize(QSize(20, 20))

    def apply_theme(self):
        pal = DARK if self.dark else LIGHT
        QApplication.instance().setStyleSheet(build_qss(pal, self._check_icon(), self._arrow_icons()))
        self._update_theme_btn()
        self.p_results.set_dark(self.dark)

    def toggle_theme(self):
        self.dark = not self.dark
        self.qs.setValue("dark", self.dark)
        self.apply_theme()

    # --------------------------------------------------------------- قواعد
    def save_rules(self):
        self.qs.setValue("rules", json.dumps(self.p_rules.settings().to_dict()))

    def load_rules(self):
        raw = self.qs.value("rules", "")
        if raw:
            try:
                self.p_rules.apply(Settings.from_dict(json.loads(raw)))
            except Exception:  # noqa: BLE001
                pass

    # --------------------------------------------------------------- بيانات نموذجية
    def load_sample(self):
        from ..sample import make
        d = tempfile.mkdtemp(prefix="recon_sample_")
        a, b = make(d)
        self.p_import.card_a.load_path(a)
        self.p_import.card_b.load_path(b)
        self.statusBar().showMessage("تم تحميل بيانات نموذجية للتجربة", 5000)

    # --------------------------------------------------------------- تشغيل
    def start(self):
        ca, cb = self.p_import.card_a, self.p_import.card_b
        if not (ca.is_ready() and cb.is_ready()):
            return
        self.dlg = ProgressDialog(self)
        self.worker = ReconWorker(ca.table, ca.mapping(), ca.default_currency(),
                                  cb.table, cb.mapping(), cb.default_currency(), self.p_rules.settings())
        self.worker.progress.connect(self.dlg.update_progress)
        self.worker.done.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.start()
        self.dlg.show()

    def _failed(self, msg: str):
        self.dlg.close()
        QMessageBox.critical(self, "تعذّرت المطابقة", msg)

    def _finished(self, res, skipped):
        self.dlg.close()
        self.res, self.skipped = res, skipped
        self._remember_last_run(res)
        ca, cb = self.p_import.card_a, self.p_import.card_b
        self.p_results.show_result(res, (ca.table.name, cb.table.name))
        self.nav[2].setEnabled(True)
        self.nav[2].setToolTip(self._nav_tips[2])
        self.go(2)
        c = res.counts
        self.statusBar().showMessage(
            f"اكتملت المطابقة: {c['متطابقة']:,} متطابقة · {c['مختلفة']:,} مختلفة · "
            f"{c['مفقودة في الصرافة'] + c['مفقودة في ملف المحاسب']:,} مفقودة · {c['مكررة']:,} مكررة")

    # --------------------------------------------------------------- تصدير
    def export(self):
        if not self.res:
            return
        last = self.qs.value("last_dir", str(Path.home()))
        default = str(Path(last) / f"تقرير_المطابقة_{datetime.now():%Y%m%d_%H%M}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير Excel", default, "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            ca, cb = self.p_import.card_a, self.p_import.card_b
            export_report(path, self.res, ca.table, cb.table, self.skipped, (ca.table.name, cb.table.name))
        except PermissionError:
            QMessageBox.warning(self, "تعذّر الحفظ", "الملف مفتوح في برنامج آخر. أغلقه ثم أعد المحاولة.")
            return
        except Exception as ex:  # noqa: BLE001
            QMessageBox.critical(self, "تعذّر التصدير", str(ex))
            return
        self.qs.setValue("last_dir", str(Path(path).parent))
        self.statusBar().showMessage(f"تم حفظ التقرير: {path}", 8000)
        box = QMessageBox(self)
        box.setWindowTitle("تم التصدير")
        box.setText("تم إنشاء تقرير Excel بنجاح.")
        o = box.addButton("فتح الملف", QMessageBox.AcceptRole)
        box.addButton("إغلاق", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is o:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
