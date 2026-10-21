"""
اختبار الواجهة كاملة (من غير شاشة): أول تشغيل كسيرفر ← تفعيل ← إنشاء شركة ← دخول ←
كل الصفحات ← طلب جديد ← المراحل ← مستخدم بصلاحيات محدودة ← انتهاء الترخيص (للعرض بس).
لو PySide6 مش متثبتة الاختبار ده بيتخطى.
التشغيل:  QT_QPA_PLATFORM=offscreen python -m unittest tests.test_gui -v
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
import warnings
from datetime import date, timedelta

warnings.simplefilter("ignore", ResourceWarning)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_DATA = tempfile.mkdtemp()
os.environ["TM_DATA_DIR"] = _DATA

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402  (بيظبط مفتاح التراخيص بتاع الاختبار)

try:
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit
except ImportError:      # pragma: no cover
    QApplication = None

SHOTS = os.environ.get("TM_SHOTS")       # فولدر لو عايز صور الشاشات


@unittest.skipIf(QApplication is None, "PySide6 مش متثبتة")
class GuiFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import qt_widgets as ui
        import printing
        cls.messages = []
        cls.answers = []
        ui.show_info = lambda parent, text, title="تم": cls.messages.append(("info", str(text)))
        ui.show_error = lambda parent, error, title="خطأ": cls.messages.append(("error", str(error)))
        ui.ask_yes_no = lambda parent, text, title="تأكيد": cls.answers.pop(0) if cls.answers else True
        cls.printed = []
        printing.preview = lambda parent, html, title="": cls.printed.append(title)
        helpers.reset_shadow()
        from qt_main import AppController
        cls.c = AppController()
        cls.c.window.show()

    @classmethod
    def tearDownClass(cls):
        cls.c.quit_all(confirm=False) if cls.c.server else None
        shutil.rmtree(_DATA, ignore_errors=True)

    # ---------- أدوات ----------

    def pump(self, cond=lambda: False, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            QApplication.processEvents()
            if not self.c.worker.is_busy() and cond():
                return True
            time.sleep(0.01)
        QApplication.processEvents()
        return cond()

    def idle(self):
        self.pump(lambda: True)
        self.pump(lambda: not self.c.worker.is_busy())

    def screen(self):
        return self.c.window.centralWidget()

    def shot(self, name, widget=None):
        if SHOTS:
            for _ in range(20):
                QApplication.processEvents()
                time.sleep(0.01)
            os.makedirs(SHOTS, exist_ok=True)
            (widget or self.c.window).grab().save(os.path.join(SHOTS, f"{name}.png"))

    def dialogs(self, cls=QDialog):
        return [w for w in QApplication.topLevelWidgets() if isinstance(w, cls) and w.isVisible()]

    def close_dialogs(self):
        for d in self.dialogs():
            d.close()
        self.idle()

    def no_errors(self):
        errors = [m for m in self.messages if m[0] == "error"]
        self.messages.clear()
        self.assertEqual(errors, [])

    # ---------- الاختبار ----------

    def test_full_flow(self):
        from qt_auth import SetupScreen, ActivationScreen, CreateCompanyScreen, LoginScreen
        from qt_main import MainPage
        c = self.c
        self.pump(lambda: isinstance(self.screen(), SetupScreen))
        self.shot("01_setup")
        c.choose_mode("server")
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), ActivationScreen)))
        self.shot("02_activation")

        act = self.screen()
        act._code.setPlainText("WRONG-CODE")
        act._activate()
        self.idle()
        self.assertIn("❌", act.msg.text())
        act._code.setPlainText(helpers.license_code(plan=3, users=3))
        act._activate()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), CreateCompanyScreen)))

        cc = self.screen()
        cc._company.setText("مصنع النجمة للبدل")
        cc._phone.setText("01000000000")
        cc._name.setText("محمود")
        cc._pass.setText("1234")
        cc._pass2.setText("1234")
        self.shot("03_create_company")
        cc._create()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), MainPage)))
        main = self.screen()
        self.idle()
        self.assertEqual(main._busy.text(), "")          # مؤشر التحميل بيختفى لما الشغل يخلص
        self.shot("04_dashboard")
        self.no_errors()

        # كل الصفحات بتفتح من غير أخطاء
        for i, title in enumerate(main.page_titles()):
            main.show_page(i)
            self.idle()
            self.shot(f"05_page_{i:02d}")
        self.no_errors()
        self.assertEqual(len(main.page_titles()), 16)

        b = c.backend
        cash = [m for m in main.lookups["payment_methods"] if m["channel"] == "cash"][0]["id"]
        suit = [g for g in main.lookups["garment_types"] if g["name"] == "بدلة 2 قطعة"][0]["id"]
        b.add_staff(name="عم سيد", kind="worker", craft="خياط")
        b.add_staff(name="منى", kind="sales", pay_type="salary")
        b.save_material(name="قماش صوف كحلى", unit="متر", category="قماش", reorder_level=3)
        main.reload_lookups()
        self.idle()

        # ---------- طلب جديد من الواجهة ----------
        from pages_orders import OrderDialog, CutDialog, OrderDetailDialog, ReadySaleDialog
        orders_page = main.show_page_key("orders")
        self.idle()
        dlg = OrderDialog(orders_page)
        self.idle()
        dlg._mobile.setText("01011111111")
        dlg._lookup_customer()
        dlg._name.setText("كريم عادل")
        dlg._type.setCurrentIndex([dlg._type.itemData(i) for i in range(dlg._type.count())].index(suit))
        dlg._price.setText("8,500")
        dlg._deposit.setText("٣٠٠٠")          # أرقام عربى
        first = list(dlg._measure._edits.values())
        first[0].setText("76")
        first[1].setText("46")
        fabric_id = [m for m in b.materials() if m["name"] == "قماش صوف كحلى"][0]["id"]
        dlg._fabric_mat.setCurrentIndex(dlg._fabric_mat.findData(fabric_id))
        self.idle()
        self.assertIn("قماش صوف كحلى", dlg._plan_label.text())     # الخامات اتحسبت بالمعادلات
        self.assertIn("بطانة", dlg._plan_label.text())
        self.shot("06_order_dialog", dlg)
        self.answers.extend([True, False])    # المخزن مش مكفّى: كمّل؟ أيوه — تطبع إيصال؟ لأ
        dlg._save()
        self.idle()
        self.assertFalse(dlg.isVisible(), dlg._msg.text())
        orders = b.orders()
        self.assertEqual(len(orders), 1)
        oid = orders[0]["id"]
        self.assertEqual(orders[0]["deposit"], 3000)
        self.assertEqual(len(orders[0]["measurements"]), 2)
        self.assertEqual({p["name"]: p["qty"] for p in orders[0]["materials_plan"]}["قماش صوف كحلى"], 3.25)

        # نفس الموبايل ← العميل بيتعرف ومقاساته بتنزل لوحدها
        dlg2 = OrderDialog(orders_page)
        self.idle()
        dlg2._mobile.setText("01011111111")
        dlg2._lookup_customer()
        self.idle()
        self.assertEqual(dlg2._name.text(), "كريم عادل")
        self.assertEqual(len(dlg2._measure.get()), 2)
        dlg2.close()

        # تفاصيل + طباعة
        detail = OrderDetailDialog(orders_page, oid)
        self.idle()
        self.shot("07_order_detail", detail)
        detail.close()
        from pages_orders import print_receipt, print_ticket
        print_receipt(orders_page, oid)
        print_ticket(orders_page, oid)
        self.idle()
        self.assertEqual(len(self.printed), 2)

        # تأكيد العربون من صفحة الحسابات
        acc = main.show_page_key("accounts")
        self.idle()
        acc._dep_table.select_key(oid)
        acc._confirm_deposit()
        self.idle()
        self.assertEqual(b.order_detail(order_id=oid)["status"], "cutting")

        # القص بخامات
        b.receive_material(material_id=fabric_id, qty=10, unit_cost=250)
        main.reload_lookups()
        self.idle()
        cut = main.show_page_key("cutting")
        self.idle()
        cut._table.select_key(oid)
        cut._with(cut._advance)
        self.idle()
        cd = self.dialogs(CutDialog)[0]
        self.assertEqual(len(cd._rows), 5)            # الكميات جاية جاهزة من المعادلات
        combo, qty, _ = [r for r in cd._rows if r[0].currentData() == fabric_id][0]
        self.assertEqual(qty.text(), "3.25")
        qty.setText("3.5")
        self.shot("08_cut_dialog", cd)
        cd._save()
        self.idle()
        o = b.order_detail(order_id=oid)
        self.assertEqual(o["status"], "sewing")
        self.assertAlmostEqual(o["material_cost"], 875)

        for stage_fn in (lambda: b.finish_sewing(order_id=oid), lambda: b.fitting_result(order_id=oid, ok=True),
                         lambda: b.finish_finishing(order_id=oid)):
            stage_fn()
        main.after_change()
        self.idle()
        delivery = main.show_page_key("delivery")
        self.idle()
        self.assertEqual(delivery._table.rowCount(), 1)
        self.no_errors()

        # بيع جاهز من الواجهة
        pid = b.save_product(name="بدلة جاهزة", size="50", price=4000)
        b.product_in(product_id=pid, qty=2, unit_cost=2000)
        main.reload_lookups()
        self.idle()
        rs = ReadySaleDialog(orders_page)
        rs._rows[0]["combo"].setCurrentIndex(1)
        self.assertEqual(rs._rows[0]["price"].text(), "4000")
        self.answers.append(False)
        rs._save()
        self.idle()
        self.assertEqual(len(b.ready_sales()), 1)

        # الإعدادات: مستخدم جديد بصلاحية القص بس
        from pages_settings import PermissionsDialog
        settings = main.show_page_key("settings")
        self.idle()
        self.shot("09_settings")
        pd = PermissionsDialog(settings, main, None)
        pd._name.setText("حسن القصاص")
        pd._username.setText("hassan")
        pd._password.setText("1111")
        pd._checks[("cutting", "view")].setChecked(True)
        pd._checks[("cutting", "edit")].setChecked(True)
        pd._save()
        self.idle()
        self.assertEqual(len(b.users()), 2)
        self.no_errors()

        # تركيبة الخامات: تجربة معادلة وحفظها من الإعدادات
        from pages_settings import BomDialog
        bd = BomDialog(settings)
        bd._type.setCurrentIndex(bd._type.findData(suit))
        bd._formula.setPlainText("تقريب([بنطلون الطول] ÷ 100 + 0.3، 0.25)")
        list(bd._sample._edits.values())[0].setText("100")
        bd._sample.set({"بنطلون|الطول": "100"})
        bd._test()
        self.idle()
        self.assertIn("1.5", bd._result.text())
        self.shot("09b_bom_dialog", bd)
        before = len(b.lookups()["bom_lines"])
        bd._save()
        self.idle()
        self.assertEqual(len(b.lookups()["bom_lines"]), before + 1)
        self.no_errors()

        # خروج ودخول بالمستخدم المحدود
        c.logout()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), LoginScreen)))
        self.shot("10_login")
        ls = self.screen()
        ls._user.setText("hassan")
        ls._password.setText("1111")
        ls._login()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), MainPage)))
        limited = self.screen()
        self.assertEqual(limited.page_titles(), ["✂️ القص"])
        self.idle()
        self.no_errors()

        # الترخيص انتهى ← للعرض بس (الأزرار بتختفى + شريط أحمر)
        svc = c.server.service
        old = helpers.license_code(plan=1, users=3, start=date.today() - timedelta(days=60))
        svc.conn.execute("update meta set value = ? where key = 'license'", (old,))
        svc._license_cache = None
        c.logout()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), LoginScreen)))
        ls = self.screen()
        ls._user.setText("admin")
        ls._password.setText("1234")
        ls._login()
        self.assertTrue(self.pump(lambda: isinstance(self.screen(), MainPage)))
        ro = self.screen()
        self.idle()
        self.assertTrue(ro.me.read_only())
        self.assertTrue(ro._banner.isVisible() or not ro._banner.isHidden())
        self.shot("11_read_only")
        for i in range(len(ro.page_titles())):
            ro.show_page(i)
            self.idle()
        self.no_errors()


if __name__ == "__main__":
    unittest.main()
