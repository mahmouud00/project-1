"""
qt_auth.py
----------
الشاشات اللى قبل البرنامج نفسه:
  أول تشغيل ← الجهاز ده السيرفر؟ ولا جهاز موظف (يتصل بالسيرفر)؟
  مفيش ترخيص ← شاشة التفعيل (كود الجهاز + كود التفعيل)
  مفيش شركة ← إنشاء الشركة وحساب المدير
  الدخول ← اسم المستخدم والباسورد
"""

import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QFrame, QLineEdit, QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget

import local_config
import qt_widgets as ui
from app_info import APP_NAME, APP_SUBTITLE, APP_VERSION, SELLER_NAME, SELLER_PHONE, resource_path
from backend import ping
from server.api import discover


def logo_label(width, data=None) -> QWidget:
    lbl = ui.label()
    pix = QPixmap()
    if not (data and pix.loadFromData(data)):
        pix = QPixmap(resource_path("assets", "logo.png"))
    if not pix.isNull():
        pix = pix.scaled(width, width, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl.setPixmap(pix)
        lbl.setMinimumSize(pix.size())
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class CardScreen(QWidget):
    """شاشة فيها كارت فى النص (الكلاس الأب لكل شاشات الدخول)."""

    def __init__(self, title, subtitle="", width=440, logo=None):
        super().__init__()
        self.setObjectName("loginPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.addStretch(1)
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(width)
        self.card = QVBoxLayout(card)
        self.card.setContentsMargins(32, 24, 32, 24)
        self.card.setSpacing(10)
        self.card.addWidget(logo_label(150, logo))
        t = ui.label(title, "pageTitle", wrap=True)
        t.setAlignment(Qt.AlignCenter)
        self.card.addWidget(t)
        if subtitle:
            s = ui.label(subtitle, "muted", wrap=True)
            s.setAlignment(Qt.AlignCenter)
            self.card.addWidget(s)
        host_lay.addWidget(card, 0, Qt.AlignHCenter)
        host_lay.addStretch(1)
        scroll.setWidget(host)
        self.msg = ui.label("", "errorMsg", wrap=True)
        self.msg.setAlignment(Qt.AlignCenter)

    def field(self, placeholder, password=False, text="") -> QLineEdit:
        w = QLineEdit(text)
        w.setPlaceholderText(placeholder)
        if password:
            w.setEchoMode(QLineEdit.Password)
        self.card.addWidget(w)
        return w

    def busy(self, button, text):
        self.msg.setText("")
        button.setEnabled(False)
        button.setText(text)

    def failed(self, button, text, error):
        self.msg.setStyleSheet(f"color: {ui.RED};")
        self.msg.setText(f"❌ {error}")
        button.setEnabled(True)
        button.setText(text)

    def note(self, text, color):
        self.msg.setStyleSheet(f"color: {color};")
        self.msg.setText(text)

    def version_line(self):
        v = ui.label(f"{APP_NAME} — الإصدار {APP_VERSION}", "muted")
        v.setAlignment(Qt.AlignCenter)
        self.card.addWidget(v)


# ============================================================
#                       أول تشغيل
# ============================================================

class SetupScreen(CardScreen):
    def __init__(self, app):
        super().__init__(f"أهلاً بيك فى {APP_NAME}", f"{APP_SUBTITLE}\nالجهاز ده هيشتغل إزاى؟", width=520)
        self._app = app
        server = ui.button("🖥️  الجهاز ده هو السيرفر\n(أو المحل عنده جهاز واحد بس)", "big",
                           lambda: app.choose_mode("server"))
        self.card.addWidget(server)
        self.card.addWidget(ui.muted("قاعدة البيانات بتتحفظ على الجهاز ده. لازم يكون مفتوح والبرنامج شغّال "
                                     "عشان باقى الأجهزة تشتغل. اختار جهاز ثابت (جهاز المدير أو الحسابات)."))
        client = ui.button("💻  جهاز موظف\n(بيتصل بالسيرفر على شبكة المحل)", "big", app.show_connect)
        client.setProperty("variant", "big")
        client.setStyleSheet("background: #3b82f6;")
        self.card.addWidget(client)
        self.card.addWidget(ui.muted("لازم يكون الجهاز ده على نفس الشبكة (الواى فاى أو الكابل) اللى عليها السيرفر."))
        self.version_line()


class ConnectScreen(CardScreen):
    """جهاز موظف: يدوّر على السيرفر أوتوماتيك، أو يكتب عنوانه."""

    def __init__(self, app, message=None):
        super().__init__("💻 الاتصال بالسيرفر", "دوس «دوّر على السيرفر»، أو اكتب العنوان اللى المدير شايفه "
                                               "فى صفحة الإعدادات على جهاز السيرفر.")
        self._app = app
        cfg = local_config.load()
        self._find_btn = ui.button("🔎 دوّر على السيرفر", "blue", self._find)
        self.card.addWidget(self._find_btn)
        self._found = QVBoxLayout()
        self.card.addLayout(self._found)
        self._host = self.field("عنوان السيرفر (مثال: 192.168.1.10)", text=cfg.get("host", ""))
        self._port = self.field("البورت", text=str(cfg.get("port") or local_config.DEFAULT_PORT))
        self._btn = ui.button("🔌 اتصال", "green", self._connect)
        self._host.returnPressed.connect(self._connect)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        self.card.addWidget(ui.button("↩️ رجوع", "light", app.show_setup))
        if message:
            self.note(f"❌ {message}", ui.RED)

    def _find(self):
        self.busy(self._find_btn, "جارى البحث…")

        def done(servers):
            self._find_btn.setEnabled(True)
            self._find_btn.setText("🔎 دوّر تانى")
            while self._found.count():
                w = self._found.takeAt(0).widget()
                if w:
                    w.deleteLater()
            if not servers:
                self.note("ملقيتش سيرفر. اتأكد إن البرنامج مفتوح على جهاز السيرفر، أو اكتب العنوان بإيدك.", ui.AMBER)
                return
            self.note("دوس على السيرفر بتاعك:", ui.GREEN)
            for ip, port, company in servers:
                self._found.addWidget(ui.button(f"🏢 {company or 'سيرفر'} — {ip}", "light",
                                                lambda i=ip, p=port: self._use(i, p)))

        self._app.worker.run(discover, done, lambda e: self.failed(self._find_btn, "🔎 دوّر على السيرفر", e))

    def _use(self, host, port):
        self._host.setText(host)
        self._port.setText(str(port))
        self._connect()

    def _connect(self):
        if not self._btn.isEnabled():
            return
        host = self._host.text().strip()
        try:
            port = int(self._port.text().strip() or local_config.DEFAULT_PORT)
        except ValueError:
            self.failed(self._btn, "🔌 اتصال", "البورت لازم يكون رقم")
            return
        if not host:
            self.failed(self._btn, "🔌 اتصال", "اكتب عنوان السيرفر")
            return
        self.busy(self._btn, "جارى الاتصال…")

        def done(info):
            if info:
                self._app.choose_mode("client", host, port)
            else:
                self.failed(self._btn, "🔌 اتصال", "مفيش سيرفر للبرنامج على العنوان ده")

        self._app.worker.run(lambda: ping(host, port, 4), done, lambda e: self.failed(self._btn, "🔌 اتصال", e))


class ConnectionErrorScreen(CardScreen):
    def __init__(self, app, error):
        server_mode = local_config.load().get("mode") == "server"
        super().__init__("⚠️ مش قادر أتصل", str(error))
        self._app = app
        self.card.addWidget(ui.button("🔄 حاول تانى", "green", app.connect))
        if not server_mode:
            self.card.addWidget(ui.button("⚙️ غيّر عنوان السيرفر", "blue", app.show_connect))
        self.card.addWidget(ui.button("↩️ أول تشغيل (اختار نوع الجهاز من جديد)", "light", app.reset_mode))
        self.version_line()


# ============================================================
#                       التفعيل
# ============================================================

class ActivationScreen(CardScreen):
    def __init__(self, app, status):
        lic = status.get("license") or {}
        super().__init__("🔑 تفعيل البرنامج", "البرنامج محتاج كود تفعيل عشان يشتغل", width=520)
        self._app = app
        if lic.get("state") == "invalid":
            self.card.addWidget(ui.label(f"⚠️ {lic.get('message')}", "errorMsg", wrap=True))
        self.card.addWidget(ui.label("1️⃣ ابعت كود الجهاز ده:", "boxTitle"))
        code = ui.label(lic.get("machine", "—"), "pageTitle")
        code.setObjectName("code")
        code.setStyleSheet(f"font-size: 18pt; color: {ui.NAVY}; letter-spacing: 2px;")
        code.setAlignment(Qt.AlignCenter)
        code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.card.addWidget(code)
        self.card.addWidget(ui.button("📋 انسخ كود الجهاز", "light",
                                      lambda: (QGuiApplication.clipboard().setText(lic.get("machine", "")),
                                               self.note("✅ اتنسخ — ابعته واتساب", ui.GREEN))))
        self.card.addWidget(ui.muted(f"لـ {SELLER_NAME} — {SELLER_PHONE}"))
        self.card.addWidget(ui.label("2️⃣ الصق كود التفعيل اللى وصلك:", "boxTitle"))
        self._code = QPlainTextEdit()
        self._code.setPlaceholderText("XXXXX-XXXXX-XXXXX-...")
        self._code.setMaximumHeight(110)
        self.card.addWidget(self._code)
        self._btn = ui.button("✅ تفعيل", "green", self._activate)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        if local_config.load().get("mode") == "client":
            self.card.addWidget(ui.muted("التفعيل ده بيتعمل للسيرفر (كود الجهاز فوق بتاع جهاز السيرفر)."))
        self.version_line()

    def _activate(self):
        code = self._code.toPlainText().strip()
        self.busy(self._btn, "جارى التفعيل…")
        self._app.worker.run(lambda: self._app.backend.activate(code=code),
                             lambda _lic: self._app.connect(),
                             lambda e: self.failed(self._btn, "✅ تفعيل", e))


# ============================================================
#                       إنشاء الشركة
# ============================================================

class CreateCompanyScreen(CardScreen):
    def __init__(self, app):
        super().__init__("🏢 بيانات الشركة", "مرة واحدة بس: اسم الشركة وحساب المدير")
        self._app = app
        self._company = self.field("اسم الشركة *")
        self._phone = self.field("تليفون الشركة (بيتطبع على الإيصالات)")
        self._logo = ui.FilePicker("🖼️ لوجو الشركة (اختيارى)", "صور (*.png *.jpg *.jpeg)", multiple=False)
        self.card.addWidget(self._logo)
        self.card.addWidget(ui.muted("اللوجو بيظهر جوا البرنامج جنب اسم الشركة وعلى الإيصالات. "
                                     "تقدر تغيّره بعدين من الإعدادات."))
        self.card.addWidget(ui.section_title("👤 حساب المدير"))
        self._name = self.field("اسمك *")
        self._user = self.field("اسم المستخدم (اللى هتدخل بيه) *", text="admin")
        self._pass = self.field("الباسورد (4 حروف أو أرقام على الأقل) *", password=True)
        self._pass2 = self.field("اكتب الباسورد تانى *", password=True)
        self._pass2.returnPressed.connect(self._create)
        self._btn = ui.button("✨ إنشاء الشركة", "green", self._create)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)

    def _create(self):
        if not self._btn.isEnabled():
            return
        if self._pass.text() != self._pass2.text():
            self.failed(self._btn, "✨ إنشاء الشركة", "الباسورد والتأكيد مش زى بعض")
            return
        args = dict(company_name=self._company.text(), full_name=self._name.text(), username=self._user.text(),
                    password=self._pass.text(), phone=self._phone.text(),
                    logo_path=(self._logo.get() or [None])[0])
        self.busy(self._btn, "جارى الإنشاء…")
        self._app.worker.run(lambda: self._app.backend.create_company(**args), self._app.logged_in,
                             lambda e: self.failed(self._btn, "✨ إنشاء الشركة", e))


# ============================================================
#                       الدخول
# ============================================================

class LoginScreen(CardScreen):
    def __init__(self, app, status, logo=None, message=None):
        super().__init__(status.get("company") or APP_NAME, "سجّل دخولك للمتابعة", logo=logo)
        self._app = app
        self._user = self.field("اسم المستخدم")
        self._password = self.field("الباسورد", password=True)
        self._password.returnPressed.connect(self._login)
        self._user.returnPressed.connect(self._password.setFocus)
        self._btn = ui.button("🔓 دخول", "green", self._login)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        lic = status.get("license") or {}
        if lic.get("state") in ("expired", "tamper", "expiring"):
            warn = ui.label(("⚠️ " if lic["state"] == "expiring" else "⛔ ") + lic.get("message", ""), wrap=True)
            warn.setStyleSheet(f"color: {ui.AMBER if lic['state'] == 'expiring' else ui.RED}; font-weight: bold;")
            warn.setAlignment(Qt.AlignCenter)
            self.card.addWidget(warn)
        if status.get("version") and status["version"] != APP_VERSION:
            v = ui.label(f"⚠️ إصدار البرنامج هنا ({APP_VERSION}) مختلف عن السيرفر ({status['version']}) — "
                         "ثبّت نفس الإصدار على كل الأجهزة", wrap=True)
            v.setStyleSheet(f"color: {ui.AMBER};")
            self.card.addWidget(v)
        if local_config.load().get("mode") == "client":
            self.card.addWidget(ui.button("⚙️ إعدادات الاتصال بالسيرفر", "light", app.show_connect))
        self.version_line()
        if message:
            self.note(message, ui.AMBER)
        self._user.setFocus()

    def _login(self):
        if not self._btn.isEnabled():
            return
        username, password = self._user.text(), self._password.text()
        self.busy(self._btn, "جارى الدخول…")
        self._app.worker.run(lambda: self._app.backend.login(username, password), self._app.logged_in,
                             lambda e: self.failed(self._btn, "🔓 دخول", e))


def decode_logo(data):
    try:
        return base64.b64decode(data) if data else None
    except (ValueError, TypeError):
        return None
