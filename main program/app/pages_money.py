"""
pages_money.py
--------------
صفحات الفلوس: الداش بورد، الخزينة، الموردين، الشيكات.
"""

from PySide6.QtWidgets import QComboBox, QDialog, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import qt_widgets as ui
from qt_widgets import (BasePage, ScrollPage, DataTable, Box, BarRow, FormDialog, fill_combo, combo_value,
                        NAVY, BLUE, GREEN, RED, AMBER, PURPLE, money, today_text)
from models import (CHANNEL_LABELS, STATUS_LABELS, SUPPLIER_TXN_LABELS, num, iso_to_display, month_label,
                    parse_amount, parse_user_date, AppError)


def branch_filter(page, on_change):
    """قايمة "كل الفروع / فرع معين" - بتظهر بس لو الشركة عندها أكتر من فرع.
    الفرع المختار بيتحفظ فى page._branch_id من الـ main thread، عشان load() (اللى بتشتغل
    فى الخلفية) متلمسش الواجهة - Qt مش بيحب حد يلمس الـ widgets من thread تانى."""
    combo = QComboBox()
    fill_combo(combo, page.app.branch_options(with_all=True))
    page._branch_id = None

    def changed(_index):
        page._branch_id = combo_value(combo)
        on_change()

    combo.currentIndexChanged.connect(changed)
    combo.setVisible(page.app.multi_branch())
    return combo


# ============================================================
#                       الداش بورد
# ============================================================

