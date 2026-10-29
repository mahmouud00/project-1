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
        "bg": "#f5f4f7", "surface": "#ffffff", "surface_alt": "#f6f3f6", "border": "#e4dfe6",
        "text": "#1f1b24", "muted": "#6e6676",
        "accent": "#714b67", "accent_hover": "#5e3d55", "accent_soft": "#f3eaf1", "accent_text": "#714b67",
        "sidebar_bg": "#ffffff", "sidebar_text": "#4b4452", "sidebar_hover": "#f5eff4",
        "input_bg": "#ffffff", "input_border": "#d8d1db",
        "table_header_bg": "#f4eff4", "table_header_text": "#4b4452",
        "selection_bg": "#ead9e6", "selection_text": "#1f1b24", "track": "#eee9ef",
        "button_light": "#eeeaf0", "button_light_hover": "#e2dbe5",
    },
    "dark": {
        "bg": "#14111a", "surface": "#1d1924", "surface_alt": "#231e2b", "border": "#352d3f",
        "text": "#ece8f0", "muted": "#a59cb0",
        "accent": "#9b6a8f", "accent_hover": "#b07fa4", "accent_soft": "#33263a", "accent_text": "#e0b3d4",
        "sidebar_bg": "#18141f", "sidebar_text": "#c2b8cc", "sidebar_hover": "#262030",
        "input_bg": "#131017", "input_border": "#3e3448",
        "table_header_bg": "#231e2b", "table_header_text": "#d2c9db",
        "selection_bg": "#4a3550", "selection_text": "#ffffff", "track": "#2a2333",
        "button_light": "#2b2434", "button_light_hover": "#362d41",
    },
}

# ألوان المعنى (مكسب/خسارة/تحذير...) - متختارة بحيث تبان كويس على الفاتح والداكن
SEMANTIC = {"green": "#1f9d57", "red": "#e04848", "amber": "#b06f00", "purple": "#8b5cf6", "blue": "#3b82f6",
            "teal": "#0f9e9e"}

MODES = [("🖥️ زى الجهاز", "system"), ("☀️ فاتح", "light"), ("🌙 داكن", "dark")]


_CHECK_FILE = None


