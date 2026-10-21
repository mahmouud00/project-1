"""
اختبارات السيرفر (من غير واجهة): الترخيص، المستخدمين والصلاحيات، دورة الطلب كاملة،
المخزن، الأجور، الموردين، الخزينة، النسخ الاحتياطى.
التشغيل (من فولدر final_system):   python -m unittest discover tests -v
"""

import base64
import os
import tempfile
import unittest
import warnings
from datetime import date, timedelta

import helpers
warnings.simplefilter("ignore", ResourceWarning)

from helpers import AppError, Client, SessionError, Service, license_code, login, new_company


class LicenseTests(unittest.TestCase):
    def setUp(self):
        helpers.reset_shadow()
        self.svc = Service(tempfile.mkdtemp(), "test")
        self.anon = Client(self.svc)

    def test_no_license_blocks_everything(self):
        st = self.anon.status()
        self.assertEqual(st["license"]["state"], "none")
        self.assertFalse(st["has_company"])
        with self.assertRaises(AppError):
            self.anon.create_company(company_name="x", full_name="x", username="a", password="1234")

    def test_bad_codes(self):
        with self.assertRaises(AppError):
            self.anon.activate(code="ABCDE-12345")
        other_machine = "ABCD-ABCD-ABCD-ABCD"
        with self.assertRaisesRegex(AppError, "جهاز تانى"):
            self.anon.activate(code=license_code(machine=other_machine))
        # كود متلعب فيه (حرف اتغير) ← التوقيع مش هيطابق
        code = license_code()
        tampered = code[:-3] + ("A" if code[-3] != "A" else "B") + code[-2:]
        with self.assertRaises(AppError):
            self.anon.activate(code=tampered)

    def test_activate_then_create_company(self):
        st = self.anon.activate(code=license_code(plan=1, users=3))
        self.assertEqual(st["state"], "ok")
        self.assertTrue(st["writable"])
        self.assertEqual(st["users"], 3)
        with self.assertRaisesRegex(AppError, "متفعّل بالفعل"):
            self.anon.activate(code=license_code())
        res = self.anon.create_company(company_name="مصنع", full_name="أحمد", username="admin", password="1234")
        self.assertTrue(res["me"]["user"]["is_admin"])
        lk = Client(self.svc, res["token"]).lookups()
        self.assertTrue(lk["measure_fields"])
        self.assertEqual(len(lk["branches"]), 1)

    def test_expired_is_read_only(self):
        self.anon.activate(code=license_code(plan=1, users=3))
        res = self.anon.create_company(company_name="مصنع", full_name="أحمد", username="admin", password="1234")
        admin = Client(self.svc, res["token"])
        cid = admin.save_customer(name="عميل", mobile="010")
        # اشتراك شهر بدأ من 3 شهور ← انتهى
        old = license_code(plan=1, users=3, start=date.today() - timedelta(days=90))
        self.svc.conn.execute("update meta set value = ? where key = 'license'", (old,))
        self.svc._license_cache = None
        st = admin.me()["license"]
        self.assertEqual(st["state"], "expired")
        self.assertFalse(st["writable"])
        with self.assertRaisesRegex(AppError, "للعرض"):
            admin.save_customer(name="عميل 2", mobile="011")
        self.assertEqual(len(admin.customers()), 1)          # القراءة شغالة
        self.assertTrue(login(self.svc, "admin", "1234"))    # الدخول شغال
        self.assertTrue(admin.backup_data())                 # النسخة الاحتياطية شغالة
        st = admin.renew_license(code=license_code(plan=3, users=3))
        self.assertTrue(st["writable"])
        admin.save_customer(name="عميل 2", mobile="011", customer_id=None)
        self.assertEqual(cid, 1)

    def test_expiring_warning_and_lifetime(self):
        self.anon.activate(code=license_code(plan=1, users=3, start=date.today() - timedelta(days=27)))
        st = self.anon.status()["license"]
        self.assertEqual(st["state"], "expiring")
        self.assertTrue(st["writable"])
        self.assertLessEqual(st["days_left"], 7)
        self.svc.conn.execute("update meta set value = ? where key = 'license'", (license_code(plan=0),))
        self.svc._license_cache = None
        st = self.anon.status()["license"]
        self.assertEqual(st["state"], "ok")
        self.assertIsNone(st["expires"])

    def test_clock_tamper(self):
        self.anon.activate(code=license_code(plan=3))
        future = (date.today() + timedelta(days=30)).isoformat()
        self.svc.conn.execute("update meta set value = ? where key = 'last_seen'", (future,))
        self.svc._license_cache = None
        st = self.anon.status()["license"]
        self.assertEqual(st["state"], "tamper")
        self.assertFalse(st["writable"])

    def test_plan_expiry_math(self):
        from server.licensing import add_months, plan_expiry
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(plan_expiry(2, date(2026, 10, 21)), date(2027, 4, 21))
        self.assertEqual(plan_expiry(3, date(2026, 10, 21)), date(2027, 10, 21))
        self.assertIsNone(plan_expiry(0, date(2026, 10, 21)))


class UsersTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.admin = new_company(users=3)

    def test_login_and_wrong_password(self):
        with self.assertRaisesRegex(AppError, "غلط"):
            Client(self.svc).login(username="admin", password="xxxx")
        self.assertTrue(login(self.svc, "ADMIN", "1234").me()["user"]["is_admin"])   # الاسم مش حساس للحروف

    def test_permissions_and_limits(self):
        uid = self.admin.create_user(full_name="محمد", username="mohamed", password="1111", role_title="قصاص",
                                     pages=["cutting"], edit_pages=["cutting"], delete_pages=[])
        mo = login(self.svc, "mohamed", "1111")
        self.assertEqual(mo.me()["user"]["edit_pages"], ["cutting"])
        with self.assertRaisesRegex(AppError, "صلاحية"):
            mo.treasury()
        with self.assertRaisesRegex(AppError, "المدير"):
            mo.users()
        self.admin.create_user(full_name="سارة", username="sara", password="1111")
        # الترخيص لـ 3: المدير + محمد + سارة. الرابع مرفوض
        with self.assertRaisesRegex(AppError, "3"):
            self.admin.create_user(full_name="كريم", username="karim", password="1111")
        # إيقاف موظف بيقفل جلسته
        self.admin.set_member(user_id=uid, is_active=False, is_admin=False, pages=[], edit_pages=[],
                              delete_pages=[])
        with self.assertRaises(SessionError):
            mo.me()
        with self.assertRaisesRegex(AppError, "موقوف"):
            login(self.svc, "mohamed", "1111")
        self.admin.create_user(full_name="كريم", username="karim", password="1111")   # دلوقتى فيه مكان
        with self.assertRaisesRegex(AppError, "3"):
            self.admin.set_member(user_id=uid, is_active=True, is_admin=False, pages=[], edit_pages=[],
                                  delete_pages=[])
        self.admin.remove_member(user_id=uid)
        self.assertEqual(len(self.admin.users()), 3)
        with self.assertRaisesRegex(AppError, "نفسك"):
            self.admin.set_member(user_id=1, is_active=True, is_admin=False, pages=[], edit_pages=[],
                                  delete_pages=[])

    def test_passwords(self):
        self.admin.change_my_password(old_password="1234", new_password="5678")
        login(self.svc, "admin", "5678")
        uid = self.admin.create_user(full_name="محمد", username="mo", password="1111")
        self.admin.reset_password(user_id=uid, new_password="2222")
        login(self.svc, "mo", "2222")
        with self.assertRaises(AppError):
            self.admin.create_user(full_name="x", username="mo", password="1111")      # اسم مكرر

    def test_settings_and_logo(self):
        gid = self.admin.save_setting(table="garment_types", values={"name": "بدلة سهرة", "default_price": "5000"})
        self.admin.save_setting(table="garment_types", values={"is_active": False}, row_id=gid)
        lk = self.admin.lookups()
        self.assertFalse([g for g in lk["garment_types"] if g["id"] == gid][0]["is_active"])
        with self.assertRaises(AppError):
            self.admin.save_setting(table="users", values={"name": "x"})
        self.admin.set_logo(data_b64=base64.b64encode(b"\x89PNG fake").decode(), mime="image/png")
        self.assertTrue(self.admin.me()["company"]["has_logo"])
        self.assertEqual(base64.b64decode(self.admin.company_logo()), b"\x89PNG fake")
        b2 = self.admin.save_setting(table="branches", values={"name": "فرع المهندسين", "is_main": True})
        branches = self.admin.lookups()["branches"]
        self.assertEqual([b["id"] for b in branches if b["is_main"]], [b2])


class OrderCycleTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.a = new_company()
        lk = self.a.lookups()
        self.cash = [m for m in lk["payment_methods"] if m["channel"] == "cash"][0]["id"]
        self.suit = [g for g in lk["garment_types"] if g["name"] == "بدلة 2 قطعة"][0]["id"]
        self.a.save_piece_rate(garment_type_id=self.suit, stage="sewing", rate=150)
        self.a.save_piece_rate(garment_type_id=self.suit, stage="cutting", rate=40)
        self.tailor = self.a.add_staff(name="عم سيد", kind="worker", craft="خياط", pay_type="piece")
        self.cutter = self.a.add_staff(name="حسن", kind="worker", craft="قصاص", pay_type="salary", salary=6000)
        self.seller = self.a.add_staff(name="منى", kind="sales", pay_type="salary", salary=0)
        self.fabric = self.a.save_material(name="قماش صوف كحلى", unit="متر", category="قماش", reorder_level=5)
        self.sup = self.a.add_supplier(name="مورد القماش")
        self.a.receive_material(material_id=self.fabric, qty=20, unit_cost=300, supplier_id=self.sup)
        self.a.receive_material(material_id=self.fabric, qty=10, unit_cost=360)

    def mat(self, mid=None):
        mid = mid or self.fabric
        return [m for m in self.a.materials() if m["id"] == mid][0]

    def treasury_total(self):
        rows = self.a.treasury()
        return sum(r["amount_in"] for r in rows) - sum(r["amount_out"] for r in rows)

    def test_full_cycle(self):
        m = self.mat()
        self.assertAlmostEqual(m["avg_cost"], 320)          # (20×300 + 10×360) / 30
        self.assertEqual(self.a.supplier_balances()[0]["remaining"], 6000)

        oid = self.a.add_order(customer_name="كريم", mobile="01000000000", garment_type_id=self.suit, quantity=2,
                               price=9000, deposit=3000, deposit_method_id=self.cash, seller_id=self.seller,
                               measurements={"جاكيت|الطول": "76", "جاكيت|الكتف": " 46 ", "بنطلون|الوسط": ""},
                               style={"الياقة": "شال"}, due_date=(date.today() + timedelta(days=10)).isoformat())
        o = self.a.order_detail(order_id=oid)
        self.assertEqual(o["status"], "awaiting_deposit")
        self.assertEqual(o["measurements"], {"جاكيت|الطول": "76", "جاكيت|الكتف": "46"})
        cust = self.a.customer_detail(customer_id=o["customer_id"])
        self.assertEqual(cust["customer"]["measurements"]["جاكيت|الكتف"], "46")
        self.assertEqual(len(cust["history"]), 1)
        self.assertEqual(self.treasury_total(), 0)

        with self.assertRaisesRegex(AppError, "مرحلة"):
            self.a.finish_cutting(order_id=oid)
        self.a.confirm_deposit(order_id=oid)
        self.assertEqual(self.treasury_total(), 3000)
        with self.assertRaisesRegex(AppError, "مرحلة"):
            self.a.confirm_deposit(order_id=oid)              # مفيش ترحيل مرتين
        with self.assertRaisesRegex(AppError, "العربون"):
            self.a.update_order(order_id=oid, deposit=4000)

        with self.assertRaisesRegex(AppError, "الموجودة"):
            self.a.finish_cutting(order_id=oid, materials=[{"material_id": self.fabric, "qty": 50}])
        self.a.finish_cutting(order_id=oid, worker_id=self.cutter, materials=[{"material_id": self.fabric, "qty": 6}])
        self.assertAlmostEqual(self.mat()["qty"], 24)
        self.assertEqual(self.a.finish_sewing(order_id=oid, worker_id=self.tailor), "fitting")
        self.a.fitting_result(order_id=oid, ok=False, note="الكم طويل")
        self.assertEqual(self.a.order_detail(order_id=oid)["status"], "sewing")
        self.a.finish_sewing(order_id=oid, worker_id=self.tailor)
        self.a.fitting_result(order_id=oid, ok=True)
        self.a.finish_finishing(order_id=oid)
        self.a.deliver_order(order_id=oid, collected=6000, method_id=self.cash)
        self.assertEqual(self.treasury_total(), 3000)        # لسه مستنى تأكيد الحسابات
        self.a.confirm_final(order_id=oid)
        self.assertEqual(self.treasury_total(), 9000)

        o = self.a.order_detail(order_id=oid)
        self.assertEqual(o["status"], "completed")
        self.assertEqual(o["remaining"], 0)
        self.assertAlmostEqual(o["material_cost"], 6 * 320)
        self.assertAlmostEqual(o["labor_cost"], 2 * 150 * 2)  # خياطة مرتين (بعد البروفة) × عدد 2 — القصاص بمرتب
        self.assertEqual(o["fitting_count"], 1)
        self.assertGreaterEqual(len(o["events"]), 8)
        with self.assertRaisesRegex(AppError, "اتقفل"):
            self.a.update_order(order_id=oid, price=1)
        with self.assertRaisesRegex(AppError, "للخزينة"):
            self.a.delete_order(order_id=oid)

        pay = {r["name"]: r for r in self.a.payroll()["rows"]}
        self.assertEqual(pay["عم سيد"]["pieces"], 600)
        self.assertEqual(pay["حسن"]["salary"], 6000)
        self.a.add_staff_txn(staff_id=self.tailor, txn_type="advance", amount=200, method_id=self.cash)
        self.a.add_staff_txn(staff_id=self.tailor, txn_type="bonus", amount=50)
        self.a.add_staff_txn(staff_id=self.tailor, txn_type="payment", amount=300, method_id=self.cash)
        pay = {r["name"]: r for r in self.a.payroll()["rows"]}
        self.assertEqual(pay["عم سيد"]["remaining"], 600 + 50 - 200 - 300)
        self.assertEqual(self.treasury_total(), 9000 - 500)

        d = self.a.dashboard()
        self.assertEqual(d["kpis"]["raseed"], 8500)
        self.assertEqual(d["kpis"]["open_orders"], 0)
        self.assertEqual(d["sellers"][0]["name"], "منى")

    def test_no_fitting_and_step_back(self):
        oid = self.a.add_order(customer_name="علاء", mobile="0111", price=3000, needs_fitting=False)
        self.a.confirm_deposit(order_id=oid)
        self.a.finish_cutting(order_id=oid)
        self.assertEqual(self.a.finish_sewing(order_id=oid), "finishing")
        self.assertEqual(self.a.step_back(order_id=oid), "sewing")
        self.a.delete_order(order_id=oid)               # مفيش فلوس ولا خامات ولا أجور ← يتمسح
        self.assertEqual(self.a.orders(), [])

    def test_validation(self):
        with self.assertRaisesRegex(AppError, "موبايل"):
            self.a.add_order(customer_name="x", price=100)
        with self.assertRaisesRegex(AppError, "العربون"):
            self.a.add_order(customer_name="x", mobile="1", price=100, deposit=200, deposit_method_id=self.cash)
        with self.assertRaisesRegex(AppError, "طريقة"):
            self.a.add_order(customer_name="x", mobile="1", price=100, deposit=50)
        with self.assertRaisesRegex(AppError, "ناقص"):
            self.a.add_order(customer_name="x", mobile="1", price=100, bogus=1)
        # نفس الموبايل = نفس العميل
        o1 = self.a.add_order(customer_name="سامح", mobile="0122", price=100)
        o2 = self.a.add_order(customer_name="سامح على", mobile="0122", price=100)
        self.assertEqual(self.a.order_detail(order_id=o1)["customer_id"], self.a.order_detail(order_id=o2)["customer_id"])

    def test_ready_sale_and_files(self):
        pid = self.a.save_product(name="بدلة جاهزة كحلى", size="50", color="كحلى", price=4500)
        self.a.product_in(product_id=pid, qty=3, unit_cost=2500)
        with self.assertRaisesRegex(AppError, "المتاح"):
            self.a.add_ready_sale(items=[{"product_id": pid, "qty": 5}], method_id=self.cash)
        sid = self.a.add_ready_sale(items=[{"product_id": pid, "qty": 2}], method_id=self.cash, customer_name="زبون")
        self.assertEqual(self.a.products()[0]["qty"], 1)
        self.assertEqual(self.treasury_total(), 9000)
        entry = [r for r in self.a.treasury() if r["source"] == "ready_sale"][0]
        with self.assertRaisesRegex(AppError, "ألغِ"):
            self.a.delete_treasury_entry(entry_id=entry["id"])
        self.a.delete_ready_sale(sale_id=sid)
        self.assertEqual(self.a.products()[0]["qty"], 3)
        self.assertEqual(self.treasury_total(), 0)

        data = base64.b64encode(b"%PDF-1.4 test").decode()
        oid = self.a.add_order(customer_name="x", mobile="5", price=100,
                               files=[{"name": "فاتورة.pdf", "mime": "application/pdf", "data": data}])
        f = self.a.order_detail(order_id=oid)["files"][0]
        self.assertEqual(base64.b64decode(self.a.get_file(file_id=f["id"])["data"]), b"%PDF-1.4 test")

    def test_suppliers_cheques_treasury(self):
        self.a.add_supplier_txn(supplier_id=self.sup, txn_type="cash_payment", amount=1000)
        self.a.add_supplier_txn(supplier_id=self.sup, txn_type="cheque", amount=2000, cheque_no="55",
                                due_date=date.today().isoformat())
        self.a.add_supplier_txn(supplier_id=self.sup, txn_type="cheque", amount=500, cheque_no="56",
                                due_date=(date.today() + timedelta(days=20)).isoformat())
        b = self.a.supplier_balances()[0]
        self.assertEqual(b["remaining"], 6000 - 1000 - 2500)
        self.assertEqual(b["cheques_due"], 2500)
        self.assertEqual(self.a.cash_due_cheques(), 1)
        self.assertEqual(self.a.cash_due_cheques(), 0)
        self.assertEqual(len(self.a.due_cheques()), 1)
        self.assertEqual(self.treasury_total(), -3000)
        # مسح قيد صرف الشيك ← الشيك يرجع مستحق
        cheque_entry = [r for r in self.a.treasury() if r["source"] == "cheque"][0]
        self.a.delete_treasury_entry(entry_id=cheque_entry["id"])
        self.assertEqual(len(self.a.due_cheques()), 2)
        # مسح دفعة نقدية ← حركة المورد تتمسح معاها
        pay_entry = [r for r in self.a.treasury() if r["source"] == "supplier_payment"][0]
        self.assertEqual(self.a.delete_treasury_entry(entry_id=pay_entry["id"]), 1)
        self.assertEqual(self.a.supplier_balances()[0]["remaining"], 6000 - 2500)
        e = self.a.add_treasury_entry(direction="out", amount=750, description="كهربا", payment_method_id=self.cash)
        self.assertTrue(e)
        with self.assertRaises(AppError):
            self.a.add_treasury_entry(direction="out", amount=0, description="x")

    def test_inventory_adjust(self):
        self.a.adjust_material(material_id=self.fabric, new_qty=28, note="جرد آخر الشهر")
        self.assertAlmostEqual(self.mat()["qty"], 28)
        self.a.issue_material(material_id=self.fabric, qty=25, note="هالك")
        self.assertTrue(self.mat()["low"])
        self.assertEqual(self.a.dashboard()["kpis"]["low_stock"], 1)
        self.assertEqual(len(self.a.material_moves(material_id=self.fabric)), 4)


