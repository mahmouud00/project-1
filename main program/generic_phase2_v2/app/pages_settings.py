"""
pages_settings.py
-----------------
صفحة الإعدادات (للمدير بس):
  - بيانات الشركة + كود الانضمام
  - الموظفين: تفعيل وصلاحيات
  - القوائم: الفروع، طرق الدفع، الأنواع، الإدارات
"""

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QLineEdit, QVBoxLayout

import qt_widgets as ui
from qt_widgets import ScrollPage, DataTable, Box, fill_combo, combo_value, GREEN, RED, AMBER, NAVY, PURPLE
from models import PAGES, CHANNEL_LABELS, iso_to_display, parse_user_date, is_active_row

YES, NO = "✔", ""

# كل قايمة: (الجدول، العنوان، الأعمدة، حقول الفورم)
LISTS = {
    "branches": ("🏬 الفروع", [("الاسم", "wide"), ("رئيسى", "text")],
                 lambda r: [r["name"], YES if r.get("is_main") else NO],
                 lambda r: [{"key": "name", "label": "اسم الفرع *", "default": r.get("name", "")}]),
    "payment_methods": ("💳 طرق الدفع", [("الاسم", "wide"), ("القناة", "text"), ("شغّالة", "text")],
                        lambda r: [r["name"], CHANNEL_LABELS.get(r["channel"]), YES if r.get("is_active") else NO],
                        lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                                   {"key": "channel", "label": "القناة", "type": "combo",
                                    "options": [(v, k) for k, v in CHANNEL_LABELS.items()],
                                    "default": r.get("channel", "cash")},
                                   {"key": "is_active", "label": "شغّالة", "type": "check",
                                    "default": r.get("is_active", True)}]),
    "product_types": ("🪟 أنواع الشغل", [("الاسم", "wide"), ("تعاقدات", "text"), ("صيانة", "text"),
                                        ("شغّال", "text")],
                      lambda r: [r["name"], YES if r.get("for_contracts") else NO,
                                 YES if r.get("for_maintenance") else NO, YES if r.get("is_active") else NO],
                      lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                                 {"key": "for_contracts", "label": "يظهر فى التعاقدات", "type": "check",
                                  "default": r.get("for_contracts", True)},
                                 {"key": "for_maintenance", "label": "يظهر فى الصيانة", "type": "check",
                                  "default": r.get("for_maintenance", True)},
                                 {"key": "is_active", "label": "شغّال", "type": "check",
                                  "default": r.get("is_active", True)}]),
    "departments": ("🏢 الإدارات", [("الاسم", "wide"), ("وارده مبيعات", "text"), ("منصرفه تكلفة", "text"),
                                   ("شغّالة", "text")],
                    lambda r: [r["name"], YES if r.get("is_sales") else NO, YES if r.get("in_profit") else NO,
                               YES if r.get("is_active") else NO],
                    lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                               {"key": "is_sales", "label": "الوارد بيها = مبيعات (فى الربح)", "type": "check",
                                "default": r.get("is_sales", False)},
                               {"key": "in_profit", "label": "المنصرف بيها = تكلفة (فى الربح)", "type": "check",
                                "default": r.get("in_profit", False)},
                               {"key": "is_active", "label": "شغّالة", "type": "check",
                                "default": r.get("is_active", True)}]),
}


