"""
qt_theme.py
-----------
الشكل كله (فاتح / داكن / زى الجهاز) من مكان واحد.

ليه كل لون متحدد هنا صراحة؟
  لو سبنا ويندوز يختار لون الكلام، وويندوز على الوضع الداكن، هيدّى كلام أبيض -
  ولو الخلفية بيضا الكلام بيختفى (وده كان سبب "الكلام مش بيبان غير لما أحدده").
  هنا كل لون (الخلفية والكلام والجداول والخانات) متحدد لكل وضع، فمفيش حاجة بتختفى.

عايز تغيّر الألوان؟ عدّل القيم فى THEMES بس - البرنامج كله بيتبنى منها.
"""

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

THEMES = {
    "light": {
        "bg": "#f4f6fb", "surface": "#ffffff", "surface_alt": "#f1f4f9", "border": "#e3e7ef",
        "text": "#1e2433", "muted": "#6b7486",
        "accent": "#5b5bd6", "accent_hover": "#4848c4", "accent_soft": "#eef0fe", "accent_text": "#5b5bd6",
        "sidebar_bg": "#ffffff", "sidebar_text": "#4a5264", "sidebar_hover": "#f1f4fb",
        "input_bg": "#ffffff", "input_border": "#d7dce6",
        "table_header_bg": "#f1f4f9", "table_header_text": "#4a5264",
        "selection_bg": "#e3e6fd", "selection_text": "#1e2433", "track": "#edf0f6",
        "button_light": "#eceff5", "button_light_hover": "#e0e4ec",
    },
    "dark": {
        "bg": "#0f1420", "surface": "#171d2b", "surface_alt": "#1d2435", "border": "#2a3346",
        "text": "#e6e9f0", "muted": "#94a0b8",
        "accent": "#6d6df0", "accent_hover": "#8181f5", "accent_soft": "#262f4d", "accent_text": "#a5b4fc",
        "sidebar_bg": "#121827", "sidebar_text": "#aab4c8", "sidebar_hover": "#1c2436",
        "input_bg": "#10151f", "input_border": "#323c52",
        "table_header_bg": "#1d2435", "table_header_text": "#c3cbdb",
        "selection_bg": "#2b3561", "selection_text": "#ffffff", "track": "#232b3d",
        "button_light": "#252d40", "button_light_hover": "#2f3850",
    },
}

# ألوان المعنى (مكسب/خسارة/تحذير...) - متختارة بحيث تبان كويس على الفاتح والداكن
SEMANTIC = {"green": "#22a35a", "red": "#e04848", "amber": "#b06f00", "purple": "#8b5cf6", "blue": "#3b82f6"}

MODES = [("🖥️ زى الجهاز", "system"), ("☀️ فاتح", "light"), ("🌙 داكن", "dark")]


