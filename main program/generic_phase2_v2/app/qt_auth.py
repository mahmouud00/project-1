"""
qt_auth.py
----------
الشاشات اللى قبل البرنامج نفسه:
  دخول ← (لو أول مرة) إنشاء حساب
  حساب جديد مالوش شركة ← إنشاء شركة جديدة، أو الانضمام لشركة بكود
  منضم ومستنى ← "طلبك وصل للمدير"
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLineEdit, QVBoxLayout, QWidget

import qt_widgets as ui
from app_info import APP_NAME, APP_VERSION, resource_path


def logo_label(width) -> QWidget:
    lbl = ui.label()
    pix = QPixmap(resource_path("assets", "logo.png"))
    if not pix.isNull():
        lbl.setPixmap(pix.scaledToWidth(width, Qt.SmoothTransformation))
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class CardScreen(QWidget):
    """شاشة فيها كارت فى النص (الكلاس الأب لكل شاشات الدخول)."""

    def __init__(self, title, subtitle=""):
        super().__init__()
        self.setObjectName("loginPage")
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(420)
        self.card = QVBoxLayout(card)
        self.card.setContentsMargins(32, 26, 32, 26)
        self.card.setSpacing(10)
        self.card.addWidget(logo_label(170))
        t = ui.label(title, "pageTitle")
        t.setAlignment(Qt.AlignCenter)
        self.card.addWidget(t)
        if subtitle:
            s = ui.label(subtitle, "muted", wrap=True)
            s.setAlignment(Qt.AlignCenter)
            self.card.addWidget(s)
        outer.addWidget(card, 0, Qt.AlignHCenter)
        outer.addStretch(1)
        self.msg = ui.label("", "errorMsg", wrap=True)
        self.msg.setAlignment(Qt.AlignCenter)

    def field(self, placeholder, password=False) -> QLineEdit:
        w = QLineEdit()
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


class LoginScreen(CardScreen):
    def __init__(self, app):
        super().__init__(APP_NAME, "سجّل دخولك للمتابعة")
        self._app = app
        self._email = self.field("الإيميل")
        self._password = self.field("الباسورد", password=True)
        self._password.returnPressed.connect(self._login)
        self._email.returnPressed.connect(self._password.setFocus)
        self._btn = ui.button("🔓 دخول", "green", self._login)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        self.card.addWidget(ui.button("✨ معندكش حساب؟ اعمل حساب جديد", "light", app.show_signup))
        v = ui.label(f"الإصدار {APP_VERSION}", "muted")
        v.setAlignment(Qt.AlignCenter)
        self.card.addWidget(v)
        self._email.setFocus()

    def _login(self):
        if not self._btn.isEnabled():
            return
        email, password = self._email.text(), self._password.text()
        self.busy(self._btn, "جارى الدخول…")
        self._app.worker.run(lambda: self._app.backend.sign_in(email, password), self._app.route,
                             lambda e: self.failed(self._btn, "🔓 دخول", e))


class SignUpScreen(CardScreen):
    def __init__(self, app):
        super().__init__("حساب جديد", "بعد ما تعمل الحساب هتختار: تعمل شركة جديدة، أو تنضم لشركتك بالكود")
        self._app = app
        self._email = self.field("الإيميل")
        self._password = self.field("الباسورد (6 حروف أو أرقام على الأقل)", password=True)
        self._confirm = self.field("اكتب الباسورد تانى", password=True)
        self._confirm.returnPressed.connect(self._signup)
        self._btn = ui.button("✨ اعمل الحساب", "green", self._signup)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        self.card.addWidget(ui.button("↩️ عندى حساب — رجوع للدخول", "light", app.show_login))

    def _signup(self):
        if not self._btn.isEnabled():
            return
        email, password = self._email.text(), self._password.text()
        if password != self._confirm.text():
            self.failed(self._btn, "✨ اعمل الحساب", "الباسورد والتأكيد مش زى بعض")
            return
        self.busy(self._btn, "جارى إنشاء الحساب…")

        def work():
            if self._app.backend.sign_up(email, password):
                return self._app.backend.load_me()
            return None

        def done(me):
            if me is None:
                self._btn.setEnabled(True)
                self._btn.setText("✨ اعمل الحساب")
                self.msg.setStyleSheet(f"color: {ui.GREEN};")
                self.msg.setText("✅ الحساب اتعمل. افتح إيميلك ودوس على لينك التأكيد، وبعدين ارجع ادخل.")
            else:
                self._app.route(me)

        self._app.worker.run(work, done, lambda e: self.failed(self._btn, "✨ اعمل الحساب", e))


class OnboardingScreen(CardScreen):
    """حساب جديد مالوش شركة: يعمل شركة، أو ينضم لشركة موجودة."""

    def __init__(self, app):
        super().__init__("أهلاً بيك 👋", "حسابك جاهز. اختار واحدة من الاتنين:")
        self._app = app
        self._name = self.field("اسمك")

        self.card.addWidget(ui.section_title("🏢 صاحب شركة؟ اعمل شركتك"))
        self._company = self.field("اسم الشركة")
        self._logo = ui.FilePicker("🖼️ لوجو الشركة (اختيارى)", "صور (*.png *.jpg *.jpeg)", multiple=False)
        self.card.addWidget(self._logo)
        self.card.addWidget(ui.muted("اللوجو بيظهر جوا البرنامج جنب اسم الشركة. تقدر تضيفه أو تغيّره بعدين من الإعدادات."))
        self._create_btn = ui.button("إنشاء الشركة", "green", self._create)
        self.card.addWidget(self._create_btn)

        self.card.addWidget(ui.section_title("👥 موظف؟ انضم لشركتك"))
        self._code = self.field("كود الشركة (خده من المدير)")
        self._join_btn = ui.button("طلب انضمام", "blue", self._join)
        self.card.addWidget(self._join_btn)
        self.card.addWidget(self.msg)
        self.card.addWidget(ui.button("🚪 خروج", "light", app.logout))

    def _create(self):
        name, company, logo = self._name.text(), self._company.text(), self._logo.get()
        self.busy(self._create_btn, "جارى الإنشاء…")

        def work():
            backend = self._app.backend
            me = backend.create_company(company, name)
            logo_error = None
            if logo:
                try:
                    backend.upload_logo(logo[0])
                except Exception as e:  # noqa: BLE001 - الشركة اتعملت خلاص؛ اللوجو يتضاف بعدين
                    logo_error = str(e)
                me = backend.me
            return me, logo_error

        def done(result):
            me, logo_error = result
            self._app.route(me)
            if logo_error:
                ui.show_error(self._app.window, f"الشركة اتعملت، بس اللوجو مترفعش: {logo_error}\n"
                                                "تقدر ترفعه من صفحة الإعدادات.")

        self._app.worker.run(work, done, lambda e: self.failed(self._create_btn, "إنشاء الشركة", e))

    def _join(self):
        name, code = self._name.text(), self._code.text()
        self.busy(self._join_btn, "جارى الإرسال…")
        self._app.worker.run(lambda: self._app.backend.join_company(code, name), self._app.route,
                             lambda e: self.failed(self._join_btn, "طلب انضمام", e))


class PendingScreen(CardScreen):
    def __init__(self, app):
        super().__init__("⏳ طلبك وصل للمدير",
                         "مدير الشركة لازم يفعّل حسابك ويحدد صلاحياتك من صفحة الإعدادات. "
                         "لما يفعّلك دوس «اتأكد تانى».")
        self._app = app
        self._btn = ui.button("🔄 اتأكد تانى", "green", self._check)
        self.card.addWidget(self._btn)
        self.card.addWidget(self.msg)
        self.card.addWidget(ui.button("🚪 خروج", "light", app.logout))

    def _check(self):
        self.busy(self._btn, "جارى التأكد…")

        def done(me):
            if me.is_active():
                self._app.route(me)
            else:
                self._btn.setEnabled(True)
                self._btn.setText("🔄 اتأكد تانى")
                self.msg.setStyleSheet(f"color: {ui.AMBER};")
                self.msg.setText("لسه متفعّلش — كلّم المدير")

        self._app.worker.run(self._app.backend.load_me, done,
                             lambda e: self.failed(self._btn, "🔄 اتأكد تانى", e))
