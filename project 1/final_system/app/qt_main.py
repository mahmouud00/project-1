"""
qt_main.py
----------
- AppController: بيقرر يعرض أنهى شاشة (أول تشغيل، اتصال، تفعيل، إنشاء شركة، دخول، البرنامج)،
  وعلى جهاز السيرفر بيشغّل السيرفر نفسه + أيقونة جنب الساعة (السيرفر يفضل شغّال لو قفلت الشباك).
- MainPage: البرنامج نفسه - قايمة جانبية + هيدر + الصفحات المسموحة للمستخدم.
  الصفحات بتعتبره "app": منه بتاخد me و backend و worker والقوائم المشتركة.
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QMainWindow, QMenu,
                               QScrollArea, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

import local_config
import qt_theme
import qt_widgets as ui
from app_info import APP_NAME, APP_SUBTITLE, APP_VERSION, resource_path, server_data_dir
from backend import Backend, ping
from models import PAGES, AppError, is_active_row
from qt_auth import (ActivationScreen, ConnectionErrorScreen, ConnectScreen, CreateCompanyScreen, LoginScreen,
                     SetupScreen, decode_logo, logo_label)
from qt_worker import QtWorker
from pages_money import DashboardPage, TreasuryPage, SuppliersPage, ChequesPage
from pages_orders import CustomersPage, OrdersPage, StagePage, AccountsPage, SalesPage
from pages_stock import InventoryPage
from pages_workers import WorkersPage
from pages_settings import SettingsPage, renew_license_dialog


def make_page(key, app):
    return {
        "dashboard": lambda: DashboardPage(app),
        "customers": lambda: CustomersPage(app),
        "orders": lambda: OrdersPage(app),
        "cutting": lambda: StagePage(app, "cutting"),
        "sewing": lambda: StagePage(app, "sewing"),
        "fitting": lambda: StagePage(app, "fitting"),
        "finishing": lambda: StagePage(app, "finishing"),
        "delivery": lambda: StagePage(app, "delivery"),
        "accounts": lambda: AccountsPage(app),
        "sales": lambda: SalesPage(app),
        "treasury": lambda: TreasuryPage(app),
        "inventory": lambda: InventoryPage(app),
        "suppliers": lambda: SuppliersPage(app),
        "cheques": lambda: ChequesPage(app),
        "workers": lambda: WorkersPage(app),
    }[key]()


class MainPage(QWidget):
    def __init__(self, controller, lookups):
        super().__init__()
        self.controller = controller
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
        side.setFixedWidth(230)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(10, 12, 10, 10)
        side_lay.setSpacing(3)
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(ui.label(APP_NAME, "sidebarTitle"))
        title.addWidget(ui.label(APP_SUBTITLE, "sidebarSub"))
        side_lay.addLayout(ui.hbox(logo_label(34), title))
        side_lay.addSpacing(8)
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav = QWidget()
        self._side = QVBoxLayout(nav)
        self._side.setContentsMargins(0, 0, 0, 0)
        self._side.setSpacing(2)
        nav_scroll.setWidget(nav)
        side_lay.addWidget(nav_scroll, 1)
        root.addWidget(side)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 10, 20, 10)
        self._title = ui.label("", "pageTitle")
        self._busy = ui.label("", "busy")
        self._company_logo = ui.label()
        self._company_logo.setFixedHeight(44)
        self._company_name = ui.label("", "companyName")
        hl.addWidget(self._title)
        hl.addSpacing(10)
        hl.addWidget(self._busy)
        hl.addStretch(1)
        hl.addWidget(self._company_name)
        hl.addWidget(self._company_logo)
        cl.addWidget(header)
        self._banner = ui.Banner()
        cl.addWidget(self._banner)
        self._stack = QStackedWidget()
        cl.addWidget(self._stack, 1)
        root.addWidget(content, 1)

        for key, _title in PAGES:
            if self.me.can_view(key):
                self._add(make_page(key, self))
        if self.me.is_admin():
            self._add(SettingsPage(self))
        self._side.addStretch(1)

        side_lay.addWidget(ui.label(f"👤 {self.me.get_full_name()}\n{self.me.get_role_title()}",
                                    "sidebarUser", wrap=True))
        self._theme = QComboBox()
        ui.fill_combo(self._theme, qt_theme.MODES, controller.theme_mode)
        self._theme.currentIndexChanged.connect(lambda _i: controller.set_theme(ui.combo_value(self._theme)))
        side_lay.addWidget(self._theme)
        refresh = ui.button("🔄 تحديث", on_click=self.force_refresh)
        password = ui.button("🔑", on_click=self._change_password, tooltip="تغيير الباسورد بتاعى")
        logout = ui.button("🚪 خروج", on_click=controller.logout)
        for b in (refresh, password, logout):
            b.setObjectName("sideAction")
        side_lay.addLayout(ui.hbox(refresh, password, logout, stretch_end=False))

        if not self._pages:
            self._stack.addWidget(ui.label("مفيش صفحات متاحة لحسابك — كلّم المدير", "sectionTitle"))
        self.worker.add_busy_listener(lambda busy: self._busy.setText("⏳ جارى التحميل…" if busy else ""))
        self.refresh_company_header()
        self.update_banner()
        if self._pages:
            self.show_page(0)
        self._me_timer = QTimer(self)
        self._me_timer.timeout.connect(self._reload_me)
        self._me_timer.start(10 * 60 * 1000)

    # ---------- اسم ولوجو الشركة فى الهيدر ----------

    def refresh_company_header(self, logo_bytes=None):
        """بيكتب اسم الشركة، وبيجيب اللوجو (لو مش جاى معانا) من السيرفر فى الخلفية."""
        self._company_name.setText(self.me.get_company().get("name", ""))
        if logo_bytes is not None:
            self._show_logo(logo_bytes)
        elif self.me.get_company().get("has_logo"):
            self.worker.run(self.backend.company_logo, self._show_logo, lambda e: None)
        else:
            self._show_logo(None)

    def _show_logo(self, data):
        self.controller.logo_bytes = data
        pix = QPixmap()
        if data and pix.loadFromData(data):
            self._company_logo.setPixmap(pix.scaledToHeight(44, Qt.SmoothTransformation))
        else:
            self._company_logo.clear()

    @property
    def logo_bytes(self):
        return self.controller.logo_bytes

    # ---------- تنبيه الترخيص ----------

    def update_banner(self):
        lic = self.me.license()
        state = lic.get("state")
        while self._banner.actions.count():
            w = self._banner.actions.takeAt(0).widget()
            if w:
                w.deleteLater()
        if state in ("expired", "tamper", "invalid", "none"):
            self._banner.show_message("⛔ " + (lic.get("message") or "البرنامج للعرض بس"), ui.RED)
        elif state == "expiring":
            self._banner.show_message("⚠️ " + lic.get("message", ""), ui.AMBER)
        else:
            self._banner.hide()
            return
        if self.me.is_admin():
            self._banner.actions.addWidget(ui.button("🔑 إدخال كود التجديد", "light",
                                                     lambda: renew_license_dialog(self)))

    def _reload_me(self):
        def done(me):
            self.update_banner()
            self.refresh_company_header()
        self.worker.run(self.backend.load_me, done, lambda e: None)

    # ---------- اللى الصفحات بتحتاجه ----------

    @property
    def me(self):
        return self.backend.me

    def options(self, table, active_only=True, **flags):
        """[(الاسم، id)] من القوائم - الشغّال بس، ولو فيه flags بيفلتر بيها (مثلاً kind='worker')."""
        out = []
        for r in self.lookups.get(table, []):
            if active_only and not is_active_row(r):
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
        self.worker.run(self.backend.lookups, self.set_lookups, lambda e: None)

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

    def show_page_key(self, key):
        for i, page in enumerate(self._pages):
            if getattr(page, "PAGE", None) == key:
                self.show_page(i)
                return page
        return None

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
        self._reload_me()
        self.after_change()

    def _change_password(self):
        ui.FormDialog(self, self, "🔑 تغيير الباسورد بتاعى", [
            {"key": "old", "label": "الباسورد الحالى", "type": "password"},
            {"key": "new", "label": "الباسورد الجديد", "type": "password"},
            {"key": "new2", "label": "الباسورد الجديد تانى", "type": "password"},
        ], self._do_change_password, on_done=lambda _r: ui.show_info(self, "✅ الباسورد اتغيّر"))

    def _do_change_password(self, v):
        if v["new"] != v["new2"]:
            raise AppError("الباسورد الجديد والتأكيد مش زى بعض")
        return self.backend.change_my_password(old_password=v["old"], new_password=v["new"])


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller

    def closeEvent(self, event):
        self._controller.on_close(event)


class AppController:
    """بيمسك الشباك الرئيسى ويقرر يعرض فيه أنهى شاشة، وبيشغّل السيرفر على جهاز السيرفر."""

    def __init__(self, tray_only=False):
        self.qt = QApplication.instance() or QApplication(sys.argv)
        self.qt.setLayoutDirection(Qt.RightToLeft)
        self.tray_only = tray_only
        self.theme_mode = qt_theme.saved_mode()
        qt_theme.apply_theme(self.qt, self.theme_mode)
        try:   # لو الوضع "زى الجهاز" والمستخدم غيّر ثيم ويندوز والبرنامج مفتوح
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        except AttributeError:
            pass
        self.icon = QIcon(resource_path("assets", "app.ico"))
        self.qt.setWindowIcon(self.icon)
        self.window = MainWindow(self)
        self.window.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.window.setWindowIcon(self.icon)
        self.window.resize(1366, 820)
        self.backend = None
        self.server = None             # السيرفر لو شغّال جوه البرنامج ده
        self.tray = None
        self.logo_bytes = None
        self.status = None
        self._started = False
        self.worker = QtWorker(lambda e: ui.show_error(self.window, e))
        self.worker.on_session_expired = self.session_expired

    # ---------- الشكل ----------

    def set_theme(self, mode):
        self.theme_mode = mode
        qt_theme.save_mode(mode)
        qt_theme.apply_theme(self.qt, mode)

    def _system_theme_changed(self, *_):
        if self.theme_mode == "system":
            qt_theme.apply_theme(self.qt, "system")

    def _set(self, widget):
        self.worker.clear_busy_listeners()
        self.window.setCentralWidget(widget)

    def _waiting(self, text):
        w = ui.label(text, "sectionTitle")
        w.setAlignment(Qt.AlignCenter)
        self._set(w)

    # ---------- أول تشغيل والاتصال ----------

    def mode(self):
        return local_config.load().get("mode")

    def show_setup(self):
        self._set(SetupScreen(self))

    def show_connect(self, message=None):
        self._set(ConnectScreen(self, message))

    def reset_mode(self):
        local_config.reset()
        self.show_setup()

    def choose_mode(self, mode, host=None, port=None):
        values = {"mode": mode}
        if mode == "client":
            values.update(host=host, port=port)
        local_config.update(**values)
        self.connect()

    def connect(self):
        self._started = True
        cfg = local_config.load()
        if cfg.get("mode") == "server":
            try:
                host, port = "127.0.0.1", self.start_server()
            except Exception as e:  # noqa: BLE001
                self._set(ConnectionErrorScreen(self, f"مش قادر أشغّل السيرفر على الجهاز ده:\n{e}"))
                return
        elif cfg.get("mode") == "client":
            host, port = cfg.get("host"), int(cfg.get("port") or local_config.DEFAULT_PORT)
        else:
            self.show_setup()
            return
        self.backend = Backend(host, port)
        self._waiting("⏳ جارى الاتصال بالسيرفر…")
        self.worker.run(self._fetch_status, self.route_status,
                        lambda e: self._set(ConnectionErrorScreen(self, e)))

    def _fetch_status(self):
        st = self.backend.status()
        logo = None
        if st.get("has_company"):
            try:
                logo = decode_logo(self.backend.public_logo())
            except AppError:
                pass
        return st, logo

    def route_status(self, data, message=None):
        st, logo = data
        self.status = st
        lic = st.get("license") or {}
        if lic.get("state") in ("none", "invalid"):
            self._set(ActivationScreen(self, st))
        elif not st.get("has_company"):
            self._set(CreateCompanyScreen(self))
        else:
            self._set(LoginScreen(self, st, logo, message))

    def logged_in(self, me):
        self._waiting("⏳ جارى تحميل بيانات الشركة…")
        self.worker.run(self.backend.lookups, lambda lookups: self._set(MainPage(self, lookups)),
                        lambda e: (ui.show_error(self.window, e), self.connect()))

    def logout(self):
        self.worker.run(self.backend.sign_out, lambda _: self.connect(), lambda _e: self.connect())

    def session_expired(self, error):
        if self.backend:
            self.backend.token = None
        self.worker.run(self._fetch_status, lambda data: self.route_status(data, f"⚠️ {error}"),
                        lambda e: self._set(ConnectionErrorScreen(self, e)))

    # ---------- السيرفر (على جهاز السيرفر بس) ----------

    def start_server(self) -> int:
        if self.server:
            return self.server.port
        from server.api import ApiServer
        from server.service import Service
        cfg = local_config.load()
        port = int(cfg.get("port") or local_config.DEFAULT_PORT)
        if ping("127.0.0.1", port, 1.5):
            return port           # السيرفر شغّال بالفعل (البرنامج مفتوح جنب الساعة)
        service = Service(server_data_dir(), APP_VERSION)
        last_error = None
        for p in [port] + [local_config.DEFAULT_PORT + i for i in range(1, 10)]:
            api = ApiServer(service, port=p)
            try:
                api.start()
            except OSError as e:
                last_error = e
                continue
            if p != port:
                local_config.update(port=p)
            self.server = api
            self.make_tray()
            return p
        raise AppError(f"كل البورتات مشغولة: {last_error}")

    def make_tray(self):
        if self.tray or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.icon, self.qt)
        self.tray.setToolTip(f"{APP_NAME} — السيرفر شغّال")
        menu = QMenu()
        open_action = QAction("📂 فتح البرنامج", menu)
        open_action.triggered.connect(self.show_window)
        quit_action = QAction("⛔ إيقاف السيرفر والخروج", menu)
        quit_action.triggered.connect(self.quit_all)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window()
                                    if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()
        self.qt.setQuitOnLastWindowClosed(False)

    def show_window(self):
        if not self._started:
            self.connect()
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def on_close(self, event):
        if self.server and self.tray:
            event.ignore()
            self.window.hide()
            self.tray.showMessage(APP_NAME, "السيرفر لسه شغّال عشان باقى الأجهزة. "
                                            "عشان توقفه: كليك يمين على الأيقونة جنب الساعة ← إيقاف السيرفر.",
                                  QSystemTrayIcon.Information, 6000)
        else:
            event.accept()
            self.quit_all(confirm=False)

    def quit_all(self, confirm=True):
        if confirm and self.server and not ui.ask_yes_no(
                None, "لو وقفت السيرفر، كل الأجهزة التانية هتفصل لحد ما تفتح البرنامج تانى.\nمتأكد؟"):
            return
        if self.server:
            self.server.stop()
            try:
                self.server.service.close()
            except Exception:  # noqa: BLE001
                pass
            self.server = None
        if self.tray:
            self.tray.hide()
        self.qt.quit()

    def run(self) -> int:
        if self.tray_only and self.mode() == "server":
            try:
                self.start_server()
            except Exception as e:  # noqa: BLE001
                ui.show_error(None, f"مش قادر أشغّل السيرفر:\n{e}")
                return 1
            if not self.tray:            # مفيش مكان للأيقونة ← افتح الشباك عادى
                self.show_window()
        else:
            self.window.show()
            if self.mode():
                self.connect()
            else:
                self.show_setup()
        return self.qt.exec()
