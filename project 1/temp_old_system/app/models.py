"""
models.py
---------
- AppError: أى خطأ المستخدم المفروض يشوفه (رسالته بالعربى وجاهزة للعرض).
- PAGES: كل صفحات البرنامج ومفاتيحها (نفس المفاتيح اللى فى قاعدة البيانات).
- Me: المستخدم اللى داخل + شركته + صلاحياته.
- دوال صغيرة للتواريخ والأرقام.
"""

from datetime import date, datetime


class AppError(Exception):
    """خطأ رسالته جاهزة تتعرض للمستخدم."""
    pass


# (المفتاح، الاسم اللى بيظهر) - بنفس ترتيب القايمة الجانبية
PAGES = [
    ("dashboard", "📊 الداش بورد"),
    ("treasury", "💰 الخزينة"),
    ("sales", "🧾 المبيعات"),
    ("inspections", "🔍 المعاينات"),
    ("factory", "🏭 المصانع"),
    ("install", "🔧 التركيبات"),
    ("accounts", "✅ تأكيد الحسابات"),
    ("suppliers", "🏗️ الموردين"),
    ("cheques", "💳 الشيكات"),
    ("staff", "👥 فريق العمل"),
]
PAGE_TITLES = dict(PAGES)

STATUS_LABELS = {
    "awaiting_advance": "تأكيد مقدم", "manufacturing": "تصنيع", "installing": "تركيب",
    "awaiting_accounts": "تأكيد الحسابات", "completed": "مكتمل",
}
CHANNEL_LABELS = {"cash": "نقدى", "bank": "بنك", "wallet": "محافظ إلكترونية", "cheque": "شيكات"}
SUPPLIER_TXN_LABELS = {
    "invoice": "فاتورة", "cash_payment": "دفعة نقدية", "bank_payment": "دفعة بنكية",
    "cheque": "شيك", "return": "مرتجع",
}
STAFF_KINDS = {"sales": "سيلز", "craftsman": "صنايعى", "other": "أخرى"}


class Me:
    """المستخدم الحالى. is_admin بيشوف ويعمل كل حاجة."""

    def __init__(self, user_id, email, profile=None, company=None):
        self._user_id = user_id
        self._email = email
        p = profile or {}
        self._has_profile = profile is not None
        self._full_name = p.get("full_name") or email
        self._role_title = p.get("role_title") or ""
        self._is_active = bool(p.get("is_active"))
        self._is_admin = bool(p.get("is_admin"))
        self._pages = set(p.get("pages") or [])
        self._edit = set(p.get("edit_pages") or [])
        self._delete = set(p.get("delete_pages") or [])
        self._company = company or {}

    def get_user_id(self):
        return self._user_id

    def get_email(self):
        return self._email

    def get_full_name(self):
        return self._full_name

    def get_role_title(self):
        return self._role_title

    def get_company(self) -> dict:
        return self._company

    def get_company_id(self):
        return self._company.get("id")

    def has_company(self) -> bool:
        return self._has_profile

    def is_active(self) -> bool:
        return self._is_active and bool(self._company)

    def is_admin(self) -> bool:
        return self._is_admin and self.is_active()

    def can_view(self, page) -> bool:
        return self.is_admin() or (self.is_active() and (page in self._pages or page in self._edit))

    def can_edit(self, page) -> bool:
        return self.is_admin() or (self.is_active() and page in self._edit)

    def can_delete(self, page) -> bool:
        return self.is_admin() or (self.is_active() and page in self._delete)


# ======================= تواريخ وأرقام =======================

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_user_date(text):
    """التاريخ اللى المستخدم بيكتبه (25/12/2026) ← date. فاضى ← None. غلط ← AppError."""
    text = str(text or "").strip().translate(_ARABIC_DIGITS)
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise AppError(f"التاريخ «{text}» مش مفهوم (اكتبه كده: 25/12/2026)")


def parse_amount(text, label="المبلغ", allow_zero=False):
    """رقم اللى المستخدم بيكتبه ← float. بيقبل الفواصل والأرقام العربى."""
    raw = str(text if text is not None else "").strip().translate(_ARABIC_DIGITS).replace(",", "")
    if not raw:
        if allow_zero:
            return 0.0
        raise AppError(f"{label} مطلوب")
    try:
        value = float(raw)
    except ValueError:
        raise AppError(f"{label} لازم يكون رقم")
    if value < 0 or (value == 0 and not allow_zero):
        raise AppError(f"{label} لازم يكون أكبر من صفر")
    return value


def iso_to_display(value) -> str:
    """'2026-10-18' أو '2026-10-18T10:20:00+00:00' ← '18/10/2026'."""
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def month_label(value) -> str:
    """'2026-10-01' ← '10/2026'."""
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        return f"{d.month:02d}/{d.year}"
    except ValueError:
        return str(value)


def is_active_row(row) -> bool:
    """فيه جداول (زى الفروع) مالهاش عمود is_active - دى بتتعتبر شغّالة دايمًا."""
    return row["is_active"] is not False if "is_active" in row else True


def num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
