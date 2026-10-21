"""
license_tool.py — أداة التراخيص (عندك إنت بس، مش بتتباع مع البرنامج)
---------------------------------------------------------------------
العميل يبعتلك "كود الجهاز" ← تختار الباقة وعدد المستخدمين ← الأداة تطلّع "كود التفعيل"
وتسجّله فى licenses_log.csv (سجل بكل التراخيص اللى طلعت).

التشغيل: دبل كليك على SUITS-License-Tool.exe (أو: python license_tool/license_tool.py)
أول مرة بيسألك على مكان ملف المفتاح السرى seller_private_key.pem وبيفتكره.
"""

import os
import sys
from datetime import date, datetime

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,  # noqa: E402
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import license_core  # noqa: E402
from license_core import licensing  # noqa: E402


def parse_date(text):
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError("التاريخ لازم يكون كده: 25/12/2026")


SETTINGS = ("MYTECH", "SuitesLicenseTool")


def find_key(parent=None, ask=False):
    """مكان المفتاح السرى: جنب الأداة، أو آخر مكان اتختار، أو بيسأل."""
    saved = QSettings(*SETTINGS).value("key_path", "")
    for path in ([] if ask else [license_core.PRIVATE_KEY_PATH, saved]):
        if path and os.path.isfile(path):
            return path
    QMessageBox.information(parent, "المفتاح السرى",
                            "اختار ملف المفتاح السرى seller_private_key.pem\n"
                            "(اللى اتعمل بـ keygen — غالبًا فى فولدر license_tool أو على الفلاشة).\n\n"
                            "الأداة هتفتكر مكانه، وسجل التراخيص هيتحفظ جنبه.")
    path, _ = QFileDialog.getOpenFileName(parent, "اختار seller_private_key.pem", os.path.dirname(saved or ""),
                                          "المفتاح السرى (*.pem)")
    return path or None


