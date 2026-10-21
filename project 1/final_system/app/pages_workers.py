"""
pages_workers.py
----------------
العمال والأجور:
  - كل عامل طريقة حسابه: بالقطعة، أو مرتب، أو مرتب + قطعة (الشركة بتحدد).
  - شغل القطعة بيتسجل أوتوماتيك لما العامل يخلّص مرحلة (القص/الخياطة/التشطيب)
    حسب أسعار القطعة فى الإعدادات. وتقدر تسجل شغل إضافى بإيدك.
  - كشف الأجور الشهرى: المستحق (مرتب + قطعة + مكافآت − خصومات) − المصروف (سلف + صرف) = الباقى.
  - السلفة والصرف بينزلوا منصرف فى الخزينة أوتوماتيك.
"""

from PySide6.QtWidgets import QComboBox, QDialog, QTabWidget, QVBoxLayout, QWidget

import qt_widgets as ui
from qt_widgets import BasePage, DataTable, fill_combo, combo_value, money, amount_text, today_text, \
    GREEN, RED, AMBER, PURPLE, BLUE, TEAL
from models import (PAY_TYPES, STAFF_KINDS, STAFF_TXN_LABELS, STAGE_LABELS, iso_date, iso_to_display, month_label,
                    num, parse_amount, recent_months, datetime_display)

CRAFTS = ["قصاص", "خياط", "مكوجى", "مساعد", "مشطّب", "سيلز", "محاسب", "أخرى"]


