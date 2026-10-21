"""
backend.py
----------
الطبقة الوحيدة اللى بتكلّم Supabase. الواجهة مش بتعرف حاجة عن Supabase خالص،
بتنادى دوال الكلاس ده وبس - فلو غيّرنا السيرفر بعدين، الملف ده بس اللى بيتغير.

- القراءة: من الـ views (treasury_view, jobs_view...). قاعدة البيانات نفسها
  بتضمن إن كل شركة تشوف بياناتها بس.
- الكتابة: كل عملية بتنادى دالة على السيرفر (rpc) بنفس اسمها فى 03_functions.sql.
- أى خطأ بيتحوّل لـ AppError برسالة عربى مفهومة.
"""

import os
import uuid
from datetime import date

from models import AppError, Me

PAGE_SIZE = 1000          # أقصى عدد صفوف Supabase بيرجّعه فى المرة
INVOICE_BUCKET = "invoices"
MAX_INVOICE_MB = 20
LOGO_BUCKET = "company-logos"
MAX_LOGO_MB = 2
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

AUTH_MESSAGES = {
    "invalid login credentials": "الإيميل أو الباسورد غلط",
    "user already registered": "الإيميل ده مسجّل قبل كده — ادخل بيه بدل ما تعمل حساب جديد",
    "email not confirmed": "لازم تأكد إيميلك الأول: افتح الإيميل اللى وصلك من Supabase ودوس على اللينك",
    "password should be at least": "الباسورد لازم يكون 6 حروف أو أرقام على الأقل",
    "unable to validate email address": "الإيميل مكتوب غلط",
    "email rate limit exceeded": "اتبعتت إيميلات كتير الساعة دى — استنى شوية وجرّب تانى",
    "jwt expired": "الجلسة خلصت — اعمل خروج ودخول تانى",
}
NETWORK_HINTS = ("connecterror", "connection", "getaddrinfo", "name or service", "timed out",
                 "timeout", "network", "unreachable", "ssl")


def friendly_error(error) -> str:
    """بيحوّل أى خطأ من Supabase أو النت لرسالة عربى."""
    message = getattr(error, "message", None)
    if isinstance(message, dict):
        message = message.get("message")
    text = str(message or error or "").strip()
    low = text.lower()
    for key, arabic in AUTH_MESSAGES.items():
        if key in low:
            return arabic
    if any(h in low or h in type(error).__name__.lower() for h in NETWORK_HINTS):
        return "مفيش اتصال بالإنترنت أو السيرفر مش بيرد — اتأكد من النت وجرّب تانى"
    return text or "حصل خطأ غير معروف"


