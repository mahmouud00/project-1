"""
pages_money.py
--------------
صفحات الفلوس: الداش بورد، الخزينة، الموردين، الشيكات.
"""

from PySide6.QtWidgets import QComboBox, QDialog, QGridLayout, QLineEdit, QVBoxLayout, QWidget

import qt_widgets as ui
from qt_widgets import (BasePage, ScrollPage, DataTable, Box, BarRow, FormDialog, fill_combo, combo_value,
                        BLUE, GREEN, RED, AMBER, PURPLE, TEAL, money, today_text)
from models import (CHANNEL_LABELS, STATUS_LABELS, SUPPLIER_TXN_LABELS, num, iso_to_display, iso_date, month_label,
                    parse_amount, AppError)


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
        if app.multi_branch():
            self.body.insertLayout(0, ui.hbox(ui.label("الفرع:"), self._branch))

    def load(self):
        return self.backend.dashboard(branch_id=self._branch_id)

    def render(self, data):
        k = data["kpis"]
        page = self.new_content()
        rebh, raseed = num(k.get("rebh")), num(k.get("raseed"))
        page.addWidget(ui.cards_grid([
            ("رصيد الخزينة", money(raseed), GREEN if raseed >= 0 else RED),
            ("الوارد", money(k.get("wared")), GREEN),
            ("المنصرف", money(k.get("monsaref")), RED),
            ("صافى الربح", money(rebh), GREEN if rebh >= 0 else RED),
            ("قيمة المخزن", money(k.get("stock_value")), TEAL),
            ("طلبات شغّالة", str(int(num(k.get("open_orders")))), BLUE),
            ("قيمة الطلبات الشغّالة", money(k.get("open_value")), BLUE),
            ("المتبقى على العملاء", money(k.get("customers_remaining")), RED),
            ("طلبات متأخرة", str(int(num(k.get("late_orders")))), RED if k.get("late_orders") else GREEN),
            ("جاهز ومستنى العميل", str(int(num(k.get("ready_orders")))), PURPLE),
            ("تسليمها الأسبوع ده", str(int(num(k.get("due_week")))), AMBER),
            ("مستحق للموردين", money(k.get("suppliers_due")), RED),
            ("شيكات لسه متصرفتش", money(k.get("cheques_due")), AMBER),
            ("خامات قربت تخلص", str(int(num(k.get("low_stock")))), RED if k.get("low_stock") else GREEN),
            ("عدد قيود الخزينة", str(int(num(k.get("amaliyat")))), BLUE),
        ]))
        start = self.me.get_company().get("profit_start_date")
        page.addWidget(ui.muted("صافى الربح = وارد إدارات المبيعات − منصرف الإدارات اللى بتدخل فى التكلفة"
                                + (f" (من {iso_to_display(start)})" if start else "")
                                + ". تقدر تغيّر الإدارات دى من الإعدادات."))

        stages = k.get("stages") or {}
        if any(stages.values()):
            page.addWidget(ui.section_title("🧵 الطلبات فى كل مرحلة"))
            b = Box()
            mx = max(stages.values()) or 1
            for key, count in stages.items():
                b.body.addWidget(BarRow(STATUS_LABELS.get(key, key), count, mx, PURPLE, str(count)))
            page.addWidget(b)

        late = data.get("late") or []
        if late:
            page.addWidget(ui.section_title(f"⏰ طلبات فات ميعاد تسليمها ({len(late)})"))
            t = DataTable([("رقم", "int"), ("العميل", "text"), ("الموبايل", "text"), ("النوع", "text"),
                           ("ميعاد التسليم", "date"), ("المرحلة", "wide")], min_height=150)
            t.set_rows([{"key": o["id"], "color": RED, "values": [
                o["id"], o["customer_name"], o.get("customer_mobile"), o.get("garment_type"),
                iso_to_display(o.get("due_date")), o["status_label"]]} for o in late])
            page.addWidget(t)

        rows = data["treasury"]
        channels = {}
        for r in rows:
            name = CHANNEL_LABELS.get(r.get("channel"), "غير محدد")
            c = channels.setdefault(name, [0.0, 0.0])
            c[0] += num(r.get("amount_in"))
            c[1] += num(r.get("amount_out"))
        if channels:
            page.addWidget(ui.section_title("💵 الفلوس حسب طريقة الدفع"))
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

        sellers = data.get("sellers") or []
        if sellers:
            page.addWidget(ui.section_title("🏆 مبيعات الشهر الحالى لكل سيلز"))
            b = Box()
            mx = max(num(s["total"]) for s in sellers) or 1
            for s in sellers:
                b.body.addWidget(BarRow(f"{s['name']} ({s['orders']} طلب)", num(s["total"]), mx, BLUE))
            page.addWidget(b)

        profit = data["profit"]
        if profit:
            page.addWidget(ui.section_title("📈 صافى الربح الشهرى"))
            mx = max([1] + [max(num(m["sales"]), num(m["expenses"]), abs(num(m["profit"]))) for m in profit])
            for m in reversed(profit[-12:]):
                p = num(m["profit"])
                b = Box(month_label(m["month"]), GREEN if p >= 0 else RED)
                b.body.addWidget(BarRow("المبيعات", num(m["sales"]), mx, BLUE))
                b.body.addWidget(BarRow("التكاليف", num(m["expenses"]), mx, RED))
                b.body.addWidget(BarRow("صافى الربح", abs(p), mx, GREEN if p >= 0 else RED))
                page.addWidget(b)

        monthly = data["orders_by_month"]
        if monthly:
            page.addWidget(ui.section_title("📑 قيمة الطلبات الجديدة كل شهر"))
            page.addWidget(ui.muted("دوس على أى شهر عشان تشوف الطلبات"))
            mx = max(num(m["total_value"]) for m in monthly) or 1
            for m in reversed(monthly[-12:]):
                b = Box(f"{month_label(m['month'])} — {m['orders']} طلب", PURPLE, clickable=True)
                b.body.addWidget(BarRow("إجمالى القيمة", num(m["total_value"]), mx, PURPLE))
                b.on_click(lambda mo=m["month"]: MonthOrdersDialog(self, self.app, mo, self._branch_id))
                page.addWidget(b)
        page.addStretch(1)