class WorkersPage(BasePage):
    PAGE = "workers"
    TITLE = "👷 العمال والأجور"

    def __init__(self, app):
        super().__init__(app)
        self._staff, self._s_by_id = [], {}
        self._pay, self._pay_by_id = [], {}
        can = self.me.can_edit(self.PAGE)
        tabs = QTabWidget()
        self.body.addWidget(tabs, 1)

        # ---------- كشف الأجور ----------
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        self._month = QComboBox()
        fill_combo(self._month, recent_months(18))
        self._month.currentIndexChanged.connect(lambda _i: self.refresh())
        self._pay_title = ui.section_title("")
        buttons = [ui.button("📜 كشف حساب العامل", "light", lambda: self._with_pay(self._statement))]
        if can:
            buttons = [ui.button("💵 صرف أجر", "green", lambda: self._with_pay(lambda r: self._txn(r, "payment"))),
                       ui.button("💸 سلفة", "amber", lambda: self._with_pay(lambda r: self._txn(r, "advance"))),
                       ui.button("🎁 مكافأة", "teal", lambda: self._with_pay(lambda r: self._txn(r, "bonus"))),
                       ui.button("➖ خصم", "red", lambda: self._with_pay(lambda r: self._txn(r, "deduction"))),
                       ui.button("✍️ شغل بالقطعة", "purple", lambda: self._with_pay(self._work))] + buttons
        l1.addLayout(ui.hbox(ui.label("الشهر:"), self._month, self._pay_title, None, *buttons))
        self._pay_totals = ui.label("", "muted")
        l1.addWidget(self._pay_totals)
        l1.addWidget(ui.muted("المستحق = المرتب + شغل القطعة + المكافآت − الخصومات · الباقى = المستحق − (السلف + "
                              "اللى اتصرف). دوس مرتين على أى عامل عشان تشوف كشف حسابه بالتفصيل."))
        self._pay_table = DataTable([("الاسم", "wide"), ("الشغلانة", "text"), ("الحساب", "text"), ("المرتب", "money"),
                                     ("قطع", "qty"), ("أجر القطعة", "money"), ("مكافآت", "money"),
                                     ("خصومات", "money"), ("المستحق", "money"), ("سلف", "money"),
                                     ("اتصرف", "money"), ("الباقى", "money")])
        self._pay_table.cellDoubleClicked.connect(lambda r, c: self._with_pay(self._statement))
        l1.addWidget(self._pay_table, 1)
        tabs.addTab(w1, "💰 كشف الأجور")

        # ---------- العمال ----------
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        self._staff_title = ui.section_title("")
        buttons = []
        if can:
            buttons = [ui.button("➕ إضافة", "green", lambda: self._staff_form()),
                       ui.button("✏️ تعديل", "blue", lambda: self._with_staff(self._staff_form))]
        l2.addLayout(ui.hbox(self._staff_title, None, *buttons))
        l2.addWidget(ui.muted("العمال بيظهروا فى صفحات القص والخياطة والتشطيب، والسيلز بيظهروا فى الطلبات. "
                              "الرمادى = موقوف (مش هيظهر فى القوايم)."))
        self._staff_table = DataTable([("الاسم", "wide"), ("النوع", "text"), ("الشغلانة", "text"),
                                       ("طريقة الحساب", "text"), ("المرتب الشهرى", "money"), ("الموبايل", "text"),
                                       ("تاريخ التعيين", "date")])
        self._staff_table.cellDoubleClicked.connect(lambda r, c: can and self._with_staff(self._staff_form))
        l2.addWidget(self._staff_table, 1)
        tabs.addTab(w2, "👷 العمال والموظفين")

    def _month_value(self):
        return combo_value(self._month)

    def load(self):
        month = self._month_value()
        return self.backend.staff_list(), self.backend.payroll(month=month)

    def render(self, data):
        staff, payroll = data
        self._staff, self._s_by_id = staff, {s["id"]: s for s in staff}
        self._pay = payroll["rows"]
        self._pay_by_id = {r["staff_id"]: r for r in self._pay}
        self._staff_title.setText(f"👷 العمال والموظفين ({sum(1 for s in staff if s['is_active'])} شغّال)")
        self._staff_table.set_rows([{"key": s["id"], "color": None if s["is_active"] else ui.GRAY, "values": [
            s["name"], STAFF_KINDS.get(s["kind"], s["kind"]), s.get("craft"), PAY_TYPES.get(s["pay_type"]),
            s["salary"] if s["pay_type"] != "piece" else "", s.get("mobile"), iso_to_display(s.get("hired_on"))]}
            for s in staff])
        self._pay_title.setText(f"كشف أجور {month_label(payroll['month'])}")
        t = {k: sum(num(r[k]) for r in self._pay) for k in ("earned", "paid", "remaining")}
        self._pay_totals.setText(f"المستحق {money(t['earned'])} · اتصرف (سلف + صرف) {money(t['paid'])} · "
                                 f"الباقى {money(t['remaining'])}")
        self._pay_table.set_rows([{
            "key": r["staff_id"],
            "color": ui.GRAY if not r["is_active"] else (RED if r["remaining"] < -0.01 else
                                                          (GREEN if abs(r["remaining"]) < 0.01 else None)),
            "values": [r["name"], r.get("craft"), PAY_TYPES.get(r["pay_type"]), r["salary"], r["pieces_qty"],
                       r["pieces"], r["bonus"], r["deduction"], r["earned"], r["advance"], r["payment"],
                       r["remaining"]]} for r in self._pay])

    def _with_pay(self, func):
        r = self.selected(self._pay_table, self._pay_by_id, "اختار عامل من الجدول الأول")
        if r:
            func(r)

    def _with_staff(self, func):
        s = self.selected(self._staff_table, self._s_by_id, "اختار من الجدول الأول")
        if s:
            func(s)

    # ---------- العمال ----------

    def _staff_form(self, s=None):
        s = s or {}
        fields = [
            {"key": "name", "label": "الاسم *", "default": s.get("name", "")},
            {"key": "kind", "label": "النوع", "type": "combo", "options": [(v, k) for k, v in STAFF_KINDS.items()],
             "default": s.get("kind", "worker")},
            {"key": "craft", "label": "الشغلانة", "type": "combo_edit", "options": CRAFTS, "default": s.get("craft")},
            {"key": "pay", "label": "طريقة الحساب", "type": "combo", "options": [(v, k) for k, v in PAY_TYPES.items()],
             "default": s.get("pay_type", "piece")},
            {"key": "salary", "label": "المرتب الشهرى (لو بمرتب)", "default": amount_text(s.get("salary", 0))},
            {"key": "mobile", "label": "الموبايل", "default": s.get("mobile", "")},
            {"key": "hired", "label": "تاريخ التعيين", "default": iso_to_display(s.get("hired_on")) or today_text()},
        ]
        if s:
            fields.append({"key": "active", "label": "شغّال", "type": "check", "default": s.get("is_active", True)})

        def action(v):
            args = dict(name=v["name"], mobile=v["mobile"], kind=v["kind"], craft=v["craft"], pay_type=v["pay"],
                        salary=parse_amount(v["salary"], "المرتب", allow_zero=True), hired_on=iso_date(v["hired"]))
            if s:
                return self.backend.update_staff(staff_id=s["id"], is_active=v["active"], **args)
            return self.backend.add_staff(**args)

        self.form("✏️ تعديل" if s else "➕ إضافة عامل / موظف", fields, action,
                  then=lambda _r: self.app.reload_lookups(), color=PURPLE)

    # ---------- الأجور ----------

    def _txn(self, r, txn_type):
        label = STAFF_TXN_LABELS[txn_type]
        fields = [{"key": "amount", "label": "المبلغ *",
                   "default": amount_text(r["remaining"]) if txn_type == "payment" and r["remaining"] > 0 else ""},
                  {"key": "month", "label": "عن شهر", "type": "combo", "options": recent_months(18),
                   "default": self._month_value()},
                  {"key": "desc", "label": "البيان"}]
        if txn_type in ("advance", "payment"):
            fields.insert(1, {"key": "method", "label": "طريقة الدفع", "type": "combo",
                              "options": self.app.options("payment_methods")})
        note = "هتنزل منصرف فى الخزينة أوتوماتيك" if txn_type in ("advance", "payment") else None
        colors = {"payment": GREEN, "advance": AMBER, "bonus": TEAL, "deduction": RED}
        self.form(f"{label} — {r['name']}", fields, lambda v: self.backend.add_staff_txn(
            staff_id=r["staff_id"], txn_type=txn_type, amount=parse_amount(v["amount"]), for_month=v["month"],
            description=v["desc"], method_id=v.get("method")), color=colors[txn_type], note=note)

    def _work(self, r):
        self.form(f"✍️ شغل بالقطعة — {r['name']}", [
            {"key": "desc", "label": "الشغل *", "placeholder": "مثال: تقصير 3 بنطلونات"},
            {"key": "qty", "label": "العدد", "default": "1"},
            {"key": "rate", "label": "سعر القطعة *"},
            {"key": "month", "label": "عن شهر", "type": "combo", "options": recent_months(18),
             "default": self._month_value()},
        ], lambda v: self.backend.add_work(staff_id=r["staff_id"], description=v["desc"],
                                           qty=parse_amount(v["qty"], "العدد"),
                                           rate=parse_amount(v["rate"], "سعر القطعة"), work_month=v["month"]),
            color=PURPLE)

    def _statement(self, r):
        StatementDialog(self, r, self._month_value())