class MaterialsFormulaTests(unittest.TestCase):
    """تركيبة الخامات: المعادلات الافتراضية، الحجز عند الطلب، الخصم عند القص، وتعديل المعادلات."""

    def setUp(self):
        self.svc, self.a = new_company()
        lk = self.a.lookups()
        self.types = {g["name"]: g["id"] for g in lk["garment_types"]}
        self.mats = {m["name"]: m["id"] for m in lk["materials"]}
        self.fabric = self.a.save_material(name="صوف كحلى", unit="متر", category="قماش")
        self.a.receive_material(material_id=self.fabric, qty=10, unit_cost=300)
        self.a.receive_material(material_id=self.mats["بطانة"], qty=20, unit_cost=50)
        self.m = {"جاكيت|الطول": "76", "جاكيت|طول الكم": "62", "بنطلون|الطول": "105", "جاكيت|الصدر": "112"}

    def test_defaults_seeded(self):
        lk = self.a.lookups()
        self.assertTrue({"بطانة", "حشو وتقوية", "زراير بدلة", "خيط"} <= set(self.mats))
        suit_lines = [b for b in lk["bom_lines"] if b["garment_type_id"] == self.types["بدلة 2 قطعة"]]
        self.assertEqual(len(suit_lines), 5)
        self.assertTrue(suit_lines[0]["is_fabric"])
        buttons = [o for o in lk["style_options"] if o["name"] == "الزراير"][0]
        self.assertIn("دبل (صفين) = +0.3", buttons["choices"])

    def test_calc_reserve_and_cut(self):
        plan = self.a.calc_materials(garment_type_id=self.types["بدلة 2 قطعة"], quantity=1, measurements=self.m,
                                     fabric_material_id=self.fabric)
        q = {p["name"]: p["qty"] for p in plan}
        self.assertEqual(q["صوف كحلى"], 3.25)      # (76 + 105 + 62) ÷ 100 + 0.4 + 0.25 ← تقريب لأقرب ربع
        self.assertEqual(q["بطانة"], 1.5)
        self.assertEqual(q["زراير بدلة"], 10)
        self.assertTrue([p for p in plan if p["name"] == "زراير بدلة"][0]["short"])   # مفيش زراير فى المخزن
        # دبل ← قماش زيادة 0.3
        plan2 = self.a.calc_materials(garment_type_id=self.types["بدلة 2 قطعة"], measurements=self.m,
                                      style={"الزراير": "دبل (صفين)"}, fabric_material_id=self.fabric)
        self.assertAlmostEqual({p["name"]: p["qty"] for p in plan2}["صوف كحلى"], 3.55)
        # قماش العميل ← مفيش قماش من المخزن
        plan3 = self.a.calc_materials(garment_type_id=self.types["بدلة 2 قطعة"], measurements=self.m,
                                      fabric_source="customer", fabric_material_id=self.fabric)
        self.assertNotIn("صوف كحلى", {p["name"] for p in plan3})

        oid = self.a.add_order(customer_name="كريم", mobile="011", price=9000, garment_type_id=self.types["بدلة 2 قطعة"],
                               quantity=2, measurements=self.m, fabric_material_id=self.fabric)
        fabric = [m for m in self.a.materials() if m["id"] == self.fabric][0]
        self.assertEqual(fabric["reserved"], 6.5)
        self.assertEqual(fabric["available"], 3.5)
        self.assertEqual(fabric["qty"], 10)                  # لسه متخصمش
        o = self.a.order_detail(order_id=oid)
        self.assertEqual({p["name"]: p["qty"] for p in o["materials_plan"]}["صوف كحلى"], 6.5)
        # تعديل الطلب قبل القص ← الحجز بيتحسب تانى
        self.a.update_order(order_id=oid, quantity=1)
        self.assertEqual([m for m in self.a.materials() if m["id"] == self.fabric][0]["reserved"], 3.25)
        self.a.confirm_deposit(order_id=oid)
        used = [{"material_id": p["material_id"], "qty": p["qty"]} for p in self.a.order_detail(order_id=oid)
                ["materials_plan"] if p["material_id"] in (self.fabric, self.mats["بطانة"])]
        self.a.finish_cutting(order_id=oid, materials=used)
        fabric = [m for m in self.a.materials() if m["id"] == self.fabric][0]
        self.assertEqual((fabric["qty"], fabric["reserved"]), (6.75, 0))     # اتخصم والحجز اتفك

    def test_missing_measure_uses_fallback(self):
        plan = self.a.calc_materials(garment_type_id=self.types["جاكيت"], measurements={},
                                     fabric_material_id=self.fabric)
        p = [x for x in plan if x["name"] == "صوف كحلى"][0]
        self.assertEqual(p["qty"], 1.9)
        self.assertIn("ناقص", p["note"])

    def test_edit_formulas(self):
        t = self.types["بنطلون"]
        line = self.a.save_bom_line(garment_type_id=t, is_fabric=True, formula="[بنطلون الطول] ÷ 100 + 0.5",
                                    fallback_qty=1.5, sort=0)
        with self.assertRaisesRegex(AppError, "مش موجود"):
            self.a.save_bom_line(garment_type_id=t, is_fabric=True, formula="[بنطلون الوزن] + 1")
        with self.assertRaisesRegex(AppError, "غلط"):
            self.a.save_bom_line(garment_type_id=t, is_fabric=True, formula="(1 +")
        self.assertEqual(self.a.test_formula(formula="[بنطلون الطول] ÷ 100 + 0.5",
                                             measurements={"بنطلون|الطول": "100"}), {"ok": True, "qty": 1.5})
        self.assertFalse(self.a.test_formula(formula="[بنطلون الطول]")["ok"])
        for b in self.a.lookups()["bom_lines"]:
            if b["garment_type_id"] == t and b["id"] != line and b["is_fabric"]:
                self.a.delete_bom_line(line_id=b["id"])
        plan = self.a.calc_materials(garment_type_id=t, measurements={"بنطلون|الطول": "100"},
                                     fabric_material_id=self.fabric)
        self.assertEqual({p["name"]: p["qty"] for p in plan}["صوف كحلى"], 1.5)


