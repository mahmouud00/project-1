"""
pages_stock.py
--------------
المخزن: الخامات (قماش، بطانة، زراير...) والبدل الجاهزة.
  - استلام خامات ← الكمية بتزيد ومتوسط السعر بيتحسب، ولو فيه مورد: الفاتورة بتتسجل عليه.
  - القص بيخصم الخامات أوتوماتيك (من صفحة القص).
  - الجرد: تكتب الكمية اللى على الرف فعلاً والفرق بيتسجل.
"""

from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QWidget

import qt_widgets as ui
from qt_widgets import BasePage, DataTable, GREEN, RED, AMBER, TEAL, money, today_text, amount_text
from models import datetime_display, iso_date, iso_to_display, num, parse_amount, parse_int
from pages_money import add_supplier_form

MOVE_LABELS = {"in": "دخول", "out": "صرف", "adjust": "جرد", "sale": "بيع", "return": "مرتجع"}
UNITS = ["متر", "قطعة", "بكرة", "علبة", "كيلو", "دستة", "طقم"]
CATEGORIES = ["قماش", "بطانة", "زراير", "خيط", "حشو وتقوية", "إكسسوار", "أخرى"]


class InventoryPage(BasePage):
    PAGE = "inventory"
    TITLE = "🗃️ المخزن"

    def __init__(self, app):
        super().__init__(app)
        self._m_by_id, self._p_by_id = {}, {}
        self._materials, self._products = [], []
        can = self.me.can_edit(self.PAGE)
        tabs = QTabWidget()
        self.body.addWidget(tabs, 1)

        # ---------- الخامات ----------
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        self._m_title = ui.section_title("")
        buttons = [ui.button("📜 الحركات", "light", lambda: self._with_m(self._m_moves))]
        if can:
            buttons = [ui.button("📥 استلام", "green", lambda: self._with_m(self._receive)),
                       ui.button("📤 صرف", "amber", lambda: self._with_m(self._issue)),
                       ui.button("🧮 جرد", "teal", lambda: self._with_m(self._adjust)),
                       ui.button("➕ خامة جديدة", "purple", lambda: self._material_form()),
                       ui.button("✏️ تعديل", "blue", lambda: self._with_m(self._material_form))] + buttons
        l1.addLayout(ui.hbox(self._m_title, None, *buttons))
        self._m_search = ui.search_box("🔍 بحث بالاسم أو النوع", self._render_materials)
        self._m_totals = ui.label("", "muted")
        l1.addLayout(ui.hbox(self._m_search, self._m_totals))
        l1.addWidget(ui.muted("🔴 قربت تخلص (الكمية وصلت لحد الطلب). الرمادى = موقوفة. "
                              "القص بيخصم الخامات من هنا أوتوماتيك."))
        self._m_table = DataTable([("الخامة", "wide"), ("النوع", "text"), ("الكمية", "qty"), ("الوحدة", "text"),
                                   ("متوسط السعر", "money"), ("القيمة", "money"), ("حد الطلب", "qty")])
        self._m_table.cellDoubleClicked.connect(lambda r, c: self._with_m(self._m_moves))
        l1.addWidget(self._m_table, 1)
        tabs.addTab(w1, "🧵 الخامات")

        # ---------- البدل الجاهزة ----------
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        self._p_title = ui.section_title("")
        buttons = [ui.button("📜 الحركات", "light", lambda: self._with_p(self._p_moves))]
        if can:
            buttons = [ui.button("📥 إضافة كمية", "green", lambda: self._with_p(self._product_in)),
                       ui.button("🧮 جرد", "teal", lambda: self._with_p(self._product_adjust)),
                       ui.button("➕ صنف جديد", "purple", lambda: self._product_form()),
                       ui.button("✏️ تعديل", "blue", lambda: self._with_p(self._product_form))] + buttons
        l2.addLayout(ui.hbox(self._p_title, None, *buttons))
        self._p_search = ui.search_box("🔍 بحث بالاسم أو المقاس أو اللون", self._render_products)
        self._p_totals = ui.label("", "muted")
        l2.addLayout(ui.hbox(self._p_search, self._p_totals))
        l2.addWidget(ui.muted("البيع بيتعمل من صفحة الطلبات ← «بيع جاهز». الإضافة هنا للبضاعة اللى خلصت "
                              "تصنيع للمخزن أو اتشترت جاهزة."))
        self._p_table = DataTable([("الصنف", "wide"), ("النوع", "text"), ("المقاس", "text"), ("اللون", "text"),
                                   ("الكمية", "qty"), ("التكلفة", "money"), ("سعر البيع", "money"),
                                   ("قيمة المخزون", "money")])
        self._p_table.cellDoubleClicked.connect(lambda r, c: self._with_p(self._p_moves))
        l2.addWidget(self._p_table, 1)
        tabs.addTab(w2, "🤵 البدل الجاهزة")

    def load(self):
        return self.backend.materials(), self.backend.products()

    def render(self, data):
        self._materials, self._products = data
        self._m_by_id = {m["id"]: m for m in self._materials}
        self._p_by_id = {p["id"]: p for p in self._products}
        self._render_materials()
        self._render_products()

    def _render_materials(self):
        shown = [m for m in self._materials if ui.matches(self._m_search.text(), m, ("name", "category"))]
        low = sum(1 for m in shown if m["low"] and m["is_active"])
        self._m_title.setText(f"🧵 الخامات ({len(shown)})" + (f" · ⚠️ {low} قربت تخلص" if low else ""))
        self._m_totals.setText(f"قيمة الخامات: {money(sum(num(m['value']) for m in shown if num(m['qty']) > 0))}")
        self._m_table.set_rows([{
            "key": m["id"], "color": ui.GRAY if not m["is_active"] else (RED if m["low"] else None),
            "values": [m["name"], m.get("category"), m["qty"], m["unit"], m["avg_cost"], m["value"],
                       m["reorder_level"]]} for m in shown])

    def _render_products(self):
        shown = [p for p in self._products if ui.matches(self._p_search.text(), p, ("name", "size", "color"))]
        self._p_title.setText(f"🤵 البدل الجاهزة ({len(shown)}) · {sum(int(p['qty']) for p in shown)} قطعة")
        self._p_totals.setText(f"قيمة المخزون: {money(sum(num(p['value']) for p in shown if p['qty'] > 0))}")
        self._p_table.set_rows([{
            "key": p["id"], "color": ui.GRAY if not p["is_active"] else (AMBER if p["qty"] <= 0 else None),
            "values": [p["name"], p.get("garment_type"), p.get("size"), p.get("color"), p["qty"], p["cost"],
                       p["price"], p["value"]]} for p in shown])

    def _with_m(self, func):
        m = self.selected(self._m_table, self._m_by_id, "اختار خامة من الجدول الأول")
        if m:
            func(m)

    def _with_p(self, func):
        p = self.selected(self._p_table, self._p_by_id, "اختار صنف من الجدول الأول")
        if p:
            func(p)

    def _done_reload(self, _r=None):
        self.app.reload_lookups()

    # ---------- الخامات ----------

    def _material_form(self, m=None):
        m = m or {}
        self.form("✏️ تعديل خامة" if m else "➕ خامة جديدة", [
            {"key": "name", "label": "اسم الخامة *", "default": m.get("name", ""),
             "placeholder": "مثال: قماش صوف إيطالى كحلى"},
            {"key": "category", "label": "النوع", "type": "combo_edit", "options": CATEGORIES,
             "default": m.get("category")},
            {"key": "unit", "label": "الوحدة", "type": "combo_edit", "options": UNITS, "default": m.get("unit", "متر")},
            {"key": "reorder", "label": "حد الطلب (نبّهنى لما الكمية توصل له)",
             "default": amount_text(m.get("reorder_level", 0))},
            {"key": "active", "label": "شغّالة", "type": "check", "default": m.get("is_active", True)},
        ], lambda v: self.backend.save_material(
            material_id=m.get("id"), name=v["name"], category=v["category"], unit=v["unit"] or "متر",
            reorder_level=parse_amount(v["reorder"], "حد الطلب", allow_zero=True), is_active=v["active"]),
            then=self._done_reload, color=TEAL)

    def _receive(self, m):
        suppliers = [("— من غير مورد —", None)] + [(s["name"], s["id"]) for s in self.app.lookups.get("suppliers", [])]

        def action(v):
            return self.backend.receive_material(
                material_id=m["id"], qty=parse_amount(v["qty"], "الكمية"),
                unit_cost=parse_amount(v["cost"], "سعر الوحدة", allow_zero=True),
                supplier_id=v["supplier"] if isinstance(v["supplier"], int) else None, note=v["note"],
                move_date=iso_date(v["date"]), add_supplier_invoice=v["invoice"])

        dialog = self.form(f"📥 استلام {m['name']}", [
            {"key": "qty", "label": f"الكمية ({m['unit']}) *"},
            {"key": "cost", "label": f"سعر الـ{m['unit']}", "default": amount_text(m["avg_cost"])},
            {"key": "supplier", "label": "المورد", "type": "search", "options": suppliers},
            {"key": "invoice", "label": "سجّل المبلغ فاتورة على حساب المورد", "type": "check", "default": True},
            {"key": "date", "label": "التاريخ", "default": today_text()},
            {"key": "note", "label": "ملاحظة"},
        ], action, then=self._done_reload, color=GREEN)
        if self.me.can_edit("suppliers"):
            dialog.layout().addWidget(ui.button("➕ مورد جديد مش فى القايمة", "light",
                                                lambda: (dialog.reject(), add_supplier_form(
                                                    self, then=lambda _r: self.app.reload_lookups()))))

    def _issue(self, m):
        self.form(f"📤 صرف {m['name']} (متاح {ui.qty(m['qty'])} {m['unit']})", [
            {"key": "qty", "label": f"الكمية ({m['unit']}) *"},
            {"key": "order", "label": "رقم الطلب (لو الصرف لطلب معين)"},
            {"key": "note", "label": "السبب", "placeholder": "هالك، عينة، تصليح..."},
        ], lambda v: self.backend.issue_material(
            material_id=m["id"], qty=parse_amount(v["qty"], "الكمية"), note=v["note"],
            order_id=parse_int(v["order"].lstrip("#"), "رقم الطلب") if v["order"] else None),
            then=self._done_reload, color=AMBER)

    def _adjust(self, m):
        self.form(f"🧮 جرد {m['name']}", [
            {"key": "info", "type": "info", "label": f"الكمية فى البرنامج: {ui.qty(m['qty'])} {m['unit']}"},
            {"key": "qty", "label": "الكمية الفعلية على الرف *"},
            {"key": "note", "label": "ملاحظة", "default": "جرد"},
        ], lambda v: self.backend.adjust_material(material_id=m["id"],
                                                  new_qty=parse_amount(v["qty"], "الكمية", allow_zero=True),
                                                  note=v["note"]),
            then=self._done_reload, color=TEAL)

    def _m_moves(self, m):
        MovesDialog(self, f"📜 حركات {m['name']}", lambda: self.backend.material_moves(material_id=m["id"]),
                    material=True)

    # ---------- البدل الجاهزة ----------

    def _product_form(self, p=None):
        p = p or {}
        self.form("✏️ تعديل صنف" if p else "➕ صنف جاهز جديد", [
            {"key": "name", "label": "اسم الصنف *", "default": p.get("name", ""),
             "placeholder": "مثال: بدلة كلاسيك كحلى"},
            {"key": "type", "label": "النوع", "type": "combo",
             "options": [("—", None)] + self.app.options("garment_types"), "default": p.get("garment_type_id")},
            {"key": "size", "label": "المقاس", "default": p.get("size", "")},
            {"key": "color", "label": "اللون", "default": p.get("color", "")},
            {"key": "price", "label": "سعر البيع", "default": amount_text(p.get("price", 0))},
            {"key": "active", "label": "شغّال", "type": "check", "default": p.get("is_active", True)},
        ], lambda v: self.backend.save_product(
            product_id=p.get("id"), name=v["name"], garment_type_id=v["type"], size=v["size"], color=v["color"],
            price=parse_amount(v["price"], "سعر البيع", allow_zero=True), is_active=v["active"]),
            then=self._done_reload, color=TEAL)

    def _product_in(self, p):
        self.form(f"📥 إضافة كمية — {p['name']}", [
            {"key": "qty", "label": "العدد *"},
            {"key": "cost", "label": "تكلفة القطعة", "default": amount_text(p["cost"])},
            {"key": "note", "label": "ملاحظة", "placeholder": "تصنيع للمخزن / شراء جاهز"},
        ], lambda v: self.backend.product_in(product_id=p["id"], qty=parse_int(v["qty"], "العدد"),
                                             unit_cost=parse_amount(v["cost"], "التكلفة", allow_zero=True),
                                             note=v["note"]),
            then=self._done_reload, color=GREEN)

    def _product_adjust(self, p):
        self.form(f"🧮 جرد {p['name']}", [
            {"key": "info", "type": "info", "label": f"العدد فى البرنامج: {p['qty']}"},
            {"key": "qty", "label": "العدد الفعلى *"},
            {"key": "note", "label": "ملاحظة", "default": "جرد"},
        ], lambda v: self.backend.adjust_product(product_id=p["id"], new_qty=parse_int(v["qty"], "العدد", minimum=0),
                                                 note=v["note"]),
            then=self._done_reload, color=TEAL)

    def _p_moves(self, p):
        MovesDialog(self, f"📜 حركات {p['name']}", lambda: self.backend.product_moves(product_id=p["id"]))