class MonthOrdersDialog(QDialog):
    def __init__(self, parent, app, month, branch_id):
        super().__init__(parent)
        self._month = str(month)[:7]
        self.setWindowTitle(f"طلبات {month_label(month)}")
        self.resize(860, 480)
        lay = QVBoxLayout(self)
        self._title = ui.section_title("جارى التحميل…")
        lay.addWidget(self._title)
        self._table = DataTable([("رقم", "int"), ("العميل", "wide"), ("الموبايل", "text"), ("السيلز", "text"),
                                 ("النوع", "text"), ("السعر", "money"), ("الحالة", "text")])
        lay.addWidget(self._table)
        self.show()
        app.worker.run(lambda: app.backend.orders(branch_id=branch_id), self._render)

    def _render(self, orders):
        rows = [o for o in orders if str(o["created_at"])[:7] == self._month]
        self._title.setText(f"👤 الطلبات ({len(rows)}) — الإجمالى {money(sum(num(o['price']) for o in rows))}")
        colors = {"completed": GREEN, "awaiting_deposit": AMBER}
        self._table.set_rows([{"key": o["id"], "color": colors.get(o["status"], BLUE), "values": [
            o["id"], o["customer_name"], o.get("customer_mobile"), o.get("seller_name"), o.get("garment_type"),
            o["price"], o["status_label"]]} for o in rows])


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
            self._counterparty = QLineEdit()
            self._counterparty.setPlaceholderText("الجهة (اختيارى)")
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
            grid.addWidget(ui.label("الجهة"), 1, 6)
            grid.addWidget(self._counterparty, 1, 7)
            if app.multi_branch():
                grid.addWidget(ui.label("الفرع"), 2, 0)
                grid.addWidget(self._entry_branch, 2, 1)
            box.body.addLayout(grid)
            self._save_btn = ui.button("💾 حفظ القيد", "green", self._save)
            self._form_msg = ui.label("")
            box.body.addLayout(ui.hbox(self._save_btn, self._form_msg))
            self.body.addWidget(box)
            app.add_lookups_listener(self._fill_form_lists)

        self._search = ui.search_box("🔍 بحث فى الوصف أو الجهة أو الإدارة", self._render_table)
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
                                 ("الجهة", "text"), ("الفرع", "text"), ("سجّله", "text")])
        self.body.addWidget(self._table, 1)

    def _fill_form_lists(self):
        fill_combo(self._method, self.app.options("payment_methods"))
        fill_combo(self._dept, [("— بدون —", None)] + self.app.options("departments"))
        fill_combo(self._entry_branch, self.app.branch_options())

    def load(self):
        return self.backend.treasury(branch_id=self._branch_id)

    def render(self, rows):
        self._rows = rows
        self._by_id = {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        text = self._search.text()
        shown = [r for r in self._rows if ui.matches(text, r, ("description", "counterparty", "department"))]
        w_in = sum(num(r["amount_in"]) for r in shown)
        w_out = sum(num(r["amount_out"]) for r in shown)
        self._totals.setText(f"{len(shown)} قيد · وارد {money(w_in)} · منصرف {money(w_out)} · الرصيد {money(w_in - w_out)}")
        self._table.set_rows([{
            "key": r["id"], "color": GREEN if num(r["amount_in"]) else RED,
            "values": [r["id"], iso_to_display(r["entry_date"]), r["description"],
                       num(r["amount_in"]) or "", num(r["amount_out"]) or "", r.get("payment_method"),
                       r.get("department"), r.get("counterparty"), r.get("branch_name"), r.get("user_name")],
        } for r in shown])

    def _save(self):
        if not self._save_btn.isEnabled():
            return
        try:
            amount = parse_amount(self._amount.text())
            entry_date = iso_date(self._date.text())
        except AppError as e:
            self._form_msg.setStyleSheet(f"color: {RED};")
            self._form_msg.setText(f"❌ {e}")
            return
        args = dict(direction=combo_value(self._direction), amount=amount, description=self._desc.text(),
                    payment_method_id=combo_value(self._method), department_id=combo_value(self._dept),
                    entry_date=entry_date, branch_id=combo_value(self._entry_branch),
                    counterparty=self._counterparty.text())
        self._save_btn.setEnabled(False)
        self._save_btn.setText("جارى الحفظ…")

        def ok(entry_id):
            self._save_btn.setEnabled(True)
            self._save_btn.setText("💾 حفظ القيد")
            self._amount.clear()
            self._desc.clear()
            self._counterparty.clear()
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
            ], lambda v: self.backend.update_treasury_department(entry_id=r["id"], department_id=v["dept"]))

    def _delete(self):
        r = self.selected(self._table, self._by_id, "اختار قيد من الجدول الأول")
        if not r or not ui.ask_yes_no(self, f"هتمسح القيد رقم {r['id']} ({r['description']}).\nمتأكد؟"):
            return

        def done(linked):
            if linked:
                ui.show_info(self, f"اتمسح القيد، واتمسح معاه {linked} حركة مرتبطة بيه (مورد أو أجور)")
            self.app.after_change()
        self.app.worker.run(lambda: self.backend.delete_treasury_entry(entry_id=r["id"]), done,
                            lambda e: ui.show_error(self, e))