class Backend:
    def __init__(self, url, key, client=None):
        if client is None:
            from supabase import create_client   # بنستورده هنا عشان الاختبارات تشتغل من غيره
            client = create_client(url, key)
        self._c = client
        self._user_id = None
        self._email = None
        self.me = None

    # =========================================================
    #                       أدوات داخلية
    # =========================================================

    def _run(self, func):
        try:
            return func()
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001
            raise AppError(friendly_error(e)) from e

    def _rpc(self, name, params=None):
        return self._run(lambda: self._c.rpc(name, params or {}).execute().data)

    def _select(self, table, filters=(), order=(), columns="*"):
        """بيجيب كل الصفوف (على دفعات كل 1000) - filters = [(op, عمود, قيمة)]."""
        def fetch():
            rows, start = [], 0
            while True:
                q = self._c.table(table).select(columns)
                for op, col, val in filters:
                    q = getattr(q, op)(col, val)
                for col, desc in order:
                    q = q.order(col, desc=desc)
                batch = q.range(start, start + PAGE_SIZE - 1).execute().data or []
                rows.extend(batch)
                if len(batch) < PAGE_SIZE:
                    return rows
                start += PAGE_SIZE
        return self._run(fetch)

    @staticmethod
    def _iso(d):
        return d.isoformat() if isinstance(d, date) else d

    # =========================================================
    #                  الدخول والحساب والشركة
    # =========================================================

    def sign_in(self, email, password) -> Me:
        email = (email or "").strip().lower()
        if not email or not password:
            raise AppError("اكتب الإيميل والباسورد")
        res = self._run(lambda: self._c.auth.sign_in_with_password({"email": email, "password": password}))
        self._user_id, self._email = res.user.id, res.user.email
        return self.load_me()

    def sign_up(self, email, password) -> bool:
        """بيرجّع True لو دخل على طول، False لو محتاج يأكد إيميله الأول."""
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            raise AppError("اكتب إيميل صحيح")
        if len(password or "") < 6:
            raise AppError("الباسورد لازم يكون 6 حروف أو أرقام على الأقل")
        res = self._run(lambda: self._c.auth.sign_up({"email": email, "password": password}))
        if res.session is None:
            return False
        self._user_id, self._email = res.user.id, res.user.email
        return True

    def sign_out(self):
        try:
            self._c.auth.sign_out()
        except Exception:  # noqa: BLE001 - الخروج ميفشلش أبدًا من ناحية المستخدم
            pass
        self._user_id = self._email = self.me = None

    def load_me(self) -> Me:
        if not self._user_id:
            raise AppError("سجّل دخول الأول")
        profiles = self._select("profiles", [("eq", "user_id", self._user_id)])
        profile = profiles[0] if profiles else None
        company = None
        if profile:
            companies = self._select("companies", [("eq", "id", profile["company_id"])])
            company = companies[0] if companies else None
        self.me = Me(self._user_id, self._email, profile, company)
        return self.me

    def create_company(self, company_name, full_name) -> Me:
        self._rpc("create_company", {"p_company_name": company_name, "p_full_name": full_name})
        return self.load_me()

    def join_company(self, code, full_name) -> Me:
        self._rpc("join_company", {"p_join_code": code, "p_full_name": full_name})
        return self.load_me()

    # =========================================================
    #                  القوائم (الإعدادات)
    # =========================================================

    def load_lookups(self) -> dict:
        order = [("sort", False), ("name", False)]
        return {
            "branches": self._select("branches", order=[("is_main", True), ("name", False)]),
            "payment_methods": self._select("payment_methods", order=order),
            "product_types": self._select("product_types", order=order),
            "departments": self._select("departments", order=order),
            "staff": self._select("staff", order=[("name", False)]),
        }

    # =========================================================
    #                       القراءة
    # =========================================================

    def treasury(self, branch_id=None):
        filters = [("eq", "branch_id", branch_id)] if branch_id else []
        return self._select("treasury_view", filters, [("entry_date", True), ("id", True)])

    def jobs(self, statuses, branch_id=None):
        filters = [("in_", "status", list(statuses))]
        if branch_id:
            filters.append(("eq", "branch_id", branch_id))
        return self._select("jobs_view", filters, [("created_at", True)])

    def inspections(self):
        return self._select("inspections_view", order=[("status", False), ("created_at", True)])

    def supplier_balances(self):
        return self._select("supplier_balances", order=[("name", False)])

    def supplier_txns(self, supplier_id):
        return self._select("supplier_txns", [("eq", "supplier_id", supplier_id)],
                            [("txn_date", True), ("id", True)])

    def due_cheques(self):
        return self._select("due_cheques_view", order=[("due_date", False)])

    def profiles(self):
        return self._select("profiles", order=[("is_active", False), ("full_name", False)])

    def dashboard(self, branch_id=None) -> dict:
        p = {"p_branch_id": branch_id}
        return {
            "kpis": self._rpc("dashboard_kpis", p) or {},
            "profit": self._rpc("profit_by_month", p) or [],
            "contracts": self._rpc("contracts_value_by_month", p) or [],
            "treasury": self.treasury(branch_id),
        }

    # =========================================================
    #                       الكتابة (العمليات)
    # =========================================================

    # ---- الخزينة ----
    def add_treasury_entry(self, direction, amount, description, payment_method_id=None,
                           department_id=None, entry_date=None, branch_id=None, counterparty=None):
        return self._rpc("add_treasury_entry", {
            "p_direction": direction, "p_amount": amount, "p_description": description,
            "p_payment_method_id": payment_method_id, "p_department_id": department_id,
            "p_entry_date": self._iso(entry_date), "p_branch_id": branch_id, "p_counterparty": counterparty})

    def update_treasury_department(self, entry_id, department_id):
        return self._rpc("update_treasury_department", {"p_entry_id": entry_id, "p_department_id": department_id})

    def delete_treasury_entry(self, entry_id) -> int:
        return self._rpc("delete_treasury_entry", {"p_entry_id": entry_id}) or 0

    # ---- الموردين والشيكات ----
    def add_supplier(self, name, material=None, mobile=None, supplier_type=None):
        return self._rpc("add_supplier", {"p_name": name, "p_material": material, "p_mobile": mobile,
                                          "p_supplier_type": supplier_type})

    def add_supplier_txn(self, supplier_id, txn_type, amount, description=None, cheque_no=None,
                         due_date=None, branch_id=None):
        return self._rpc("add_supplier_txn", {
            "p_supplier_id": supplier_id, "p_txn_type": txn_type, "p_amount": amount,
            "p_description": description, "p_cheque_no": cheque_no, "p_due_date": self._iso(due_date),
            "p_branch_id": branch_id})

    def cash_due_cheques(self, branch_id=None) -> int:
        return self._rpc("cash_due_cheques", {"p_branch_id": branch_id}) or 0

    # ---- المعاينات ----
    def add_inspection(self, customer_name, mobile, place, product_type_id=None, notes=None, branch_id=None):
        return self._rpc("add_inspection", {
            "p_customer_name": customer_name, "p_mobile": mobile, "p_place": place,
            "p_product_type_id": product_type_id, "p_notes": notes, "p_branch_id": branch_id})

    def close_inspection(self, inspection_id):
        return self._rpc("close_inspection", {"p_id": inspection_id})

    def update_inspection(self, inspection_id, place, notes):
        return self._rpc("update_inspection", {"p_id": inspection_id, "p_place": place, "p_notes": notes})

    def delete_inspection(self, inspection_id):
        return self._rpc("delete_inspection", {"p_id": inspection_id})

    # ---- العمليات (تعاقد/صيانة) ----
    def add_job(self, kind, customer_name, mobile, place, product_type_id, price, meters=0, advance=0,
                advance_method_id=None, seller_id=None, invoice_paths=(), description=None, branch_id=None):
        return self._rpc("add_job", {
            "p_kind": kind, "p_customer_name": customer_name, "p_mobile": mobile, "p_place": place,
            "p_product_type_id": product_type_id, "p_price": price, "p_meters": meters,
            "p_advance": advance, "p_advance_method_id": advance_method_id, "p_seller_id": seller_id,
            "p_invoice_paths": list(invoice_paths), "p_description": description, "p_branch_id": branch_id})

    def confirm_advance(self, job_id):
        return self._rpc("confirm_advance", {"p_job_id": job_id})

    def finish_manufacturing(self, job_id):
        return self._rpc("finish_manufacturing", {"p_job_id": job_id})

    def finish_installation(self, job_id, collected, method_id, craftsman):
        return self._rpc("finish_installation", {"p_job_id": job_id, "p_collected": collected,
                                                 "p_method_id": method_id, "p_craftsman": craftsman})

    def confirm_final(self, job_id):
        return self._rpc("confirm_final", {"p_job_id": job_id})

    def update_job(self, job_id, place=None, price=None, advance=None, meters=None):
        return self._rpc("update_job", {"p_job_id": job_id, "p_place": place, "p_price": price,
                                        "p_advance": advance, "p_meters": meters})

    def set_job_note(self, job_id, note):
        return self._rpc("set_job_note", {"p_job_id": job_id, "p_note": note})

    def delete_job(self, job_id):
        return self._rpc("delete_job", {"p_job_id": job_id})

    # ---- فريق العمل ----
    def add_staff(self, name, mobile=None, kind="sales", hired_on=None):
        return self._rpc("add_staff", {"p_name": name, "p_mobile": mobile, "p_kind": kind,
                                       "p_hired_on": self._iso(hired_on)})

    # =========================================================
    #                    الإعدادات (المدير)
    # =========================================================

    def update_company(self, name, profit_start_date, require_invoice):
        self._rpc("update_company", {"p_name": name, "p_profit_start_date": self._iso(profit_start_date),
                                     "p_require_invoice": require_invoice})
        return self.load_me()

    def regenerate_join_code(self) -> str:
        code = self._rpc("regenerate_join_code")
        self.load_me()
        return code

    def set_member(self, user_id, is_active, is_admin, pages, edit_pages, delete_pages, role_title=None):
        return self._rpc("set_member", {
            "p_user_id": user_id, "p_is_active": is_active, "p_is_admin": is_admin,
            "p_pages": list(pages), "p_edit_pages": list(edit_pages), "p_delete_pages": list(delete_pages),
            "p_role_title": role_title})

    def remove_member(self, user_id):
        """يشيل الموظف من الشركة خالص (حسابه بيفضل، ويقدر ينضم تانى بالكود)."""
        return self._rpc("remove_member", {"p_user_id": user_id})

    def set_member_active(self, profile: dict, active: bool):
        """إيقاف/تفعيل موظف مع الحفاظ على صلاحياته زى ما هى."""
        return self.set_member(profile["user_id"], active, profile["is_admin"], profile.get("pages") or [],
                               profile.get("edit_pages") or [], profile.get("delete_pages") or [],
                               profile.get("role_title"))

    # ---------- لوجو الشركة ----------

    def upload_logo(self, path) -> bytes:
        """بيرفع اللوجو ويسجّله للشركة، وبيرجّع الصورة نفسها عشان تتعرض على طول."""
        ext = os.path.splitext(path)[1].lower()
        if ext not in LOGO_TYPES:
            raise AppError("اللوجو لازم يكون صورة PNG أو JPG")
        if not os.path.isfile(path):
            raise AppError("الملف مش موجود")
        if os.path.getsize(path) > MAX_LOGO_MB * 1024 * 1024:
            raise AppError(f"اللوجو أكبر من {MAX_LOGO_MB} ميجا — صغّر الصورة وجرّب تانى")
        with open(path, "rb") as f:
            content = f.read()
        key = f"{self.me.get_company_id()}/logo-{uuid.uuid4().hex}{ext}"
        self._run(lambda: self._c.storage.from_(LOGO_BUCKET).upload(key, content, {"content-type": LOGO_TYPES[ext]}))
        self._rpc("set_company_logo", {"p_logo_path": key})
        self.load_me()
        return content

    def remove_logo(self):
        self._rpc("set_company_logo", {"p_logo_path": None})
        self.load_me()

    def company_logo(self):
        """صورة لوجو الشركة (bytes) أو None لو مفيش."""
        path = (self.me.get_company() if self.me else {}).get("logo_path")
        if not path:
            return None
        return self._run(lambda: self._c.storage.from_(LOGO_BUCKET).download(path))

    SETTINGS_TABLES = ("branches", "payment_methods", "product_types", "departments")

    def save_setting(self, table, values: dict, row_id=None):
        """إضافة أو تعديل فرع / طريقة دفع / نوع / إدارة (المدير بس - قاعدة البيانات بتتأكد)."""
        if table not in self.SETTINGS_TABLES:
            raise AppError("جدول غير معروف")
        if not str(values.get("name", "")).strip():
            raise AppError("الاسم مطلوب")
        data = dict(values)
        if row_id:
            return self._run(lambda: self._c.table(table).update(data).eq("id", row_id).execute().data)
        data["company_id"] = self.me.get_company_id()
        return self._run(lambda: self._c.table(table).insert(data).execute().data)

    # =========================================================
    #                       الفواتير
    # =========================================================

    @staticmethod
    def check_invoice_files(paths):
        for path in paths:
            name = os.path.basename(path)
            if not os.path.isfile(path):
                raise AppError(f"الملف مش موجود: {name}")
            if not path.lower().endswith(".pdf"):
                raise AppError(f"الفاتورة لازم تكون PDF: {name}")
            if os.path.getsize(path) > MAX_INVOICE_MB * 1024 * 1024:
                raise AppError(f"الملف أكبر من {MAX_INVOICE_MB} ميجا: {name}")

    def upload_invoices(self, paths) -> list:
        """بيرفع الفواتير فى فولدر الشركة وبيرجّع أماكنها. اسم الملف بيتغير لرقم عشوائى
        (Supabase مش بيقبل الأسماء العربى فى المسار)."""
        self.check_invoice_files(paths)
        company = self.me.get_company_id()
        keys = []
        for path in paths:
            key = f"{company}/{uuid.uuid4().hex}.pdf"
            with open(path, "rb") as f:
                content = f.read()
            self._run(lambda: self._c.storage.from_(INVOICE_BUCKET).upload(
                key, content, {"content-type": "application/pdf"}))
            keys.append(key)
        return keys

    def invoice_url(self, key) -> str:
        """رابط مؤقت (ساعة) لفتح الفاتورة."""
        res = self._run(lambda: self._c.storage.from_(INVOICE_BUCKET).create_signed_url(key, 3600))
        url = (res or {}).get("signedURL") or (res or {}).get("signedUrl")
        if not url:
            raise AppError("مش قادر أفتح الفاتورة")
        return url