class SettingsPage(ScrollPage):
    PAGE = "settings"
    TITLE = "⚙️ الإعدادات"

    def load(self):
        return self.backend.profiles(), self.backend.load_lookups()

    def render(self, data):
        profiles, lookups = data
        self.app.set_lookups(lookups)
        company = self.me.get_company()
        page = self.new_content()

        # ---------- الشركة ----------
        box = Box("🏢 بيانات الشركة", NAVY)
        box.body.addLayout(ui.kv_row("الاسم", company.get("name", "")))
        box.body.addLayout(ui.kv_row("حساب الربح من",
                                     iso_to_display(company.get("profit_start_date")) or "من الأول"))
        box.body.addLayout(ui.kv_row("الفاتورة إجبارية مع التعاقد",
                                     "أيوه" if company.get("require_invoice", True) else "لأ"))
        logo_buttons = [ui.button("🖼️ رفع / تغيير اللوجو", "purple", self._upload_logo)]
        if company.get("logo_path"):
            logo_buttons.append(ui.button("إزالة اللوجو", "light", self._remove_logo))
        box.body.addLayout(ui.hbox(ui.label("لوجو الشركة:"),
                                   ui.label("✔ موجود" if company.get("logo_path") else "مفيش لوجو", "muted"),
                                   None, *logo_buttons))
        code = ui.label(company.get("join_code", ""), "pageTitle")
        code.setStyleSheet(f"color: {PURPLE}; letter-spacing: 3px;")
        box.body.addLayout(ui.hbox(ui.label("كود انضمام الموظفين:"), code, None,
                                   ui.button("✏️ تعديل البيانات", "blue", self._edit_company),
                                   ui.button("🔄 كود جديد", "amber", self._new_code)))
        box.body.addWidget(ui.muted("الموظف بيعمل حساب من البرنامج، ويختار «انضم لشركتك» ويكتب الكود ده. "
                                    "بعدين بيظهر هنا تحت ومستنى تفعّله."))
        page.addWidget(box)

        # ---------- الموظفين ----------
        self._profiles = {p["user_id"]: p for p in profiles}
        pending = sum(1 for p in profiles if not p["is_active"])
        page.addLayout(ui.hbox(ui.section_title(f"👥 مستخدمين البرنامج ({len(profiles)})"),
                               ui.label(f"⏳ {pending} مستنيين التفعيل" if pending else "", "busy"), None,
                               ui.button("🔐 الصلاحيات", "blue", self._edit_member),
                               ui.button("⏸️ إيقاف / ▶️ تفعيل", "amber", self._toggle_member),
                               ui.button("🗑️ حذف من الشركة", "red", self._remove_member)))
        page.addWidget(ui.muted("«إيقاف» = الموظف مش هيقدر يدخل، وصلاحياته محفوظة لو رجّعته. "
                                "«حذف» = بيتشال من الشركة خالص، ولو رجع لازم ينضم بالكود من جديد."))
        self._members = DataTable([("الاسم", "text"), ("الإيميل", "text"), ("الوظيفة", "text"),
                                   ("الحالة", "text"), ("الصفحات", "wide")], min_height=200)
        self._members.set_rows([{
            "key": p["user_id"],
            "color": AMBER if not p["is_active"] else (GREEN if p["is_admin"] else None),
            "values": [p["full_name"], p.get("email"), p.get("role_title"),
                       "مدير" if p["is_admin"] else ("شغّال" if p["is_active"] else "⏳ مستنى التفعيل"),
                       "كل حاجة" if p["is_admin"] else "، ".join(
                           title for key, title in PAGES if key in (p.get("pages") or []) + (p.get("edit_pages") or []))],
        } for p in profiles])
        self._members.cellDoubleClicked.connect(lambda r, c: self._edit_member())
        page.addWidget(self._members)

        # ---------- القوائم ----------
        self._tables = {}
        for table, (title, columns, values, _fields) in LISTS.items():
            rows = lookups.get(table, [])
            page.addLayout(ui.hbox(ui.section_title(title), None,
                                   ui.button("➕ إضافة", "green", lambda checked=False, t=table: self._edit_row(t)),
                                   ui.button("✏️ تعديل", "blue",
                                             lambda checked=False, t=table: self._edit_row(t, selected=True))))
            t = DataTable(columns, min_height=160)
            t.set_rows([{"key": r["id"], "color": None if is_active_row(r) else ui.GRAY,
                         "values": values(r)} for r in rows])
            self._tables[table] = (t, {r["id"]: r for r in rows})
            page.addWidget(t)
        page.addStretch(1)

    # ---------- أفعال ----------

    def _edit_company(self):
        c = self.me.get_company()
        self.form("✏️ بيانات الشركة", [
            {"key": "name", "label": "اسم الشركة *", "default": c.get("name", "")},
            {"key": "start", "label": "حساب الربح من (يوم/شهر/سنة) — فاضى = من الأول",
             "default": iso_to_display(c.get("profit_start_date"))},
            {"key": "invoice", "label": "الفاتورة PDF إجبارية مع كل تعاقد", "type": "check",
             "default": c.get("require_invoice", True)},
        ], lambda v: self.backend.update_company(v["name"], parse_user_date(v["start"]), v["invoice"]),
            then=self.app.refresh_company_header)

    def _new_code(self):
        if ui.ask_yes_no(self, "الكود القديم هيبطل يشتغل، والموظفين الجداد هيحتاجوا الكود الجديد.\nمتأكد؟"):
            self.run_action(self.backend.regenerate_join_code)

    def _edit_member(self):
        p = self.selected(self._members, self._profiles, "اختار موظف من الجدول الأول")
        if p:
            PermissionsDialog(self, self.app, p)

    def _member_other_than_me(self):
        p = self.selected(self._members, self._profiles, "اختار موظف من الجدول الأول")
        if p and p["user_id"] == self.me.get_user_id():
            ui.show_info(self, "ده حسابك إنت — مينفعش توقفه أو تشيله", "تنبيه")
            return None
        return p

    def _toggle_member(self):
        p = self._member_other_than_me()
        if not p:
            return
        if p["is_active"]:
            if ui.ask_yes_no(self, f"إيقاف {p['full_name']}؟ مش هيقدر يدخل البرنامج لحد ما ترجّعه."):
                self.run_action(lambda: self.backend.set_member_active(p, False))
        else:
            self.run_action(lambda: self.backend.set_member_active(p, True),
                            f"✅ {p['full_name']} اتفعّل. لو لسه ملوش صفحات، حددها من «الصلاحيات».")

    def _remove_member(self):
        p = self._member_other_than_me()
        if p and ui.ask_yes_no(self, f"حذف {p['full_name']} من الشركة خالص؟\n"
                                     "لو رجع بعد كده، لازم يعمل «انضم لشركتك» بالكود من جديد."):
            self.run_action(lambda: self.backend.remove_member(p["user_id"]))

    def _upload_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختار لوجو الشركة", "", "صور (*.png *.jpg *.jpeg)")
        if not path:
            return

        def done(data):
            self.app.refresh_company_header(data)
            self.app.after_change()
            ui.show_info(self, "✅ اللوجو اتغيّر")
        self.app.worker.run(lambda: self.backend.upload_logo(path), done, lambda e: ui.show_error(self, e))

    def _remove_logo(self):
        if ui.ask_yes_no(self, "إزالة لوجو الشركة؟"):
            def done(_):
                self.app.refresh_company_header()
                self.app.after_change()
            self.app.worker.run(self.backend.remove_logo, done, lambda e: ui.show_error(self, e))

    def _edit_row(self, table, selected=False):
        title, _cols, _values, fields = LISTS[table]
        row = {}
        if selected:
            t, items = self._tables[table]
            row = self.selected(t, items, "اختار صف من الجدول الأول")
            if not row:
                return
        self.form(("✏️ تعديل" if row else "➕ إضافة") + " — " + title, fields(row),
                  lambda v: self.backend.save_setting(table, v, row.get("id")))


