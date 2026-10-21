"""
qt_widgets.py
-------------
الحاجات المشتركة بين كل الشاشات: الشكل (الألوان والـ stylesheet)، الجداول،
الكروت، الرسوم البيانية، نافذة الفورم، والكلاس الأب لكل الصفحات (BasePage).

الاتجاه من اليمين للشمال متظبط على البرنامج كله (setLayoutDirection في main.py)،
فأي حاجة بتتضاف في layout أفقي بتتحط من اليمين - أول عنصر = أقصى اليمين.

فكرة BasePage (وراثة - Inheritance):
  كل صفحة بتورث منه وبتكتب دالتين بس:
    load()        ← بتجيب البيانات من جوجل (بتشتغل في الخلفية)
    render(data)  ← بترسم البيانات في الشاشة (بتشتغل في الواجهة)
"""

import os
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


# ======================= الألوان =======================
# ألوان "المعنى" بس (مكسب/خسارة/تحذير) - نفسها فى الفاتح والداكن.
# الخلفيات ولون الكلام بتيجى من qt_theme.py حسب الوضع.
from qt_theme import SEMANTIC

GREEN = SEMANTIC["green"]
RED = SEMANTIC["red"]
AMBER = SEMANTIC["amber"]
PURPLE = SEMANTIC["purple"]
BLUE = SEMANTIC["blue"]
NAVY = "#5b5bd6"      # لون البراند (عناوين النوافذ)
GRAY = "#8a94a6"      # للحاجات الموقوفة - بيبان على الفاتح والداكن


# ======================= تنسيق الأرقام =======================

def money(n) -> str:
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return "0"


def num(n) -> str:
    """رقم زي الأمتار: 12.5 تفضل 12.5 و 12.0 تبقى 12."""
    try:
        f = float(n)
    except (TypeError, ValueError):
        return "—"
    if not f:
        return "—"
    return str(int(f)) if f.is_integer() else f"{f:g}"


def dash(value) -> str:
    return value if value not in ("", None) else "—"


def today_text() -> str:
    return date.today().strftime("%d/%m/%Y")


def fill_combo(combo, options, default=None):
    """options = ["نص", ...] أو [("نص", القيمة), ...]. القيمة بتترجع بـ combo_value."""
    combo.clear()
    for opt in options:
        if isinstance(opt, tuple):
            combo.addItem(str(opt[0]), opt[1])
        else:
            combo.addItem(str(opt), opt)
    if default is not None:
        for i, opt in enumerate(options):
            value = opt[1] if isinstance(opt, tuple) else opt
            if value == default:
                combo.setCurrentIndex(i)
                break


def combo_value(combo):
    """القيمة المختارة (الـ id لو الاختيارات فيها ids)، أو النص لو القايمة قابلة للكتابة."""
    if combo.isEditable():
        text = combo.currentText().strip()
        index = combo.findText(text)
        return combo.itemData(index) if index >= 0 else text
    return combo.currentData()


# ======================= رسائل بالعربي =======================

def show_info(parent, text, title="تم"):
    QMessageBox.information(parent, title, str(text))


def show_error(parent, error, title="خطأ"):
    QMessageBox.critical(parent, title, str(error))


def ask_yes_no(parent, text, title="تأكيد") -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(str(text))
    box.setIcon(QMessageBox.Question)
    yes = box.addButton("نعم", QMessageBox.YesRole)
    box.addButton("لا", QMessageBox.NoRole)
    box.exec()
    return box.clickedButton() is yes


def ask_text(parent, title, label, default=""):
    """بيرجّع النص اللي المستخدم كتبه، أو None لو لغى."""
    text, ok = QInputDialog.getText(parent, title, label, QLineEdit.Normal, default)
    return text if ok else None


# ======================= أزرار وعناوين =======================

