"""
pages_jobs.py
-------------
صفحات الشغل: المبيعات، المعاينات، المصانع، التركيبات، تأكيد الحسابات، فريق العمل.
"""

from datetime import date

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLineEdit

import qt_widgets as ui
from qt_widgets import (BasePage, ScrollPage, DataTable, Box, BarRow,
                        NAVY, BLUE, GREEN, RED, AMBER, PURPLE, money, today_text)
from models import STAFF_KINDS, AppError, num, iso_to_display, parse_amount, parse_user_date, is_active_row


# ============================================================
#              فورمات المعاينة والتعاقد والصيانة
# ============================================================

def _branch_field(page):
    if page.app.multi_branch():
        return [{"key": "branch", "label": "الفرع", "type": "combo", "options": page.app.branch_options()}]
    return []


def open_inspection_form(page):
    page.form("🔍 طلب معاينة جديد", [
        {"key": "name", "label": "اسم العميل *"},
        {"key": "mobile", "label": "الموبايل *"},
        {"key": "place", "label": "المكان *"},
        {"key": "type", "label": "النوع", "type": "combo",
         "options": [("—", None)] + page.app.options("product_types")},
        {"key": "notes", "label": "ملاحظات"},
    ] + _branch_field(page), lambda v: page.backend.add_inspection(
        v["name"], v["mobile"], v["place"], v["type"], v["notes"], v.get("branch")),
        success_message="✅ اتسجل طلب المعاينة", color=PURPLE)


def open_contract_form(page):
    require_invoice = page.me.get_company().get("require_invoice", True)

    def action(v):
        price = parse_amount(v["price"], "السعر الإجمالى")
        meters = parse_amount(v["meters"], "الأمتار")
        advance = parse_amount(v["advance"], "المقدم", allow_zero=True)
        if require_invoice and not v["invoices"]:
            raise AppError("لازم تختار فاتورة واحدة على الأقل PDF")
        page.backend.check_invoice_files(v["invoices"])
        keys = page.backend.upload_invoices(v["invoices"]) if v["invoices"] else []
        return page.backend.add_job("contract", v["name"], v["mobile"], v["place"], v["type"], price, meters,
                                    advance, v["method"] if advance else None, v["seller"], keys,
                                    None, v.get("branch"))

    page.form("📄 تعاقد جديد", [
        {"key": "seller", "label": "السيلز", "type": "combo",
         "options": [("—", None)] + page.app.options("staff", kind="sales")},
        {"key": "name", "label": "اسم العميل *"},
        {"key": "mobile", "label": "الموبايل *"},
        {"key": "place", "label": "المكان *"},
        {"key": "type", "label": "النوع", "type": "combo",
         "options": page.app.options("product_types", for_contracts=True)},
        {"key": "meters", "label": "الأمتار *"},
        {"key": "price", "label": "السعر الإجمالى *"},
        {"key": "advance", "label": "المقدم", "default": "0"},
        {"key": "method", "label": "طريقة دفع المقدم", "type": "combo", "options": page.app.options("payment_methods")},
        {"key": "invoices", "label": "الفواتير PDF" + (" *" if require_invoice else ""), "type": "files"},
    ] + _branch_field(page), action,
        success_message="✅ اتسجل التعاقد — مستنى تأكيد الحسابات للمقدم", color=BLUE)


def open_maintenance_form(page):
    page.form("🔧 طلب صيانة جديد", [
        {"key": "name", "label": "اسم العميل *"},
        {"key": "mobile", "label": "الموبايل"},
        {"key": "place", "label": "المكان"},
        {"key": "type", "label": "النوع", "type": "combo",
         "options": page.app.options("product_types", for_maintenance=True)},
        {"key": "price", "label": "سعر الصيانة *"},
        {"key": "desc", "label": "وصف الصيانة"},
    ] + _branch_field(page), lambda v: page.backend.add_job(
        "maintenance", v["name"], v["mobile"], v["place"], v["type"], parse_amount(v["price"], "سعر الصيانة"),
        description=v["desc"], branch_id=v.get("branch")),
        success_message="✅ اتسجلت الصيانة ودخلت التركيبات على طول", color=AMBER)


