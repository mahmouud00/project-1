"""
pages_orders.py
---------------
صفحات الشغل: العملاء والمقاسات، الطلبات (تفصيل + بيع جاهز)، مراحل المصنع
(القص، الخياطة، البروفة، التشطيب)، التسليم، تأكيد الحسابات، المبيعات.

دورة الطلب:
  طلب جديد بعربون ← تأكيد العربون (الحسابات) ← قص ← خياطة ← بروفة (لو محتاج) ← تشطيب
  ← جاهز ← تسليم للعميل وتحصيل الباقى ← تأكيد الحساب النهائى (الحسابات) ← المبيعات
"""

import os
import tempfile
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QGroupBox, QLineEdit,
                               QPlainTextEdit, QScrollArea, QTabWidget, QVBoxLayout, QWidget)

import printing
import qt_widgets as ui
from qt_widgets import (BasePage, DataTable, FilePicker, MeasurementsEditor, StyleEditor, fill_combo, combo_value,
                        searchable, amount_text, money, NAVY, BLUE, GREEN, RED, AMBER, PURPLE, TEAL, GRAY)
from models import (FABRIC_SOURCES, OPEN_STATUSES, STATUS_LABELS, AppError, datetime_display, iso_date,
                    iso_to_display, num, parse_amount, parse_int)


# ============================================================
#                    أدوات مشتركة
# ============================================================

def _today_iso():
    return date.today().isoformat()


def due_color(o):
    """أحمر = فات ميعاد التسليم، أصفر = فاضل يومين أو أقل."""
    due = o.get("due_date")
    if not due or o.get("status") in ("ready", "awaiting_accounts", "completed"):
        return None
    if due < _today_iso():
        return RED
    if due <= (date.today() + timedelta(days=2)).isoformat():
        return AMBER
    return None


def print_receipt(page, order_id):
    app = page.app
    app.worker.run(lambda: app.backend.order_detail(order_id=order_id),
                   lambda o: printing.preview(page, printing.order_receipt_html(o, app.me.get_company(),
                                                                                app.logo_bytes), "إيصال الطلب"),
                   lambda e: ui.show_error(page, e))


def print_ticket(page, order_id):
    app = page.app
    app.worker.run(lambda: app.backend.order_detail(order_id=order_id),
                   lambda o: printing.preview(page, printing.workshop_ticket_html(o, app.me.get_company()),
                                              "ورقة المصنع"),
                   lambda e: ui.show_error(page, e))


def open_order_file(page, file_id):
    folder = os.path.join(tempfile.gettempdir(), "TailorMaster")
    os.makedirs(folder, exist_ok=True)
    page.app.worker.run(lambda: page.backend.download_file(file_id, folder), ui.open_path,
                        lambda e: ui.show_error(page, e))


def workers_options(app):
    return [("— مش محدد —", None)] + app.options("staff", kind="worker")


def can_edit_order(me, o):
    from server.service import STAGE_PAGE   # نفس جدول الصلاحيات اللى فى السيرفر
    return o["status"] != "completed" and (me.can_edit("orders") or me.can_edit(STAGE_PAGE[o["status"]]))


# ============================================================
#                    نافذة الطلب (جديد / تعديل)
# ============================================================