def button(text, variant=None, on_click=None, tooltip=None) -> QPushButton:
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    if on_click:
        btn.clicked.connect(on_click)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def label(text="", object_name=None, wrap=False) -> QLabel:
    lbl = QLabel(text)
    if object_name:
        lbl.setObjectName(object_name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def section_title(text) -> QLabel:
    return label(text, "sectionTitle")


def muted(text) -> QLabel:
    return label(text, "muted", wrap=True)


def hbox(*widgets, stretch_end=True, spacing=6) -> QHBoxLayout:
    """صف أفقي: أول عنصر على اليمين. None = مسافة مرنة في المكان ده."""
    row = QHBoxLayout()
    row.setSpacing(spacing)
    for w in widgets:
        if w is None:
            row.addStretch(1)
        elif isinstance(w, QWidget):
            row.addWidget(w)
        else:
            row.addLayout(w)
    if stretch_end and None not in widgets:
        row.addStretch(1)
    return row


# ======================= كروت وصناديق ورسوم =======================

class KPICard(QFrame):
    def __init__(self, title, value_text, color):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"#card {{ border-top: 4px solid {color}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(label(title, "cardTitle"))
        value = label(value_text, "cardValue")
        value.setStyleSheet(f"color: {color};")
        lay.addWidget(value)


def cards_grid(specs, per_row=5) -> QWidget:
    """specs = [(عنوان, القيمة كنص, اللون)]."""
    w = QWidget()
    grid = QGridLayout(w)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(10)
    for i, (title, value_text, color) in enumerate(specs):
        grid.addWidget(KPICard(title, value_text, color), i // per_row, i % per_row)
    return w


class Box(QFrame):
    """صندوق أبيض بخط ملوّن على الجنب. حط الحاجات في box.body (QVBoxLayout)."""

    def __init__(self, title=None, color=None, clickable=False):
        super().__init__()
        self.setObjectName("box")
        if color:
            self.setStyleSheet(f"#box {{ border-right: 5px solid {color}; }}")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 10, 14, 10)
        self.body.setSpacing(4)
        if title:
            self.body.addWidget(label(title, "boxTitle"))
        self._on_click = None
        if clickable:
            self.setCursor(Qt.PointingHandCursor)

    def on_click(self, func):
        self._on_click = func

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click()
        else:
            super().mousePressEvent(event)


class BarRow(QWidget):
    """سطر رسم بياني أفقي: الاسم يمين، العمود في النص بيكبر من اليمين، الرقم شمال."""

    def __init__(self, title, value, max_value, color):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        name = label(title)
        name.setFixedWidth(150)
        row.addWidget(name)

        track = QFrame()
        track.setObjectName("barTrack")
        track.setFixedHeight(14)
        inner = QHBoxLayout(track)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        ratio = min(abs(value) / max_value, 1.0) if max_value else 0.0
        filled = int(round(ratio * 1000))
        if filled:
            fill = QFrame()
            fill.setStyleSheet(f"background: {color}; border-radius: 5px;")
            inner.addWidget(fill, filled)
        if 1000 - filled:
            inner.addStretch(1000 - filled)
        row.addWidget(track, 1)

        amount = label(money(value))
        amount.setStyleSheet(f"color: {color}; font-weight: bold;")
        amount.setFixedWidth(110)
        row.addWidget(amount)


def kv_row(title, value, color=None) -> QHBoxLayout:
    key = label(title, "muted")
    val = label(str(value))
    val.setStyleSheet(f"color: {color}; font-weight: bold;" if color else "font-weight: bold;")
    return hbox(key, None, val, stretch_end=False)


# ======================= الجداول =======================

class SortItem(QTableWidgetItem):
    """خلية بتترتب بقيمتها الحقيقية: 9,000 قبل 10,000 (مش بالحروف)، والتواريخ صح."""

    def __init__(self, text, sort_value=None):
        super().__init__(text)
        self._sort = sort_value if sort_value is not None else text

    def __lt__(self, other):
        a, b = self._sort, getattr(other, "_sort", other.text())
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


def _date_sort(text):
    try:
        d, m, y = str(text).split("/")
        return int(y) * 10000 + int(m) * 100 + int(d)
    except ValueError:
        return 0


class DataTable(QTableWidget):
    """
    جدول بيترتب لما تدوس على العنوان، وكل صف ليه "مفتاح" (رقم الصف في الشيت مثلاً).
    columns = [(العنوان, النوع)]   النوع: "text" | "money" | "num" | "int" | "date" | "wide"
    """

    def __init__(self, columns, min_height=None):
        super().__init__(0, len(columns))
        self._kinds = [kind for _, kind in columns]
        self.setHorizontalHeaderLabels([title for title, _ in columns])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        for i, kind in enumerate(self._kinds):
            if kind == "wide":
                header.setSectionResizeMode(i, QHeaderView.Stretch)
        if min_height:
            self.setMinimumHeight(min_height)

    def set_rows(self, rows):
        """rows = [{"key": ..., "values": [...], "color": "#hex" أو None}]"""
        self.setSortingEnabled(False)
        self.clearContents()
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            color = row.get("color")
            for c, value in enumerate(row["values"]):
                kind = self._kinds[c]
                if kind == "money":
                    item = SortItem(money(value) if value not in ("", None) else "—", float(value or 0))
                elif kind == "num":
                    item = SortItem(num(value), float(value or 0))
                elif kind == "int":
                    item = SortItem(str(int(value)), int(value))
                elif kind == "date":
                    item = SortItem(dash(value), _date_sort(value))
                else:
                    item = SortItem(dash(str(value)) if value not in ("", None) else "—")
                if kind in ("money", "num", "int", "date"):
                    item.setTextAlignment(Qt.AlignCenter)
                if color:
                    item.setForeground(QBrush(QColor(color)))
                if c == 0:
                    item.setData(Qt.UserRole, row.get("key"))
                self.setItem(r, c, item)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()
        for i, kind in enumerate(self._kinds):
            if kind == "wide":
                self.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    def selected_key(self):
        row = self.currentRow()
        if row < 0 or not self.selectedItems():
            return None
        item = self.item(row, 0)
        return item.data(Qt.UserRole) if item else None


# ======================= اختيار ملفات PDF =======================

class FilePicker(QWidget):
    """زرار يختار ملفات. افتراضيًا PDF وأكتر من ملف؛ للوجو: صورة واحدة."""

    def __init__(self, title="📎 اختار ملفات PDF", file_filter="PDF (*.pdf)", multiple=True):
        super().__init__()
        self._paths = []
        self._filter = file_filter
        self._multiple = multiple
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(button(title, "light", self._choose))
        self._label = label("مفيش ملفات", "muted", wrap=True)
        row.addWidget(self._label, 1)

    def _choose(self):
        if self._multiple:
            paths, _ = QFileDialog.getOpenFileNames(self, "اختار الملفات", "", self._filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "اختار الملف", "", self._filter)
            paths = [path] if path else []
        if paths:
            self.set_paths(paths)

    def set_paths(self, paths):
        self._paths = list(paths)
        names = "، ".join(os.path.basename(p) for p in self._paths)
        self._label.setText(f"{len(self._paths)} ملف: {names}" if self._paths else "مفيش ملفات")

    def get(self):
        return list(self._paths)


# ======================= نافذة فورم عامة =======================

class FormDialog(QDialog):
    """
    fields = [{"key", "label", "type": "entry"|"combo"|"combo_edit"|"files"|"check", "options", "default"}]
    options فى الـ combo: ["نص"...] أو [("نص", id)...] - القيمة اللى بترجع هى الـ id.
    action(values) بتتنفذ في الخلفية. لو رمت خطأ، الرسالة بتظهر جوا النافذة
    والنافذة متتقفلش عشان المستخدم يصلّح ويحاول تاني.
    """

    def __init__(self, parent, app, title, fields, action, on_done=None,
                 submit_text="💾 حفظ", color=NAVY):
        super().__init__(parent)
        self._app = app
        self._action = action
        self._on_done = on_done
        self._submit_text = submit_text
        self._widgets = {}
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        heading = label(title, "dialogTitle", wrap=True)
        heading.setStyleSheet(f"color: {color};")
        lay.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(8)
        for f in fields:
            kind = f.get("type", "entry")
            if kind == "files":
                w = FilePicker()
            elif kind == "check":
                w = QCheckBox()
                w.setChecked(bool(f.get("default")))
            elif kind in ("combo", "combo_edit"):
                w = QComboBox()
                w.setEditable(kind == "combo_edit")
                fill_combo(w, f.get("options", []), f.get("default"))
                if kind == "combo_edit" and f.get("default") in (None, ""):
                    w.setCurrentText("")
            else:
                w = QLineEdit()
                if f.get("default") not in (None, ""):
                    w.setText(str(f["default"]))
            form.addRow(f["label"], w)
            self._widgets[f["key"]] = w
        lay.addLayout(form)

        self._btn = button(submit_text, "green", self._submit)
        self._btn.setDefault(True)
        lay.addWidget(self._btn)
        self._msg = label("", "errorMsg", wrap=True)
        lay.addWidget(self._msg)
        self.setModal(True)
        self.show()

    def _value(self, w):
        if isinstance(w, FilePicker):
            return w.get()
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, QComboBox):
            return combo_value(w)
        return w.text().strip()

    def _submit(self):
        if not self._btn.isEnabled():
            return
        values = {k: self._value(w) for k, w in self._widgets.items()}
        uploading = any(isinstance(w, FilePicker) and w.get() for w in self._widgets.values())
        self._btn.setEnabled(False)
        self._btn.setText("جارى رفع الفواتير والحفظ…" if uploading else "جارى الحفظ…")
        self._msg.setText("")
        self._app.worker.run(lambda: self._action(values), self._ok, self._fail)

    def _ok(self, result):
        self.accept()
        if self._on_done:
            self._on_done(result)

    def _fail(self, error):
        self._msg.setText(f"❌ {error}")
        self._btn.setEnabled(True)
        self._btn.setText(self._submit_text)