class MovesDialog(QDialog):
    def __init__(self, page, title, loader, material=False):
        super().__init__(page)
        self.setWindowTitle(title)
        self.resize(900, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(title, "dialogTitle"))
        cols = [("التاريخ", "date"), ("الحركة", "text"), ("الكمية", "qty"), ("السعر", "money")]
        if material:
            cols += [("طلب", "text"), ("المورد", "text")]
        cols += [("ملاحظة", "wide"), ("مين", "text")]
        self._material = material
        self._table = DataTable(cols)
        lay.addWidget(self._table, 1)
        self.show()
        page.app.worker.run(loader, self._render, lambda e: ui.show_error(self, e))

    def _render(self, rows):
        out = []
        for r in rows:
            values = [datetime_display(r["created_at"]) if not r.get("move_date") else iso_to_display(r["move_date"]),
                      MOVE_LABELS.get(r["move_type"], r["move_type"]), r["qty"], r.get("unit_cost", r.get("unit_price"))]
            if self._material:
                values += [f"#{r['order_id']}" if r.get("order_id") else "", r.get("supplier_name")]
            values += [r.get("note"), r.get("user_name")]
            out.append({"key": r["id"], "color": GREEN if num(r["qty"]) > 0 else RED, "values": values})
        self._table.set_rows(out)