def build_stylesheet(t: dict) -> str:
    s = SEMANTIC
    return f"""
* {{ font-family: "Segoe UI"; font-size: 10pt; color: {t['text']}; }}
QMainWindow, QDialog, #page, #loginPage {{ background: {t['bg']}; }}
QToolTip {{ color: {t['text']}; background: {t['surface']}; border: 1px solid {t['border']}; padding: 4px; }}
QLabel {{ background: transparent; }}

#sidebar {{ background: {t['sidebar_bg']}; border-left: 1px solid {t['border']}; }}
#sidebarTitle {{ font-size: 12pt; font-weight: bold; color: {t['text']}; }}
#sidebarUser {{ color: {t['muted']}; font-size: 9pt; }}
#sidebar QPushButton {{ color: {t['sidebar_text']}; background: transparent; text-align: right;
    padding: 9px 14px; border: none; border-radius: 8px; font-size: 10.5pt; font-weight: normal; }}
#sidebar QPushButton:hover {{ background: {t['sidebar_hover']}; }}
#sidebar QPushButton:checked {{ background: {t['accent_soft']}; color: {t['accent_text']}; font-weight: bold; }}
#sidebar QPushButton#sideAction {{ background: {t['button_light']}; color: {t['text']}; text-align: center;
    padding: 7px; }}
#sidebar QPushButton#sideAction:hover {{ background: {t['button_light_hover']}; }}

#header {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
#pageTitle {{ font-size: 15pt; font-weight: bold; color: {t['text']}; }}
#companyName {{ font-size: 11pt; font-weight: bold; color: {t['text']}; }}
#busy {{ color: {s['amber']}; font-size: 9pt; }}

QPushButton {{ background: {t['accent']}; color: white; border: none; border-radius: 8px;
    padding: 7px 14px; font-weight: bold; }}
QPushButton:hover {{ background: {t['accent_hover']}; }}
QPushButton:disabled {{ background: {t['button_light']}; color: {t['muted']}; }}
QPushButton[variant="green"] {{ background: {s['green']}; }}
QPushButton[variant="red"] {{ background: {s['red']}; }}
QPushButton[variant="amber"] {{ background: {s['amber']}; }}
QPushButton[variant="purple"] {{ background: {s['purple']}; }}
QPushButton[variant="blue"] {{ background: {s['blue']}; }}
QPushButton[variant="green"]:hover, QPushButton[variant="red"]:hover, QPushButton[variant="amber"]:hover,
QPushButton[variant="purple"]:hover, QPushButton[variant="blue"]:hover {{ border: 2px solid {t['border']}; }}
QPushButton[variant="light"] {{ background: {t['button_light']}; color: {t['text']}; font-weight: normal; }}
QPushButton[variant="light"]:hover {{ background: {t['button_light_hover']}; }}

QLineEdit, QComboBox {{ background: {t['input_bg']}; color: {t['text']}; border: 1px solid {t['input_border']};
    border-radius: 8px; padding: 6px 8px; min-height: 20px; selection-background-color: {t['selection_bg']};
    selection-color: {t['selection_text']}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; color: {t['text']};
    selection-background-color: {t['selection_bg']}; selection-color: {t['selection_text']}; }}
QCheckBox {{ spacing: 8px; }}

QTableWidget {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 10px; gridline-color: {t['border']}; alternate-background-color: {t['surface_alt']};
    selection-background-color: {t['selection_bg']}; selection-color: {t['selection_text']}; }}
QHeaderView::section {{ background: {t['table_header_bg']}; color: {t['table_header_text']}; padding: 7px;
    border: none; border-bottom: 1px solid {t['border']}; font-weight: bold; }}
QTableCornerButton::section {{ background: {t['table_header_bg']}; border: none; }}

#card, #box, #loginCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px; }}
#cardTitle {{ color: {t['muted']}; font-size: 9pt; }}
#cardValue {{ font-size: 16pt; font-weight: bold; }}
#boxTitle {{ font-weight: bold; color: {t['text']}; }}
#sectionTitle {{ font-size: 12.5pt; font-weight: bold; color: {t['text']}; }}
#dialogTitle {{ font-size: 12.5pt; font-weight: bold; }}
#muted {{ color: {t['muted']}; font-size: 9pt; }}
#errorMsg {{ color: {s['red']}; }}
#barTrack {{ background: {t['track']}; border-radius: 5px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""


def build_palette(t: dict) -> QPalette:
    """الألوان الأساسية لكل أجزاء Qt (حتى رسايل التأكيد وفتح الملفات)."""
    p = QPalette()
    roles = {
        QPalette.Window: t["bg"], QPalette.WindowText: t["text"], QPalette.Base: t["input_bg"],
        QPalette.AlternateBase: t["surface_alt"], QPalette.Text: t["text"], QPalette.Button: t["button_light"],
        QPalette.ButtonText: t["text"], QPalette.Highlight: t["selection_bg"],
        QPalette.HighlightedText: t["selection_text"], QPalette.ToolTipBase: t["surface"],
        QPalette.ToolTipText: t["text"], QPalette.PlaceholderText: t["muted"], QPalette.Link: t["accent"],
        QPalette.Mid: t["border"], QPalette.Dark: t["border"], QPalette.Light: t["surface"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    return p


def system_is_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:      # Qt أقدم من 6.5
        return False


def resolve(mode: str) -> str:
    if mode == "system":
        return "dark" if system_is_dark() else "light"
    return mode if mode in THEMES else "light"


def apply_theme(qt_app, mode: str) -> str:
    """بيطبّق الوضع على البرنامج كله فورًا، وبيرجّع "light" أو "dark"."""
    name = resolve(mode)
    t = THEMES[name]
    qt_app.setStyle("Fusion")          # نفس الشكل على كل الأجهزة، ومش بيتأثر بثيم ويندوز
    qt_app.setPalette(build_palette(t))
    qt_app.setStyleSheet(build_stylesheet(t))
    return name


def saved_mode() -> str:
    mode = QSettings("WorkshopManager", "Desktop").value("theme", "system")
    return mode if mode in ("system", "light", "dark") else "system"


def save_mode(mode: str):
    QSettings("WorkshopManager", "Desktop").setValue("theme", mode)