# ======================= الكلاس الأب للصفحات =======================

class BasePage(QWidget):
    """كل صفحة بتورث منه. الولد بيكتب load() و render(data) بس، وبيحط حاجاته في self.body."""
    TITLE = ""

    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.app = app
        self.backend = app.backend
        self._stale = True
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 18, 14)
        self.body.setSpacing(10)

    @property
    def me(self):
        """المستخدم الحالى - دايمًا أحدث نسخة (لو المدير غيّر بيانات الشركة مثلاً)."""
        return self.app.me

    def load(self):
        return None

    def render(self, data):
        pass

    def is_stale(self) -> bool:
        return self._stale

    def mark_stale(self):
        self._stale = True

    def refresh(self):
        self._stale = False
        self.app.worker.run(self.load, self.render, self._load_failed)

    def _load_failed(self, error):
        self._stale = True
        show_error(self, error)

    def run_action(self, func, success_message=None):
        """تنفيذ عملية (تأكيد، مسح...) في الخلفية وبعدها تحديث كل الصفحات."""
        def done(_result):
            if success_message:
                show_info(self, success_message)
            self.app.after_change()
        self.app.worker.run(func, done, lambda e: show_error(self, e))

    def form(self, title, fields, action, success_message=None, then=None, **kwargs):
        """then = دالة إضافية تتنادى بعد النجاح (مثلاً تحديث اسم الشركة فى الهيدر)."""
        def done(_result):
            if success_message:
                show_info(self, success_message)
            if then:
                then()
            self.app.after_change()
        return FormDialog(self, self.app, title, fields, action, on_done=done, **kwargs)

    def selected(self, table, items_by_key, message="اختار صف من الجدول الأول"):
        key = table.selected_key()
        if key is None or key not in items_by_key:
            show_info(self, message, "تنبيه")
            return None
        return items_by_key[key]


class ScrollPage(BasePage):
    """صفحة طويلة بتسكرول (الداش بورد، شاور اند شاتر...).
    render بتنادي new_content() وتملا الـ layout اللي راجع."""

    def __init__(self, app):
        super().__init__(app)
        self.body.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self.body.addWidget(self._scroll)

    def new_content(self) -> QVBoxLayout:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(18, 14, 18, 18)
        lay.setSpacing(10)
        self._scroll.setWidget(content)   # Qt بيمسح المحتوى القديم لوحده
        return lay