class LicenseTool(QWidget):
    def __init__(self, key_path=None):
        super().__init__()
        self.setWindowTitle("🔑 أداة التراخيص — SUITS")
        self.resize(1100, 760)
        self.setLayoutDirection(Qt.RightToLeft)
        self._load_key(key_path or license_core.PRIVATE_KEY_PATH)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.customer = QLineEdit()
        self.mobile = QLineEdit()
        self.machine = QLineEdit()
        self.machine.setPlaceholderText("ABCD-1234-EF56-7890 (العميل بيبعته من شاشة التفعيل)")
        self.machine.textChanged.connect(self._machine_changed)
        self.history = QLabel("")
        self.history.setStyleSheet("color: #b06f00; font-weight: bold;")
        self.plan = QComboBox()
        for code in (1, 2, 3, 0, 4):
            self.plan.addItem(licensing.PLANS[code], code)
        self.plan.currentIndexChanged.connect(self._update_expiry)
        self.users = QSpinBox()
        self.users.setRange(1, 999)
        self.users.setValue(5)
        self.start = QLineEdit(date.today().strftime("%d/%m/%Y"))
        self.start.textChanged.connect(self._update_expiry)
        # التجديد قبل الانتهاء: بإيدك بس (مش أوتوماتيك)، وعمره ما بيكمّل بعد فترة التجربة
        self.chain = QPushButton("")
        self.chain.setVisible(False)
        self.chain.clicked.connect(lambda: self.start.setText(self._chain_date.strftime("%d/%m/%Y")))
        today_btn = QPushButton("📅 من النهارده")
        today_btn.clicked.connect(lambda: self.start.setText(date.today().strftime("%d/%m/%Y")))
        start_row = QHBoxLayout()
        start_row.addWidget(self.start, 1)
        start_row.addWidget(today_btn)
        start_row.addWidget(self.chain)
        self._chain_date = None
        self.trial = QSpinBox()
        self.trial.setRange(1, 90)
        self.trial.setValue(14)
        self.trial.valueChanged.connect(self._update_expiry)
        self.expiry = QLabel("")
        self.notes = QLineEdit()
        form.addRow("اسم العميل / الشركة", self.customer)
        form.addRow("الموبايل", self.mobile)
        form.addRow("كود الجهاز *", self.machine)
        form.addRow("", self.history)
        form.addRow("الباقة", self.plan)
        form.addRow("عدد المستخدمين", self.users)
        form.addRow("يبدأ من", start_row)
        form.addRow("أيام التجربة (لباقة التجربة بس)", self.trial)
        form.addRow("ينتهى", self.expiry)
        form.addRow("ملاحظات (المبلغ، طريقة الدفع...)", self.notes)
        lay.addLayout(form)

        make = QPushButton("🔑 اعمل كود التفعيل")
        make.setStyleSheet("background: #1f9d57; color: white; font-weight: bold; padding: 10px;")
        make.clicked.connect(self._make)
        lay.addWidget(make)

        self.code = QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setMaximumHeight(90)
        self.code.setStyleSheet("font-family: Consolas, monospace; font-size: 11pt;")
        lay.addWidget(self.code)
        row = QHBoxLayout()
        copy_code = QPushButton("📋 انسخ الكود بس")
        copy_code.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.code.toPlainText()))
        copy_msg = QPushButton("💬 انسخ رسالة واتساب جاهزة")
        copy_msg.clicked.connect(self._copy_message)
        row.addWidget(copy_code)
        row.addWidget(copy_msg)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addWidget(QLabel("📜 كل التراخيص اللى طلعت (licenses_log.csv):"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 بحث بالاسم أو الموبايل أو كود الجهاز")
        self.search.textChanged.connect(self._fill_log)
        lay.addWidget(self.search)
        self.table = QTableWidget(0, len(license_core.LOG_HEADER) - 1)
        self.table.setHorizontalHeaderLabels(license_core.LOG_HEADER[:-2] + [license_core.LOG_HEADER[-1]])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.table, 1)
        self._last = None
        self._update_expiry()
        self._fill_log()

        footer = QHBoxLayout()
        self.key_label = QLabel(f"🔐 المفتاح: {license_core.PRIVATE_KEY_PATH}  —  السجل: {license_core.LOG_PATH}")
        self.key_label.setStyleSheet("color: #777;")
        change = QPushButton("تغيير مكان المفتاح")
        change.clicked.connect(self._change_key)
        footer.addWidget(self.key_label, 1)
        footer.addWidget(change)
        lay.addLayout(footer)

    # ---------- ---------- ----------

    def _load_key(self, path):
        try:
            self.key = license_core.load_private_key(path)
        except FileNotFoundError as e:
            QMessageBox.critical(self, "مفيش مفتاح", str(e))
            raise SystemExit(1)
        except Exception:  # noqa: BLE001 - ملف تانى مش المفتاح
            QMessageBox.critical(self, "خطأ", "الملف ده مش مفتاح تراخيص صالح")
            raise SystemExit(1)
        license_core.use_key_file(path)
        QSettings(*SETTINGS).setValue("key_path", path)

    def _change_key(self):
        path = find_key(self, ask=True)
        if path:
            self._load_key(path)
            self.key_label.setText(f"🔐 المفتاح: {license_core.PRIVATE_KEY_PATH}  —  السجل: {license_core.LOG_PATH}")
            self._fill_log()

    def _rows(self):
        return license_core.read_log()

    def _fill_log(self):
        text = self.search.text().strip()
        rows = [r for r in self._rows() if not text or any(text in c for c in r)]
        self.table.setRowCount(len(rows))
        for i, r in enumerate(reversed(rows)):
            values = r[:-2] + [r[-1]] if len(r) >= len(license_core.LOG_HEADER) else r
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(v))

    def _machine_changed(self):
        try:
            machine = licensing.format_machine(licensing.parse_machine(self.machine.text()))
        except licensing.LicenseError:
            self.history.setText("")
            return
        self.chain.setVisible(False)
        self._chain_date = None
        old = [r for r in self._rows() if len(r) > 7 and r[3] == machine]
        if not old:
            self.history.setText("جهاز جديد — أول ترخيص")
            return
        last = old[-1]
        self.history.setText(f"آخر كود اتعمل للجهاز ده: {last[4]} — {last[5]} مستخدم — ينتهى {last[7]} ({last[1]})")
        if not self.customer.text():
            self.customer.setText(last[1])
            self.mobile.setText(last[2])
        try:
            last_end = datetime.strptime(last[7], "%Y-%m-%d").date()
        except ValueError:
            return
        # لو العميل بيجدد بدرى (والقديم مش تجربة)، زرار يخلّى الجديد يبدأ من يوم انتهاء القديم عشان ميخسرش أيام
        if last_end > date.today() and last[4] != licensing.PLANS[4]:
            self._chain_date = last_end
            self.chain.setText(f"⏩ يبدأ بعد انتهاء الحالى ({last_end.strftime('%d/%m/%Y')})")
            self.chain.setVisible(True)

    def _update_expiry(self):
        try:
            exp = licensing.plan_expiry(self.plan.currentData(), parse_date(self.start.text()), self.trial.value())
            self.expiry.setText(exp.strftime("%d/%m/%Y") if exp else "مدى الحياة — مش بينتهى")
        except ValueError as e:
            self.expiry.setText(f"❌ {e}")

    def _make(self):
        try:
            start = parse_date(self.start.text())
            exp = licensing.plan_expiry(self.plan.currentData(), start, self.trial.value())
            licensing.parse_machine(self.machine.text())
        except (ValueError, licensing.LicenseError) as e:
            QMessageBox.critical(self, "خطأ", str(e))
            return
        summary = (f"الباقة: {licensing.PLANS[self.plan.currentData()]} — {self.users.value()} مستخدم\n"
                   f"من {start.strftime('%d/%m/%Y')} لحد " + (exp.strftime('%d/%m/%Y') if exp else "مدى الحياة")
                   + "\n\nالكود الجديد بيلغى أى كود قبله على نفس الجهاز. أعمله؟")
        if QMessageBox.question(self, "تأكيد", summary) != QMessageBox.Yes:
            return
        try:
            code, expires, serial = license_core.make_code(self.key, self.machine.text(), self.plan.currentData(),
                                                           self.users.value(), start, self.trial.value())
        except (ValueError, licensing.LicenseError) as e:
            QMessageBox.critical(self, "خطأ", str(e))
            return
        machine = licensing.format_machine(licensing.parse_machine(self.machine.text()))
        license_core.log_license(self.customer.text(), self.mobile.text(), machine, self.plan.currentData(),
                                 self.users.value(), start, expires, serial, code, self.notes.text())
        self.code.setPlainText(code)
        self._last = (code, expires)
        self._fill_log()

    def _copy_message(self):
        if not self._last:
            return
        code, expires = self._last
        msg = (f"أهلاً {self.customer.text()} 👋\n"
               f"ده كود تفعيل البرنامج ({licensing.PLANS[self.plan.currentData()]} — {self.users.value()} مستخدم"
               + (f"، لحد {expires.strftime('%d/%m/%Y')}" if expires else "، مدى الحياة") + "):\n\n"
               f"{code}\n\n"
               "انسخه كله والصقه فى شاشة التفعيل (أو الإعدادات ← إدخال كود تجديد).")
        QGuiApplication.clipboard().setText(msg)


def selftest():
    """للـ build: بيتأكد إن الأداة بتعمل كود والبرنامج بيقبله (بمفتاح تجربة مؤقت)."""
    import tempfile
    import traceback
    out = os.path.join(tempfile.gettempdir(), "suits_license_tool_selftest.txt")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key = Ed25519PrivateKey.generate()
        licensing.PUBLIC_KEY_HEX = key.public_key().public_bytes(serialization.Encoding.Raw,
                                                                 serialization.PublicFormat.Raw).hex()
        machine = "ABCD-1234-EF56-7890"
        code, _exp, _serial = license_core.make_code(key, machine, 3, 5)
        lic = licensing.verify(code, licensing.parse_machine(machine))
        result, rc = f"OK users={lic.users} plan={lic.plan_label}", 0
    except Exception:  # noqa: BLE001
        result, rc = "FAIL\n" + traceback.format_exc(), 1
    with open(out, "w", encoding="utf-8") as f:
        f.write(result)
    return rc


def main():
    if "--selftest" in sys.argv:
        return selftest()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    icon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    path = find_key()
    if not path:
        return 0
    w = LicenseTool(path)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
