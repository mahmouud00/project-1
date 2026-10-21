"""
pages_settings.py
-----------------
صفحة الإعدادات (للمدير بس):
  - الترخيص: الحالة + كود الجهاز + إدخال كود التجديد
  - بيانات الشركة واللوجو
  - السيرفر والنسخ الاحتياطى (عنوان السيرفر للموظفين، نسخة، استرجاع، التشغيل مع ويندوز)
  - المستخدمين: إضافة، صلاحيات، باسورد، إيقاف، حذف
  - القوائم: الفروع، طرق الدفع، أنواع الشغل، الإدارات، المقاسات، تفاصيل الموديل، أسعار القطعة
"""

from datetime import datetime

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QLineEdit,
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

import autostart
import local_config
import qt_widgets as ui
from app_info import SELLER_NAME, SELLER_PHONE
from qt_widgets import ScrollPage, DataTable, Box, MeasurementsEditor, amount_text, money, GREEN, RED, AMBER, NAVY, PURPLE, TEAL, BLUE
from models import (PAGES, CHANNEL_LABELS, DEPT_ROLES, STAGE_LABELS, AppError, datetime_display, iso_date,
                    iso_to_display, num, parse_amount)

YES, NO = "✔", ""

# كل قايمة: (الجدول، العنوان، الأعمدة، قيم الصف، حقول الفورم)
LISTS = {
    "branches": ("🏬 الفروع", [("الاسم", "wide"), ("رئيسى", "text")],
                 lambda r: [r["name"], YES if r.get("is_main") else NO],
                 lambda r: [{"key": "name", "label": "اسم الفرع *", "default": r.get("name", "")},
                            {"key": "is_main", "label": "الفرع الرئيسى", "type": "check",
                             "default": r.get("is_main", False)}]),
    "payment_methods": ("💳 طرق الدفع", [("الاسم", "wide"), ("القناة", "text"), ("شغّالة", "text")],
                        lambda r: [r["name"], CHANNEL_LABELS.get(r["channel"]), YES if r.get("is_active") else NO],
                        lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                                   {"key": "channel", "label": "القناة", "type": "combo",
                                    "options": [(v, k) for k, v in CHANNEL_LABELS.items()],
                                    "default": r.get("channel", "cash")},
                                   {"key": "sort", "label": "الترتيب", "default": str(r.get("sort", 0))},
                                   {"key": "is_active", "label": "شغّالة", "type": "check",
                                    "default": r.get("is_active", True)}]),
    "garment_types": ("👔 أنواع الشغل", [("الاسم", "wide"), ("السعر الافتراضى", "money"), ("شغّال", "text")],
                      lambda r: [r["name"], r.get("default_price"), YES if r.get("is_active") else NO],
                      lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                                 {"key": "default_price", "label": "السعر الافتراضى (بيتكتب لوحده فى الطلب)",
                                  "default": amount_text(r.get("default_price", 0))},
                                 {"key": "sort", "label": "الترتيب", "default": str(r.get("sort", 0))},
                                 {"key": "is_active", "label": "شغّال", "type": "check",
                                  "default": r.get("is_active", True)}]),
    "departments": ("🏢 الإدارات", [("الاسم", "wide"), ("وارده مبيعات", "text"), ("منصرفه تكلفة", "text"),
                                   ("بتتستخدم أوتوماتيك فى", "text"), ("شغّالة", "text")],
                    lambda r: [r["name"], YES if r.get("is_sales") else NO, YES if r.get("in_profit") else NO,
                               DEPT_ROLES.get(r.get("role") or "", ""), YES if r.get("is_active") else NO],
                    lambda r: [{"key": "name", "label": "الاسم *", "default": r.get("name", "")},
                               {"key": "is_sales", "label": "الوارد بيها = مبيعات (فى الربح)", "type": "check",
                                "default": r.get("is_sales", False)},
                               {"key": "in_profit", "label": "المنصرف بيها = تكلفة (فى الربح)", "type": "check",
                                "default": r.get("in_profit", False)},
                               {"key": "role", "label": "البرنامج يستخدمها أوتوماتيك فى", "type": "combo",
                                "options": [(v, k) for k, v in DEPT_ROLES.items()], "default": r.get("role", "")},
                               {"key": "is_active", "label": "شغّالة", "type": "check",
                                "default": r.get("is_active", True)}]),
    "measure_fields": ("📏 خانات المقاسات", [("المجموعة", "text"), ("المقاس", "wide"), ("الترتيب", "int"),
                                            ("شغّال", "text")],
                       lambda r: [r["grp"], r["name"], r.get("sort", 0), YES if r.get("is_active") else NO],
                       lambda r: [{"key": "grp", "label": "المجموعة * (جاكيت، بنطلون، صديرى، قميص...)",
                                   "default": r.get("grp", "")},
                                  {"key": "name", "label": "اسم المقاس *", "default": r.get("name", "")},
                                  {"key": "sort", "label": "الترتيب", "default": str(r.get("sort", 0))},
                                  {"key": "is_active", "label": "شغّال", "type": "check",
                                   "default": r.get("is_active", True)}]),
    "style_options": ("✂️ تفاصيل الموديل", [("الاسم", "text"), ("الاختيارات", "wide"), ("شغّال", "text")],
                      lambda r: [r["name"], "، ".join(str(r.get("choices") or "").splitlines()),
                                 YES if r.get("is_active") else NO],
                      lambda r: [{"key": "name", "label": "الاسم * (مثال: الياقة)", "default": r.get("name", "")},
                                 {"key": "choices", "label": "الاختيارات (كل اختيار فى سطر — ولو بياخد قماش زيادة "
                                                             "اكتب جنبه = +0.3 مثلاً)", "type": "text",
                                  "default": r.get("choices", "")},
                                 {"key": "sort", "label": "الترتيب", "default": str(r.get("sort", 0))},
                                 {"key": "is_active", "label": "شغّال", "type": "check",
                                  "default": r.get("is_active", True)}]),
}

