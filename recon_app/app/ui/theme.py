"""السمات (فاتح/داكن) وأنماط QSS."""
from __future__ import annotations

from ..engine import (STATUS_DIFF, STATUS_DUP, STATUS_MATCHED, STATUS_MISSING_A,
                      STATUS_MISSING_B, STATUS_POSSIBLE)

LIGHT = dict(
    name="light", bg="#F2F7F7", card="#FFFFFF", card2="#F6FAFA", text="#14262B", muted="#62767B",
    border="#E1EAEA", primary="#0D9488", primary_hover="#0B7F75", primary_soft="#DDF4F0",
    side="#0E8F84", side_b="#2FBBA9", side2="#0B7A70", side_text="#E2F6F2", side_active="#FFFFFF",
    input="#FFFFFF", hover="#EAF5F3", sel="#D3F0EB", shadow="#0B2B2A",
    ok_bg="#E3F5EA", ok_fg="#14693A", bad_bg="#FDE3E1", bad_fg="#A1261C",
    warn_bg="#FFF1CF", warn_fg="#8A5A00", warn_bd="#F1D48A", err_bd="#F3B4AE",
    border_strong="#C9D7D8", ring="#9ADBD2", head_bg="#E4ECEE",
    hero_a="#0E9488", hero_b="#3F6EB5",
)
DARK = dict(
    name="dark", bg="#0A1416", card="#112023", card2="#16292C", text="#E6F0F0", muted="#8FA6A9",
    border="#21393C", primary="#2DD4BF", primary_hover="#5EE3D2", primary_soft="#133632",
    side="#0A2E2B", side_b="#0F4F46", side2="#0D3F39", side_text="#CDEBE6", side_active="#FFFFFF",
    input="#0E1C1E", hover="#172E31", sel="#1B4742", shadow="#000000",
    ok_bg="#16382A", ok_fg="#6FD9A0", bad_bg="#4A1F1C", bad_fg="#FF9C92",
    warn_bg="#46380F", warn_fg="#F5CB6A", warn_bd="#6B5416", err_bd="#7A322C",
    border_strong="#385558", ring="#1E6A60", head_bg="#1B3236",
    hero_a="#0F6F66", hero_b="#2B4C8C",
)

# ألوان الحالات: (لون رئيسي، خلفية فاتحة، خلفية داكنة)
STATUS = {
    STATUS_MATCHED: ("#1F9D55", "#E3F5EA", "#16382A"),
    STATUS_DIFF: ("#D99100", "#FFF1CF", "#46380F"),
    STATUS_POSSIBLE: ("#3B7DDD", "#E0EBFF", "#1B2F57"),
    STATUS_MISSING_B: ("#D64535", "#FDE3E1", "#4A1F1C"),
    STATUS_MISSING_A: ("#B2362B", "#FDE3E1", "#4A1F1C"),
    STATUS_DUP: ("#8E4FD1", "#EDE2FA", "#36224F"),
}
PRIORITY = {"عالية": "#D64535", "متوسطة": "#D99100", "منخفضة": "#1F9D55", "—": "#98A1AE"}


def status_colors(status: str, dark: bool):
    main, light_bg, dark_bg = STATUS.get(status, ("#667085", "#EEE", "#222"))
    return main, (dark_bg if dark else light_bg)


