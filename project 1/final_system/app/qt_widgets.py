"""
qt_widgets.py
-------------
الحاجات المشتركة بين كل الشاشات: الجداول، الكروت، الرسوم البيانية، نافذة الفورم،
خانات المقاسات وتفاصيل الموديل، والكلاس الأب لكل الصفحات (BasePage).

الاتجاه من اليمين للشمال متظبط على البرنامج كله (setLayoutDirection فى qt_main.py)،
فأى حاجة بتتضاف فى layout أفقى بتتحط من اليمين - أول عنصر = أقصى اليمين.

فكرة BasePage (وراثة - Inheritance):
  كل صفحة بتورث منه وبتكتب دالتين بس:
    load()        ← بتجيب البيانات من السيرفر (بتشتغل فى الخلفية)
    render(data)  ← بترسم البيانات فى الشاشة (بتشتغل فى الواجهة)
"""

import os
from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from models import measure_key

# ======================= الألوان =======================
# ألوان "المعنى" بس (مكسب/خسارة/تحذير) - نفسها فى الفاتح والداكن.
# الخلفيات ولون الكلام بتيجى من qt_theme.py حسب الوضع.
from qt_theme import SEMANTIC

GREEN = SEMANTIC["green"]
RED = SEMANTIC["red"]
AMBER = SEMANTIC["amber"]
PURPLE = SEMANTIC["purple"]
BLUE = SEMANTIC["blue"]
TEAL = SEMANTIC["teal"]
NAVY = "#714b67"      # لون البراند (عناوين النوافذ)
GRAY = "#8a8494"      # للحاجات الموقوفة - بيبان على الفاتح والداكن


# ======================= تنسيق الأرقام =======================

def money(n) -> str:
    try:
        f = float(n)
    except (TypeError, ValueError):
        return "0"
    return f"{f:,.0f}" if abs(f - round(f)) < 0.005 else f"{f:,.2f}"


def num(n) -> str:
    """رقم زى الأمتار: 12.5 تفضل 12.5 و 12.0 تبقى 12. الصفر ← —"""
    try:
        f = float(n)
    except (TypeError, ValueError):
        return "—"
    if not f:
        return "—"
    return str(int(f)) if f.is_integer() else f"{f:g}"


def qty(n) -> str:
    """كمية فى المخزن: الصفر بيبان 0."""
    try:
        f = round(float(n), 3)
    except (TypeError, ValueError):
        return "0"
    return str(int(f)) if f.is_integer() else f"{f:g}"


def amount_text(n) -> str:
    """رقم فى خانة يتعدّل: 1500.0 ← 1500."""
    try:
        f = float(n or 0)
    except (TypeError, ValueError):
        return ""
    return f"{f:g}"


def dash(value) -> str:
    return value if value not in ("", None) else "—"


def today_text() -> str:
    return date.today().strftime("%d/%m/%Y")


def fill_combo(combo, options, default=None):
    """options = ["نص", ...] أو [("نص", القيمة), ...]. القيمة بتترجع بـ combo_value."""
    combo.blockSignals(True)
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
    combo.blockSignals(False)


def combo_value(combo):
    """القيمة المختارة (الـ id لو الاختيارات فيها ids)، أو النص لو القايمة قابلة للكتابة."""
    if combo.isEditable():
        text = combo.currentText().strip()
        index = combo.findText(text)
        return combo.itemData(index) if index >= 0 else text
    return combo.currentData()


def searchable(combo):
    """قايمة تقدر تكتب فيها وتدوّر بأى جزء من الاسم."""
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    completer = combo.completer()
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    return combo