def edit_job_form(page, j):
    fields = [{"key": "place", "label": "المكان", "default": j.get("place") or ""},
              {"key": "price", "label": "السعر الإجمالى", "default": f"{num(j['price']):g}"},
              {"key": "meters", "label": "الأمتار", "default": f"{num(j['meters']):g}"}]
    if j["status"] == "awaiting_advance":
        fields.append({"key": "advance", "label": "المقدم", "default": f"{num(j['advance']):g}"})
    page.form(f"✏️ تعديل — {j['customer_name']}", fields, lambda v: page.backend.update_job(
        j["id"], v["place"], parse_amount(v["price"], "السعر"),
        parse_amount(v["advance"], "المقدم", allow_zero=True) if "advance" in v else None,
        parse_amount(v["meters"], "الأمتار", allow_zero=True)))


def delete_job(page, j):
    if ui.ask_yes_no(page, f"هتمسح عملية {j['customer_name']} نهائيًا؟"):
        page.run_action(lambda: page.backend.delete_job(j["id"]))


def open_invoices(page, j):
    keys = j.get("invoice_paths") or []
    if not keys:
        ui.show_info(page, "العملية دى مفيهاش فواتير", "تنبيه")
        return

    def opened(urls):
        for url in urls:
            QDesktopServices.openUrl(QUrl(url))
    page.app.worker.run(lambda: [page.backend.invoice_url(k) for k in keys], opened,
                        lambda e: ui.show_error(page, e))


JOB_COLUMNS = [("العميل", "text"), ("الموبايل", "text"), ("المكان", "text"), ("النوع", "text"),
               ("الأمتار", "num"), ("السعر", "money"), ("المتبقى", "money"), ("الفرع", "text"),
               ("ملاحظة / وصف", "wide")]


def job_values(j):
    return [j["customer_name"], j.get("customer_mobile"), j.get("place"), j.get("product_type"),
            num(j["meters"]), num(j["price"]), num(j["remaining"]), j.get("branch_name"),
            " | ".join(x for x in (j.get("note"), j.get("description")) if x)]


# ============================================================
#                       المبيعات
# ============================================================