STATE_COLORS = {"ok": GREEN, "expiring": AMBER, "expired": RED, "tamper": RED, "invalid": RED, "none": RED}


def renew_license_dialog(page):
    """إدخال كود تجديد (من صفحة الإعدادات أو من شريط التنبيه)."""
    app = page if hasattr(page, "controller") else page.app
    lic = app.me.license()

    def done(_lic):
        app.update_banner()
        ui.show_info(page, "✅ الترخيص اتجدد. اعمل خروج ودخول عشان كل حاجة تتحدث.")
        app.after_change()

    def action(v):
        result = app.backend.renew_license(code=v["code"])
        app.backend.load_me()
        return result

    ui.FormDialog(page, app, "🔑 تجديد الترخيص", [
        {"key": "info", "type": "info", "label": f"كود الجهاز: {lic.get('machine', '—')} — ابعته لـ {SELLER_NAME} "
                                                 f"({SELLER_PHONE}) واطلب كود التجديد."},
        {"key": "code", "label": "كود التفعيل الجديد", "type": "text"},
    ], action, on_done=done, submit_text="✅ تفعيل الكود")


class SettingsPage(ScrollPage):
    PAGE = "settings"
    TITLE = "⚙️ الإعدادات"

    def load(self):
        server = None
        try:
            server = self.backend.server_info()
        except AppError:
            pass
        return self.backend.users(), self.backend.lookups(), self.backend.load_me(), server, self.backend.backups()

    def render(self, data):
        users, lookups, _me, server, backups = data
        self.app.set_lookups(lookups)
        self.app.update_banner()
        company = self.me.get_company()
        lic = self.me.license()
        page = self.new_content()

        # ---------- الترخيص ----------
        color = STATE_COLORS.get(lic.get("state"), AMBER)
        box = Box("🔑 الترخيص", color)
        box.body.addLayout(ui.kv_row("الحالة", lic.get("message", ""), color))
        box.body.addLayout(ui.kv_row("الباقة", lic.get("plan_label", "—")))
        box.body.addLayout(ui.kv_row("ينتهى", iso_to_display(lic.get("expires")) or "مدى الحياة"))
        box.body.addLayout(ui.kv_row("المستخدمين", f"{lic.get('active_users', 0)} شغّال من {lic.get('users', '—')}"))
        machine = lic.get("machine", "—")
        code = ui.label(machine, "code")
        code.setStyleSheet(f"color: {NAVY}; font-weight: bold;")
        box.body.addLayout(ui.hbox(ui.label("كود الجهاز (السيرفر):"), code, None,
                                   ui.button("📋 نسخ", "light", lambda: QGuiApplication.clipboard().setText(machine)),
                                   ui.button("🔑 إدخال كود تجديد", "purple", lambda: renew_license_dialog(self))))
        box.body.addWidget(ui.muted(f"للتجديد أو زيادة عدد المستخدمين: ابعت كود الجهاز لـ {SELLER_NAME} "
                                    f"({SELLER_PHONE})."))
        page.addWidget(box)

        writable = not self.me.read_only()

        # ---------- الشركة ----------
        box = Box("🏢 بيانات الشركة", NAVY)
        box.body.addLayout(ui.kv_row("الاسم", company.get("name", "")))
        box.body.addLayout(ui.kv_row("التليفون", company.get("phone") or "—"))
        box.body.addLayout(ui.kv_row("العنوان", company.get("address") or "—"))
        box.body.addLayout(ui.kv_row("كلام تحت الإيصال", company.get("receipt_note") or "—"))
        box.body.addLayout(ui.kv_row("حساب الربح من",
                                     iso_to_display(company.get("profit_start_date")) or "من الأول"))
        box.body.addLayout(ui.kv_row("ملف إجبارى مع كل طلب", "أيوه" if company.get("require_attachment") else "لأ"))
        logo_buttons = []
        if writable:
            logo_buttons = [ui.button("🖼️ رفع / تغيير اللوجو", "purple", self._upload_logo)]
            if company.get("has_logo"):
                logo_buttons.append(ui.button("إزالة اللوجو", "light", self._remove_logo))
        box.body.addLayout(ui.hbox(ui.label("لوجو الشركة:"),
                                   ui.label("✔ موجود" if company.get("has_logo") else "مفيش لوجو", "muted"),
                                   None, *logo_buttons,
                                   *([ui.button("✏️ تعديل البيانات", "blue", self._edit_company)] if writable else [])))
        page.addWidget(box)

        # ---------- السيرفر والنسخ الاحتياطى ----------
        page.addWidget(self._server_box(server, backups))

        # ---------- المستخدمين ----------
        self._users = {u["id"]: u for u in users}
        buttons = []
        if writable:
            buttons = [ui.button("➕ مستخدم جديد", "green", self._new_user),
                       ui.button("🔐 الصلاحيات", "blue", self._edit_member),
                       ui.button("⏸️ إيقاف / ▶️ تفعيل", "amber", self._toggle_member),
                       ui.button("🗑️ حذف", "red", self._remove_member)]
        buttons.insert(min(len(buttons), 2), ui.button("🔑 تغيير الباسورد", "purple", self._reset_password))
        page.addLayout(ui.hbox(ui.section_title(f"👥 مستخدمين البرنامج ({len(users)})"), None, *buttons))
        page.addWidget(ui.muted("كل موظف بيدخل باسم مستخدم وباسورد. «إيقاف» = مش هيقدر يدخل وصلاحياته محفوظة. "
                                "«حذف» = بيتشال خالص. عدد المستخدمين الشغّالين محدود بالترخيص."))
        self._members = DataTable([("الاسم", "text"), ("اسم المستخدم", "text"), ("الوظيفة", "text"),
                                   ("الحالة", "text"), ("آخر دخول", "date"), ("الصفحات", "wide")], min_height=200)
        self._members.set_rows([{
            "key": u["id"],
            "color": ui.GRAY if not u["is_active"] else (GREEN if u["is_admin"] else None),
            "values": [u["full_name"], u["username"], u.get("role_title"),
                       "مدير" if u["is_admin"] else ("شغّال" if u["is_active"] else "⏸️ موقوف"),
                       datetime_display(u.get("last_login")) if u.get("last_login") else "",
                       "كل حاجة" if u["is_admin"] else "، ".join(
                           title for key, title in PAGES if key in u["pages"] + u["edit_pages"])],
        } for u in users])
        if writable:
            self._members.cellDoubleClicked.connect(lambda r, c: self._edit_member())
        page.addWidget(self._members)

        # ---------- القوائم ----------
        self._tables = {}
        for table, (title, columns, values, _fields) in LISTS.items():
            rows = lookups.get(table, [])
            btns = [ui.button("➕ إضافة", "green", lambda t=table: self._edit_row(t)),
                    ui.button("✏️ تعديل", "blue", lambda t=table: self._edit_row(t, selected=True))] if writable else []
            page.addLayout(ui.hbox(ui.section_title(title), None, *btns))
            t = DataTable(columns, min_height=150)
            t.set_rows([{"key": r["id"], "color": None if r.get("is_active", 1) else ui.GRAY,
                         "values": values(r)} for r in rows])
            self._tables[table] = (t, {r["id"]: r for r in rows})
            page.addWidget(t)
            if table == "measure_fields":
                page.addWidget(ui.muted("الخانات بتظهر فى فورم الطلب متقسمة بالمجموعة. خانة موقوفة مش بتظهر، "
                                        "بس المقاسات القديمة اللى فيها بتفضل محفوظة."))

        # ---------- أسعار القطعة ----------
        page.addLayout(ui.hbox(ui.section_title("💵 أسعار القطعة (للعمال اللى بيتحاسبوا بالقطعة)"), None,
                               *([ui.button("✏️ تعديل الأسعار", "blue", self._edit_rates)] if writable else [])))
        rates = {(r["garment_type_id"], r["stage"]): r["rate"] for r in lookups.get("piece_rates", [])}
        t = DataTable([("النوع", "wide")] + [(v, "money") for v in STAGE_LABELS.values()], min_height=160)
        t.set_rows([{"key": g["id"], "values": [g["name"]] + [rates.get((g["id"], s), "") for s in STAGE_LABELS]}
                    for g in lookups.get("garment_types", []) if g["is_active"]])
        page.addWidget(t)
        page.addWidget(ui.muted("لما العامل يخلّص مرحلة، أجره = سعر القطعة × عدد القطع فى الطلب، وبيتسجل فى كشف "
                                "الأجور أوتوماتيك."))

        # ---------- تركيبة الخامات (المعادلات) ----------
        btns = [ui.button("➕ إضافة", "green", lambda: BomDialog(self)),
                ui.button("✏️ تعديل", "blue", self._edit_bom),
                ui.button("🗑️ مسح", "red", self._delete_bom)] if writable else []
        page.addLayout(ui.hbox(ui.section_title("🧮 تركيبة الخامات (المعادلات)"), None, *btns))
        page.addWidget(ui.muted("لكل نوع شغل: الخامات وكميتها للقطعة الواحدة (رقم أو معادلة بالمقاسات). البرنامج بيحسبها "
                                "لوحده فى الطلب ويحجزها من المخزن، وبتتخصم عند القص. لو مقاس من المعادلة مش متسجل "
                                "بتتحسب «الكمية لو المقاسات ناقصة»."))
        types = {g["id"]: g["name"] for g in lookups.get("garment_types", [])}
        self._bom = {b["id"]: b for b in lookups.get("bom_lines", [])}
        self._bom_table = DataTable([("النوع", "text"), ("الخامة", "text"), ("الكمية للقطعة (المعادلة)", "wide"),
                                     ("لو المقاسات ناقصة", "qty"), ("شغّال", "text")], min_height=220)
        self._bom_table.set_rows([{
            "key": b["id"], "color": None if b["is_active"] else ui.GRAY,
            "values": [types.get(b["garment_type_id"], "—"),
                       "🧵 القماش اللى اتختار فى الطلب" if b["is_fabric"] else b.get("material_name"),
                       b["formula"], b["fallback_qty"], YES if b["is_active"] else NO]}
            for b in self._bom.values()])
        if writable:
            self._bom_table.cellDoubleClicked.connect(lambda r, c: self._edit_bom())
        page.addWidget(self._bom_table)

        page.addLayout(ui.hbox(None, ui.button("📜 سجل النشاط (مين عمل إيه)", "light", lambda: ActivityDialog(self))))
        page.addStretch(1)

    # ---------- السيرفر والنسخ الاحتياطى ----------

    def _server_box(self, server, backups):
        mode = local_config.load().get("mode")
        box = Box("🖥️ السيرفر والنسخ الاحتياطى", TEAL)
        if mode == "server" and server:
            from server.api import local_ips
            port = server.get("port") or local_config.load().get("port") or local_config.DEFAULT_PORT
            ips = "  أو  ".join(local_ips())
            box.body.addLayout(ui.kv_row("عنوان السيرفر (اديه للموظفين)", f"{ips}   —   البورت {port}", TEAL))
            box.body.addLayout(ui.kv_row("مكان البيانات", server.get("data_dir", "")))
            box.body.addLayout(ui.kv_row("حجم البيانات", f"{num(server.get('db_size')) / 1024 / 1024:.1f} ميجا"))
            if autostart.supported():
                cb = QCheckBox("شغّل السيرفر لوحده أول ما ويندوز يفتح (جنب الساعة، من غير ما تفتح البرنامج)")
                cb.setChecked(autostart.is_enabled())
                cb.toggled.connect(self._toggle_autostart)
                box.body.addWidget(cb)
            box.body.addWidget(ui.muted("أول مرة السيرفر يشتغل، ويندوز ممكن يسأل «Allow access» — دوس Allow "
                                        "(واختار Private networks) عشان باقى الأجهزة تقدر تتصل."))
        else:
            cfg = local_config.load()
            box.body.addLayout(ui.kv_row("متصل بالسيرفر", f"{cfg.get('host')} — البورت {cfg.get('port')}"))
        box.body.addLayout(ui.hbox(
            ui.button("💾 اعمل نسخة احتياطية (فلاشة / فولدر)", "green", self._backup),
            ui.button("♻️ استرجاع من ملف", "red", self._restore_file), None))
        autos = [b for b in backups if b["name"].startswith("auto-")]
        box.body.addWidget(ui.muted(
            f"السيرفر بيعمل نسخة أوتوماتيك كل يوم (آخر 30 يوم). موجود دلوقتى {len(autos)} نسخة"
            + (f"، آخرها {autos[0]['modified']}" if autos else "") + ". خد نسخة على فلاشة كل أسبوع على الأقل."))
        if backups:
            box.body.addLayout(ui.hbox(ui.button("📂 النسخ اللى على السيرفر", "light",
                                                 lambda: BackupsDialog(self, backups))))
        return box

    def _toggle_autostart(self, enabled):
        try:
            autostart.set_enabled(enabled)
        except OSError as e:
            ui.show_error(self, f"مش قادر أغيّر الإعداد ده: {e}")

    def _backup(self):
        name = f"SUITES-backup-{datetime.now():%Y-%m-%d_%H%M}.db"
        path, _ = QFileDialog.getSaveFileName(self, "احفظ النسخة الاحتياطية فين؟", name, "نسخة احتياطية (*.db)")
        if not path:
            return
        self.app.worker.run(lambda: self.backend.save_backup(path),
                            lambda size: ui.show_info(self, f"✅ النسخة اتحفظت ({size / 1024 / 1024:.1f} ميجا):\n{path}"),
                            lambda e: ui.show_error(self, e))

    def _confirm_restore(self):
        return ui.ask_yes_no(self, "⚠️ الاسترجاع بيرجّع البيانات زى ما كانت وقت النسخة دى، وأى حاجة اتعملت بعدها "
                                   "هتضيع.\n(البرنامج بيحفظ نسخة من البيانات الحالية قبلها للأمان)\n\n"
                                   "كل الأجهزة هتحتاج تدخل تانى. متأكد؟")

    def _restore_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختار ملف النسخة الاحتياطية", "", "نسخة احتياطية (*.db)")
        if path and self._confirm_restore():
            self.app.worker.run(lambda: self.backend.restore_from_file(path), self._restored,
                                lambda e: ui.show_error(self, e))

    def restore_server_file(self, name):
        if self._confirm_restore():
            self.app.worker.run(lambda: self.backend.restore_backup(server_file=name), self._restored,
                                lambda e: ui.show_error(self, e))

    def _restored(self, _r):
        ui.show_info(self, "✅ البيانات رجعت. ادخل تانى.")
        self.app.controller.connect()

    # ---------- الشركة ----------

    def _edit_company(self):
        c = self.me.get_company()
        self.form("✏️ بيانات الشركة", [
            {"key": "name", "label": "اسم الشركة *", "default": c.get("name", "")},
            {"key": "phone", "label": "التليفون", "default": c.get("phone") or ""},
            {"key": "address", "label": "العنوان", "default": c.get("address") or ""},
            {"key": "note", "label": "كلام بيتطبع تحت الإيصال", "type": "text", "default": c.get("receipt_note") or "",
             "placeholder": "مثال: البضاعة لا ترد ولا تستبدل بعد 14 يوم"},
            {"key": "start", "label": "حساب الربح من (يوم/شهر/سنة) — فاضى = من الأول",
             "default": iso_to_display(c.get("profit_start_date"))},
            {"key": "attach", "label": "لازم ملف (فاتورة/صورة) مع كل طلب", "type": "check",
             "default": c.get("require_attachment", False)},
        ], lambda v: (self.backend.update_company(name=v["name"], phone=v["phone"], address=v["address"],
                                                  receipt_note=v["note"], profit_start_date=iso_date(v["start"]),
                                                  require_attachment=v["attach"]), self.backend.load_me()),
            then=lambda _r: self.app.refresh_company_header())

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

    # ---------- المستخدمين ----------

    def _sel_user(self):
        return self.selected(self._members, self._users, "اختار مستخدم من الجدول الأول")

    def _new_user(self):
        PermissionsDialog(self, self.app, None)

    def _edit_member(self):
        u = self._sel_user()
        if u:
            PermissionsDialog(self, self.app, u)

    def _member_other_than_me(self):
        u = self._sel_user()
        if u and u["id"] == self.me.get_user_id():
            ui.show_info(self, "ده حسابك إنت — مينفعش توقفه أو تمسحه", "تنبيه")
            return None
        return u

    def _toggle_member(self):
        u = self._member_other_than_me()
        if not u:
            return
        args = dict(user_id=u["id"], is_admin=u["is_admin"], pages=u["pages"], edit_pages=u["edit_pages"],
                    delete_pages=u["delete_pages"], role_title=u.get("role_title"))
        if u["is_active"]:
            if ui.ask_yes_no(self, f"إيقاف {u['full_name']}؟ مش هيقدر يدخل البرنامج لحد ما ترجّعه."):
                self.run_action(lambda: self.backend.set_member(is_active=False, **args))
        else:
            self.run_action(lambda: self.backend.set_member(is_active=True, **args), f"✅ {u['full_name']} اتفعّل")

    def _remove_member(self):
        u = self._member_other_than_me()
        if u and ui.ask_yes_no(self, f"حذف {u['full_name']} ({u['username']}) خالص؟"):
            self.run_action(lambda: self.backend.remove_member(user_id=u["id"]))

    def _reset_password(self):
        u = self._sel_user()
        if not u:
            return

        def action(v):
            if v["p1"] != v["p2"]:
                raise AppError("الباسورد والتأكيد مش زى بعض")
            return self.backend.reset_password(user_id=u["id"], new_password=v["p1"])
        self.form(f"🔑 باسورد جديد لـ {u['full_name']}", [
            {"key": "p1", "label": "الباسورد الجديد", "type": "password"},
            {"key": "p2", "label": "اكتبه تانى", "type": "password"},
        ], action, success_message="✅ الباسورد اتغيّر", color=PURPLE)

    # ---------- القوائم ----------

    def _edit_row(self, table, selected=False):
        title, _cols, _values, fields = LISTS[table]
        row = {}
        if selected:
            t, items = self._tables[table]
            row = self.selected(t, items, "اختار صف من الجدول الأول")
            if not row:
                return
        self.form(("✏️ تعديل" if row else "➕ إضافة") + " — " + title, fields(row),
                  lambda v: self.backend.save_setting(table=table, values=v, row_id=row.get("id")),
                  then=lambda _r: self.app.reload_lookups())

    def _edit_rates(self):
        RatesDialog(self)

    def _edit_bom(self):
        b = self.selected(self._bom_table, self._bom, "اختار سطر من جدول تركيبة الخامات")
        if b:
            BomDialog(self, b)

    def _delete_bom(self):
        b = self.selected(self._bom_table, self._bom, "اختار سطر من جدول تركيبة الخامات")
        if b and ui.ask_yes_no(self, "تمسح السطر ده من التركيبة؟ (الطلبات القديمة مش بتتأثر)"):
            self.run_action(lambda: self.backend.delete_bom_line(line_id=b["id"]),
                            then=lambda _r: self.app.reload_lookups())