def _check_icon():
    """علامة ✓ بيضا للـ checkbox (بتتعمل مرة واحدة فى فولدر مؤقت)."""
    global _CHECK_FILE
    if _CHECK_FILE is None:
        import os
        import tempfile
        _CHECK_FILE = os.path.join(tempfile.gettempdir(), "suits_check.svg").replace("\\", "/")
        with open(_CHECK_FILE, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                    '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="white" stroke-width="2.2" '
                    'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return _CHECK_FILE


def build_stylesheet(t: dict) -> str:
    return _stylesheet(t).replace("__CHECK__", _check_icon())


def _stylesheet(t: dict) -> str:
    s = SEMANTIC
    return f"""
* {{ font-family: "Segoe UI", "Tahoma", "Arial"; font-size: 10pt; color: {t['text']}; }}
QMainWindow, QDialog, #page, #loginPage {{ background: {t['bg']}; }}
QToolTip {{ color: {t['text']}; background: {t['surface']}; border: 1px solid {t['border']}; padding: 4px; }}
QLabel {{ background: transparent; }}

#sidebar {{ background: {t['sidebar_bg']}; border-left: 1px solid {t['border']}; }}
#sidebarTitle {{ font-size: 12pt; font-weight: bold; color: {t['accent_text']}; }}
#sidebarSub {{ color: {t['muted']}; font-size: 8.5pt; }}
#sidebarUser {{ color: {t['muted']}; font-size: 9pt; }}
#sidebar QPushButton {{ color: {t['sidebar_text']}; background: transparent; text-align: right;
    padding: 8px 12px; border: none; border-radius: 8px; font-size: 10.5pt; font-weight: normal; }}
#sidebar QPushButton:hover {{ background: {t['sidebar_hover']}; }}
#sidebar QPushButton:checked {{ background: {t['accent_soft']}; color: {t['accent_text']}; font-weight: bold; }}
#sidebar QPushButton#sideAction {{ background: {t['button_light']}; color: {t['text']}; text-align: center;
    padding: 6px; }}
#sidebar QPushButton#sideAction:hover {{ background: {t['button_light_hover']}; }}

#header {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
#pageTitle {{ font-size: 15pt; font-weight: bold; color: {t['text']}; }}
#companyName {{ font-size: 11pt; font-weight: bold; color: {t['text']}; }}
#busy {{ color: {s['amber']}; font-size: 9pt; }}
#banner {{ border: none; padding: 8px 16px; font-weight: bold; color: white; }}
#banner QLabel {{ color: white; font-weight: bold; }}

QPushButton {{ background: {t['accent']}; color: white; border: none; border-radius: 8px;
    padding: 7px 14px; font-weight: bold; }}
QPushButton:hover {{ background: {t['accent_hover']}; }}
QPushButton:disabled {{ background: {t['button_light']}; color: {t['muted']}; }}
QPushButton[variant="green"] {{ background: {s['green']}; }}
QPushButton[variant="red"] {{ background: {s['red']}; }}
QPushButton[variant="amber"] {{ background: {s['amber']}; }}
QPushButton[variant="purple"] {{ background: {s['purple']}; }}
QPushButton[variant="blue"] {{ background: {s['blue']}; }}
QPushButton[variant="teal"] {{ background: {s['teal']}; }}
QPushButton[variant="green"]:hover, QPushButton[variant="red"]:hover, QPushButton[variant="amber"]:hover,
QPushButton[variant="purple"]:hover, QPushButton[variant="blue"]:hover, QPushButton[variant="teal"]:hover
    {{ border: 2px solid {t['border']}; }}
QPushButton[variant="light"] {{ background: {t['button_light']}; color: {t['text']}; font-weight: normal; }}
QPushButton[variant="light"]:hover {{ background: {t['button_light_hover']}; }}
QPushButton[variant="big"] {{ padding: 16px; font-size: 12pt; text-align: right; }}

QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{ background: {t['input_bg']}; color: {t['text']};
    border: 1px solid {t['input_border']}; border-radius: 8px; padding: 6px 8px; min-height: 20px;
    selection-background-color: {t['selection_bg']}; selection-color: {t['selection_text']}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {t['accent']}; }}
QLineEdit:read-only {{ background: {t['surface_alt']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; color: {t['text']};
    selection-background-color: {t['selection_bg']}; selection-color: {t['selection_text']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t['muted']}; border-radius: 4px;
    background: {t['input_bg']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border: 1px solid {t['accent']};
    image: url(__CHECK__); }}
QCheckBox::indicator:disabled {{ border-color: {t['border']}; }}
QGroupBox {{ border: 1px solid {t['border']}; border-radius: 10px; margin-top: 14px; padding: 10px 8px 8px 8px;
    background: {t['surface']}; font-weight: bold; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top right; padding: 0 8px;
    color: {t['accent_text']}; }}

QTabWidget::pane {{ border: 1px solid {t['border']}; border-radius: 10px; background: {t['bg']}; top: -1px; }}
QTabBar::tab {{ background: {t['button_light']}; color: {t['text']}; padding: 8px 16px; margin: 0 2px;
    border-top-left-radius: 8px; border-top-right-radius: 8px; }}
QTabBar::tab:selected {{ background: {t['accent']}; color: white; font-weight: bold; }}

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
#code {{ font-family: "Consolas", "Courier New", monospace; font-size: 11pt; letter-spacing: 1px; }}
#barTrack {{ background: {t['track']}; border-radius: 5px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 5px; min-width: 30px; }}
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
    mode = QSettings("TailorMaster", "Desktop").value("theme", "system")
    return mode if mode in ("system", "light", "dark") else "system"


def save_mode(mode: str):
    QSettings("TailorMaster", "Desktop").setValue("theme", mode)
