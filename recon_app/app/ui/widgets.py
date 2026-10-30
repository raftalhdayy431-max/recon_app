"""مكوّنات واجهة مخصصة: بطاقة إسقاط الملفات، مخطط دائري، بطاقة مؤشر، شريحة حالة."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFileDialog, QGraphicsDropShadowEffect, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

from .theme import status_colors


def repolish(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def make_icon(kind: str, color: str = "#FFFFFF", size: int = 24) -> QPixmap:
    """أيقونات متجهة بسيطة تُرسم برمجياً (بلا ملفات خارجية)."""
    S = 96
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    L = lambda x1, y1, x2, y2: p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    R = lambda x, y, w, h, r=10: p.drawRoundedRect(QRectF(x, y, w, h), r, r)
    if kind == "import":      # سهم داخل صينية
        L(48, 14, 48, 56); L(30, 40, 48, 58); L(66, 40, 48, 58)
        p.drawPolyline([QPointF(16, 58), QPointF(16, 80), QPointF(80, 80), QPointF(80, 58)])
    elif kind == "rules":     # منزلقات
        for y, x in ((26, 34), (48, 62), (70, 40)):
            L(14, y, 82, y)
            p.setBrush(QColor(color)); p.drawEllipse(QPointF(x, y), 9, 9); p.setBrush(Qt.NoBrush)
    elif kind == "chart":     # أعمدة
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        for x, h in ((16, 30), (40, 52), (64, 70)):
            p.drawRoundedRect(QRectF(x, 84 - h, 18, h), 5, 5)
    elif kind == "files":     # مستند
        R(22, 12, 52, 72); L(34, 36, 62, 36); L(34, 52, 62, 52); L(34, 68, 52, 68)
    elif kind == "percent":
        L(66, 26, 30, 70); p.drawEllipse(QPointF(30, 30), 9, 9); p.drawEllipse(QPointF(66, 66), 9, 9)
    elif kind == "alert":
        p.drawPolygon([QPointF(48, 14), QPointF(84, 76), QPointF(12, 76)]); L(48, 38, 48, 55); L(48, 65, 48, 66)
    elif kind == "check":
        L(20, 50, 40, 70); L(40, 70, 78, 26)
    elif kind == "diff":      # ≠
        L(22, 38, 74, 38); L(22, 58, 74, 58); L(58, 22, 38, 76)
    elif kind == "search":
        p.drawEllipse(QPointF(42, 42), 22, 22); L(58, 58, 80, 80)
    elif kind == "link":
        R(8, 36, 44, 24, 12); R(44, 36, 44, 24, 12)
    elif kind == "copy":
        R(30, 30, 46, 52, 8); p.drawPolyline([QPointF(22, 66), QPointF(22, 16), QPointF(58, 16)])
    elif kind == "moon":
        path = QPainterPath(); path.moveTo(60, 16)
        path.arcTo(QRectF(16, 16, 64, 64), 100, 220)
        path.arcTo(QRectF(36, 14, 52, 56), 250, -190)
        p.drawPath(path)
    elif kind == "sun":
        p.drawEllipse(QPointF(48, 48), 14, 14)
        for a in range(8):
            c, s_ = math.cos(a * math.pi / 4), math.sin(a * math.pi / 4)
            L(48 + c * 26, 48 + s_ * 26, 48 + c * 36, 48 + s_ * 36)
    elif kind == "export":
        L(48, 56, 48, 14); L(30, 32, 48, 14); L(66, 32, 48, 14)
        p.drawPolyline([QPointF(16, 52), QPointF(16, 82), QPointF(80, 82), QPointF(80, 52)])
    elif kind == "plus":
        L(48, 20, 48, 76); L(20, 48, 76, 48)
    elif kind == "bolt":
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(54, 8), QPointF(22, 54), QPointF(44, 54), QPointF(38, 88), QPointF(74, 38), QPointF(52, 38)])
    elif kind == "swap":
        L(16, 34, 78, 34); L(62, 18, 78, 34); L(62, 50, 78, 34)
        L(80, 64, 18, 64); L(34, 48, 18, 64); L(34, 80, 18, 64)
    p.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def icon(kind: str, color: str = "#FFFFFF", size: int = 24) -> QIcon:
    return QIcon(make_icon(kind, color, size * 2))


def add_shadow(w: QWidget, blur: int = 28, dy: int = 6, alpha: int = 28):
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(15, 30, 60, alpha))
    w.setGraphicsEffect(eff)


class IconTile(QLabel):
    """مربع أيقونة ملوّن بخلفية شفافة (مثل بطاقات المؤشرات)."""
    def __init__(self, kind: str, color: str, size: int = 46, solid: bool = False):
        super().__init__()
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        c = QColor(color)
        if solid:
            self.setStyleSheet(f"background: rgba(255,255,255,0.20); border-radius: {size // 3}px;")
            self.setPixmap(make_icon(kind, "#FFFFFF", int(size * 0.52)))
        else:
            self.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},0.14); border-radius: {size // 3}px;")
            self.setPixmap(make_icon(kind, color, int(size * 0.52)))


class PageHeader(QFrame):
    """شريط عنوان متدرّج: أيقونة + عنوان + وصف، وأزرار إجراءات على الطرف الآخر."""
    def __init__(self, title: str, subtitle: str, kind: str, extra: QWidget | None = None):
        super().__init__()
        self.setObjectName("Hero")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 20, 26, 20)
        outer.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(IconTile(kind, "#FFFFFF", 58, solid=True), 0, Qt.AlignTop)
        tv = QVBoxLayout()
        tv.setSpacing(3)
        self.title = QLabel(title)
        self.title.setObjectName("HeroTitle")
        self.sub = QLabel(subtitle)
        self.sub.setObjectName("HeroSub")
        self.sub.setWordWrap(True)
        tv.addWidget(self.title)
        tv.addWidget(self.sub)
        row.addLayout(tv, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(10)
        row.addLayout(self.actions)
        outer.addLayout(row)
        if extra is not None:
            outer.addWidget(extra)
        add_shadow(self, 30, 8, 40)

    def add_action(self, btn):
        self.actions.addWidget(btn, 0, Qt.AlignVCenter)


class DropZone(QFrame):
    """منطقة سحب وإفلات/نقر لاختيار ملف."""
    fileChosen = Signal(str)

    def __init__(self, title: str, hint: str):
        super().__init__()
        self.setObjectName("Drop")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setToolTip("انقر لاختيار ملف، أو اسحبه وأفلته هنا")
        self.setProperty("hover", False)
        self.setProperty("loaded", False)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)
        self.icon = QLabel("⤓")
        self.icon.setObjectName("DropIcon")
        self.icon.setFixedSize(52, 52)
        self.icon.setAlignment(Qt.AlignCenter)
        self.title = QLabel(title)
        self.title.setObjectName("H3")
        self.title.setAlignment(Qt.AlignCenter)
        self.hint = QLabel(hint)
        self.hint.setObjectName("Muted")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.title.setWordWrap(True)
        self.setMinimumWidth(0)
        lay.addWidget(self.icon, 0, Qt.AlignHCenter)
        for w in (self.title, self.hint):
            w.setStyleSheet("background: transparent;")
            lay.addWidget(w)

    def set_loaded(self, name: str, detail: str):
        self.setProperty("loaded", True)
        self.icon.setText("✔")
        self.title.setText(name)
        self.hint.setText(detail + "  ·  انقر أو اسحب ملفاً آخر للاستبدال")
        repolish(self)

    def mousePressEvent(self, e):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف Excel", "", "ملفات Excel وCSV (*.xlsx *.xlsm *.xls *.csv);;كل الملفات (*)")
        if path:
            self.fileChosen.emit(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setProperty("hover", True)
            repolish(self)

    def dragLeaveEvent(self, e):
        self.setProperty("hover", False)
        repolish(self)

    def dropEvent(self, e):
        self.setProperty("hover", False)
        repolish(self)
        urls = e.mimeData().urls()
        if urls:
            self.fileChosen.emit(urls[0].toLocalFile())


class KpiCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, color: str = "#2563EB", clickable: bool = False, icon_kind: str = "chart"):
        super().__init__()
        self.setObjectName("Card")
        self._color = color
        self._clickable = clickable
        self.setProperty("clickable", clickable)
        self.setProperty("hover", False)
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 14)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.tile = IconTile(icon_kind, color, 42)
        top.addWidget(self.tile)
        top.addStretch(1)
        lay.addLayout(top)
        lay.addSpacing(4)
        self.v = QLabel("0")
        self.v.setObjectName("Big")
        self.v.setStyleSheet(f"color: {color}; background: transparent;")
        self.t = QLabel(title)
        self.t.setObjectName("H3")
        self.t.setStyleSheet("background: transparent;")
        self.s = QLabel("")
        self.s.setObjectName("Muted")
        self.s.setStyleSheet("background: transparent;")
        for w in (self.v, self.t, self.s):
            lay.addWidget(w)
        add_shadow(self, 22, 4, 22)

    def set(self, value: str, sub: str = ""):
        self.v.setText(value)
        self.s.setText(sub)
        self.s.setVisible(bool(sub))

    def enterEvent(self, e):
        if self._clickable:
            self.setProperty("hover", True)
            repolish(self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._clickable:
            self.setProperty("hover", False)
            repolish(self)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self.clicked.emit()


class DonutChart(QWidget):
    def __init__(self):
        super().__init__()
        self.data: list[tuple[str, int, str]] = []   # (اسم، عدد، لون)
        self.center_top = ""
        self.center_bottom = ""
        self.setMinimumSize(260, 260)
        self.dark = False

    def set_data(self, data, center_top="", center_bottom=""):
        self.data = data
        self.center_top, self.center_bottom = center_top, center_bottom
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 24
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        total = sum(c for _, c, _ in self.data)
        thick = side * 0.17
        track = QColor("#2A3550" if self.dark else "#E8EDF5")
        pen = QPen(track, thick)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        inner = rect.adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        p.drawArc(inner, 0, 360 * 16)
        if total > 0:
            start = 90 * 16
            for _, cnt, col in self.data:
                if cnt <= 0:
                    continue
                span = -int(360 * 16 * cnt / total)
                pen = QPen(QColor(col), thick)
                pen.setCapStyle(Qt.FlatCap)
                p.setPen(pen)
                p.drawArc(inner, start, span)
                start += span
        p.setPen(QColor("#E8EDF7" if self.dark else "#172033"))
        f = QFont(self.font())
        big = max(22, int(side * 0.17))
        f.setPixelSize(big)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(rect.left(), rect.center().y() - big - 2, rect.width(), big + 8), Qt.AlignCenter, self.center_top)
        f.setPixelSize(max(12, int(side * 0.062)))
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#93A0BA" if self.dark else "#667085"))
        p.drawText(QRectF(rect.left(), rect.center().y() + 6, rect.width(), 26), Qt.AlignCenter, self.center_bottom)


class StatusChip(QLabel):
    def __init__(self, status: str = "", dark: bool = False):
        super().__init__(status)
        self.setAlignment(Qt.AlignCenter)
        self.set_status(status, dark)

    def set_status(self, status: str, dark: bool = False):
        self.setText(status)
        main, bg = status_colors(status, dark)
        self.setStyleSheet(f"background:{bg}; color:{main}; border-radius: 12px; padding: 4px 14px; font-weight: 700; font-size: 9.5pt;")


class HBar(QWidget):
    """شريط نسبة صغير (الثقة)."""
    def __init__(self):
        super().__init__()
        self.value = 0
        self.color = "#2563EB"
        self.setFixedHeight(8)

    def set(self, v: int, color: str = "#2563EB"):
        self.value, self.color = v, color
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(128, 140, 165, 70))
        p.drawRoundedRect(r, 4, 4)
        p.setBrush(QColor(self.color))
        p.drawRoundedRect(QRectF(r.right() - r.width() * self.value / 100, r.top(), r.width() * self.value / 100, r.height()), 4, 4)


def human_size(path: str) -> str:
    try:
        n = Path(path).stat().st_size
    except OSError:
        return ""
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return ""