class PermissionsDialog(QDialog):
    """مستخدم جديد أو صلاحيات مستخدم: لكل صفحة (يشوف / يضيف ويعدّل / يمسح) + مدير."""

    def __init__(self, parent, app, user):
        super().__init__(parent)
        self._app = app
        self._u = user
        new = user is None
        user = user or {"pages": [], "edit_pages": [], "delete_pages": [], "is_admin": False, "is_active": True}
        self.setWindowTitle("➕ مستخدم جديد" if new else f"صلاحيات {user['full_name']}")
        self.setMinimumWidth(620)
        outer = QVBoxLayout(self)
        outer.addWidget(ui.label(self.windowTitle(), "dialogTitle"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        grid = QGridLayout()
        self._name = QLineEdit(user.get("full_name", ""))
        self._name.setPlaceholderText("اسم الموظف *")
        self._role = QLineEdit(user.get("role_title") or "")
        self._role.setPlaceholderText("الوظيفة (مثال: محاسب، قصاص، استقبال)")
        grid.addWidget(ui.label("الاسم"), 0, 0)
        grid.addWidget(self._name, 0, 1)
        grid.addWidget(ui.label("الوظيفة"), 0, 2)
        grid.addWidget(self._role, 0, 3)
        self._username = QLineEdit(user.get("username", ""))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        if new:
            self._username.setPlaceholderText("اسم المستخدم (إنجليزى من غير مسافات) *")
            self._password.setPlaceholderText("الباسورد *")
            grid.addWidget(ui.label("اسم المستخدم"), 1, 0)
            grid.addWidget(self._username, 1, 1)
            grid.addWidget(ui.label("الباسورد"), 1, 2)
            grid.addWidget(self._password, 1, 3)
        lay.addLayout(grid)
        self._active = QCheckBox("الحساب شغّال (يقدر يدخل البرنامج)")
        self._active.setChecked(bool(user["is_active"]))
        self._admin = QCheckBox("مدير (يشوف ويعمل كل حاجة + الإعدادات)")
        self._admin.setChecked(bool(user["is_admin"]))
        if not new:
            lay.addWidget(self._active)
        lay.addWidget(self._admin)

        grid = QGridLayout()
        for col, head in enumerate(("الصفحة", "يشوف", "يضيف ويعدّل", "يمسح")):
            grid.addWidget(ui.label(head, "boxTitle"), 0, col)
        self._checks = {}
        sets = {"view": set(user["pages"]), "edit": set(user["edit_pages"]), "delete": set(user["delete_pages"])}
        for row, (key, title) in enumerate(PAGES, start=1):
            grid.addWidget(ui.label(title), row, 0)
            for col, action in enumerate(("view", "edit", "delete"), start=1):
                cb = QCheckBox()
                cb.setChecked(key in sets[action])
                grid.addWidget(cb, row, col)
                self._checks[(key, action)] = cb
        lay.addLayout(grid)
        lay.addWidget(ui.muted("«يضيف ويعدّل» بتشمل «يشوف». المدير مش محتاج يتعلّم على أى صفحة. "
                               "مثال: القصاص ← «القص» (يشوف + يضيف ويعدّل) بس."))

        self._btn = ui.button("💾 حفظ", "green", self._save)
        outer.addWidget(self._btn)
        self._msg = ui.label("", "errorMsg", wrap=True)
        outer.addWidget(self._msg)
        self.resize(660, 720)
        self.setModal(True)
        self.show()

    def _save(self):
        pick = lambda action: [k for (k, a), cb in self._checks.items() if a == action and cb.isChecked()]  # noqa
        backend = self._app.backend
        common = dict(is_admin=self._admin.isChecked(), pages=pick("view"), edit_pages=pick("edit"),
                      delete_pages=pick("delete"), role_title=self._role.text().strip() or None)
        if self._u is None:
            name, username, password = self._name.text(), self._username.text(), self._password.text()
            action = lambda: backend.create_user(full_name=name, username=username, password=password,  # noqa
                                                 **common)
        else:
            uid, active, name = self._u["id"], self._active.isChecked(), self._name.text()
            action = lambda: backend.set_member(user_id=uid, is_active=active, full_name=name, **common)  # noqa
        self._btn.setEnabled(False)

        def ok(_):
            self.accept()
            self._app.after_change()

        def fail(e):
            self._btn.setEnabled(True)
            self._msg.setText(f"❌ {e}")

        self._app.worker.run(action, ok, fail)


class BomDialog(QDialog):
    """سطر فى تركيبة الخامات: النوع + الخامة + المعادلة، مع زرار يضيف اسم مقاس وتجربة المعادلة."""

    FUNCS = [("تقريب لأقرب ربع", "تقريب(…، 0.25)"), ("لو (شرط)", "لو([جاكيت الصدر] > 110، 0.25، 0)"),
             ("أكبر", "أكبر(…، …)"), ("أصغر", "أصغر(…، …)")]

    def __init__(self, page, line=None):
        super().__init__(page)
        self._page = page
        self._line = line or {}
        app = page.app
        lk = app.lookups
        self.setWindowTitle("✏️ سطر فى التركيبة" if line else "➕ سطر جديد فى التركيبة")
        self.resize(760, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(self.windowTitle(), "dialogTitle"))
        grid = QGridLayout()
        self._type = QComboBox()
        ui.fill_combo(self._type, [(g["name"], g["id"]) for g in lk.get("garment_types", [])],
                      self._line.get("garment_type_id"))
        self._material = ui.searchable(QComboBox())
        ui.fill_combo(self._material, [("🧵 القماش اللى اتختار فى الطلب", "fabric")] + [
            (f"{m['name']} ({m['unit']})", m["id"]) for m in lk.get("materials", []) if m["is_active"]],
            "fabric" if self._line.get("is_fabric", line is None) else self._line.get("material_id"))
        self._fallback = QLineEdit(amount_text(self._line.get("fallback_qty", 0)))
        self._sort = QLineEdit(str(self._line.get("sort", 0)))
        self._active = QCheckBox("شغّال")
        self._active.setChecked(bool(self._line.get("is_active", True)))
        for r, (title, w) in enumerate((("النوع", self._type), ("الخامة", self._material),
                                        ("الكمية لو المقاسات ناقصة", self._fallback), ("الترتيب", self._sort))):
            grid.addWidget(ui.label(title), r, 0)
            grid.addWidget(w, r, 1)
        grid.addWidget(self._active, 4, 1)
        lay.addLayout(grid)

        lay.addWidget(ui.label("الكمية للقطعة الواحدة (رقم زى 1.5 أو معادلة):", "boxTitle"))
        self._formula = QPlainTextEdit(self._line.get("formula", ""))
        self._formula.setMaximumHeight(90)
        self._formula.setPlaceholderText("مثال: تقريب(([جاكيت الطول] + [جاكيت طول الكم]) ÷ 100 + 0.35، 0.25)")
        lay.addWidget(self._formula)
        self._measure_pick = ui.searchable(QComboBox())
        fields = [f for f in lk.get("measure_fields", []) if f["is_active"]]
        ui.fill_combo(self._measure_pick, [("➕ ضيف مقاس للمعادلة…", None)] + [
            (f"{f['grp']} — {f['name']}", f"[{f['grp']} {f['name']}]") for f in fields])
        self._measure_pick.activated.connect(self._insert_measure)
        func_btns = [ui.button(title, "light", lambda t=text: self._formula.insertPlainText(t))
                     for title, text in self.FUNCS]
        lay.addLayout(ui.hbox(self._measure_pick, *func_btns))
        lay.addWidget(ui.muted("المقاسات بالسنتيمتر زى ما بتتكتب فى الطلب، فالقسمة على 100 بتحوّلها متر. "
                               "÷ × + − والأقواس، و«تقريب(القيمة، 0.25)» بيقرّب لفوق لأقرب ربع متر. "
                               "الناتج بيتضرب فى عدد القطع فى الطلب أوتوماتيك."))

        test = QGroupBox("🧪 جرّب المعادلة بمقاسات")
        tl = QVBoxLayout(test)
        self._sample = MeasurementsEditor(fields, {})
        tl.addWidget(self._sample)
        self._result = ui.label("", "boxTitle")
        tl.addLayout(ui.hbox(ui.button("🧪 احسب", "teal", self._test), self._result))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(test)
        lay.addWidget(scroll, 1)

        self._btn = ui.button("💾 حفظ", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addLayout(ui.hbox(self._btn, self._msg))
        self.setModal(True)
        self.show()

    def _insert_measure(self, _index):
        value = ui.combo_value(self._measure_pick)
        if isinstance(value, str) and value.startswith("["):
            self._formula.insertPlainText(value)
        self._measure_pick.setCurrentIndex(0)

    def _test(self):
        formula, sample = self._formula.toPlainText(), self._sample.get()
        self._page.app.worker.run(
            lambda: self._page.backend.test_formula(formula=formula, measurements=sample),
            lambda r: self._result.setText(f"✔ النتيجة: {ui.qty(r['qty'])} للقطعة" if r["ok"] else f"❌ {r['error']}"),
            lambda e: self._result.setText(f"❌ {e}"))

    def _save(self):
        material = ui.combo_value(self._material)
        try:
            args = dict(garment_type_id=ui.combo_value(self._type), formula=self._formula.toPlainText(),
                        is_fabric=material == "fabric", material_id=material if isinstance(material, int) else None,
                        fallback_qty=parse_amount(self._fallback.text(), "الكمية الافتراضية", allow_zero=True),
                        sort=int(parse_amount(self._sort.text() or "0", "الترتيب", allow_zero=True)),
                        is_active=self._active.isChecked(), line_id=self._line.get("id"))
        except AppError as e:
            self._msg.setText(f"❌ {e}")
            return
        self._btn.setEnabled(False)
        app = self._page.app
        app.worker.run(lambda: self._page.backend.save_bom_line(**args),
                       lambda _r: (self.accept(), app.reload_lookups(), app.after_change()),
                       lambda e: (self._msg.setText(f"❌ {e}"), self._btn.setEnabled(True)))


class RatesDialog(QDialog):
    """أسعار القطعة: لكل نوع شغل × مرحلة."""

    def __init__(self, page):
        super().__init__(page)
        self._page = page
        app = page.app
        self.setWindowTitle("💵 أسعار القطعة")
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label("💵 أسعار القطعة (اللى العامل بياخده عن كل قطعة)", "dialogTitle"))
        grid = QGridLayout()
        grid.addWidget(ui.label("النوع", "boxTitle"), 0, 0)
        for c, title in enumerate(STAGE_LABELS.values(), 1):
            grid.addWidget(ui.label(title, "boxTitle"), 0, c)
        rates = {(r["garment_type_id"], r["stage"]): r["rate"] for r in app.lookups.get("piece_rates", [])}
        self._edits = {}
        types = [g for g in app.lookups.get("garment_types", []) if g["is_active"]]
        for r, g in enumerate(types, 1):
            grid.addWidget(ui.label(g["name"]), r, 0)
            for c, stage in enumerate(STAGE_LABELS, 1):
                e = QLineEdit(amount_text(rates.get((g["id"], stage), 0)))
                e.setMaximumWidth(100)
                grid.addWidget(e, r, c)
                self._edits[(g["id"], stage)] = (e, rates.get((g["id"], stage), 0))
        lay.addLayout(grid)
        self._btn = ui.button("💾 حفظ الأسعار", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addWidget(self._btn)
        lay.addWidget(self._msg)
        self.setModal(True)
        self.show()

    def _save(self):
        try:
            changes = [(gid, stage, parse_amount(e.text(), "السعر", allow_zero=True))
                       for (gid, stage), (e, old) in self._edits.items()
                       if parse_amount(e.text(), "السعر", allow_zero=True) != num(old)]
        except AppError as e:
            self._msg.setText(f"❌ {e}")
            return
        backend = self._page.backend
        self._btn.setEnabled(False)

        def work():
            for gid, stage, rate in changes:
                backend.save_piece_rate(garment_type_id=gid, stage=stage, rate=rate)
            return len(changes)

        self._page.app.worker.run(work, lambda _n: (self.accept(), self._page.app.reload_lookups(),
                                                   self._page.app.after_change()),
                                  lambda e: (self._msg.setText(f"❌ {e}"), self._btn.setEnabled(True)))


class BackupsDialog(QDialog):
    def __init__(self, page, backups):
        super().__init__(page)
        self._page = page
        self.setWindowTitle("📂 النسخ الاحتياطية على السيرفر")
        self.resize(640, 440)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.muted("auto = نسخة يومية أوتوماتيك · before-restore = نسخة اتعملت قبل استرجاع"))
        self._table = DataTable([("الملف", "wide"), ("الوقت", "text"), ("الحجم (ميجا)", "text")])
        self._table.set_rows([{"key": b["name"], "values": [b["name"], b["modified"], f"{b['size'] / 1024 / 1024:.1f}"]}
                              for b in backups])
        lay.addWidget(self._table, 1)
        lay.addWidget(ui.button("♻️ استرجاع النسخة المختارة", "red", self._restore))
        self.show()

    def _restore(self):
        name = self._table.selected_key()
        if not name:
            ui.show_info(self, "اختار نسخة من الجدول", "تنبيه")
            return
        self.accept()
        self._page.restore_server_file(name)


class ActivityDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.setWindowTitle("📜 سجل النشاط")
        self.resize(940, 600)
        lay = QVBoxLayout(self)
        self._search = ui.search_box("🔍 بحث", self._render)
        lay.addWidget(self._search)
        self._table = DataTable([("الوقت", "date"), ("مين", "text"), ("العملية", "text"), ("التفاصيل", "wide"),
                                 ("المبلغ", "money")])
        lay.addWidget(self._table, 1)
        self._rows = []
        self.show()
        page.app.worker.run(lambda: page.backend.activity(limit=1000), self._got, lambda e: ui.show_error(self, e))

    def _got(self, rows):
        self._rows = rows
        self._render()

    def _render(self):
        self._table.set_rows([{"key": r["id"], "values": [
            datetime_display(r["created_at"]), r.get("user_name"), r["action"], r.get("details"), r.get("amount") or ""]}
            for r in self._rows if ui.matches(self._search.text(), r, ("user_name", "action", "details"))])
