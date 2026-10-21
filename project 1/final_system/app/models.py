"""
models.py
---------
تحديد بنية البيانات، الصفحات، وصلاحيات المستخدمين.
"""
from datetime import date, datetime

class AppError(Exception):
    """خطأ رسالته جاهزة تتعرض للمستخدم."""
    pass

# الصفحات المتاحة في نظام إدارة مصنع البدل
PAGES = [
    ("dashboard", "🏠 الرئيسية"),
    ("manufacturing", "✂️ التصنيع"),
    ("inventory", "📦 المخازن"),
    ("sales", "🧾 المبيعات"),
    ("customers", "👔 العملاء والمقاسات"),
    ("accounting", "💰 الحسابات"),
    ("hr", "👥 الموارد البشرية"),
]
PAGE_TITLES = dict(PAGES)

class Me:
    """المستخدم الحالي وصلاحياته."""
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

    def get_full_name(self): return self._full_name
    def get_role_title(self): return self._role_title
    def has_company(self): return self._has_profile
    def is_active(self): return self._is_active and bool(self._company)
    def is_admin(self): return self._is_admin and self.is_active()
    def get_company(self): return self._company
    def get_company_id(self): return self._company.get("id")

    def can_view(self, page):
        return self.is_admin() or (self.is_active() and (page in self._pages or page in self._edit))

def iso_to_display(value):
    if not value: return ""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(value)
