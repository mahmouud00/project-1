"""ورقة المصنع: كل مرحلة خلصت إمتى ومين عملها، بالترتيب (والبروفة المتعادة فى مكانها)."""

import os
import sys
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402

try:
    import printing
except ImportError:      # pragma: no cover
    printing = None


@unittest.skipIf(printing is None, "PySide6 مش متثبتة")
class TicketTest(unittest.TestCase):
    def test_stage_times(self):
        _svc, a = helpers.new_company()
        cutter = a.add_staff(name="حسن", kind="worker")
        tailor = a.add_staff(name="عم سيد", kind="worker")
        oid = a.add_order(customer_name="محمود", mobile="010", price=5000)
        a.confirm_deposit(order_id=oid)
        a.finish_cutting(order_id=oid, worker_id=cutter)
        a.finish_sewing(order_id=oid, worker_id=tailor)
        a.fitting_result(order_id=oid, ok=False, note="الكم طويل")
        a.finish_sewing(order_id=oid, worker_id=tailor)
        rows = printing.production_rows(a.order_detail(order_id=oid))
        done = [r[0] for r in rows if r[4]]
        self.assertEqual(done, ["استلام الطلب", "تأكيد العربون", "القص", "الخياطة", "البروفة — محتاجة تعديل",
                                "الخياطة"])
        self.assertEqual([r[0] for r in rows if not r[4]], ["التشطيب والكى", "التسليم للعميل"])
        self.assertIn("حسن", rows[2][2])
        self.assertTrue(all(r[1] for r in rows if r[4]))           # كل مرحلة خلصت ليها وقت
        self.assertEqual(rows[0][2], "")                            # من غير أسعار فى ورقة المصنع
        html = printing.workshop_ticket_html(a.order_detail(order_id=oid), a.me()["company"])
        self.assertIn("مراحل التصنيع", html)
        self.assertNotIn("5000", html)


if __name__ == "__main__":
    unittest.main()