# ============================================================
#                       الموردين
# ============================================================

def add_supplier_form(page, then=None):
    page.form("➕ مورد جديد", [
        {"key": "name", "label": "اسم المورد *"},
        {"key": "material", "label": "بيورّد إيه (قماش، بطانة، إكسسوار...)"},
        {"key": "mobile", "label": "الموبايل"},
        {"key": "type", "label": "النوع", "type": "combo", "options": ["تاجر جملة", "مصنع", "مستورد", "أخرى"]},
    ], lambda v: page.backend.add_supplier(name=v["name"], material=v["material"], mobile=v["mobile"],
                                           supplier_type=v["type"]), color=GREEN, then=then)


class SuppliersPage(BasePage):
    PAGE = "suppliers"
    TITLE = "🏗️ الموردين"

    def __init__(self, app):
        super().__init__(app)
        self._by_id = {}
        self._count = ui.section_title("")
        buttons = [ui.button("📂 فتح حساب المورد", "blue", self._open)]
        if self.me.can_edit(self.PAGE):
            buttons.insert(0, ui.button("➕ إضافة مورد", "green", lambda: add_supplier_form(self)))
        self.body.addLayout(ui.hbox(self._count, None, *buttons))
        self.body.addWidget(ui.muted("💡 دوس مرتين على أى مورد عشان تفتح حسابه وتسجّل فاتورة أو دفعة أو شيك. "
                                     "استلام الخامات من صفحة المخزن بيسجّل الفاتورة على المورد أوتوماتيك."))
        self._table = DataTable([("المورد", "wide"), ("الخامة", "text"), ("الموبايل", "text"),
                                 ("الفواتير", "money"), ("مرتجع", "money"), ("مدفوع نقدى", "money"),
                                 ("مدفوع بنك", "money"), ("شيكات مستحقة", "money"), ("المتبقى", "money")])
        self._table.cellDoubleClicked.connect(lambda r, c: self._open())
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.supplier_balances()

    def render(self, rows):
        self._by_id = {r["id"]: r for r in rows}
        total = sum(num(r["remaining"]) for r in rows)
        self._count.setText(f"{len(rows)} مورد · المستحق عليك {money(total)}")
        self._table.set_rows([{
            "key": r["id"], "color": GREEN if num(r["remaining"]) <= 0 else RED,
            "values": [r["name"], r.get("material"), r.get("mobile"), num(r["invoices"]), num(r["returns"]),
                       num(r["cash_paid"]), num(r["bank_paid"]), num(r["cheques_due"]), num(r["remaining"])],
        } for r in rows])

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
                                              lambda tt=t: self._add_txn(tt))
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
                     self._app.backend.supplier_txns(supplier_id=sid)), self._render)

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
            due = iso_date(v.get("due")) if txn_type == "cheque" else None
            if txn_type == "cheque" and due is None:
                raise AppError("تاريخ استحقاق الشيك مطلوب")
            return self._app.backend.add_supplier_txn(
                supplier_id=self._s["id"], txn_type=txn_type, amount=parse_amount(v["amount"]),
                description=v.get("desc"), cheque_no=v.get("cheque_no"), due_date=due)

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
        self._title.setText(f"💳 شيكات لسه متصرفتش ({len(rows)}) · {money(sum(num(r['amount']) for r in rows))}")
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