def build_qss(p: dict, check_icon: str = "", icons: dict | None = None) -> str:
    """يبني أنماط QSS. `icons` اختياري: مسارات أسهم صغيرة (down/up) تُرسم عند التشغيل."""
    icons = icons or {}
    chk = f"image: url({check_icon});" if check_icon else ""
    dn = f"image: url({icons['down']}); width: 12px; height: 12px;" if icons.get("down") else ""
    up = f"image: url({icons['up']}); width: 12px; height: 12px;" if icons.get("up") else ""
    return f"""
* {{ font-family: "Arial", "Tahoma", "Noto Naskh Arabic", "DejaVu Sans", sans-serif; font-size: 10.5pt; }}
QWidget {{ color: {p['text']}; }}
QMainWindow, QWidget#Root, QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {p['bg']}; }}
QDialog, QMessageBox {{ background: {p['card']}; }}
QMessageBox QLabel {{ background: transparent; color: {p['text']}; }}
QMessageBox QPushButton {{ min-width: 92px; }}
QToolTip {{ background: {p['card']}; color: {p['text']}; border: 1px solid {p['border_strong']}; padding: 6px 8px; border-radius: 6px; }}

/* الشريط الجانبي */
QFrame#Sidebar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {p['side']}, stop:1 {p['side_b']}); border: none; }}
QFrame#SideLine {{ background: rgba(255,255,255,0.22); border: none; min-height: 1px; max-height: 1px; }}
QWidget#BrandBox {{ background: rgba(255,255,255,0.14); border-radius: 18px; }}
QLabel#Brand {{ color: #FFFFFF; font-size: 11pt; font-weight: 700; background: transparent; }}
QLabel#BrandSub {{ color: {p['side_text']}; font-size: 8.5pt; background: transparent; }}
QLabel#SideSection {{ color: rgba(255,255,255,0.65); font-size: 8.5pt; font-weight: 700; padding: 2px 8px; background: transparent; }}
QPushButton#Nav {{ background: transparent; color: {p['side_text']}; border: 1px solid transparent; border-radius: 14px;
    padding: 13px 14px; text-align: right; font-size: 10.5pt; }}
QPushButton#Nav:hover {{ background: rgba(255,255,255,0.14); color: #FFFFFF; }}
QPushButton#Nav:pressed {{ background: rgba(255,255,255,0.26); }}
QPushButton#Nav:checked {{ background: rgba(255,255,255,0.24); border: 1px solid rgba(255,255,255,0.38); color: #FFFFFF; }}
QPushButton#Nav:disabled {{ color: rgba(255,255,255,0.45); background: transparent; }}
QPushButton#Nav[compact="true"] {{ text-align: center; padding: 12px 0px; font-size: 13pt; }}
QLabel#SideFoot {{ color: rgba(255,255,255,0.65); font-size: 8.5pt; background: transparent; }}

/* العنوان المتدرّج للصفحات */
QFrame#Hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {p['hero_b']}, stop:1 {p['hero_a']}); border: none; border-radius: 22px; }}
QLabel#HeroTitle {{ color: #FFFFFF; font-size: 18pt; font-weight: 800; background: transparent; }}
QLabel#HeroSub {{ color: rgba(255,255,255,0.88); font-size: 10pt; background: transparent; }}
QLabel#HeroChip {{ background: rgba(255,255,255,0.20); color: #FFFFFF; border-radius: 14px; padding: 6px 14px; font-weight: 600; font-size: 9.5pt; }}
QPushButton#HeroBtn {{ background: rgba(255,255,255,0.14); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.65); border-radius: 12px; padding: 10px 20px; font-weight: 600; }}
QPushButton#HeroBtn:hover {{ background: rgba(255,255,255,0.28); border-color: #FFFFFF; }}
QPushButton#HeroSolid {{ background: #FFFFFF; color: #0B6F66; border: none; border-radius: 12px; padding: 11px 22px; font-weight: 800; }}
QPushButton#HeroSolid:hover {{ background: #E9FBF8; }}
QPushButton#HeroSolid:disabled {{ background: rgba(255,255,255,0.45); color: rgba(11,111,102,0.6); }}

QLabel#DropOverlay {{ background: rgba(13,148,136,0.88); color: #FFFFFF; border: 3px dashed #FFFFFF; border-radius: 24px; font-size: 18pt; font-weight: 800; }}
QWidget#Plain {{ background: transparent; }}
/* البطاقات */
QFrame#Card {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 18px; }}
QFrame#Card[clickable="true"][hover="true"] {{ border: 1px solid {p['primary']}; background: {p['card2']}; }}
QFrame#CardFlat {{ background: {p['card2']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QFrame#ActionBar {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame#Drop {{ background: {p['card2']}; border: 2px dashed {p['border_strong']}; border-radius: 14px; }}
QFrame#Drop[hover="true"] {{ border-color: {p['primary']}; background: {p['primary_soft']}; }}
QFrame#Drop[loaded="true"] {{ border: 2px solid {p['primary']}; background: {p['primary_soft']}; }}
QLabel#DropIcon {{ background: {p['primary_soft']}; color: {p['primary']}; border-radius: 26px; font-size: 20pt; font-weight: 700; }}
QFrame#Drop[hover="true"] QLabel#DropIcon {{ background: {p['primary']}; color: #FFFFFF; }}
QFrame#Drop[loaded="true"] QLabel#DropIcon {{ background: {p['primary']}; color: #FFFFFF; }}
QFrame#HLine {{ background: {p['border']}; border: none; min-height: 1px; max-height: 1px; }}
QLabel#H1 {{ font-size: 20pt; font-weight: 800; }}
QLabel#H2 {{ font-size: 13pt; font-weight: 700; }}
QLabel#H3 {{ font-size: 11pt; font-weight: 700; }}
QLabel#Eyebrow {{ color: {p['primary']}; font-size: 9pt; font-weight: 700; }}
QLabel#Muted {{ color: {p['muted']}; font-size: 9.5pt; padding: 1px 0px; }}
QLabel#Big {{ font-size: 22pt; font-weight: 800; }}
QLabel#Pct {{ color: {p['primary']}; font-size: 11pt; font-weight: 700; }}
QLabel#Badge {{ background: {p['primary_soft']}; color: {p['primary']}; border-radius: 9px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}
QLabel#BadgeOk {{ background: {p['ok_bg']}; color: {p['ok_fg']}; border-radius: 9px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}
QLabel#BadgeBad {{ background: {p['bad_bg']}; color: {p['bad_fg']}; border-radius: 9px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}
QLabel#BadgeWarn {{ background: {p['warn_bg']}; color: {p['warn_fg']}; border-radius: 9px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}
QLabel#Warn {{ background: {p['warn_bg']}; color: {p['warn_fg']}; border: 1px solid {p['warn_bd']}; border-radius: 10px; padding: 10px 14px; }}
QLabel#Err {{ background: {p['bad_bg']}; color: {p['bad_fg']}; border: 1px solid {p['err_bd']}; border-radius: 10px; padding: 8px 12px; }}

/* الأزرار */
QPushButton {{ background: {p['card']}; border: 1px solid {p['border_strong']}; border-radius: 10px; padding: 10px 20px; }}
QPushButton:hover {{ background: {p['hover']}; border-color: {p['primary']}; }}
QPushButton:pressed {{ background: {p['sel']}; }}
QPushButton:disabled {{ color: {p['muted']}; background: {p['card2']}; border-color: {p['border']}; }}
QPushButton#Primary {{ background: {p['primary']}; color: #FFFFFF; border: none; font-weight: 700; padding: 13px 30px; border-radius: 12px; }}
QPushButton#Primary:hover {{ background: {p['primary_hover']}; }}
QPushButton#Primary:pressed {{ background: {p['primary_hover']}; padding-top: 12px; }}
QPushButton#Primary:disabled {{ background: {p['border']}; color: {p['muted']}; }}
QPushButton#Good {{ background: #1F9D55; color: #FFFFFF; border: none; font-weight: 700; }}
QPushButton#Good:hover {{ background: #188246; }}
QPushButton#Good:disabled {{ background: {p['card2']}; color: {p['muted']}; border: 1px solid {p['border']}; }}
QPushButton#Bad {{ background: #D64535; color: #FFFFFF; border: none; font-weight: 700; }}
QPushButton#Bad:hover {{ background: #B93728; }}
QPushButton#Bad:disabled {{ background: {p['card2']}; color: {p['muted']}; border: 1px solid {p['border']}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {p['border_strong']}; }}
QPushButton#Ghost:hover {{ background: {p['hover']}; border-color: {p['primary']}; color: {p['primary']}; }}
QPushButton#Chip {{ background: {p['card']}; border: 1px solid {p['border_strong']}; border-radius: 16px; padding: 8px 18px; }}
QPushButton#Chip:hover {{ border-color: {p['primary']}; color: {p['primary']}; }}
QPushButton#Chip:checked {{ background: {p['primary']}; color: #FFFFFF; border-color: {p['primary']}; font-weight: 700; }}

/* الحقول */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{ background: {p['input']}; border: 1px solid {p['border_strong']};
    border-radius: 10px; padding: 9px 12px; min-height: 22px; selection-background-color: {p['primary']}; selection-color: #FFFFFF; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QTextEdit:hover {{ border: 1px solid {p['muted']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{ border: 1px solid {p['primary']}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ background: {p['card2']}; color: {p['muted']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ {dn} }}
QComboBox QAbstractItemView {{ background: {p['card']}; border: 1px solid {p['border_strong']}; border-radius: 8px; padding: 4px;
    selection-background-color: {p['sel']}; selection-color: {p['text']}; outline: 0; }}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 2px 8px; border-radius: 6px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top left; width: 20px; border: none; background: transparent; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom left; width: 20px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ {up.replace('12px', '9px')} }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ {dn.replace('12px', '9px')} }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 1px solid {p['border_strong']}; background: {p['input']}; }}
QCheckBox::indicator:hover {{ border-color: {p['primary']}; }}
QCheckBox::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; {chk} }}

/* الجداول */
QTableView, QTableWidget {{ background: {p['card']}; alternate-background-color: {p['card2']}; border: 1px solid {p['border']};
    border-radius: 12px; gridline-color: transparent; selection-background-color: {p['sel']}; selection-color: {p['text']}; outline: 0; }}
QTableView::item {{ padding: 6px 10px; border: none; }}
QTableView::item:hover {{ background: {p['hover']}; }}
QTableView::item:selected {{ background: {p['sel']}; color: {p['text']}; }}
QHeaderView::section {{ background: {p['head_bg']}; color: {p['text']}; border: none; border-bottom: 2px solid {p['border_strong']};
    padding: 13px 10px; font-weight: 800; font-size: 9.8pt; }}
QHeaderView::down-arrow {{ {dn.replace('12px', '10px')} subcontrol-origin: padding; subcontrol-position: center left; }}
QHeaderView::up-arrow {{ {up.replace('12px', '10px')} subcontrol-origin: padding; subcontrol-position: center left; }}
QTableCornerButton::section {{ background: {p['head_bg']}; border: none; }}

/* التبويب */
QTabWidget::pane {{ border: none; border-top: 1px solid {p['border']}; }}
QTabBar::tab {{ background: transparent; color: {p['muted']}; padding: 12px 28px; border: none; border-bottom: 3px solid transparent; font-weight: 600; margin-left: 8px; }}
QTabBar::tab:selected {{ color: {p['primary']}; border-bottom: 3px solid {p['primary']}; }}
QTabBar::tab:hover:!selected {{ color: {p['text']}; border-bottom: 3px solid {p['border_strong']}; }}

/* التمرير */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border_strong']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border_strong']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QProgressBar {{ background: {p['border']}; border: none; border-radius: 6px; height: 12px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {p['primary']}; border-radius: 6px; }}
QSplitter::handle {{ background: transparent; width: 10px; }}
QSplitter::handle:hover {{ background: {p['border']}; border-radius: 4px; }}
QStatusBar {{ background: {p['card']}; color: {p['muted']}; border-top: 1px solid {p['border']}; font-size: 9.5pt; }}
QStatusBar::item {{ border: none; }}
QGroupBox {{ border: none; }}
"""