def open_path(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# ======================= رسائل بالعربى =======================

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
    """بيرجّع النص اللى المستخدم كتبه، أو None لو لغى."""
    text, ok = QInputDialog.getText(parent, title, label, QLineEdit.Normal, default)
    return text if ok else None


# ======================= أزرار وعناوين =======================

def button(text, variant=None, on_click=None, tooltip=None) -> QPushButton:
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    if on_click:
        btn.clicked.connect(lambda _checked=False: on_click())
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
    """صف أفقى: أول عنصر على اليمين. None = مسافة مرنة فى المكان ده."""
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


def search_box(placeholder, on_change) -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setClearButtonEnabled(True)
    w.setMinimumWidth(260)
    w.textChanged.connect(lambda _t: on_change())
    return w


def matches(text, row, keys) -> bool:
    text = (text or "").strip()
    return not text or any(text in str(row.get(k) or "") for k in keys)


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
    """صندوق بخط ملوّن على الجنب. حط الحاجات فى box.body (QVBoxLayout)."""

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
    """سطر رسم بيانى أفقى: الاسم يمين، العمود فى النص بيكبر من اليمين، الرقم شمال."""

    def __init__(self, title, value, max_value, color, value_text=None):
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

        amount = label(value_text if value_text is not None else money(value))
        amount.setStyleSheet(f"color: {color}; font-weight: bold;")
        amount.setFixedWidth(110)
        row.addWidget(amount)


def kv_row(title, value, color=None) -> QHBoxLayout:
    key = label(title, "muted")
    val = label(str(value))
    val.setTextInteractionFlags(Qt.TextSelectableByMouse)
    val.setStyleSheet(f"color: {color}; font-weight: bold;" if color else "font-weight: bold;")
    return hbox(key, None, val, stretch_end=False)


class Banner(QFrame):
    """شريط ملوّن فوق الصفحة (تنبيه الترخيص مثلاً)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        self.text = label("", wrap=True)
        lay.addWidget(self.text, 1)
        self.actions = QHBoxLayout()
        lay.addLayout(self.actions)
        self.hide()

    def show_message(self, text, color):
        self.setStyleSheet(f"#banner {{ background: {color}; }}")
        self.text.setText(text)
        self.show()


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
        d, m, y = str(text).split(" ")[0].split("/")
        return int(y) * 10000 + int(m) * 100 + int(d)
    except ValueError:
        return 0


class DataTable(QTableWidget):
    """
    جدول بيترتب لما تدوس على العنوان، وكل صف ليه "مفتاح" (رقم الطلب مثلاً).
    columns = [(العنوان, النوع)]   النوع: "text" | "money" | "num" | "qty" | "int" | "date" | "wide"
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
        selected = self.selected_key()
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
                elif kind == "qty":
                    item = SortItem(qty(value), float(value or 0))
                elif kind == "int":
                    item = SortItem(str(int(value or 0)), int(value or 0))
                elif kind == "date":
                    item = SortItem(dash(value), _date_sort(value))
                else:
                    item = SortItem(dash(str(value)) if value not in ("", None) else "—")
                if kind in ("money", "num", "qty", "int", "date"):
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
            elif self.columnWidth(i) > 320:
                self.setColumnWidth(i, 320)
        if selected is not None:
            self.select_key(selected)

    def selected_key(self):
        row = self.currentRow()
        if row < 0 or not self.selectedItems():
            return None
        item = self.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def select_key(self, key):
        for r in range(self.rowCount()):
            item = self.item(r, 0)
            if item and item.data(Qt.UserRole) == key:
                # selectRow مش بيشتغل صح مع الاتجاه من اليمين للشمال، فبنحدد الخلية نفسها
                self.setCurrentItem(item)
                return


# ======================= اختيار ملفات =======================

class FilePicker(QWidget):
    """زرار يختار ملفات. افتراضيًا PDF وصور وأكتر من ملف؛ للوجو: صورة واحدة."""

    def __init__(self, title="📎 اختار ملفات (PDF أو صور)", file_filter="PDF أو صور (*.pdf *.png *.jpg *.jpeg)",
                 multiple=True):
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


# ======================= المقاسات وتفاصيل الموديل =======================

class MeasurementsEditor(QWidget):
    """خانات المقاسات متقسمة (جاكيت / بنطلون / ...) حسب اللى المدير محدده فى الإعدادات."""

    def __init__(self, fields, values=None, columns=4, read_only=False):
        super().__init__()
        self._edits = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        groups = {}
        for f in fields:
            if f.get("is_active", 1):
                groups.setdefault(f["grp"], []).append(f["name"])
        if not groups:
            lay.addWidget(muted("مفيش خانات مقاسات — المدير يضيفها من الإعدادات"))
        for grp, names in groups.items():
            box = QGroupBox(grp)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(8)
            for i, name in enumerate(names):
                edit = QLineEdit()
                edit.setPlaceholderText(name)
                edit.setMaximumWidth(110)
                edit.setReadOnly(read_only)
                key = measure_key(grp, name)
                self._edits[key] = edit
                r, c = divmod(i, columns)
                grid.addWidget(label(name), r, c * 2)
                grid.addWidget(edit, r, c * 2 + 1)
            lay.addWidget(box)
        self._extra = {}
        self.set(values or {})

    def set(self, values):
        values = values or {}
        for key, edit in self._edits.items():
            edit.setText(str(values.get(key, "")))
        # مقاسات قديمة لخانات اتشالت من الإعدادات: بتتحفظ زى ما هى
        self._extra = {k: v for k, v in values.items() if k not in self._edits}

    def get(self) -> dict:
        out = dict(self._extra)
        for key, edit in self._edits.items():
            text = edit.text().strip()
            if text:
                out[key] = text
            else:
                out.pop(key, None)
        return out


def measurements_text(values) -> str:
    """{"جاكيت|الطول": "76"} ← "جاكيت: الطول 76، ..." (للجداول)."""
    groups = {}
    for key, v in (values or {}).items():
        grp, _, name = key.partition("|")
        groups.setdefault(grp, []).append(f"{name} {v}")
    return " — ".join(f"{g}: {'، '.join(items)}" for g, items in groups.items())


class StyleEditor(QWidget):
    """تفاصيل الموديل: لكل اختيار قايمة (تقدر تكتب فيها حاجة مش موجودة)."""

    def __init__(self, options, values=None, columns=3):
        super().__init__()
        self._combos = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        active = [o for o in options if o.get("is_active", 1)]
        for i, opt in enumerate(active):
            combo = QComboBox()
            combo.setEditable(True)
            choices = [c for c in str(opt.get("choices") or "").splitlines() if c.strip()]
            fill_combo(combo, [""] + choices)
            combo.setMinimumWidth(130)
            self._combos[opt["name"]] = combo
            r, c = divmod(i, columns)
            grid.addWidget(label(opt["name"]), r, c * 2)
            grid.addWidget(combo, r, c * 2 + 1)
        if not active:
            grid.addWidget(muted("مفيش تفاصيل موديل — المدير يضيفها من الإعدادات"), 0, 0)
        self.set(values or {})

    def set(self, values):
        for name, combo in self._combos.items():
            combo.setCurrentText(str((values or {}).get(name, "")))

    def get(self) -> dict:
        return {name: combo.currentText().strip() for name, combo in self._combos.items()
                if combo.currentText().strip()}


# ======================= نافذة فورم عامة =======================

class FormDialog(QDialog):
    """
    fields = [{"key", "label", "type": "entry"|"password"|"text"|"combo"|"combo_edit"|"search"|"files"|"check"|"info",
               "options", "default", "placeholder"}]
    options فى الـ combo: ["نص"...] أو [("نص", id)...] - القيمة اللى بترجع هى الـ id.
    action(values) بتتنفذ فى الخلفية. لو رمت خطأ، الرسالة بتظهر جوا النافذة
    والنافذة متتقفلش عشان المستخدم يصلّح ويحاول تانى.
    """

    def __init__(self, parent, app, title, fields, action, on_done=None,
                 submit_text="💾 حفظ", color=NAVY, note=None):
        super().__init__(parent)
        self._app = app
        self._action = action
        self._on_done = on_done
        self._submit_text = submit_text
        self._widgets = {}
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        heading = label(title, "dialogTitle", wrap=True)
        heading.setStyleSheet(f"color: {color};")
        lay.addWidget(heading)
        if note:
            lay.addWidget(muted(note))

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        for f in fields:
            kind = f.get("type", "entry")
            if kind == "info":
                form.addRow(label(f["label"], "muted", wrap=True))
                continue
            if kind == "files":
                w = FilePicker()
            elif kind == "check":
                w = QCheckBox(f.get("text", ""))
                w.setChecked(bool(f.get("default")))
            elif kind in ("combo", "combo_edit", "search"):
                w = QComboBox()
                fill_combo(w, f.get("options", []), f.get("default"))
                if kind == "combo_edit":
                    w.setEditable(True)
                    if f.get("default") in (None, ""):
                        w.setCurrentText("")
                elif kind == "search":
                    searchable(w)
            elif kind == "text":
                w = QPlainTextEdit()
                w.setMinimumHeight(70)
                w.setMaximumHeight(110)
                if f.get("default"):
                    w.setPlainText(str(f["default"]))
            else:
                w = QLineEdit()
                if kind == "password":
                    w.setEchoMode(QLineEdit.Password)
                if f.get("default") not in (None, ""):
                    w.setText(str(f["default"]))
                if f.get("placeholder"):
                    w.setPlaceholderText(f["placeholder"])
                w.returnPressed.connect(self._submit)
            form.addRow(f["label"], w)
            self._widgets[f["key"]] = w
        if len(fields) > 11:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(form_host)
            scroll.setMinimumHeight(420)
            lay.addWidget(scroll, 1)
        else:
            lay.addWidget(form_host)

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
        if isinstance(w, QPlainTextEdit):
            return w.toPlainText().strip()
        return w.text().strip()

    def _submit(self):
        if not self._btn.isEnabled():
            return
        values = {k: self._value(w) for k, w in self._widgets.items()}
        uploading = any(isinstance(w, FilePicker) and w.get() for w in self._widgets.values())
        self._btn.setEnabled(False)
        self._btn.setText("جارى رفع الملفات والحفظ…" if uploading else "جارى الحفظ…")
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
    """كل صفحة بتورث منه. الولد بيكتب load() و render(data) بس، وبيحط حاجاته فى self.body."""
    TITLE = ""
    PAGE = ""

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

    def run_action(self, func, success_message=None, then=None):
        """تنفيذ عملية (تأكيد، مسح...) فى الخلفية وبعدها تحديث كل الصفحات."""
        def done(result):
            if success_message:
                show_info(self, success_message)
            if then:
                then(result)
            self.app.after_change()
        self.app.worker.run(func, done, lambda e: show_error(self, e))

    def form(self, title, fields, action, success_message=None, then=None, **kwargs):
        """then = دالة إضافية تتنادى بعد النجاح (بتاخد نتيجة العملية)."""
        def done(result):
            if success_message:
                show_info(self, success_message)
            if then:
                then(result)
            self.app.after_change()
        return FormDialog(self, self.app, title, fields, action, on_done=done, **kwargs)

    def selected(self, table, items_by_key, message="اختار صف من الجدول الأول"):
        key = table.selected_key()
        if key is None or key not in items_by_key:
            show_info(self, message, "تنبيه")
            return None
        return items_by_key[key]


class ScrollPage(BasePage):
    """صفحة طويلة بتسكرول (الداش بورد، الإعدادات...).
    render بتنادى new_content() وتملا الـ layout اللى راجع."""

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
        old = self._scroll.verticalScrollBar().value()
        self._scroll.setWidget(content)   # Qt بيمسح المحتوى القديم لوحده
        self._scroll.verticalScrollBar().setValue(old)
        return lay
