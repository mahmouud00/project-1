"""
models.py
---------
- AppError: أى خطأ المستخدم المفروض يشوفه (رسالته بالعربى وجاهزة للعرض).
- PAGES: كل صفحات البرنامج ومفاتيحها (نفس المفاتيح اللى فى السيرفر).
- Me: المستخدم اللى داخل + شركته + صلاحياته + حالة الترخيص.
- دوال صغيرة للتواريخ والأرقام.
"""

from datetime import date, datetime


class AppError(Exception):
    """خطأ رسالته جاهزة تتعرض للمستخدم."""
    pass


class SessionExpired(AppError):
    """الجلسة خلصت أو الحساب اتوقف ← البرنامج يرجع لشاشة الدخول."""
    pass


# (المفتاح، الاسم اللى بيظهر) - بنفس ترتيب القايمة الجانبية
PAGES = [
    ("dashboard", "📊 الداش بورد"),
    ("customers", "👔 العملاء والمقاسات"),
    ("orders", "📝 الطلبات"),
    ("cutting", "✂️ القص"),
    ("sewing", "🧵 الخياطة"),
    ("fitting", "🪞 البروفة"),
    ("finishing", "♨️ التشطيب والكى"),
    ("delivery", "📦 التسليم"),
    ("accounts", "✅ تأكيد الحسابات"),
    ("sales", "📜 المبيعات"),
    ("treasury", "💰 الخزينة"),
    ("inventory", "🗃️ المخزن"),
    ("suppliers", "🏗️ الموردين"),
    ("cheques", "💳 الشيكات"),
    ("workers", "👷 العمال والأجور"),
]
PAGE_TITLES = dict(PAGES)

STATUS_LABELS = {
    "awaiting_deposit": "تأكيد العربون", "cutting": "قص", "sewing": "خياطة", "fitting": "بروفة",
    "finishing": "تشطيب", "ready": "جاهز للتسليم", "awaiting_accounts": "تأكيد الحسابات", "completed": "اتسلّم",
}
OPEN_STATUSES = ["awaiting_deposit", "cutting", "sewing", "fitting", "finishing", "ready", "awaiting_accounts"]
CHANNEL_LABELS = {"cash": "نقدى", "bank": "بنك", "wallet": "محافظ إلكترونية", "cheque": "شيكات"}
SUPPLIER_TXN_LABELS = {
    "invoice": "فاتورة", "cash_payment": "دفعة نقدية", "bank_payment": "دفعة بنكية",
    "cheque": "شيك", "return": "مرتجع",
}
STAFF_KINDS = {"worker": "عامل", "sales": "سيلز", "other": "أخرى"}
PAY_TYPES = {"piece": "بالقطعة", "salary": "مرتب", "both": "مرتب + قطعة"}
STAFF_TXN_LABELS = {"advance": "سلفة", "payment": "صرف أجر", "bonus": "مكافأة", "deduction": "خصم"}
STAGE_LABELS = {"cutting": "القص", "sewing": "الخياطة", "finishing": "التشطيب"}
FABRIC_SOURCES = {"factory": "من المصنع", "customer": "قماش العميل"}
DEPT_ROLES = {"": "—", "sales": "تحصيل الطلبات والبيع", "payroll": "الأجور والسلف", "purchases": "دفعات الموردين"}


class Me:
    """المستخدم الحالى. is_admin بيشوف ويعمل كل حاجة. لو الترخيص للعرض بس، محدش بيعدّل."""

    def __init__(self, payload: dict):
        payload = payload or {}
        u = payload.get("user") or {}
        self._user = u
        self._company = payload.get("company") or {}
        self._license = payload.get("license") or {}
        self.server_version = payload.get("server_version")
        self._pages = set(u.get("pages") or [])
        self._edit = set(u.get("edit_pages") or [])
        self._delete = set(u.get("delete_pages") or [])

    def get_user_id(self):
        return self._user.get("id")

    def get_username(self):
        return self._user.get("username", "")

    def get_full_name(self):
        return self._user.get("full_name") or self.get_username()

    def get_role_title(self):
        return self._user.get("role_title") or ""

    def get_company(self) -> dict:
        return self._company

    def license(self) -> dict:
        return self._license

    def read_only(self) -> bool:
        return not self._license.get("writable")

    def is_admin(self) -> bool:
        return bool(self._user.get("is_admin"))

    def can_view(self, page) -> bool:
        return self.is_admin() or page in self._pages or page in self._edit

    def can_edit(self, page) -> bool:
        return not self.read_only() and (self.is_admin() or page in self._edit)

    def can_delete(self, page) -> bool:
        return not self.read_only() and (self.is_admin() or page in self._delete)


# ======================= تواريخ وأرقام =======================

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def parse_user_date(text):
    """التاريخ اللى المستخدم بيكتبه (25/12/2026) ← date. فاضى ← None. غلط ← AppError."""
    text = str(text or "").strip().translate(_ARABIC_DIGITS)
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise AppError(f"التاريخ «{text}» مش مفهوم (اكتبه كده: 25/12/2026)")


def iso_date(text):
    """تاريخ المستخدم ← '2026-12-25' (للسيرفر) أو None."""
    d = parse_user_date(text)
    return d.isoformat() if d else None


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


def parse_int(text, label="العدد", minimum=1):
    value = parse_amount(text, label, allow_zero=minimum <= 0)
    if not float(value).is_integer():
        raise AppError(f"{label} لازم يكون رقم صحيح")
    if value < minimum:
        raise AppError(f"{label} لازم يكون {minimum} أو أكتر")
    return int(value)


def iso_to_display(value) -> str:
    """'2026-10-18' أو '2026-10-18 10:20:00' ← '18/10/2026'."""
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def datetime_display(value) -> str:
    try:
        return datetime.strptime(str(value)[:16], "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_to_display(value)


def month_label(value) -> str:
    """'2026-10' أو '2026-10-01' ← '10/2026'."""
    try:
        d = datetime.strptime(str(value)[:7], "%Y-%m")
        return f"{d.month:02d}/{d.year}"
    except ValueError:
        return str(value)


def recent_months(n=12):
    """[('10/2026', '2026-10'), ...] - الشهر الحالى الأول."""
    today = date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append((f"{m:02d}/{y}", f"{y}-{m:02d}"))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def is_active_row(row) -> bool:
    """فيه جداول (زى الفروع) مالهاش عمود is_active - دى بتتعتبر شغّالة دايمًا."""
    return bool(row["is_active"]) if "is_active" in row else True


def num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def measure_key(grp, name) -> str:
    return f"{grp}|{name}"
