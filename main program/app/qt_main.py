"""
qt_main.py
----------
- AppController: بيقرر يعرض أنهى شاشة (دخول، حساب جديد، إنشاء/انضمام، انتظار، البرنامج).
- MainPage: البرنامج نفسه - قايمة جانبية + هيدر + الصفحات المسموحة للمستخدم.
  الصفحات بتعتبره "app": منه بتاخد me و backend و worker والقوائم المشتركة.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QMainWindow,
                               QStackedWidget, QVBoxLayout, QWidget)

import qt_widgets as ui
import qt_theme
from app_info import APP_NAME, APP_VERSION, resource_path
from models import PAGES, is_active_row
from qt_auth import LoginScreen, SignUpScreen, OnboardingScreen, PendingScreen, logo_label
from qt_worker import QtWorker
from pages_money import DashboardPage, TreasuryPage, SuppliersPage, ChequesPage
from pages_jobs import SalesPage, InspectionsPage, StagePage, AccountsPage, StaffPage
from pages_settings import SettingsPage


def make_page(key, app):
    return {
        "dashboard": lambda: DashboardPage(app),
        "treasury": lambda: TreasuryPage(app),
        "sales": lambda: SalesPage(app),
        "inspections": lambda: InspectionsPage(app),
        "factory": lambda: StagePage(app, "manufacturing", "factory"),
        "install": lambda: StagePage(app, "installing", "install"),
        "accounts": lambda: AccountsPage(app),
        "suppliers": lambda: SuppliersPage(app),
        "cheques": lambda: ChequesPage(app),
        "staff": lambda: StaffPage(app),
    }[key]()


class MainPage(QWidget):
    def __init__(self, controller, lookups):
        super().__init__()
        self._controller = controller
        self.backend = controller.backend
        self.worker = controller.worker
        self.lookups = lookups
        self._lookups_listeners = []
        self._pages = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(235)
        self._side = QVBoxLayout(side)
        self._side.setContentsMargins(12, 14, 12, 12)
        self._side.setSpacing(3)
        self._side.addLayout(ui.hbox(logo_label(34), ui.label(APP_NAME, "sidebarTitle", wrap=True)))
        self._side.addSpacing(10)
        root.addWidget(side)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)
        self._title = ui.label("", "pageTitle")
        self._busy = ui.label("", "busy")
        self._company_logo = ui.label()
        self._company_logo.setFixedHeight(40)
        self._company_name = ui.label("", "companyName")
        hl.addWidget(self._title)
        hl.addSpacing(10)
        hl.addWidget(self._busy)
        hl.addStretch(1)
        hl.addWidget(self._company_name)
        hl.addWidget(self._company_logo)
        cl.addWidget(header)
        self._stack = QStackedWidget()
        cl.addWidget(self._stack, 1)
        root.addWidget(content, 1)

        for key, _title in PAGES:
            if self.me.can_view(key):
                self._add(make_page(key, self))
        if self.me.is_admin():
            self._add(SettingsPage(self))

        self._side.addStretch(1)
        self._side.addWidget(ui.label(f"👤 {self.me.get_full_name()}\n{self.me.get_role_title()}",
                                      "sidebarUser", wrap=True))
        self._theme = QComboBox()
        ui.fill_combo(self._theme, qt_theme.MODES, controller.theme_mode)
        self._theme.currentIndexChanged.connect(lambda _i: controller.set_theme(ui.combo_value(self._theme)))
        self._side.addWidget(self._theme)
        refresh = ui.button("🔄 تحديث", on_click=self.force_refresh)
        logout = ui.button("🚪 خروج", on_click=controller.logout)
        for b in (refresh, logout):
            b.setObjectName("sideAction")
        self._side.addLayout(ui.hbox(refresh, logout, stretch_end=False))

        if not self._pages:
            self._stack.addWidget(ui.label("مفيش صفحات متاحة لحسابك — كلّم المدير", "sectionTitle"))
        self.worker.add_busy_listener(lambda busy: self._busy.setText("⏳ جارى التحميل…" if busy else ""))
        self.refresh_company_header()
        if self._pages:
            self.show_page(0)

    # ---------- اسم ولوجو الشركة فى الهيدر ----------

    def refresh_company_header(self, logo_bytes=None):
        """بيكتب اسم الشركة، وبيجيب اللوجو (لو مش جاى معانا) من السيرفر فى الخلفية."""
        self._company_name.setText(self.me.get_company().get("name", ""))
        if logo_bytes is not None:
            self._show_logo(logo_bytes)
        elif self.me.get_company().get("logo_path"):
            self.worker.run(self.backend.company_logo, self._show_logo, lambda e: None)
        else:
            self._company_logo.clear()

    def _show_logo(self, data):
        pix = QPixmap()
        if data and pix.loadFromData(data):
            self._company_logo.setPixmap(pix.scaledToHeight(40, Qt.SmoothTransformation))
        else:
            self._company_logo.clear()

    # ---------- اللى الصفحات بتحتاجه ----------

    @property
    def me(self):
        return self.backend.me

    def options(self, table, **flags):
        """[(الاسم، id)] من القوائم - الشغّال بس، ولو فيه flags بيفلتر بيها (مثلاً kind='sales')."""
        out = []
        for r in self.lookups.get(table, []):
            if not is_active_row(r):
                continue
            if any(r.get(k) != v for k, v in flags.items()):
                continue
            out.append((r["name"], r["id"]))
        return out

    def branch_options(self, with_all=False):
        opts = [(b["name"], b["id"]) for b in self.lookups.get("branches", [])]
        return ([("كل الفروع", None)] if with_all else []) + opts

    def multi_branch(self) -> bool:
        return len(self.lookups.get("branches", [])) > 1

    def add_lookups_listener(self, callback):
        self._lookups_listeners.append(callback)

    def set_lookups(self, lookups):
        self.lookups = lookups
        for callback in self._lookups_listeners:
            try:
                callback()
            except RuntimeError:
                pass

    def reload_lookups(self):
        self.worker.run(self.backend.load_lookups, self.set_lookups, lambda e: None)

    # ---------- التنقل والتحديث ----------

    def _add(self, page):
        index = len(self._pages)
        self._pages.append(page)
        self._stack.addWidget(page)
        btn = ui.button(page.TITLE, on_click=lambda: self.show_page(index))
        btn.setCheckable(True)
        self._group.addButton(btn, index)
        self._side.addWidget(btn)

    def page_titles(self):
        return [p.TITLE for p in self._pages]

    def show_page(self, index):
        page = self._pages[index]
        self._stack.setCurrentWidget(page)
        self._group.button(index).setChecked(True)
        self._title.setText(page.TITLE)
        if page.is_stale():
            page.refresh()

    def current_page(self):
        return self._stack.currentWidget()

    def after_change(self):
        for page in self._pages:
            page.mark_stale()
        current = self.current_page()
        if current in self._pages:
            current.refresh()

    def force_refresh(self):
        self.reload_lookups()
        self.after_change()


class AppController:
    """بيمسك الشباك الرئيسى ويقرر يعرض فيه أنهى شاشة."""

    def __init__(self, backend):
        self.qt = QApplication.instance() or QApplication(sys.argv)
        self.qt.setLayoutDirection(Qt.RightToLeft)
        self.theme_mode = qt_theme.saved_mode()
        qt_theme.apply_theme(self.qt, self.theme_mode)
        try:   # لو الوضع "زى الجهاز" والمستخدم غيّر ثيم ويندوز والبرنامج مفتوح
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        except AttributeError:
            pass
        icon = QIcon(resource_path("assets", "app.ico"))
        self.qt.setWindowIcon(icon)
        self.window = QMainWindow()
        self.window.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.window.setWindowIcon(icon)
        self.window.resize(1366, 820)
        self.backend = backend
        self.worker = QtWorker(lambda e: ui.show_error(self.window, e))

    def set_theme(self, mode):
        self.theme_mode = mode
        qt_theme.save_mode(mode)
        qt_theme.apply_theme(self.qt, mode)

    def _system_theme_changed(self, *_):
        if self.theme_mode == "system":
            qt_theme.apply_theme(self.qt, "system")

    def _set(self, make_widget):
        """بيعرض شاشة جديدة. make_widget = دالة بتعمل الشاشة.
        الترتيب مهم: بنمسح متابعين "جارى التحميل" القدام الأول، وبعدين نعمل الشاشة الجديدة
        (اللى ممكن تسجّل نفسها كمتابع). لو عملناها الأول، كان تسجيلها بيتمسح والكلمة بتعلّق."""
        self.worker.clear_busy_listeners()
        self.window.setCentralWidget(make_widget())

    def show_login(self):
        self._set(lambda: LoginScreen(self))

    def show_signup(self):
        self._set(lambda: SignUpScreen(self))

    def route(self, me):
        """بعد الدخول/إنشاء شركة/انضمام: يروح للشاشة المناسبة."""
        if me is None or not me.has_company():
            self._set(lambda: OnboardingScreen(self))
        elif not me.is_active():
            self._set(lambda: PendingScreen(self))
        else:
            def waiting():
                lbl = ui.label("⏳ جارى تحميل بيانات الشركة…", "sectionTitle")
                lbl.setAlignment(Qt.AlignCenter)
                return lbl
            self._set(waiting)
            self.worker.run(self.backend.load_lookups,
                            lambda lookups: self._set(lambda: MainPage(self, lookups)),
                            lambda e: (ui.show_error(self.window, e), self.show_login()))

    def logout(self):
        self.worker.run(self.backend.sign_out, lambda _: self.show_login(), lambda _e: self.show_login())

    def run(self) -> int:
        self.window.show()
        self.show_login()
        return self.qt.exec()