class MigrationTests(unittest.TestCase):
    def test_old_database_upgrades(self):
        """قاعدة بيانات من الإصدار 1 (قبل المعادلات) بتتحدّث من غير ما البيانات تضيع."""
        import sqlite3
        svc, a = new_company()
        oid = a.add_order(customer_name="قديم", mobile="1", price=100)
        path = svc.db_path
        svc.close()
        conn = sqlite3.connect(path)
        conn.execute("drop table bom_lines")
        conn.execute("alter table orders drop column materials_plan")
        conn.execute("alter table orders drop column fabric_material_id")
        conn.execute("delete from meta where key = 'bom_seeded'")
        conn.execute("update meta set value = '1' where key = 'schema_version'")
        conn.commit()
        conn.close()
        svc2 = Service(os.path.dirname(path), "test")
        a2 = login(svc2, "admin", "1234")
        self.assertEqual(a2.order_detail(order_id=oid)["customer_name"], "قديم")
        self.assertTrue(a2.lookups()["bom_lines"])
        self.assertEqual(svc2._meta("schema_version"), "2")


class BackupTests(unittest.TestCase):
    def test_backup_restore(self):
        svc, a = new_company()
        a.save_customer(name="قبل النسخة", mobile="1")
        data = a.backup_data()
        a.save_customer(name="بعد النسخة", mobile="2")
        self.assertEqual(len(a.customers()), 2)
        a.restore_backup(data_b64=data)
        with self.assertRaises(SessionError):          # كل الجلسات بتتقفل بعد الاسترجاع
            a.customers()
        a2 = login(svc, "admin", "1234")
        self.assertEqual([c["name"] for c in a2.customers()], ["قبل النسخة"])
        self.assertTrue(a2.me()["license"]["writable"])   # الترخيص فضل زى ما هو
        with self.assertRaisesRegex(AppError, "مش نسخة"):
            a2.restore_backup(data_b64=base64.b64encode(b"not a database").decode())
        self.assertTrue(svc.auto_backup())
        self.assertTrue(any(b["name"].startswith("auto-") for b in a2.backups()))
        self.assertTrue(os.path.exists(svc.db_path))


if __name__ == "__main__":
    unittest.main()