class SalesPage(BasePage):
    PAGE = "sales"
    TITLE = "🧾 المبيعات"

    def __init__(self, app):
        super().__init__(app)
        self._rows, self._by_id = [], {}
        self._count = ui.section_title("")
        buttons = [ui.button("📎 فتح الفواتير", "light", self._invoices)]
        if self.me.can_edit(self.PAGE):
            buttons = [ui.button("🔍 طلب معاينة", "purple", lambda: open_inspection_form(self)),
                       ui.button("📄 تعاقد جديد", "blue", lambda: open_contract_form(self)),
                       ui.button("🔧 طلب صيانة", "amber", lambda: open_maintenance_form(self))] + buttons
        self.body.addLayout(ui.hbox(self._count, None, *buttons))
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 بحث بالعميل أو الموبايل أو المكان أو السيلز")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._render_table)
        self.body.addWidget(self._search)
        self._table = DataTable([("تاريخ الإنهاء", "date"), ("العميل", "text"), ("الموبايل", "text"),
                                 ("المكان", "text"), ("النوع", "text"), ("السيلز", "text"), ("الصنايعى", "text"),
                                 ("السعر", "money"), ("المحصّل", "money"), ("المتبقى", "money"), ("الفرع", "wide")])
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.jobs(["completed"])

    def render(self, rows):
        self._rows, self._by_id = rows, {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        text = self._search.text().strip()
        shown = [j for j in self._rows if not text or any(
            text in str(j.get(k) or "") for k in ("customer_name", "customer_mobile", "place", "seller_name"))]
        self._count.setText(f"📜 العمليات المكتملة ({len(shown)})")
        self._table.set_rows([{
            "key": j["id"], "color": RED if num(j["remaining"]) > 0 else None,
            "values": [iso_to_display(j["completed_at"]), j["customer_name"], j.get("customer_mobile"),
                       j.get("place"), j.get("product_type"), j.get("seller_name"), j.get("craftsman"),
                       num(j["price"]), num(j["advance"]) + num(j.get("final_collected")), num(j["remaining"]),
                       j.get("branch_name")],
        } for j in shown])

    def _invoices(self):
        j = self.selected(self._table, self._by_id, "اختار عملية من الجدول الأول")
        if j:
            open_invoices(self, j)


# ============================================================
#                       المعاينات
# ============================================================

class InspectionsPage(BasePage):
    PAGE = "inspections"
    TITLE = "🔍 المعاينات"

    def __init__(self, app):
        super().__init__(app)
        self._rows, self._by_id = [], {}
        self._active = ui.section_title("")
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 بحث بالاسم أو المكان أو الموبايل")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._render_table)
        buttons = []
        if self.me.can_edit(self.PAGE):
            buttons += [ui.button("✅ تم", "green", self._close), ui.button("✏️ تعديل", "blue", self._edit)]
        if self.me.can_delete(self.PAGE):
            buttons.append(ui.button("🗑️ مسح", "red", self._delete))
        self.body.addLayout(ui.hbox(self._active, self._search, None, *buttons))
        self._table = DataTable([("التاريخ", "date"), ("العميل", "text"), ("الموبايل", "text"), ("المكان", "text"),
                                 ("النوع", "text"), ("ملاحظات", "wide"), ("الفرع", "text"), ("الحالة", "text")])
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.inspections()

    def render(self, rows):
        self._rows, self._by_id = rows, {r["id"]: r for r in rows}
        self._active.setText(f"معاينات نشطة: {sum(1 for r in rows if r['status'] == 'active')}")
        self._render_table()

    def _render_table(self):
        text = self._search.text().strip()
        self._table.set_rows([{
            "key": r["id"], "color": AMBER if r["status"] == "active" else GREEN,
            "values": [iso_to_display(r["created_at"]), r["customer_name"], r.get("customer_mobile"), r["place"],
                       r.get("product_type"), r.get("notes"), r.get("branch_name"),
                       "نشطة" if r["status"] == "active" else "تم"],
        } for r in self._rows if not text or any(
            text in str(r.get(k) or "") for k in ("customer_name", "place", "customer_mobile"))])

    def _sel(self):
        return self.selected(self._table, self._by_id, "اختار معاينة من الجدول الأول")

    def _close(self):
        r = self._sel()
        if r and ui.ask_yes_no(self, f"هتقفل معاينة {r['customer_name']} كـ«تم»؟"):
            self.run_action(lambda: self.backend.close_inspection(r["id"]))

    def _edit(self):
        r = self._sel()
        if r:
            self.form(f"✏️ معاينة {r['customer_name']}", [
                {"key": "place", "label": "المكان", "default": r["place"]},
                {"key": "notes", "label": "ملاحظات", "default": r.get("notes") or ""},
            ], lambda v: self.backend.update_inspection(r["id"], v["place"], v["notes"]))

    def _delete(self):
        r = self._sel()
        if r and ui.ask_yes_no(self, f"هتمسح معاينة {r['customer_name']} نهائيًا؟"):
            self.run_action(lambda: self.backend.delete_inspection(r["id"]))


# ============================================================
#              المصانع والتركيبات (نفس الكلاس)
# ============================================================

class StagePage(BasePage):
    def __init__(self, app, status, page_key):
        super().__init__(app)
        self._status = status
        self.PAGE = page_key
        self.TITLE = "🏭 المصانع" if status == "manufacturing" else "🔧 التركيبات"
        self._by_id = {}
        self._title = ui.section_title(self.TITLE)
        buttons = []
        if self.me.can_edit(page_key):
            buttons += [ui.button("✅ تم التصنيع" if status == "manufacturing" else "✅ تم التركيب",
                                  "green", self._advance),
                        ui.button("📝 ملاحظة", "amber", self._note),
                        ui.button("✏️ تعديل", "blue", lambda: self._with(lambda j: edit_job_form(self, j)))]
        if self.me.can_delete(page_key):
            buttons.append(ui.button("🗑️ مسح", "red", lambda: self._with(lambda j: delete_job(self, j))))
        buttons.append(ui.button("📎 الفواتير", "light", lambda: self._with(lambda j: open_invoices(self, j))))
        self.body.addLayout(ui.hbox(self._title, None, *buttons))
        self._table = DataTable(JOB_COLUMNS)
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.jobs([self._status])

    def render(self, rows):
        self._by_id = {r["id"]: r for r in rows}
        self._title.setText(f"{self.TITLE} ({len(rows)})")
        self._table.set_rows([{"key": j["id"], "color": AMBER if j["kind"] == "maintenance" else None,
                               "values": job_values(j)} for j in rows])

    def _with(self, func):
        j = self.selected(self._table, self._by_id, "اختار عملية من الجدول الأول")
        if j:
            func(j)

    def _advance(self):
        self._with(self._advance_job)

    def _advance_job(self, j):
        if self._status == "manufacturing":
            if ui.ask_yes_no(self, f"عملية {j['customer_name']} خلصت تصنيع وتروح التركيبات؟"):
                self.run_action(lambda: self.backend.finish_manufacturing(j["id"]))
            return
        self.form(f"✅ تسليم {j['customer_name']}", [
            {"key": "craftsman", "label": "الصنايعى *", "type": "combo_edit",
             "options": [r["name"] for r in self.app.lookups.get("staff", [])
                         if r["kind"] == "craftsman" and is_active_row(r)]},
            {"key": "collected", "label": "المحصّل من العميل *", "default": f"{num(j['remaining']):g}"},
            {"key": "method", "label": "طريقة الدفع *", "type": "combo", "options": self.app.options("payment_methods")},
        ], lambda v: self.backend.finish_installation(
            j["id"], parse_amount(v["collected"], "المحصّل", allow_zero=True), v["method"], v["craftsman"]),
            submit_text="💾 تأكيد وإرسال للحسابات", color=GREEN)

    def _note(self):
        self._with(lambda j: self.form(f"📝 ملاحظة — {j['customer_name']}", [
            {"key": "note", "label": "الملاحظة", "default": j.get("note") or ""},
        ], lambda v: self.backend.set_job_note(j["id"], v["note"]), color=AMBER))


# ============================================================
#                       تأكيد الحسابات
# ============================================================

class AccountsPage(BasePage):
    PAGE = "accounts"
    TITLE = "✅ تأكيد الحسابات"

    def __init__(self, app):
        super().__init__(app)
        self._adv, self._final = {}, {}
        can_e, can_d = self.me.can_edit(self.PAGE), self.me.can_delete(self.PAGE)

        def bar(title_lbl, confirm_text, confirm, table_fn, items_fn):
            buttons = [ui.button(confirm_text, "green", confirm)] if can_e else []
            if can_e:
                buttons.append(ui.button("✏️ تعديل", "blue",
                                         lambda: self._with(table_fn(), items_fn(), lambda j: edit_job_form(self, j))))
            if can_d:
                buttons.append(ui.button("🗑️ مسح", "red",
                                         lambda: self._with(table_fn(), items_fn(), lambda j: delete_job(self, j))))
            buttons.append(ui.button("📎 الفواتير", "light",
                                     lambda: self._with(table_fn(), items_fn(), lambda j: open_invoices(self, j))))
            return ui.hbox(title_lbl, None, *buttons)

        self._adv_title = ui.section_title("")
        self.body.addLayout(bar(self._adv_title, "✅ تأكيد استلام المقدم", self._confirm_advance,
                                lambda: self._adv_table, lambda: self._adv))
        self._adv_table = DataTable([("العميل", "text"), ("الموبايل", "text"), ("النوع", "text"),
                                     ("السيلز", "text"), ("السعر", "money"), ("المقدم", "money"),
                                     ("طريقة الدفع", "text"), ("الفرع", "wide")])
        self.body.addWidget(self._adv_table, 1)
        self._final_title = ui.section_title("")
        self.body.addLayout(bar(self._final_title, "✅ تأكيد نهائى", self._confirm_final,
                                lambda: self._final_table, lambda: self._final))
        self._final_table = DataTable([("العميل", "text"), ("الموبايل", "text"), ("الصنايعى", "text"),
                                       ("السعر", "money"), ("المقدم", "money"), ("المحصّل", "money"),
                                       ("طريقة الدفع", "text"), ("الفرع", "wide")])
        self.body.addWidget(self._final_table, 1)

    def load(self):
        return self.backend.jobs(["awaiting_advance", "awaiting_accounts"])

    def render(self, rows):
        adv = [j for j in rows if j["status"] == "awaiting_advance"]
        final = [j for j in rows if j["status"] == "awaiting_accounts"]
        self._adv, self._final = {j["id"]: j for j in adv}, {j["id"]: j for j in final}
        self._adv_title.setText(f"1️⃣ مقدم التعاقدات ({len(adv)})")
        self._final_title.setText(f"2️⃣ الحساب النهائى بعد التركيب ({len(final)})")
        self._adv_table.set_rows([{"key": j["id"], "values": [
            j["customer_name"], j.get("customer_mobile"), j.get("product_type"), j.get("seller_name"),
            num(j["price"]), num(j["advance"]), j.get("advance_method"), j.get("branch_name")]} for j in adv])
        self._final_table.set_rows([{"key": j["id"], "values": [
            j["customer_name"], j.get("customer_mobile"), j.get("craftsman"), num(j["price"]), num(j["advance"]),
            num(j.get("final_collected")), j.get("final_method"), j.get("branch_name")]} for j in final])

    def _with(self, table, items, func):
        j = self.selected(table, items, "اختار عملية من الجدول الأول")
        if j:
            func(j)

    def _confirm_advance(self):
        def go(j):
            msg = f"استلمت مقدم {j['customer_name']}: {money(j['advance'])} ({j.get('advance_method') or '—'})؟\n" \
                  "هيتسجل فى الخزينة والعملية هتدخل التصنيع."
            if ui.ask_yes_no(self, msg):
                self.run_action(lambda: self.backend.confirm_advance(j["id"]))
        self._with(self._adv_table, self._adv, go)

    def _confirm_final(self):
        def go(j):
            msg = f"استلمت من {j['customer_name']}: {money(j.get('final_collected'))} " \
                  f"({j.get('final_method') or '—'})؟\nهيتسجل فى الخزينة والعملية هتتقفل."
            if ui.ask_yes_no(self, msg):
                self.run_action(lambda: self.backend.confirm_final(j["id"]),
                                "✅ اتقفل الحساب والعملية اتنقلت للمبيعات")
        self._with(self._final_table, self._final, go)


# ============================================================
#                       فريق العمل
# ============================================================

class StaffPage(ScrollPage):
    PAGE = "staff"
    TITLE = "👥 فريق العمل"

    def load(self):
        lookups = self.backend.load_lookups()
        return lookups["staff"], self.backend.jobs(["awaiting_advance", "manufacturing", "installing",
                                                    "awaiting_accounts", "completed"])

    def render(self, data):
        staff, jobs = data
        self.app.lookups["staff"] = staff
        page = self.new_content()
        buttons = [ui.button("➕ إضافة", "purple", self._add)] if self.me.can_edit(self.PAGE) else []
        page.addLayout(ui.hbox(ui.section_title(f"👤 فريق العمل ({len(staff)})"), None, *buttons))

        today = date.today()
        stats = {}
        for j in jobs:
            s = stats.setdefault(j.get("seller_id"), {"active": 0, "done": 0, "sales": 0.0, "collected": 0.0})
            if j["status"] == "completed":
                s["done"] += 1
            else:
                s["active"] += 1
            if str(j["created_at"])[:7] == today.strftime("%Y-%m"):
                s["sales"] += num(j["price"])
                s["collected"] += num(j["advance"]) + (num(j.get("final_collected")) if j["status"] == "completed" else 0)

        table = DataTable([("الاسم", "wide"), ("النوع", "text"), ("الموبايل", "text"), ("تاريخ التعيين", "date"),
                           ("عمليات شغالة", "int"), ("عمليات مكتملة", "int")], min_height=240)
        table.set_rows([{"key": s["id"], "color": None if is_active_row(s) else ui.GRAY, "values": [
            s["name"], STAFF_KINDS.get(s.get("kind"), s.get("kind")), s.get("mobile"),
            iso_to_display(s.get("hired_on")), stats.get(s["id"], {}).get("active", 0),
            stats.get(s["id"], {}).get("done", 0)]} for s in staff])
        page.addWidget(table)

        sellers = [(s["name"], stats.get(s["id"])) for s in staff if s.get("kind") == "sales"]
        sellers = [(n, st) for n, st in sellers if st and (st["sales"] or st["collected"])]
        page.addWidget(ui.section_title("📈 مبيعات الشهر الحالى لكل سيلز"))
        if not sellers:
            page.addWidget(ui.muted("مفيش تعاقدات الشهر ده لسه"))
        mx = max([1] + [max(st["sales"], st["collected"]) for _, st in sellers])
        for name, st in sorted(sellers, key=lambda x: -x[1]["sales"]):
            b = Box(name, BLUE)
            b.body.addWidget(BarRow("قيمة التعاقدات", st["sales"], mx, BLUE))
            b.body.addWidget(BarRow("اتحصّل منها", st["collected"], mx, GREEN))
            page.addWidget(b)
        page.addStretch(1)

    def _add(self):
        self.form("➕ إضافة لفريق العمل", [
            {"key": "name", "label": "الاسم *"},
            {"key": "kind", "label": "النوع", "type": "combo", "options": [(v, k) for k, v in STAFF_KINDS.items()]},
            {"key": "mobile", "label": "الموبايل"},
            {"key": "hired", "label": "تاريخ التعيين", "default": today_text()},
        ], lambda v: self.backend.add_staff(v["name"], v["mobile"], v["kind"], parse_user_date(v["hired"])),
            color=PURPLE)