class DashboardPage(ScrollPage):
    PAGE = "dashboard"
    TITLE = "📊 الداش بورد"

    def __init__(self, app):
        super().__init__(app)
        self._branch = branch_filter(self, self.refresh)
        self.body.insertLayout(0, ui.hbox(ui.label("الفرع:"), self._branch) if app.multi_branch() else ui.hbox())

    def load(self):
        return self.backend.dashboard(self._branch_id)

    def render(self, data):
        k = data["kpis"]
        page = self.new_content()
        rebh, raseed = num(k.get("rebh")), num(k.get("raseed"))
        page.addWidget(ui.cards_grid([
            ("رصيد الخزينة", money(raseed), GREEN if raseed >= 0 else RED),
            ("الوارد", money(k.get("wared")), GREEN),
            ("المنصرف", money(k.get("monsaref")), RED),
            ("عدد القيود", str(int(num(k.get("amaliyat")))), BLUE),
            ("صافى الربح", money(rebh), GREEN if rebh >= 0 else RED),
            ("عمليات شغالة", str(int(num(k.get("open_jobs")))), BLUE),
            ("قيمة العمليات الشغالة", money(k.get("open_value")), BLUE),
            ("المتبقى على العملاء", money(k.get("customers_remaining")), RED),
            ("مستحق للموردين", money(k.get("suppliers_due")), RED),
            ("شيكات لسه متصرفتش", money(k.get("cheques_due")), AMBER),
        ]))
        start = self.me.get_company().get("profit_start_date")
        page.addWidget(ui.muted("صافى الربح = وارد إدارات المبيعات − منصرف الإدارات اللى بتدخل فى التكلفة"
                                + (f" (من {iso_to_display(start)})" if start else "")
                                + ". تقدر تغيّر الإدارات دى من الإعدادات."))

        rows = data["treasury"]
        channels = {}
        for r in rows:
            name = CHANNEL_LABELS.get(r.get("channel"), "غير محدد")
            c = channels.setdefault(name, [0.0, 0.0])
            c[0] += num(r.get("amount_in"))
            c[1] += num(r.get("amount_out"))
        if channels:
            page.addWidget(ui.section_title("📊 الفلوس حسب طريقة الدفع"))
            grid_w = QWidget()
            grid = QGridLayout(grid_w)
            grid.setContentsMargins(0, 0, 0, 0)
            mx = max(max(v) for v in channels.values()) or 1
            for i, (name, (w_in, w_out)) in enumerate(sorted(channels.items(), key=lambda x: x[1][1] - x[1][0])):
                bal = w_in - w_out
                b = Box(name, GREEN if bal >= 0 else RED)
                b.body.addWidget(BarRow("وارد", w_in, mx, GREEN))
                b.body.addWidget(BarRow("منصرف", w_out, mx, RED))
                b.body.addLayout(ui.kv_row("الرصيد", money(bal), GREEN if bal >= 0 else RED))
                grid.addWidget(b, i // 2, i % 2)
            page.addWidget(grid_w)

        depts = {}
        for r in rows:
            if num(r.get("amount_out")) > 0 and r.get("department"):
                depts[r["department"]] = depts.get(r["department"], 0.0) + num(r["amount_out"])
        if depts:
            page.addWidget(ui.section_title("🏢 المصروف حسب الإدارة"))
            b = Box()
            mx = max(depts.values()) or 1
            for name, value in sorted(depts.items(), key=lambda x: -x[1]):
                b.body.addWidget(BarRow(name, value, mx, PURPLE))
            page.addWidget(b)

        profit = data["profit"]
        if profit:
            page.addWidget(ui.section_title("📈 صافى الربح الشهرى"))
            mx = max([1] + [max(num(m["sales"]), num(m["expenses"]), abs(num(m["profit"]))) for m in profit])
            for m in profit:
                p = num(m["profit"])
                b = Box(month_label(m["month"]), GREEN if p >= 0 else RED)
                b.body.addWidget(BarRow("المبيعات", num(m["sales"]), mx, BLUE))
                b.body.addWidget(BarRow("التكاليف", num(m["expenses"]), mx, RED))
                b.body.addWidget(BarRow("صافى الربح", abs(p), mx, GREEN if p >= 0 else RED))
                page.addWidget(b)

        contracts = data["contracts"]
        if contracts:
            page.addWidget(ui.section_title("📑 قيمة التعاقدات كل شهر"))
            page.addWidget(ui.muted("دوس على أى شهر عشان تشوف العملاء"))
            mx = max(num(m["total_value"]) for m in contracts) or 1
            for m in contracts:
                b = Box(f"{month_label(m['month'])} — {m['contracts']} تعاقد", PURPLE, clickable=True)
                b.body.addWidget(BarRow("إجمالى القيمة", num(m["total_value"]), mx, PURPLE))
                b.on_click(lambda mo=m["month"]: MonthJobsDialog(self, self.app, mo, self._branch_id))
                page.addWidget(b)
        page.addStretch(1)


class MonthJobsDialog(QDialog):
    def __init__(self, parent, app, month, branch_id):
        super().__init__(parent)
        self._month = str(month)[:7]
        self.setWindowTitle(f"تعاقدات {month_label(month)}")
        self.resize(820, 460)
        lay = QVBoxLayout(self)
        self._title = ui.section_title("جارى التحميل…")
        lay.addWidget(self._title)
        self._table = DataTable([("العميل", "wide"), ("الموبايل", "text"), ("السيلز", "text"),
                                 ("النوع", "text"), ("السعر", "money"), ("الحالة", "text")])
        lay.addWidget(self._table)
        self.show()
        app.worker.run(lambda: app.backend.jobs(list(STATUS_LABELS), branch_id), self._render)

    def _render(self, jobs):
        rows = [j for j in jobs if j["kind"] == "contract" and str(j["created_at"])[:7] == self._month]
        self._title.setText(f"👤 العملاء ({len(rows)})")
        colors = {"completed": GREEN, "awaiting_advance": AMBER}
        self._table.set_rows([{"key": j["id"], "color": colors.get(j["status"], BLUE), "values": [
            j["customer_name"], j.get("customer_mobile"), j.get("seller_name"), j.get("product_type"),
            j["price"], j["status_label"]]} for j in rows])


# ============================================================
#                       الخزينة
# ============================================================

class TreasuryPage(BasePage):
    PAGE = "treasury"
    TITLE = "💰 الخزينة"

    def __init__(self, app):
        super().__init__(app)
        self._rows = []
        self._by_id = {}

        if self.me.can_edit(self.PAGE):
            box = Box("➕ قيد جديد", GREEN)
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            self._direction = QComboBox()
            fill_combo(self._direction, [("وارد (مدين)", "in"), ("منصرف (دائن)", "out")])
            self._amount = QLineEdit()
            self._amount.setPlaceholderText("المبلغ")
            self._method = QComboBox()
            self._date = QLineEdit(today_text())
            self._desc = QLineEdit()
            self._desc.setPlaceholderText("وصف القيد")
            self._dept = QComboBox()
            self._entry_branch = QComboBox()
            self._fill_form_lists()
            cells = [("النوع", self._direction), ("المبلغ", self._amount), ("طريقة الدفع", self._method),
                     ("التاريخ", self._date)]
            for col, (title, w) in enumerate(cells):
                grid.addWidget(ui.label(title), 0, col * 2)
                grid.addWidget(w, 0, col * 2 + 1)
            grid.addWidget(ui.label("الوصف"), 1, 0)
            grid.addWidget(self._desc, 1, 1, 1, 3)
            grid.addWidget(ui.label("الإدارة"), 1, 4)
            grid.addWidget(self._dept, 1, 5)
            if app.multi_branch():
                grid.addWidget(ui.label("الفرع"), 1, 6)
                grid.addWidget(self._entry_branch, 1, 7)
            box.body.addLayout(grid)
            self._save_btn = ui.button("💾 حفظ القيد", "green", self._save)
            self._form_msg = ui.label("")
            box.body.addLayout(ui.hbox(self._save_btn, self._form_msg))
            self.body.addWidget(box)
            app.add_lookups_listener(self._fill_form_lists)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 بحث فى الوصف أو الجهة أو الإدارة")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(300)
        self._search.textChanged.connect(self._render_table)
        self._branch = branch_filter(self, self.refresh)
        self._totals = ui.label("", "muted")
        buttons = []
        if self.me.can_edit(self.PAGE):
            buttons.append(ui.button("✏️ تعديل الإدارة", "blue", self._edit_dept))
        if self.me.can_delete(self.PAGE):
            buttons.append(ui.button("🗑️ مسح المحدد", "red", self._delete))
        self.body.addLayout(ui.hbox(self._search, self._branch, self._totals, None, *buttons))
        self._table = DataTable([("رقم", "int"), ("التاريخ", "date"), ("الوصف", "wide"), ("وارد", "money"),
                                 ("منصرف", "money"), ("طريقة الدفع", "text"), ("الإدارة", "text"),
                                 ("الجهة", "text"), ("الفرع", "text")])
        self.body.addWidget(self._table, 1)

    def _fill_form_lists(self):
        fill_combo(self._method, self.app.options("payment_methods"))
        fill_combo(self._dept, [("— بدون —", None)] + self.app.options("departments"))
        fill_combo(self._entry_branch, self.app.branch_options())

    def load(self):
        return self.backend.treasury(self._branch_id)

    def render(self, rows):
        self._rows = rows
        self._by_id = {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        text = self._search.text().strip()
        shown = [r for r in self._rows if not text or any(
            text in str(r.get(k) or "") for k in ("description", "counterparty", "department"))]
        self._totals.setText(f"{len(shown)} قيد · وارد {money(sum(num(r['amount_in']) for r in shown))}"
                             f" · منصرف {money(sum(num(r['amount_out']) for r in shown))}")
        self._table.set_rows([{
            "key": r["id"], "color": GREEN if num(r["amount_in"]) else RED,
            "values": [r["id"], iso_to_display(r["entry_date"]), r["description"],
                       num(r["amount_in"]) or "", num(r["amount_out"]) or "", r.get("payment_method"),
                       r.get("department"), r.get("counterparty"), r.get("branch_name")],
        } for r in shown])

    def _save(self):
        if not self._save_btn.isEnabled():
            return
        try:
            amount = parse_amount(self._amount.text())
            entry_date = parse_user_date(self._date.text())
        except AppError as e:
            self._form_msg.setStyleSheet(f"color: {RED};")
            self._form_msg.setText(f"❌ {e}")
            return
        args = dict(direction=combo_value(self._direction), amount=amount, description=self._desc.text(),
                    payment_method_id=combo_value(self._method), department_id=combo_value(self._dept),
                    entry_date=entry_date, branch_id=combo_value(self._entry_branch))
        self._save_btn.setEnabled(False)
        self._save_btn.setText("جارى الحفظ…")

        def ok(entry_id):
            self._save_btn.setEnabled(True)
            self._save_btn.setText("💾 حفظ القيد")
            self._amount.clear()
            self._desc.clear()
            self._form_msg.setStyleSheet(f"color: {GREEN};")
            self._form_msg.setText(f"✅ اتسجل برقم {entry_id}")
            self.app.after_change()

        def fail(e):
            self._save_btn.setEnabled(True)
            self._save_btn.setText("💾 حفظ القيد")
            self._form_msg.setStyleSheet(f"color: {RED};")
            self._form_msg.setText(f"❌ {e}")

        self.app.worker.run(lambda: self.backend.add_treasury_entry(**args), ok, fail)

    def _edit_dept(self):
        r = self.selected(self._table, self._by_id, "اختار قيد من الجدول الأول")
        if r:
            self.form(f"✏️ إدارة القيد: {r['description']}", [
                {"key": "dept", "label": "الإدارة", "type": "combo",
                 "options": [("— بدون —", None)] + self.app.options("departments"),
                 "default": r.get("department_id")},
            ], lambda v: self.backend.update_treasury_department(r["id"], v["dept"]))

    def _delete(self):
        r = self.selected(self._table, self._by_id, "اختار قيد من الجدول الأول")
        if not r or not ui.ask_yes_no(self, f"هتمسح القيد رقم {r['id']} ({r['description']}).\nمتأكد؟"):
            return

        def done(linked):
            if linked:
                ui.show_info(self, f"اتمسح القيد، واتمسح معاه {linked} حركة مورد مرتبطة بيه")
            self.app.after_change()
        self.app.worker.run(lambda: self.backend.delete_treasury_entry(r["id"]), done,
                            lambda e: ui.show_error(self, e))


# ============================================================
#                       الموردين
# ============================================================

class SuppliersPage(BasePage):
    PAGE = "suppliers"
    TITLE = "🏗️ الموردين"

    def __init__(self, app):
        super().__init__(app)
        self._by_id = {}
        self._count = ui.section_title("")
        buttons = [ui.button("📂 فتح حساب المورد", "blue", self._open)]
        if self.me.can_edit(self.PAGE):
            buttons.insert(0, ui.button("➕ إضافة مورد", "green", self._add))
        self.body.addLayout(ui.hbox(self._count, None, *buttons))
        self.body.addWidget(ui.muted("💡 دوس مرتين على أى مورد عشان تفتح حسابه وتسجّل فاتورة أو دفعة أو شيك"))
        self._table = DataTable([("المورد", "wide"), ("الخامة", "text"), ("الموبايل", "text"),
                                 ("الفواتير", "money"), ("مدفوع نقدى", "money"), ("مدفوع بنك", "money"),
                                 ("شيكات مستحقة", "money"), ("المتبقى", "money")])
        self._table.cellDoubleClicked.connect(lambda r, c: self._open())
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.supplier_balances()

    def render(self, rows):
        self._by_id = {r["id"]: r for r in rows}
        self._count.setText(f"{len(rows)} مورد")
        self._table.set_rows([{
            "key": r["id"], "color": GREEN if num(r["remaining"]) <= 0 else RED,
            "values": [r["name"], r.get("material"), r.get("mobile"), num(r["invoices"]), num(r["cash_paid"]),
                       num(r["bank_paid"]), num(r["cheques_due"]), num(r["remaining"])],
        } for r in rows])

    def _add(self):
        self.form("➕ مورد جديد", [
            {"key": "name", "label": "اسم المورد *"},
            {"key": "material", "label": "الخامة"},
            {"key": "mobile", "label": "الموبايل"},
            {"key": "type", "label": "النوع", "type": "combo", "options": ["موزع", "وكيل", "مصنع", "أخرى"]},
        ], lambda v: self.backend.add_supplier(v["name"], v["material"], v["mobile"], v["type"]), color=GREEN)

    def _open(self):
        r = self.selected(self._table, self._by_id, "اختار مورد من الجدول الأول")
        if r:
            SupplierDialog(self, self.app, r)


class SupplierDialog(QDialog):
    TXN_BUTTONS = [("invoice", "➕", "green"), ("cash_payment", "💵", "green"), ("bank_payment", "🏦", "blue"),
                   ("cheque", "💳", "amber"), ("return", "↩️", "red")]

    def __init__(self, parent, app, supplier):
        super().__init__(parent)
        self._app = app
        self._s = supplier
        self.setWindowTitle(f"حساب المورد — {supplier['name']}")
        self.resize(1000, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(supplier["name"], "pageTitle"))
        self._info = ui.label("", "muted", wrap=True)
        lay.addWidget(self._info)
        if app.me.can_edit("suppliers"):
            lay.addLayout(ui.hbox(*[ui.button(f"{icon} {SUPPLIER_TXN_LABELS[t]}", color,
                                              lambda checked=False, tt=t: self._add_txn(tt))
                                    for t, icon, color in self.TXN_BUTTONS]))
        self._title = ui.section_title("📜 سجل التعاملات — جارى التحميل…")
        lay.addWidget(self._title)
        self._table = DataTable([("التاريخ", "date"), ("النوع", "text"), ("البيان", "wide"), ("المبلغ", "money"),
                                 ("رقم الشيك", "text"), ("الاستحقاق", "date"), ("حالة الشيك", "text")])
        lay.addWidget(self._table, 1)
        self.show()
        self.refresh()

    def refresh(self):
        sid = self._s["id"]
        self._app.worker.run(
            lambda: ([r for r in self._app.backend.supplier_balances() if r["id"] == sid],
                     self._app.backend.supplier_txns(sid)), self._render)

    def _render(self, data):
        balance, txns = data
        if balance:
            b = balance[0]
            self._info.setText(f"الفواتير {money(b['invoices'])} · مرتجع {money(b['returns'])} · "
                               f"نقدى {money(b['cash_paid'])} · بنك {money(b['bank_paid'])} · "
                               f"شيكات مستحقة {money(b['cheques_due'])} · شيكات اتصرفت {money(b['cheques_cashed'])}"
                               f"  ⟵  المتبقى: {money(b['remaining'])}")
        self._title.setText(f"📜 سجل التعاملات ({len(txns)})")
        status = {"due": "مستحق", "cashed": "اتصرف"}
        self._table.set_rows([{
            "key": t["id"],
            "color": AMBER if t.get("cheque_status") == "due" else (GREEN if t.get("cheque_status") else None),
            "values": [iso_to_display(t["txn_date"]), SUPPLIER_TXN_LABELS.get(t["txn_type"], t["txn_type"]),
                       t.get("description"), num(t["amount"]), t.get("cheque_no"),
                       iso_to_display(t.get("due_date")), status.get(t.get("cheque_status"), "")],
        } for t in txns])

    def _add_txn(self, txn_type):
        fields = [{"key": "amount", "label": "المبلغ *"}, {"key": "desc", "label": "البيان"}]
        if txn_type == "cheque":
            fields += [{"key": "cheque_no", "label": "رقم الشيك"},
                       {"key": "due", "label": "تاريخ الاستحقاق * (يوم/شهر/سنة)", "default": today_text()}]
        title = f"{SUPPLIER_TXN_LABELS[txn_type]} — {self._s['name']}"
        if txn_type in ("cash_payment", "bank_payment"):
            title += "  (هتنزل فى الخزينة أوتوماتيك)"

        def action(v):
            due = parse_user_date(v.get("due")) if txn_type == "cheque" else None
            if txn_type == "cheque" and due is None:
                raise AppError("تاريخ استحقاق الشيك مطلوب")
            return self._app.backend.add_supplier_txn(self._s["id"], txn_type, parse_amount(v["amount"]),
                                                      v.get("desc"), v.get("cheque_no"), due)

        def done(_):
            self.refresh()
            self._app.after_change()

        FormDialog(self, self._app, title, fields, action, on_done=done)


# ============================================================
#                       الشيكات
# ============================================================

class ChequesPage(BasePage):
    PAGE = "cheques"
    TITLE = "💳 الشيكات"

    def __init__(self, app):
        super().__init__(app)
        self._title = ui.section_title("")
        buttons = [ui.button("⚡ صرف المستحق لحد النهارده", "amber", self._cash)] \
            if self.me.can_edit(self.PAGE) else []
        self.body.addLayout(ui.hbox(self._title, None, *buttons))
        self.body.addWidget(ui.muted("🔴 فات ميعاده   🟡 فاضل 3 أيام أو أقل   🟢 لسه بدرى"))
        self._table = DataTable([("المورد", "wide"), ("رقم الشيك", "text"), ("المبلغ", "money"),
                                 ("الاستحقاق", "date"), ("الأيام المتبقية", "int")])
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.due_cheques()

    def render(self, rows):
        self._title.setText(f"💳 شيكات لسه متصرفتش ({len(rows)})")
        self._table.set_rows([{
            "key": r["id"],
            "color": RED if r["days_left"] < 0 else (AMBER if r["days_left"] <= 3 else GREEN),
            "values": [r["supplier_name"], r.get("cheque_no"), num(r["amount"]), iso_to_display(r["due_date"]),
                       r["days_left"]],
        } for r in rows])

    def _cash(self):
        if not ui.ask_yes_no(self, "كل شيك ميعاده النهارده أو فات هيتسجل منصرف فى الخزينة.\nمتأكد؟"):
            return

        def done(n):
            ui.show_info(self, "مفيش شيكات مستحقة النهارده" if not n else f"✅ اتصرف {n} شيك")
            self.app.after_change()
        self.app.worker.run(self.backend.cash_due_cheques, done, lambda e: ui.show_error(self, e))