class OrderDialog(QDialog):
    def __init__(self, page, order=None, customer=None):
        super().__init__(page)
        self._page = page
        self._app = page.app
        self._order = order
        self._customer = customer          # عميل محدد (من صفحة العملاء)
        self._customers = []
        self._matched = None
        edit = order is not None
        lk = self._app.lookups
        self.setWindowTitle(f"✏️ تعديل طلب #{order['id']}" if edit else "📝 طلب تفصيل جديد")
        self.resize(980, 760)

        outer = QVBoxLayout(self)
        heading = ui.label(self.windowTitle(), "dialogTitle")
        heading.setStyleSheet(f"color: {NAVY};")
        outer.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        # ---------- العميل ----------
        cbox = QGroupBox("👤 العميل")
        cform = QGridLayout(cbox)
        fixed = order or customer
        if fixed:
            name = (order or {}).get("customer_name") or customer.get("name")
            mobile = (order or {}).get("customer_mobile") or customer.get("mobile")
            cform.addWidget(ui.label(f"{name} — {mobile or ''}", "boxTitle"), 0, 0)
        else:
            self._mobile = QLineEdit()
            self._mobile.setPlaceholderText("الموبايل * (لو العميل موجود هيتعرف لوحده)")
            self._mobile.editingFinished.connect(self._lookup_customer)
            self._name = QLineEdit()
            self._name.setPlaceholderText("اسم العميل *")
            self._address = QLineEdit()
            self._address.setPlaceholderText("العنوان (اختيارى)")
            self._customer_note = ui.label("", "muted")
            cform.addWidget(ui.label("الموبايل"), 0, 0)
            cform.addWidget(self._mobile, 0, 1)
            cform.addWidget(ui.label("الاسم"), 0, 2)
            cform.addWidget(self._name, 0, 3)
            cform.addWidget(ui.label("العنوان"), 1, 0)
            cform.addWidget(self._address, 1, 1, 1, 3)
            cform.addWidget(self._customer_note, 2, 0, 1, 4)
            self._app.worker.run(self._app.backend.customers, self._got_customers, lambda e: None)
        lay.addWidget(cbox)

        # ---------- الطلب ----------
        obox = QGroupBox("🧾 الطلب")
        g = QGridLayout(obox)
        g.setHorizontalSpacing(10)
        self._type = QComboBox()
        fill_combo(self._type, [("—", None)] + self._app.options("garment_types"),
                   (order or {}).get("garment_type_id"))
        self._type.currentIndexChanged.connect(self._type_changed)
        self._qty = QLineEdit(str((order or {}).get("quantity", 1)))
        self._qty.editingFinished.connect(self._type_changed)
        self._price = QLineEdit(amount_text(order["price"]) if edit else "")
        self._price.setPlaceholderText("السعر الإجمالى *")
        self._deposit = QLineEdit(amount_text(order["deposit"]) if edit else "0")
        self._method = QComboBox()
        fill_combo(self._method, [("—", None)] + self._app.options("payment_methods"),
                   (order or {}).get("deposit_method_id"))
        if not edit and self._method.count() > 1:
            self._method.setCurrentIndex(1)
        if edit and order["status"] != "awaiting_deposit":
            self._deposit.setReadOnly(True)
            self._method.setEnabled(False)
            self._deposit.setToolTip("العربون اتأكد واترحّل للخزينة خلاص")
        self._seller = QComboBox()
        fill_combo(self._seller, [("—", None)] + self._app.options("staff", kind="sales"),
                   (order or {}).get("seller_id"))
        self._fabric_source = QComboBox()
        fill_combo(self._fabric_source, [(v, k) for k, v in FABRIC_SOURCES.items()],
                   (order or {}).get("fabric_source", "factory"))
        self._fabric = QLineEdit((order or {}).get("fabric_desc") or "")
        self._fabric.setPlaceholderText("نوع ولون القماش")
        # القماش من المخزن: المعادلات بتحسب الكمية وبتحجزها لحد القص
        self._fabric_mat = searchable(QComboBox())
        mats = sorted((m for m in lk.get("materials", []) if m["is_active"]),
                      key=lambda m: (m.get("category") != "قماش", m["name"]))
        fill_combo(self._fabric_mat, [("— مش محدد —", None)] + [
            (f"{m['name']} (متاح {ui.qty(m.get('available', m['qty']))} {m['unit']})", m["id"]) for m in mats],
            (order or {}).get("fabric_material_id"))
        self._locked = bool(edit and order.get("cut_at"))      # اتقص خلاص ← الخامات اتصرفت
        self._fabric_mat.setEnabled(not self._locked)
        self._fabric_source.setEnabled(not self._locked)
        self._fabric_source.currentIndexChanged.connect(self._fabric_source_changed)
        self._fitting = QCheckBox("محتاج بروفة")
        self._fitting.setChecked(bool((order or {}).get("needs_fitting", True)))
        self._fitting_date = QLineEdit(iso_to_display((order or {}).get("fitting_date")))
        self._fitting_date.setPlaceholderText("يوم/شهر/سنة")
        default_due = (date.today() + timedelta(days=14)).strftime("%d/%m/%Y")
        self._due = QLineEdit(iso_to_display(order.get("due_date")) if edit else default_due)
        self._due.setPlaceholderText("يوم/شهر/سنة")
        self._branch = QComboBox()
        fill_combo(self._branch, self._app.branch_options())
        cells = [("النوع", self._type), ("العدد", self._qty), ("السعر الإجمالى *", self._price),
                 ("العربون", self._deposit), ("طريقة دفع العربون", self._method), ("السيلز", self._seller),
                 ("القماش", self._fabric_source), ("القماش من المخزن", self._fabric_mat), ("وصف القماش", self._fabric),
                 ("ميعاد التسليم", self._due), ("ميعاد البروفة", self._fitting_date)]
        for i, (title, w) in enumerate(cells):
            r, c = divmod(i, 3)
            g.addWidget(ui.label(title), r, c * 2)
            g.addWidget(w, r, c * 2 + 1)
        row = (len(cells) + 2) // 3
        g.addWidget(self._fitting, row, 1)
        if self._app.multi_branch() and not edit:
            g.addWidget(ui.label("الفرع"), row, 2)
            g.addWidget(self._branch, row, 3)
        self._notes = QPlainTextEdit((order or {}).get("notes") or "")
        self._notes.setPlaceholderText("ملاحظات للمصنع (بتتطبع فى ورقة الشغل)")
        self._notes.setMaximumHeight(70)
        g.addWidget(ui.label("ملاحظات"), row + 1, 0)
        g.addWidget(self._notes, row + 1, 1, 1, 5)
        self._files = None
        if not edit:
            self._files = FilePicker()
            g.addWidget(ui.label("ملفات"), row + 2, 0)
            g.addWidget(self._files, row + 2, 1, 1, 5)
        lay.addWidget(obox)

        # ---------- المقاسات ----------
        mbox = QGroupBox("📏 المقاسات")
        ml = QVBoxLayout(mbox)
        start_values = (order or {}).get("measurements") or (customer or {}).get("measurements") or {}
        self._measure = MeasurementsEditor(lk.get("measure_fields", []), start_values)
        ml.addWidget(self._measure)
        self._save_measure = QCheckBox("احفظ المقاسات دى فى ملف العميل (عشان تطلع لوحدها المرة الجاية)")
        self._save_measure.setChecked(True)
        if not edit:
            ml.addWidget(self._save_measure)
        lay.addWidget(mbox)

        # ---------- تفاصيل الموديل ----------
        sbox = QGroupBox("✂️ تفاصيل الموديل")
        sl = QVBoxLayout(sbox)
        self._style = StyleEditor(lk.get("style_options", []), (order or {}).get("style"))
        sl.addWidget(self._style)
        lay.addWidget(sbox)

        # ---------- الخامات المحسوبة ----------
        bbox = QGroupBox("🧮 الخامات المطلوبة (محسوبة بالمعادلات من المقاسات)")
        bl = QVBoxLayout(bbox)
        self._plan_label = ui.label("", wrap=True)
        self._plan_label.setTextFormat(Qt.RichText)
        bl.addWidget(self._plan_label)
        bl.addLayout(ui.hbox(ui.button("📐 احسب الخامات", "teal", self._calc_plan),
                             ui.muted("بتتحجز من المخزن لما الطلب يتسجل، وبتتخصم فعلاً عند القص. "
                                      "المعادلات بتتعدّل من الإعدادات.")))
        lay.addWidget(bbox)
        lay.addStretch(1)
        for signal in (self._type.currentIndexChanged, self._fabric_mat.currentIndexChanged):
            signal.connect(lambda _i: self._calc_plan())
        self._fabric_source_changed()
        if self._locked:
            self._plan_label.setText("الطلب اتقص خلاص والخامات اتصرفت — شوفها فى تفاصيل الطلب")
        else:
            self._calc_plan()

        self._btn = ui.button("💾 حفظ التعديل" if edit else "💾 حفظ الطلب", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        outer.addLayout(ui.hbox(self._btn, self._msg))
        self.setModal(True)
        self.show()

    # ---------- العميل ----------

    def _got_customers(self, rows):
        self._customers = rows

    def _lookup_customer(self):
        mobile = self._mobile.text().strip()
        match = next((c for c in self._customers if mobile and c.get("mobile") == mobile), None)
        self._matched = match
        if not match:
            self._customer_note.setText("عميل جديد" if mobile else "")
            return
        self._name.setText(match["name"])
        self._address.setText(match.get("address") or "")
        self._customer_note.setText(f"✅ عميل موجود: {match['name']} — {match['orders_count']} طلب قبل كده"
                                    + (f" — عليه {money(match['remaining'])}" if num(match["remaining"]) else ""))

        def got(detail):
            if not self._measure.get():
                self._measure.set(detail["customer"].get("measurements") or {})
        self._app.worker.run(lambda: self._app.backend.customer_detail(customer_id=match["id"]), got, lambda e: None)

    def _fabric_source_changed(self, *_):
        customer = combo_value(self._fabric_source) == "customer"
        self._fabric_mat.setEnabled(not customer and not self._locked)
        if customer:
            self._fabric_mat.setCurrentIndex(0)
        if hasattr(self, "_plan_label") and not self._locked:
            self._calc_plan()

    def _plan_args(self):
        try:
            qty = parse_int(self._qty.text() or "1")
        except AppError:
            qty = 1
        mat = combo_value(self._fabric_mat)
        return dict(garment_type_id=combo_value(self._type), quantity=qty, measurements=self._measure.get(),
                    style=self._style.get(), fabric_source=combo_value(self._fabric_source),
                    fabric_material_id=mat if isinstance(mat, int) else None,
                    order_id=self._order["id"] if self._order else None)

    def _calc_plan(self, then=None):
        if self._locked:
            if then:
                then([])
            return
        args = self._plan_args()
        self._plan_label.setText("⏳ بيحسب…")

        def done(plan):
            self._show_plan(plan, args)
            if then:
                then(plan)
        def failed(e):
            self._plan_label.setText(f"❌ {e}")
            if then:
                self._fail(e)
        self._app.worker.run(lambda: self._app.backend.calc_materials(**args), done, failed)

    def _show_plan(self, plan, args):
        if not args["garment_type_id"]:
            self._plan_label.setText("اختار النوع عشان الخامات تتحسب")
            return
        if not plan:
            self._plan_label.setText("مفيش خامات متسجلة للنوع ده (تقدر تضيفها من الإعدادات ← تركيبة الخامات)")
            return
        rows = []
        for p in plan:
            color = ui.RED if p["short"] else ui.GREEN
            status = f"⚠️ الموجود {ui.qty(p['available'])} بس" if p["short"] else f"✔ متاح {ui.qty(p['available'])}"
            note = f" — <i>{p['note']}</i>" if p.get("note") else ""
            rows.append(f"<b>{p['name']}</b>: {ui.qty(p['qty'])} {p['unit']} "
                        f"<span style='color:{color};'>({status})</span>{note}")
        if args["fabric_source"] == "factory" and not args["fabric_material_id"]:
            rows.append(f"<span style='color:{ui.AMBER};'>اختار «القماش من المخزن» عشان القماش يتحسب ويتحجز</span>")
        self._plan_label.setText("<br>".join(rows))

    def _type_changed(self):
        if self._price.text().strip():
            return
        gid = combo_value(self._type)
        g = next((x for x in self._app.lookups.get("garment_types", []) if x["id"] == gid), None)
        if g and num(g.get("default_price")):
            try:
                q = parse_int(self._qty.text() or "1")
            except AppError:
                q = 1
            self._price.setText(amount_text(num(g["default_price"]) * q))

    # ---------- الحفظ ----------

    def _values(self):
        price = parse_amount(self._price.text(), "السعر الإجمالى")
        deposit = parse_amount(self._deposit.text(), "العربون", allow_zero=True)
        mat = combo_value(self._fabric_mat)
        values = dict(price=price, deposit=deposit, deposit_method_id=combo_value(self._method),
                      fabric_material_id=mat if isinstance(mat, int) else None,
                      quantity=parse_int(self._qty.text() or "1"), garment_type_id=combo_value(self._type),
                      seller_id=combo_value(self._seller), fabric_desc=self._fabric.text(),
                      due_date=iso_date(self._due.text()), fitting_date=iso_date(self._fitting_date.text()),
                      notes=self._notes.toPlainText(), measurements=self._measure.get(), style=self._style.get(),
                      needs_fitting=self._fitting.isChecked())
        return values

    def _save(self):
        if not self._btn.isEnabled():
            return
        try:
            v = self._values()
        except AppError as e:
            self._msg.setText(f"❌ {e}")
            return
        backend = self._app.backend
        if self._order:
            o = self._order
            if o["status"] != "awaiting_deposit":
                v.pop("deposit")
                v.pop("deposit_method_id")
            if self._locked:
                v.pop("fabric_material_id")
            else:
                v["fabric_source"] = combo_value(self._fabric_source)
                v["fabric_material_id"] = v["fabric_material_id"] or ""
            if v.get("garment_type_id") is None:
                v.pop("garment_type_id")
            if v.get("seller_id") is None:
                v["seller_id"] = ""
            for k in ("due_date", "fitting_date"):          # خانة فاضية = امسح الميعاد
                if v[k] is None:
                    v[k] = ""
            action = lambda: backend.update_order(order_id=o["id"], **v)   # noqa: E731
        else:
            v.update(fabric_source=combo_value(self._fabric_source),
                     save_measurements=self._save_measure.isChecked())
            if self._app.multi_branch():
                v["branch_id"] = combo_value(self._branch)
            if self._customer:
                v["customer_id"] = self._customer["id"]
            else:
                v.update(customer_name=self._name.text(), mobile=self._mobile.text(), address=self._address.text())
            paths = self._files.get() if self._files else []

            def action():
                return backend.add_order(files=backend.read_files(paths), **v)
        self._btn.setEnabled(False)
        self._btn.setText("جارى الحفظ…")
        self._msg.setText("")

        def checked(plan):
            short = [p for p in plan if p["short"]]
            if short and not ui.ask_yes_no(self, "المخزن مش مكفّى للطلب ده:\n" + "\n".join(
                    f"• {p['name']}: محتاج {ui.qty(p['qty'])} والمتاح {ui.qty(p['available'])} {p['unit']}"
                    for p in short) + "\n\nتسجّل الطلب برضه؟ (اشترى الناقص قبل القص)", "المخزن"):
                self._fail("اتلغى — المخزن مش مكفّى")
                return
            self._app.worker.run(action, self._done, self._fail)

        self._calc_plan(then=checked)

    def _done(self, result):
        self.accept()
        self._app.after_change()
        if not self._order and ui.ask_yes_no(self._page, f"✅ اتسجل الطلب رقم #{result} — مستنى تأكيد العربون "
                                                         "من الحسابات.\n\nتطبع إيصال للعميل؟", "تم"):
            print_receipt(self._page, result)

    def _fail(self, error):
        self._msg.setText(f"❌ {error}")
        self._btn.setEnabled(True)
        self._btn.setText("💾 حفظ التعديل" if self._order else "💾 حفظ الطلب")


# ============================================================
#                    تفاصيل الطلب
# ============================================================

class OrderDetailDialog(QDialog):
    def __init__(self, page, order_id):
        super().__init__(page)
        self._page = page
        self._app = page.app
        self._id = order_id
        self.setWindowTitle(f"طلب #{order_id}")
        self.resize(1000, 720)
        self._lay = QVBoxLayout(self)
        self._content = ui.section_title("جارى التحميل…")
        self._lay.addWidget(self._content)
        self.show()
        self.refresh()

    def refresh(self):
        self._app.worker.run(lambda: self._app.backend.order_detail(order_id=self._id), self._render,
                             lambda e: ui.show_error(self, e))

    def _render(self, o):
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        self._lay.replaceWidget(self._content, content)
        self._content.deleteLater()
        self._content = content
        me = self._app.me
        color = GREEN if o["status"] == "completed" else (due_color(o) or BLUE)
        title = ui.label(f"طلب #{o['id']} — {o['customer_name']}", "pageTitle")
        status = ui.label(f"  {o['status_label']}  ", "boxTitle")
        status.setStyleSheet(f"background: {color}; color: white; border-radius: 8px; padding: 4px;")
        buttons = [ui.button("🖨️ إيصال", "light", lambda: print_receipt(self._page, o["id"])),
                   ui.button("🧵 ورقة المصنع", "light", lambda: print_ticket(self._page, o["id"]))]
        if can_edit_order(me, o):
            buttons.insert(0, ui.button("✏️ تعديل", "blue", lambda: (self.accept(), OrderDialog(self._page, o))))
            buttons.append(ui.button("📎 إضافة ملفات", "light", lambda: self._add_files(o)))
        lay.addLayout(ui.hbox(title, status, None, *buttons))

        tabs = QTabWidget()
        lay.addWidget(tabs, 1)

        info = QWidget()
        il = QVBoxLayout(info)
        rows = [("العميل", f"{o['customer_name']} — {o.get('customer_mobile') or ''}"),
                ("النوع", f"{o.get('garment_type') or '—'} × {o['quantity']}"),
                ("القماش", f"{FABRIC_SOURCES.get(o['fabric_source'], '')} — {o.get('fabric_desc') or '—'}"),
                ("ميعاد البروفة", iso_to_display(o.get("fitting_date")) or "—"),
                ("ميعاد التسليم", iso_to_display(o.get("due_date")) or "—"),
                ("بروفة", f"أيوه (اتعمل {o['fitting_count']} تعديل)" if o["needs_fitting"] else "من غير بروفة"),
                ("السيلز", o.get("seller_name") or "—"), ("الفرع", o.get("branch_name")),
                ("سجّله", f"{o.get('created_by_name') or '—'} — {datetime_display(o['created_at'])}")]
        if me.can_view("accounts") or me.can_view("orders") or me.can_view("sales") or me.can_view("delivery"):
            rows += [("السعر", money(o["price"])), ("العربون", f"{money(o['deposit'])} ({o.get('deposit_method') or '—'})"),
                     ("المحصّل عند التسليم", money(o.get("final_collected") or 0)),
                     ("المتبقى", money(o["remaining"]))]
            if me.can_view("sales"):
                rows += [("تكلفة الخامات", money(o["material_cost"])), ("أجور بالقطعة", money(o["labor_cost"]))]
        box = ui.Box()
        for k, v in rows:
            box.body.addLayout(ui.kv_row(k, v))
        il.addWidget(box)
        if o.get("notes"):
            il.addWidget(ui.label(f"📝 {o['notes']}", wrap=True))
        if o.get("note"):
            il.addWidget(ui.label(f"📌 ملاحظة المتابعة: {o['note']}", wrap=True))
        for f in o.get("files", []):
            il.addWidget(ui.button(f"📎 {f['name']}", "light", lambda fid=f["id"]: open_order_file(self._page, fid)))
        il.addStretch(1)
        tabs.addTab(info, "📋 البيانات")

        mw = QWidget()
        mlay = QVBoxLayout(mw)
        mlay.addWidget(MeasurementsEditor(self._app.lookups.get("measure_fields", []), o["measurements"],
                                          read_only=True))
        if o["style"]:
            sb = ui.Box("✂️ تفاصيل الموديل", PURPLE)
            for k, v in o["style"].items():
                sb.body.addLayout(ui.kv_row(k, v))
            mlay.addWidget(sb)
        mlay.addStretch(1)
        tabs.addTab(mw, "📏 المقاسات والموديل")

        ev = DataTable([("الوقت", "date"), ("اللى حصل", "text"), ("التفاصيل", "wide"), ("مين", "text")])
        ev.set_rows([{"key": e["id"], "values": [datetime_display(e["created_at"]), e["action"], e.get("details"),
                                                 e.get("user_name")]} for e in o["events"]])
        tabs.addTab(ev, f"🕒 السجل ({len(o['events'])})")

        if o.get("materials_plan") and not o.get("cut_at"):
            pt = DataTable([("الخامة", "wide"), ("الكمية المحجوزة", "qty"), ("الوحدة", "text")])
            pt.set_rows([{"key": i, "values": [p["name"], p["qty"], p["unit"]]}
                         for i, p in enumerate(o["materials_plan"])])
            tabs.addTab(pt, "🧮 الخامات المحجوزة")
        if o["materials_used"] or o["work"]:
            w = QWidget()
            wl = QVBoxLayout(w)
            if o["materials_used"]:
                wl.addWidget(ui.section_title("🧵 الخامات اللى اتصرفت"))
                t = DataTable([("الخامة", "wide"), ("الكمية", "qty"), ("الوحدة", "text"), ("التكلفة", "money")])
                t.set_rows([{"key": i, "values": [m["name"], m["qty"], m["unit"], num(m["qty"]) * num(m["unit_cost"])]}
                            for i, m in enumerate(o["materials_used"])])
                wl.addWidget(t)
            if o["work"]:
                wl.addWidget(ui.section_title("👷 شغل العمال"))
                t = DataTable([("العامل", "wide"), ("الشغل", "text"), ("العدد", "qty"), ("المبلغ", "money")])
                t.set_rows([{"key": x["id"], "values": [x["staff_name"], x.get("description"), x["qty"], x["amount"]]}
                            for x in o["work"]])
                wl.addWidget(t)
            tabs.addTab(w, "🧵 الخامات والعمال")

    def _add_files(self, o):
        def action(v):
            if not v["files"]:
                raise AppError("اختار ملف واحد على الأقل")
            return self._app.backend.add_order_files(order_id=o["id"], files=self._app.backend.read_files(v["files"]))
        ui.FormDialog(self, self._app, f"📎 ملفات طلب #{o['id']}", [{"key": "files", "label": "الملفات", "type": "files"}],
                      action, on_done=lambda _r: self.refresh())


# ============================================================
#                    العملاء والمقاسات
# ============================================================

def customer_form(page, c=None, then=None):
    c = c or {}
    page.form("✏️ تعديل عميل" if c else "➕ عميل جديد", [
        {"key": "name", "label": "الاسم *", "default": c.get("name", "")},
        {"key": "mobile", "label": "الموبايل", "default": c.get("mobile", "")},
        {"key": "address", "label": "العنوان", "default": c.get("address", "")},
        {"key": "notes", "label": "ملاحظات", "type": "text", "default": c.get("notes", "")},
    ], lambda v: page.backend.save_customer(customer_id=c.get("id"), **v), then=then, color=TEAL)


class MeasureDialog(QDialog):
    """تعديل مقاسات العميل (بتتحفظ نسخة فى السجل كل مرة تتغير)."""

    def __init__(self, page, detail):
        super().__init__(page)
        self._page = page
        c = detail["customer"]
        self._c = c
        self.setWindowTitle(f"📏 مقاسات {c['name']}")
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(f"📏 مقاسات {c['name']}", "dialogTitle"))
        if c.get("measured_at"):
            lay.addWidget(ui.muted(f"آخر تعديل: {datetime_display(c['measured_at'])}"))
        self._editor = MeasurementsEditor(page.app.lookups.get("measure_fields", []), c.get("measurements"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._editor)
        lay.addWidget(scroll, 1)
        self._btn = ui.button("💾 حفظ المقاسات", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addLayout(ui.hbox(self._btn, self._msg))
        self.setModal(True)
        self.show()

    def _save(self):
        values = self._editor.get()
        self._btn.setEnabled(False)
        self._page.app.worker.run(
            lambda: self._page.backend.save_measurements(customer_id=self._c["id"], data=values),
            lambda _r: (self.accept(), self._page.app.after_change()),
            lambda e: (self._msg.setText(f"❌ {e}"), self._btn.setEnabled(True)))


class CustomerDialog(QDialog):
    """ملف العميل: بياناته + المقاسات (والقديمة) + كل طلباته."""

    def __init__(self, page, detail):
        super().__init__(page)
        c = detail["customer"]
        self.setWindowTitle(f"👔 {c['name']}")
        self.resize(980, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(f"👔 {c['name']}", "pageTitle"))
        lay.addWidget(ui.muted(" · ".join(x for x in (c.get("mobile"), c.get("address"), c.get("notes")) if x)))
        tabs = QTabWidget()
        lay.addWidget(tabs, 1)

        orders = detail["orders"]
        ot = DataTable([("رقم", "int"), ("التاريخ", "date"), ("النوع", "text"), ("العدد", "int"), ("السعر", "money"),
                        ("المتبقى", "money"), ("المرحلة", "wide")])
        ot.set_rows([{"key": o["id"], "color": GREEN if o["status"] == "completed" else due_color(o), "values": [
            o["id"], iso_to_display(o["created_at"]), o.get("garment_type"), o["quantity"], o["price"], o["remaining"],
            o["status_label"]]} for o in orders])
        ot.cellDoubleClicked.connect(lambda r, col: ot.selected_key() and OrderDetailDialog(page, ot.selected_key()))
        tabs.addTab(ot, f"🧾 الطلبات ({len(orders)})")

        fields = page.app.lookups.get("measure_fields", [])
        mw = QWidget()
        ml = QVBoxLayout(mw)
        history = detail["history"]
        self._editor = MeasurementsEditor(fields, c.get("measurements"), read_only=True)
        if history:
            combo = QComboBox()
            fill_combo(combo, [(f"{datetime_display(h['created_at'])} — {h.get('created_by_name') or ''}", i)
                               for i, h in enumerate(history)])
            combo.currentIndexChanged.connect(lambda i: self._editor.set(history[i]["data"]))
            ml.addLayout(ui.hbox(ui.label("نسخة المقاسات:"), combo))
        ml.addWidget(self._editor)
        ml.addStretch(1)
        tabs.addTab(mw, f"📏 المقاسات ({len(history)} نسخة)")
        self.show()


class CustomersPage(BasePage):
    PAGE = "customers"
    TITLE = "👔 العملاء والمقاسات"

    def __init__(self, app):
        super().__init__(app)
        self._rows, self._by_id = [], {}
        self._count = ui.section_title("")
        buttons = [ui.button("📂 ملف العميل", "light", self._open)]
        if self.me.can_edit("customers") or self.me.can_edit("orders"):
            buttons = [ui.button("➕ عميل جديد", "green", lambda: customer_form(self)),
                       ui.button("✏️ تعديل", "blue", self._edit),
                       ui.button("📏 المقاسات", "teal", self._measure)] + buttons
        if self.me.can_edit("orders"):
            buttons.insert(0, ui.button("📝 طلب جديد للعميل", "purple", self._new_order))
        if self.me.can_delete(self.PAGE):
            buttons.append(ui.button("🗑️ مسح", "red", self._delete))
        self.body.addLayout(ui.hbox(self._count, None, *buttons))
        self._search = ui.search_box("🔍 بحث بالاسم أو الموبايل", self._render_table)
        self.body.addLayout(ui.hbox(self._search))
        self._table = DataTable([("الاسم", "wide"), ("الموبايل", "text"), ("العنوان", "text"), ("الطلبات", "int"),
                                 ("قيمة الطلبات", "money"), ("المتبقى عليه", "money"), ("آخر مقاس", "date"),
                                 ("آخر طلب", "date")])
        self._table.cellDoubleClicked.connect(lambda r, c: self._open())
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.customers()

    def render(self, rows):
        self._rows, self._by_id = rows, {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        shown = [c for c in self._rows if ui.matches(self._search.text(), c, ("name", "mobile"))]
        self._count.setText(f"👔 العملاء ({len(shown)})")
        self._table.set_rows([{"key": c["id"], "color": RED if num(c["remaining"]) > 0 else None, "values": [
            c["name"], c.get("mobile"), c.get("address"), c["orders_count"], c["orders_value"], c["remaining"],
            iso_to_display(c.get("measured_at")), iso_to_display(c.get("last_order"))]} for c in shown])

    def _sel(self):
        return self.selected(self._table, self._by_id, "اختار عميل من الجدول الأول")

    def _with_detail(self, func):
        c = self._sel()
        if c:
            self.app.worker.run(lambda: self.backend.customer_detail(customer_id=c["id"]), func,
                                lambda e: ui.show_error(self, e))

    def _open(self):
        self._with_detail(lambda d: CustomerDialog(self, d))

    def _edit(self):
        c = self._sel()
        if c:
            customer_form(self, c)

    def _measure(self):
        self._with_detail(lambda d: MeasureDialog(self, d))

    def _new_order(self):
        self._with_detail(lambda d: OrderDialog(self, customer=d["customer"]))

    def _delete(self):
        c = self._sel()
        if c and ui.ask_yes_no(self, f"هتمسح العميل {c['name']} نهائيًا؟"):
            self.run_action(lambda: self.backend.delete_customer(customer_id=c["id"]))


# ============================================================
#                    الطلبات + البيع الجاهز
# ============================================================

ORDER_FILTERS = [("كل الطلبات الشغّالة", "open"), ("كل الطلبات (حتى اللى اتسلمت)", "all")] + \
    [(STATUS_LABELS[s], s) for s in OPEN_STATUSES]


class OrdersPage(BasePage):
    PAGE = "orders"
    TITLE = "📝 الطلبات"

    def __init__(self, app):
        super().__init__(app)
        self._rows, self._by_id = [], {}
        self._count = ui.section_title("")
        buttons = []
        if self.me.can_edit(self.PAGE):
            buttons += [ui.button("📝 طلب تفصيل جديد", "green", lambda: OrderDialog(self)),
                        ui.button("🛍️ بيع جاهز", "purple", lambda: ReadySaleDialog(self))]
        self.body.addLayout(ui.hbox(self._count, None, *buttons))
        self._filter = QComboBox()
        fill_combo(self._filter, ORDER_FILTERS)
        self._filter.currentIndexChanged.connect(lambda _i: self.refresh())
        self._search = ui.search_box("🔍 بحث برقم الطلب أو العميل أو الموبايل", self._render_table)
        actions = [ui.button("📂 تفاصيل", "blue", lambda: self._with(lambda o: OrderDetailDialog(self, o["id"]))),
                   ui.button("🖨️ إيصال", "light", lambda: self._with(lambda o: print_receipt(self, o["id"]))),
                   ui.button("🧵 ورقة المصنع", "light", lambda: self._with(lambda o: print_ticket(self, o["id"])))]
        if self.me.can_edit(self.PAGE):
            actions.insert(1, ui.button("✏️ تعديل", "blue", lambda: self._with(self._edit)))
        if self.me.can_delete(self.PAGE):
            actions.append(ui.button("🗑️ مسح", "red", lambda: self._with(self._delete)))
        self.body.addLayout(ui.hbox(self._search, self._filter, None, *actions))
        self.body.addWidget(ui.muted("🔴 فات ميعاد التسليم   🟡 التسليم خلال يومين   🟢 اتسلّم. دوس مرتين على أى طلب "
                                     "عشان تفتح تفاصيله."))
        self._table = DataTable([("رقم", "int"), ("التاريخ", "date"), ("العميل", "text"), ("الموبايل", "text"),
                                 ("النوع", "text"), ("العدد", "int"), ("السعر", "money"), ("العربون", "money"),
                                 ("المتبقى", "money"), ("المرحلة", "text"), ("ميعاد التسليم", "date"),
                                 ("السيلز", "text"), ("الفرع", "wide")])
        self._table.cellDoubleClicked.connect(lambda r, c: self._with(lambda o: OrderDetailDialog(self, o["id"])))
        self.body.addWidget(self._table, 1)

    def load(self):
        f = combo_value(self._filter)
        if f == "all":
            return self.backend.orders()
        return self.backend.orders(statuses=OPEN_STATUSES if f == "open" else [f])

    def render(self, rows):
        self._rows, self._by_id = rows, {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        text = self._search.text().strip().lstrip("#")
        shown = [o for o in self._rows if not text or text == str(o["id"]) or ui.matches(
            text, o, ("customer_name", "customer_mobile", "seller_name"))]
        self._count.setText(f"📝 الطلبات ({len(shown)}) · القيمة {money(sum(num(o['price']) for o in shown))}")
        self._table.set_rows([{
            "key": o["id"], "color": GREEN if o["status"] == "completed" else due_color(o),
            "values": [o["id"], iso_to_display(o["created_at"]), o["customer_name"], o.get("customer_mobile"),
                       o.get("garment_type"), o["quantity"], o["price"], o["deposit"], o["remaining"],
                       o["status_label"], iso_to_display(o.get("due_date")), o.get("seller_name"),
                       o.get("branch_name")]} for o in shown])

    def _with(self, func):
        o = self.selected(self._table, self._by_id, "اختار طلب من الجدول الأول")
        if o:
            func(o)

    def _edit(self, o):
        if o["status"] == "completed":
            ui.show_info(self, "الطلب ده اتسلّم واتقفل ومينفعش يتعدّل", "تنبيه")
            return
        OrderDialog(self, o)

    def _delete(self, o):
        if ui.ask_yes_no(self, f"هتمسح طلب #{o['id']} ({o['customer_name']}) نهائيًا؟"):
            self.run_action(lambda: self.backend.delete_order(order_id=o["id"]))


class ReadySaleDialog(QDialog):
    """بيع بدل جاهزة من المخزن: الفلوس بتدخل الخزينة على طول والكمية بتنقص."""

    def __init__(self, page):
        super().__init__(page)
        self._page = page
        self._app = page.app
        self._rows = []
        self.setWindowTitle("🛍️ بيع جاهز")
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label("🛍️ بيع جاهز", "dialogTitle"))
        self._products = [p for p in self._app.lookups.get("products", []) if p["is_active"]]
        if not self._products:
            lay.addWidget(ui.muted("مفيش أصناف جاهزة — ضيفها الأول من صفحة المخزن ← البدل الجاهزة"))
        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("اختيارى")
        self._mobile = QLineEdit()
        self._mobile.setPlaceholderText("اختيارى")
        form.addRow("اسم العميل", self._name)
        form.addRow("الموبايل", self._mobile)
        lay.addLayout(form)
        lay.addWidget(ui.section_title("الأصناف"))
        self._items = QGridLayout()
        lay.addLayout(self._items)
        lay.addLayout(ui.hbox(ui.button("➕ صنف", "light", self._add_row)))
        self._total = ui.label("الإجمالى: 0", "sectionTitle")
        lay.addWidget(self._total)
        form2 = QFormLayout()
        self._method = QComboBox()
        fill_combo(self._method, self._app.options("payment_methods"))
        self._seller = QComboBox()
        fill_combo(self._seller, [("—", None)] + self._app.options("staff", kind="sales"))
        self._branch = QComboBox()
        fill_combo(self._branch, self._app.branch_options())
        self._note = QLineEdit()
        form2.addRow("طريقة الدفع", self._method)
        form2.addRow("السيلز", self._seller)
        if self._app.multi_branch():
            form2.addRow("الفرع", self._branch)
        form2.addRow("ملاحظة", self._note)
        lay.addLayout(form2)
        lay.addStretch(1)
        self._btn = ui.button("💾 حفظ البيع", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addLayout(ui.hbox(self._btn, self._msg))
        self._add_row()
        self.setModal(True)
        self.show()

    def _add_row(self):
        combo = searchable(QComboBox())
        fill_combo(combo, [("— اختار الصنف —", None)] + [
            (" ".join(x for x in (p["name"], p.get("size") or "", p.get("color") or "") if x) + f"  (متاح {p['qty']})",
             p["id"]) for p in self._products])
        qty = QLineEdit("1")
        price = QLineEdit()
        price.setPlaceholderText("السعر")
        remove = ui.button("✖", "light")
        row = {"combo": combo, "qty": qty, "price": price, "remove": remove}
        combo.currentIndexChanged.connect(lambda _i, r=row: self._product_chosen(r))
        qty.textChanged.connect(lambda _t: self._update_total())
        price.textChanged.connect(lambda _t: self._update_total())
        remove.clicked.connect(lambda _c=False, r=row: self._remove_row(r))
        n = len(self._rows)
        for col, w in enumerate((combo, qty, price, remove)):
            self._items.addWidget(w, n, col)
        self._items.setColumnStretch(0, 1)
        self._rows.append(row)

    def _remove_row(self, row):
        for w in (row["combo"], row["qty"], row["price"], row["remove"]):
            w.hide()
        self._rows.remove(row)
        self._update_total()

    def _product_chosen(self, row):
        pid = combo_value(row["combo"])
        p = next((x for x in self._products if x["id"] == pid), None)
        if p and not row["price"].text().strip():
            row["price"].setText(amount_text(p["price"]))
        self._update_total()

    def _items_values(self):
        items = []
        for r in self._rows:
            pid = combo_value(r["combo"])
            if not isinstance(pid, int):
                continue
            items.append({"product_id": pid, "qty": parse_int(r["qty"].text(), "الكمية"),
                          "price": parse_amount(r["price"].text(), "السعر", allow_zero=True)})
        return items

    def _update_total(self):
        try:
            total = sum(i["qty"] * i["price"] for i in self._items_values())
            self._total.setText(f"الإجمالى: {money(total)}")
        except AppError:
            self._total.setText("الإجمالى: —")

    def _save(self):
        if not self._btn.isEnabled():
            return
        try:
            items = self._items_values()
        except AppError as e:
            self._msg.setText(f"❌ {e}")
            return
        args = dict(items=items, method_id=combo_value(self._method), customer_name=self._name.text(),
                    mobile=self._mobile.text(), seller_id=combo_value(self._seller), note=self._note.text())
        if self._app.multi_branch():
            args["branch_id"] = combo_value(self._branch)
        self._btn.setEnabled(False)
        names = {p["id"]: p for p in self._products}

        def done(sale_id):
            self.accept()
            self._app.after_change()
            self._app.reload_lookups()
            if ui.ask_yes_no(self._page, f"✅ اتسجل البيع #{sale_id} ودخل الخزينة.\n\nتطبع فاتورة؟", "تم"):
                sale = {"id": sale_id, "created_at": _today_iso(), "customer_name": args["customer_name"],
                        "total": sum(i["qty"] * i["price"] for i in items),
                        "items": [dict(i, name=names[i["product_id"]]["name"], size=names[i["product_id"]].get("size"),
                                       color=names[i["product_id"]].get("color")) for i in items]}
                printing.preview(self._page, printing.sale_receipt_html(sale, self._app.me.get_company(),
                                                                        self._app.logo_bytes), "فاتورة البيع")

        self._app.worker.run(lambda: self._app.backend.add_ready_sale(**args), done,
                             lambda e: (self._msg.setText(f"❌ {e}"), self._btn.setEnabled(True)))


# ============================================================
#              مراحل المصنع + التسليم (نفس الكلاس)
# ============================================================

STAGES = {
    "cutting": {"status": "cutting", "title": "✂️ القص", "done": "✅ تم القص"},
    "sewing": {"status": "sewing", "title": "🧵 الخياطة", "done": "✅ تم الخياطة"},
    "fitting": {"status": "fitting", "title": "🪞 البروفة", "done": "✅ البروفة تمام"},
    "finishing": {"status": "finishing", "title": "♨️ التشطيب والكى", "done": "✅ تم التشطيب — جاهز"},
    "delivery": {"status": "ready", "title": "📦 التسليم", "done": "✅ تسليم للعميل"},
}


class StagePage(BasePage):
    def __init__(self, app, stage):
        super().__init__(app)
        conf = STAGES[stage]
        self.PAGE = stage
        self.TITLE = conf["title"]
        self._stage = stage
        self._status = conf["status"]
        self._rows, self._by_id = [], {}
        self._title = ui.section_title(self.TITLE)
        buttons = []
        if self.me.can_edit(stage):
            buttons.append(ui.button(conf["done"], "green", lambda: self._with(self._advance)))
            if stage == "fitting":
                buttons += [ui.button("↩️ محتاجة تعديل", "amber", lambda: self._with(self._fitting_back)),
                            ui.button("📅 ميعاد البروفة", "teal", lambda: self._with(self._fitting_date))]
            buttons.append(ui.button("📝 ملاحظة", "amber", lambda: self._with(self._note)))
            buttons.append(ui.button("✏️ تعديل", "blue", lambda: self._with(lambda o: OrderDialog(self, o))))
        if self.me.is_admin() and stage != "cutting" and not self.me.read_only():
            buttons.append(ui.button("⏪ رجوع لمرحلة قبل", "light", lambda: self._with(self._back)))
        if self.me.can_delete(stage):
            buttons.append(ui.button("🗑️ مسح", "red", lambda: self._with(self._delete)))
        self.body.addLayout(ui.hbox(self._title, None, *buttons))
        self._search = ui.search_box("🔍 بحث برقم الطلب أو العميل", self._render_table)
        self.body.addLayout(ui.hbox(
            self._search, None,
            ui.button("📂 تفاصيل", "blue", lambda: self._with(lambda o: OrderDetailDialog(self, o["id"]))),
            ui.button("🧵 ورقة المصنع", "light", lambda: self._with(lambda o: print_ticket(self, o["id"])))))
        cols = [("رقم", "int"), ("العميل", "text"), ("الموبايل", "text"), ("النوع", "text"), ("العدد", "int"),
                ("القماش", "text")]
        if stage == "fitting":
            cols.append(("ميعاد البروفة", "date"))
        cols.append(("ميعاد التسليم", "date"))
        if stage == "delivery":
            cols += [("السعر", "money"), ("المتبقى", "money")]
        cols += [("ملاحظة", "wide"), ("الفرع", "text")]
        self._cols = cols
        self._table = DataTable(cols)
        self._table.cellDoubleClicked.connect(lambda r, c: self._with(lambda o: OrderDetailDialog(self, o["id"])))
        self.body.addWidget(self._table, 1)

    def load(self):
        return self.backend.orders(statuses=[self._status])

    def render(self, rows):
        self._rows, self._by_id = rows, {r["id"]: r for r in rows}
        self._render_table()

    def _render_table(self):
        text = self._search.text().strip().lstrip("#")
        shown = [o for o in self._rows if not text or text == str(o["id"]) or ui.matches(
            text, o, ("customer_name", "customer_mobile"))]
        self._title.setText(f"{self.TITLE} ({len(shown)})")
        out = []
        for o in shown:
            values = [o["id"], o["customer_name"], o.get("customer_mobile"), o.get("garment_type"), o["quantity"],
                      o.get("fabric_desc")]
            if self._stage == "fitting":
                values.append(iso_to_display(o.get("fitting_date")))
            values.append(iso_to_display(o.get("due_date")))
            if self._stage == "delivery":
                values += [o["price"], o["remaining"]]
            values += [" | ".join(x for x in (o.get("note"), o.get("notes")) if x), o.get("branch_name")]
            out.append({"key": o["id"], "color": due_color(o), "values": values})
        self._table.set_rows(out)

    def _with(self, func):
        o = self.selected(self._table, self._by_id, "اختار طلب من الجدول الأول")
        if o:
            func(o)

    def _advance(self, o):
        b = self.backend
        if self._stage == "cutting":
            CutDialog(self, o)
        elif self._stage == "fitting":
            if ui.ask_yes_no(self, f"بروفة طلب #{o['id']} ({o['customer_name']}) تمام والطلب يروح التشطيب؟"):
                self.run_action(lambda: b.fitting_result(order_id=o["id"], ok=True))
        elif self._stage == "delivery":
            self.form(f"✅ تسليم طلب #{o['id']} — {o['customer_name']}", [
                {"key": "info", "type": "info", "label": f"السعر {money(o['price'])} · المدفوع عربون {money(o['deposit'])}"},
                {"key": "collected", "label": "المحصّل من العميل *", "default": amount_text(o["remaining"])},
                {"key": "method", "label": "طريقة الدفع", "type": "combo", "options": self.app.options("payment_methods")},
            ], lambda v: b.deliver_order(order_id=o["id"], collected=parse_amount(v["collected"], "المحصّل",
                                                                                   allow_zero=True),
                                         method_id=v["method"]),
                success_message="✅ اتسلّم — المبلغ مستنى تأكيد الحسابات", submit_text="💾 تأكيد التسليم",
                color=GREEN)
        else:
            func = b.finish_sewing if self._stage == "sewing" else b.finish_finishing
            label = "الخياط" if self._stage == "sewing" else "اللى شطّب"
            self.form(f"{STAGES[self._stage]['done']} — طلب #{o['id']}", [
                {"key": "worker", "label": label, "type": "search", "options": workers_options(self.app)},
                {"key": "info", "type": "info", "label": "لو العامل بيتحاسب بالقطعة، أجره بيتسجل أوتوماتيك "
                                                         "(حسب أسعار القطعة فى الإعدادات)."},
            ], lambda v: func(order_id=o["id"], worker_id=v["worker"] if isinstance(v["worker"], int) else None),
                submit_text="💾 تأكيد", color=GREEN)

    def _fitting_back(self, o):
        self.form(f"↩️ البروفة محتاجة تعديل — طلب #{o['id']}", [
            {"key": "note", "label": "التعديلات المطلوبة *", "type": "text"},
            {"key": "date", "label": "ميعاد البروفة الجاية", "default": iso_to_display(o.get("fitting_date"))},
        ], lambda v: (self.backend.update_order(order_id=o["id"], fitting_date=iso_date(v["date"]) or ""),
                      self.backend.fitting_result(order_id=o["id"], ok=False, note=v["note"] or None)),
            submit_text="💾 رجّعه للخياطة", color=AMBER)

    def _fitting_date(self, o):
        self.form(f"📅 ميعاد بروفة طلب #{o['id']}", [
            {"key": "date", "label": "الميعاد (يوم/شهر/سنة)", "default": iso_to_display(o.get("fitting_date"))},
        ], lambda v: self.backend.update_order(order_id=o["id"], fitting_date=iso_date(v["date"]) or ""))

    def _note(self, o):
        self.form(f"📝 ملاحظة — طلب #{o['id']}", [
            {"key": "note", "label": "الملاحظة", "type": "text", "default": o.get("note") or ""},
        ], lambda v: self.backend.set_order_note(order_id=o["id"], note=v["note"]), color=AMBER)

    def _back(self, o):
        if ui.ask_yes_no(self, f"ترجّع طلب #{o['id']} للمرحلة اللى قبلها؟\n"
                               "(الخامات والأجور اللى اتسجلت مش بتترجع لوحدها)"):
            self.run_action(lambda: self.backend.step_back(order_id=o["id"]))

    def _delete(self, o):
        if ui.ask_yes_no(self, f"هتمسح طلب #{o['id']} ({o['customer_name']}) نهائيًا؟"):
            self.run_action(lambda: self.backend.delete_order(order_id=o["id"]))


class CutDialog(QDialog):
    """تم القص: مين قص + الخامات اللى اتصرفت (بتتخصم من المخزن وتتحسب على الطلب)."""

    def __init__(self, page, order):
        super().__init__(page)
        self._page = page
        self._app = page.app
        self._o = order
        self._rows = []
        self.setWindowTitle(f"✂️ تم القص — طلب #{order['id']}")
        self.resize(720, 480)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.label(f"✂️ تم القص — طلب #{order['id']} ({order['customer_name']})", "dialogTitle"))
        form = QFormLayout()
        self._worker = searchable(QComboBox())
        fill_combo(self._worker, workers_options(self._app))
        form.addRow("القصاص", self._worker)
        lay.addLayout(form)
        lay.addWidget(ui.section_title("🧵 الخامات اللى اتصرفت من المخزن"))
        if order.get("fabric_source") == "customer":
            lay.addWidget(ui.muted("القماش من العميل — سجّل البطانة والإكسسوارات بس لو اتصرفت من المخزن"))
        self._materials = [m for m in self._app.lookups.get("materials", []) if m["is_active"]]
        self._grid = QGridLayout()
        lay.addLayout(self._grid)
        lay.addLayout(ui.hbox(ui.button("➕ خامة", "light", self._add_row)))
        lay.addStretch(1)
        self._btn = ui.button("💾 تأكيد — الطلب يروح الخياطة", "green", self._save)
        self._msg = ui.label("", "errorMsg", wrap=True)
        lay.addLayout(ui.hbox(self._btn, self._msg))
        plan = order.get("materials_plan") or []
        if plan:
            lay.insertWidget(3, ui.muted("الكميات محسوبة بالمعادلات من المقاسات — عدّلها لو اللى اتصرف فعلاً مختلف، "
                                         "أو امسح السطر بـ ✖"))
            for p in plan:
                self._add_row(p["material_id"], p["qty"])
        elif self._materials:
            self._add_row()
        else:
            lay.insertWidget(3, ui.muted("مفيش خامات فى المخزن متسجلة (تقدر تكمل من غيرها)"))
        self.setModal(True)
        self.show()

    def _add_row(self, material_id=None, amount=None):
        combo = searchable(QComboBox())
        fill_combo(combo, [("— اختار الخامة —", None)] + [
            (f"{m['name']} (موجود {ui.qty(m['qty'])} {m['unit']})", m["id"]) for m in self._materials],
            material_id)
        qty = QLineEdit(ui.qty(amount) if amount else "")
        qty.setPlaceholderText("الكمية")
        remove = ui.button("✖", "light")
        row = (combo, qty, remove)
        remove.clicked.connect(lambda _c=False, r=row: self._remove(r))
        n = len(self._rows)
        self._grid.addWidget(combo, n, 0)
        self._grid.addWidget(qty, n, 1)
        self._grid.addWidget(remove, n, 2)
        self._grid.setColumnStretch(0, 1)
        self._rows.append(row)

    def _remove(self, row):
        for w in row:
            w.hide()
        self._rows.remove(row)

    def _save(self):
        if not self._btn.isEnabled():
            return
        try:
            materials = []
            for combo, qty, _ in self._rows:
                mid = combo_value(combo)
                if isinstance(mid, int):
                    materials.append({"material_id": mid, "qty": parse_amount(qty.text(), "الكمية")})
        except AppError as e:
            self._msg.setText(f"❌ {e}")
            return
        worker = combo_value(self._worker)
        stock = {m["id"]: m for m in self._materials}
        short = [f"• {stock[x['material_id']]['name']}: محتاج {ui.qty(x['qty'])} والموجود "
                 f"{ui.qty(stock[x['material_id']]['qty'])}" for x in materials
                 if x["material_id"] in stock and x["qty"] > num(stock[x["material_id"]]["qty"]) + 1e-9]
        if short and not ui.ask_yes_no(self, "الخامات دى مش مكفية فى المخزن:\n" + "\n".join(short) +
                                       "\n\nتكمل؟ (الرصيد هيبقى بالسالب لحد ما تسجّل استلام الخامات)", "المخزن"):
            return
        self._btn.setEnabled(False)
        self._app.worker.run(
            lambda: self._app.backend.finish_cutting(order_id=self._o["id"],
                                                     worker_id=worker if isinstance(worker, int) else None,
                                                     materials=materials, allow_short=bool(short)),
            lambda _r: (self.accept(), self._app.after_change(), self._app.reload_lookups()),
            lambda e: (self._msg.setText(f"❌ {e}"), self._btn.setEnabled(True)))


# ============================================================
#                       تأكيد الحسابات
# ============================================================

class AccountsPage(BasePage):
    PAGE = "accounts"
    TITLE = "✅ تأكيد الحسابات"

    def __init__(self, app):
        super().__init__(app)
        self._dep, self._final = {}, {}
        can_e, can_d = self.me.can_edit(self.PAGE), self.me.can_delete(self.PAGE)

        def bar(title_lbl, confirm_text, confirm, table_fn, items_fn):
            buttons = [ui.button(confirm_text, "green", confirm)] if can_e else []
            buttons.append(ui.button("📂 تفاصيل", "light", lambda: self._with(
                table_fn(), items_fn(), lambda o: OrderDetailDialog(self, o["id"]))))
            if can_e:
                buttons.append(ui.button("✏️ تعديل", "blue", lambda: self._with(
                    table_fn(), items_fn(), lambda o: OrderDialog(self, o))))
            if can_d:
                buttons.append(ui.button("🗑️ مسح", "red", lambda: self._with(
                    table_fn(), items_fn(), self._delete)))
            return ui.hbox(title_lbl, None, *buttons)

        self._dep_title = ui.section_title("")
        self.body.addLayout(bar(self._dep_title, "✅ تأكيد استلام العربون", self._confirm_deposit,
                                lambda: self._dep_table, lambda: self._dep))
        self._dep_table = DataTable([("رقم", "int"), ("العميل", "text"), ("الموبايل", "text"), ("النوع", "text"),
                                     ("السيلز", "text"), ("السعر", "money"), ("العربون", "money"),
                                     ("طريقة الدفع", "text"), ("سجّله", "text"), ("الفرع", "wide")])
        self.body.addWidget(self._dep_table, 1)
        self._final_title = ui.section_title("")
        self.body.addLayout(bar(self._final_title, "✅ تأكيد نهائى", self._confirm_final,
                                lambda: self._final_table, lambda: self._final))
        self._final_table = DataTable([("رقم", "int"), ("العميل", "text"), ("الموبايل", "text"), ("السعر", "money"),
                                       ("العربون", "money"), ("المحصّل", "money"), ("طريقة الدفع", "text"),
                                       ("الفرق", "money"), ("الفرع", "wide")])
        self.body.addWidget(self._final_table, 1)

    def load(self):
        return self.backend.orders(statuses=["awaiting_deposit", "awaiting_accounts"])

    def render(self, rows):
        dep = [o for o in rows if o["status"] == "awaiting_deposit"]
        final = [o for o in rows if o["status"] == "awaiting_accounts"]
        self._dep, self._final = {o["id"]: o for o in dep}, {o["id"]: o for o in final}
        self._dep_title.setText(f"1️⃣ عربون الطلبات الجديدة ({len(dep)})")
        self._final_title.setText(f"2️⃣ الحساب النهائى بعد التسليم ({len(final)})")
        self._dep_table.set_rows([{"key": o["id"], "values": [
            o["id"], o["customer_name"], o.get("customer_mobile"), o.get("garment_type"), o.get("seller_name"),
            o["price"], o["deposit"], o.get("deposit_method"), o.get("created_by_name"), o.get("branch_name")]}
            for o in dep])
        self._final_table.set_rows([{
            "key": o["id"],
            "color": RED if num(o["price"]) - num(o["deposit"]) - num(o.get("final_collected")) > 0.01 else None,
            "values": [o["id"], o["customer_name"], o.get("customer_mobile"), o["price"], o["deposit"],
                       o.get("final_collected"), o.get("final_method"),
                       num(o["price"]) - num(o["deposit"]) - num(o.get("final_collected")), o.get("branch_name")]}
            for o in final])

    def _with(self, table, items, func):
        o = self.selected(table, items, "اختار طلب من الجدول الأول")
        if o:
            func(o)

    def _confirm_deposit(self):
        def go(o):
            msg = f"استلمت عربون طلب #{o['id']} ({o['customer_name']}): {money(o['deposit'])} " \
                  f"({o.get('deposit_method') or '—'})؟\nهيتسجل فى الخزينة والطلب هيدخل القص."
            if ui.ask_yes_no(self, msg):
                self.run_action(lambda: self.backend.confirm_deposit(order_id=o["id"]))
        self._with(self._dep_table, self._dep, go)

    def _confirm_final(self):
        def go(o):
            msg = f"استلمت من {o['customer_name']} (طلب #{o['id']}): {money(o.get('final_collected'))} " \
                  f"({o.get('final_method') or '—'})؟\nهيتسجل فى الخزينة والطلب هيتقفل."
            if ui.ask_yes_no(self, msg):
                self.run_action(lambda: self.backend.confirm_final(order_id=o["id"]),
                                "✅ اتقفل الحساب والطلب اتنقل للمبيعات")
        self._with(self._final_table, self._final, go)

    def _delete(self, o):
        if ui.ask_yes_no(self, f"هتمسح طلب #{o['id']} ({o['customer_name']}) نهائيًا؟"):
            self.run_action(lambda: self.backend.delete_order(order_id=o["id"]))


# ============================================================
#                       المبيعات
# ============================================================

class SalesPage(BasePage):
    PAGE = "sales"
    TITLE = "📜 المبيعات"

    def __init__(self, app):
        super().__init__(app)
        self._orders, self._sales = [], []
        self._o_by_id, self._s_by_id = {}, {}
        tabs = QTabWidget()
        self.body.addWidget(tabs, 1)

        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        self._o_title = ui.section_title("")
        self._o_search = ui.search_box("🔍 بحث برقم الطلب أو العميل أو الموبايل أو السيلز", self._render_orders)
        l1.addLayout(ui.hbox(self._o_title, None, self._o_search,
                             ui.button("📂 تفاصيل", "blue", lambda: self._with_order(
                                 lambda o: OrderDetailDialog(self, o["id"]))),
                             ui.button("🖨️ إيصال", "light", lambda: self._with_order(
                                 lambda o: print_receipt(self, o["id"])))))
        self._o_totals = ui.label("", "muted")
        l1.addWidget(self._o_totals)
        self._o_table = DataTable([("تاريخ التسليم", "date"), ("رقم", "int"), ("العميل", "text"),
                                   ("الموبايل", "text"), ("النوع", "text"), ("العدد", "int"), ("السيلز", "text"),
                                   ("السعر", "money"), ("المحصّل", "money"), ("المتبقى", "money"),
                                   ("الخامات", "money"), ("الأجور", "money"), ("الربح التقريبى", "money"),
                                   ("الفرع", "wide")])
        self._o_table.cellDoubleClicked.connect(lambda r, c: self._with_order(
            lambda o: OrderDetailDialog(self, o["id"])))
        l1.addWidget(self._o_table, 1)
        tabs.addTab(w1, "✅ طلبات تفصيل اتسلمت")

        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        self._s_title = ui.section_title("")
        buttons = [ui.button("🖨️ فاتورة", "light", self._print_sale)]
        if self.me.can_delete(self.PAGE):
            buttons.append(ui.button("🗑️ إلغاء البيعة", "red", self._delete_sale))
        l2.addLayout(ui.hbox(self._s_title, None, *buttons))
        self._s_table = DataTable([("رقم", "int"), ("التاريخ", "date"), ("العميل", "text"), ("الأصناف", "wide"),
                                   ("الإجمالى", "money"), ("التكلفة", "money"), ("طريقة الدفع", "text"),
                                   ("السيلز", "text")])
        l2.addWidget(self._s_table, 1)
        tabs.addTab(w2, "🛍️ البيع الجاهز")

    def load(self):
        return self.backend.orders(statuses=["completed"]), self.backend.ready_sales()

    def render(self, data):
        self._orders, self._sales = data
        self._o_by_id = {o["id"]: o for o in self._orders}
        self._s_by_id = {s["id"]: s for s in self._sales}
        self._render_orders()
        self._s_title.setText(f"🛍️ البيع الجاهز ({len(self._sales)}) · {money(sum(num(s['total']) for s in self._sales))}")
        self._s_table.set_rows([{"key": s["id"], "values": [
            s["id"], iso_to_display(s["created_at"]), s.get("customer_name"),
            "، ".join(f"{i['name']} {i.get('size') or ''} × {i['qty']}" for i in s["items"]), s["total"],
            sum(num(i.get("cost")) * i["qty"] for i in s["items"]), s.get("method"), s.get("seller_name")]}
            for s in self._sales])

    def _render_orders(self):
        text = self._o_search.text().strip().lstrip("#")
        shown = [o for o in self._orders if not text or text == str(o["id"]) or ui.matches(
            text, o, ("customer_name", "customer_mobile", "seller_name"))]
        profit = lambda o: num(o["price"]) - num(o["material_cost"]) - num(o["labor_cost"])  # noqa: E731
        self._o_title.setText(f"✅ طلبات اتسلمت ({len(shown)})")
        self._o_totals.setText(f"القيمة {money(sum(num(o['price']) for o in shown))} · الخامات "
                               f"{money(sum(num(o['material_cost']) for o in shown))} · الأجور بالقطعة "
                               f"{money(sum(num(o['labor_cost']) for o in shown))} · المتبقى على العملاء "
                               f"{money(sum(num(o['remaining']) for o in shown))}")
        self._o_table.set_rows([{
            "key": o["id"], "color": RED if num(o["remaining"]) > 0.01 else None,
            "values": [iso_to_display(o.get("completed_at")), o["id"], o["customer_name"], o.get("customer_mobile"),
                       o.get("garment_type"), o["quantity"], o.get("seller_name"), o["price"],
                       num(o["deposit"]) + num(o.get("final_collected")), o["remaining"], o["material_cost"],
                       o["labor_cost"], profit(o), o.get("branch_name")]} for o in shown])

    def _with_order(self, func):
        o = self.selected(self._o_table, self._o_by_id, "اختار طلب من الجدول الأول")
        if o:
            func(o)

    def _print_sale(self):
        s = self.selected(self._s_table, self._s_by_id, "اختار بيعة من الجدول الأول")
        if s:
            printing.preview(self, printing.sale_receipt_html(s, self.me.get_company(), self.app.logo_bytes),
                             "فاتورة البيع")

    def _delete_sale(self):
        s = self.selected(self._s_table, self._s_by_id, "اختار بيعة من الجدول الأول")
        if s and ui.ask_yes_no(self, f"تلغى البيعة #{s['id']} ({money(s['total'])})؟\n"
                                     "الأصناف هترجع المخزن والمبلغ هيتشال من الخزينة."):
            self.run_action(lambda: self.backend.delete_ready_sale(sale_id=s["id"]),
                            then=lambda _r: self.app.reload_lookups())