class StatementDialog(QDialog):
    """كشف حساب عامل فى شهر: كل قطعة اشتغلها + كل سلفة/صرف/مكافأة/خصم (وتقدر تمسح الغلط)."""

    def __init__(self, page, row, month):
        super().__init__(page)
        self._page = page
        self._r = row
        self._month = month
        self.setWindowTitle(f"كشف حساب {row['name']} — {month_label(month)}")
        self.resize(940, 620)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(f"📜 {row['name']} — {month_label(month)}", "pageTitle"))
        lay.addWidget(ui.muted(f"المستحق {money(row['earned'])} · اتصرف {money(row['paid'])} · الباقى "
                               f"{money(row['remaining'])}"))
        can_delete = page.me.can_delete("workers")
        lay.addLayout(ui.hbox(ui.section_title("✂️ الشغل بالقطعة"), None,
                              *([ui.button("🗑️ مسح السطر", "red", self._delete_work)] if can_delete else [])))
        self._work = DataTable([("الوقت", "date"), ("الشغل", "wide"), ("المرحلة", "text"), ("العدد", "qty"),
                                ("السعر", "money"), ("المبلغ", "money")])
        lay.addWidget(self._work, 1)
        lay.addLayout(ui.hbox(ui.section_title("💵 السلف والصرف والمكافآت والخصومات"), None,
                              *([ui.button("🗑️ مسح الحركة", "red", self._delete_txn)] if can_delete else [])))
        self._txns = DataTable([("الوقت", "date"), ("النوع", "text"), ("المبلغ", "money"), ("البيان", "wide")])
        lay.addWidget(self._txns, 1)
        self.show()
        self.refresh()

    def refresh(self):
        self._page.app.worker.run(
            lambda: self._page.backend.staff_statement(staff_id=self._r["staff_id"], month=self._month),
            self._render, lambda e: ui.show_error(self, e))

    def _render(self, data):
        self._work.set_rows([{"key": w["id"], "values": [
            datetime_display(w["created_at"]), w.get("description"), STAGE_LABELS.get(w.get("stage"), "بإيدك"),
            w["qty"], w["rate"], w["amount"]]} for w in data["work"]])
        colors = {"advance": AMBER, "payment": GREEN, "bonus": BLUE, "deduction": RED}
        self._txns.set_rows([{"key": t["id"], "color": colors.get(t["txn_type"]), "values": [
            datetime_display(t["created_at"]), STAFF_TXN_LABELS.get(t["txn_type"]), t["amount"], t.get("description")]}
            for t in data["txns"]])

    def _delete_work(self):
        key = self._work.selected_key()
        if key is None:
            ui.show_info(self, "اختار سطر من جدول الشغل", "تنبيه")
            return
        if ui.ask_yes_no(self, "تمسح السطر ده من أجر العامل؟"):
            self._page.app.worker.run(lambda: self._page.backend.delete_work(work_id=key),
                                      lambda _r: (self.refresh(), self._page.app.after_change()),
                                      lambda e: ui.show_error(self, e))

    def _delete_txn(self):
        key = self._txns.selected_key()
        if key is None:
            ui.show_info(self, "اختار حركة من الجدول", "تنبيه")
            return
        if ui.ask_yes_no(self, "تمسح الحركة دى؟ (لو سلفة أو صرف، القيد بتاعها هيتمسح من الخزينة كمان)"):
            self._page.app.worker.run(lambda: self._page.backend.delete_staff_txn(txn_id=key),
                                      lambda _r: (self.refresh(), self._page.app.after_change()),
                                      lambda e: ui.show_error(self, e))