class PermissionsDialog(QDialog):
    """صلاحيات موظف: لكل صفحة (يشوف / يضيف ويعدّل / يمسح) + تفعيل + مدير."""

    def __init__(self, parent, app, profile):
        super().__init__(parent)
        self._app = app
        self._p = profile
        self.setWindowTitle(f"صلاحيات {profile['full_name']}")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(f"🔐 {profile['full_name']}  —  {profile.get('email') or ''}", "dialogTitle"))

        self._role = QLineEdit(profile.get("role_title") or "")
        self._role.setPlaceholderText("الوظيفة (مثال: محاسب، مصنع، سيلز)")
        lay.addWidget(self._role)
        self._active = QCheckBox("الحساب شغّال (يقدر يدخل البرنامج)")
        # موظف جديد مستنى (لسه ملوش صلاحيات) ← متعلّم جاهز للتفعيل. موظف موقوف ← يفضل موقوف.
        is_new = not (profile.get("pages") or profile.get("edit_pages") or profile["is_admin"])
        self._active.setChecked(bool(profile["is_active"]) or is_new)
        self._admin = QCheckBox("مدير (يشوف ويعمل كل حاجة + الإعدادات)")
        self._admin.setChecked(bool(profile["is_admin"]))
        lay.addWidget(self._active)
        lay.addWidget(self._admin)

        grid = QGridLayout()
        for col, head in enumerate(("الصفحة", "يشوف", "يضيف ويعدّل", "يمسح")):
            grid.addWidget(ui.label(head, "boxTitle"), 0, col)
        self._checks = {}
        sets = {"view": set(profile.get("pages") or []), "edit": set(profile.get("edit_pages") or []),
                "delete": set(profile.get("delete_pages") or [])}
        for row, (key, title) in enumerate(PAGES, start=1):
            grid.addWidget(ui.label(title), row, 0)
            for col, action in enumerate(("view", "edit", "delete"), start=1):
                cb = QCheckBox()
                cb.setChecked(key in sets[action])
                grid.addWidget(cb, row, col)
                self._checks[(key, action)] = cb
        lay.addLayout(grid)
        lay.addWidget(ui.muted("«يضيف ويعدّل» بتشمل «يشوف». المدير مش محتاج يتعلّم على أى صفحة. "
                               "شيل علامة «الحساب شغّال» عشان توقف الموظف."))

        self._btn = ui.button("💾 حفظ الصلاحيات", "green", self._save)
        lay.addWidget(self._btn)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addWidget(self._msg)
        self.setModal(True)
        self.show()

    def _save(self):
        pick = lambda action: [k for (k, a), cb in self._checks.items() if a == action and cb.isChecked()]
        args = (self._p["user_id"], self._active.isChecked(), self._admin.isChecked(),
                pick("view"), pick("edit"), pick("delete"), self._role.text().strip() or None)
        self._btn.setEnabled(False)

        def ok(_):
            self.accept()
            self._app.after_change()

        def fail(e):
            self._btn.setEnabled(True)
            self._msg.setText(f"❌ {e}")

        self._app.worker.run(lambda: self._app.backend.set_member(*args), ok, fail)
