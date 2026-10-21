"""
service.py — كل عمليات البرنامج (بتشتغل على جهاز السيرفر بس)
------------------------------------------------------------
ده بديل 03_functions.sql فى البرنامج القديم: كل عملية دالة واحدة بتعمل:
  - تتأكد إن المستخدم داخل وعنده صلاحية
  - تتأكد إن الترخيص شغّال (لو انتهى: القراءة بس مسموحة)
  - تنفذ كل الخطوات مع بعض (لو خطوة فشلت، ولا حاجة بتتسجل)
  - كل الطلبات بتتنفذ واحد ورا التانى (قفل)، فلو اتنين داسوا "تأكيد" فى نفس اللحظة،
    التانى بيلاقى الحالة اتغيرت ويترفض (مفيش فلوس بتترحّل مرتين)

البرنامج (الواجهة) بينادى الدوال دى بالاسم من backend.py عن طريق api.py.
أى دالة عليها @rpc تقدر تتنادى من برا، والباقى (اللى بيبدأ بـ _) داخلى.
"""

import base64
import hashlib
import hmac
import inspect
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta

from . import db as dbmod
from . import formulas
from . import licensing

# ========================= ثوابت =========================

# مفاتيح الصفحات (نفسها اللى فى models.py فى الواجهة)
PAGE_KEYS = ["dashboard", "treasury", "customers", "orders", "cutting", "sewing", "fitting", "finishing",
             "delivery", "accounts", "sales", "inventory", "suppliers", "cheques", "workers"]

STATUSES = ["awaiting_deposit", "cutting", "sewing", "fitting", "finishing", "ready", "awaiting_accounts",
            "completed"]
STATUS_LABELS = {"awaiting_deposit": "تأكيد العربون", "cutting": "قص", "sewing": "خياطة", "fitting": "بروفة",
                 "finishing": "تشطيب", "ready": "جاهز للتسليم", "awaiting_accounts": "تأكيد الحسابات",
                 "completed": "اتسلّم"}
# الصفحة المسئولة عن الطلب وهو فى كل مرحلة (للصلاحيات)
STAGE_PAGE = {"awaiting_deposit": "accounts", "cutting": "cutting", "sewing": "sewing", "fitting": "fitting",
              "finishing": "finishing", "ready": "delivery", "awaiting_accounts": "accounts",
              "completed": "sales"}
ORDER_PAGES = ("orders", "customers", "cutting", "sewing", "fitting", "finishing", "delivery", "accounts", "sales",
               "dashboard")

CHANNELS = ("cash", "bank", "wallet", "cheque")
SUPPLIER_TXN_TYPES = ("invoice", "cash_payment", "bank_payment", "cheque", "return")
STAFF_TXN_TYPES = ("advance", "payment", "bonus", "deduction")

MAX_FILE_MB = 15
MAX_LOGO_MB = 2
SESSION_HOURS = 18
LICENSE_CACHE_SECONDS = 60
AUTO_BACKUPS_KEPT = 30


class AppError(Exception):
    """خطأ رسالته عربى وجاهزة تتعرض للمستخدم."""
    code = "error"


class SessionError(AppError):
    code = "session"


def rpc(access="user", write=False, licensed=None):
    """access: public (من غير دخول) / user / admin.
       write: العملية بتكتب (بتتنفذ كلها مع بعض أو مفيش حاجة).
       licensed: محتاجة ترخيص شغّال؟ (افتراضيًا = write)."""
    def deco(func):
        func._rpc = (access, write, write if licensed is None else licensed)
        return func
    return deco


# ========================= أدوات صغيرة =========================

def _hash_password(password, salt=None, rounds=150_000):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds).hex()
    return f"pbkdf2${rounds}${salt}${digest}"


def _check_password(password, stored) -> bool:
    try:
        _algo, rounds, salt, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(test, digest)
    except (ValueError, AttributeError):
        return False


def _t(value):
    """نص متنضف، أو None لو فاضى."""
    text = str(value).strip() if value is not None else ""
    return text or None


def _need(value, message):
    text = _t(value)
    if not text:
        raise AppError(message)
    return text


def _amount(value, label="المبلغ", allow_zero=False):
    try:
        f = round(float(value), 2)
    except (TypeError, ValueError):
        raise AppError(f"{label} لازم يكون رقم")
    if f < 0 or (f == 0 and not allow_zero):
        raise AppError(f"{label} لازم يكون أكبر من صفر")
    return f


def _date(value, label="التاريخ"):
    text = _t(value)
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise AppError(f"{label} غير صحيح")


def _month(value=None):
    text = _t(value)
    if not text:
        return date.today().strftime("%Y-%m")
    try:
        return datetime.strptime(text[:7], "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise AppError("الشهر غير صحيح")


def _today():
    return date.today().isoformat()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _jload(text, default):
    try:
        value = json.loads(text) if text else default
        return value if isinstance(value, type(default)) else default
    except (TypeError, ValueError):
        return default


def _decode_b64(data, max_mb, label):
    try:
        raw = base64.b64decode(data or "", validate=True)
    except (ValueError, TypeError):
        raise AppError(f"{label} غير صالح")
    if not raw:
        raise AppError(f"{label} فاضى")
    if len(raw) > max_mb * 1024 * 1024:
        raise AppError(f"{label} أكبر من {max_mb} ميجا")
    return raw


# ========================= الخدمة =========================

class Service:
    def __init__(self, data_dir, app_version="0"):
        self.data_dir = data_dir
        self.backups_dir = os.path.join(data_dir, "backups")
        os.makedirs(self.backups_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "tailor.db")
        self.app_version = app_version
        self.port = None
        self.lock = threading.RLock()
        self.conn = self._open()
        self.sessions = {}            # token ← (user_id, انتهاء الجلسة)
        self._failed_logins = {}      # username ← (عدد المحاولات، آخر محاولة)
        self._license_cache = None
        self.user = None
        self.methods = {}
        for name in dir(self):
            func = getattr(self, name)
            if callable(func) and hasattr(func, "_rpc") and not name.startswith("_"):
                self.methods[name] = func

    def close(self):
        with self.lock:
            self.conn.close()

    def _open(self):
        conn = dbmod.connect(self.db_path)
        dbmod.init_schema(conn)
        # شركة موجودة من إصدار قبل المعادلات ← تاخد المعادلات الافتراضية مرة واحدة
        if conn.execute("select 1 from company where id = 1").fetchone() and \
                not conn.execute("select 1 from meta where key = 'bom_seeded'").fetchone():
            self._seed_bom(conn)
        return conn

    @staticmethod
    def _seed_bom(conn):
        """الخامات الأساسية + تركيبة كل نوع شغل (المدير يعدّلها من الإعدادات)."""
        materials = {}
        for name, category, unit in dbmod.DEFAULT_MATERIALS:
            row = conn.execute("select id from materials where name = ?", (name,)).fetchone()
            materials[name] = row[0] if row else conn.execute(
                "insert into materials (name, category, unit) values (?, ?, ?)", (name, category, unit)).lastrowid
        for type_name, lines in dbmod.DEFAULT_BOM.items():
            row = conn.execute("select id from garment_types where name = ?", (type_name,)).fetchone()
            if not row or conn.execute("select 1 from bom_lines where garment_type_id = ?", (row[0],)).fetchone():
                continue
            for i, (material, formula, fallback) in enumerate(lines, 1):
                conn.execute("insert into bom_lines (garment_type_id, material_id, is_fabric, formula, fallback_qty, "
                             "sort) values (?, ?, ?, ?, ?, ?)",
                             (row[0], materials.get(material), 1 if material is None else 0, formula, fallback, i))
        conn.execute("update style_options set choices = replace(choices, 'دبل (صفين)', 'دبل (صفين) = +0.3') "
                     "where choices like '%دبل (صفين)%' and choices not like '%دبل (صفين) =%'")
        conn.execute("insert or replace into meta (key, value) values ('bom_seeded', '1')")

    # ---------------------------------------------------------------
    #                     تنفيذ طلب جاى من برا
    # ---------------------------------------------------------------

    def call(self, method, params=None, token=None):
        params = params or {}
        with self.lock:
            func = self.methods.get(method)
            if func is None:
                raise AppError(f"العملية «{method}» مش موجودة — يمكن البرنامج على الجهاز ده إصداره أقدم من السيرفر")
            access, write, licensed = func._rpc
            self._check_params(func, params)
            self.user = None
            if access != "public":
                self.user = self._session_user(token)
                if access == "admin" and not self.user["is_admin"]:
                    raise AppError("المدير بس يقدر يعمل كده")
            if licensed:
                lic = self.license()
                if not lic["writable"]:
                    raise AppError(lic["message"] or "البرنامج للعرض بس")
            if not write:
                return func(**params)
            self.conn.execute("begin immediate")
            try:
                result = func(**params)
                self.conn.execute("commit")
                return result
            except BaseException:
                self.conn.execute("rollback")
                raise

    @staticmethod
    def _check_params(func, params):
        try:
            inspect.signature(func).bind(**params)
        except TypeError:
            raise AppError("الطلب ناقص أو فيه بيانات غلط — يمكن البرنامج محتاج تحديث")

    def _session_user(self, token):
        entry = self.sessions.get(token or "")
        if not entry or entry[1] < time.time():
            self.sessions.pop(token or "", None)
            raise SessionError("الجلسة خلصت — ادخل تانى")
        row = self.q1("select * from users where id = ?", (entry[0],))
        if not row or not row["is_active"]:
            self.sessions.pop(token, None)
            raise SessionError("حسابك اتوقف أو اتشال — كلّم المدير")
        self.sessions[token] = (entry[0], time.time() + SESSION_HOURS * 3600)
        return self._user_dict(row)

    @staticmethod
    def _user_dict(row):
        return {"id": row["id"], "username": row["username"], "full_name": row["full_name"],
                "role_title": row["role_title"] or "", "is_active": bool(row["is_active"]),
                "is_admin": bool(row["is_admin"]), "pages": _jload(row["pages"], []),
                "edit_pages": _jload(row["edit_pages"], []), "delete_pages": _jload(row["delete_pages"], []),
                "last_login": row["last_login"], "created_at": row["created_at"]}

    # ---------------------------------------------------------------
    #                     أدوات قاعدة البيانات
    # ---------------------------------------------------------------

    def q(self, sql, args=()):
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def q1(self, sql, args=()):
        row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def val(self, sql, args=(), default=None):
        row = self.conn.execute(sql, args).fetchone()
        return row[0] if row and row[0] is not None else default

    def x(self, sql, args=()):
        return self.conn.execute(sql, args).lastrowid

    def _meta(self, key, default=None):
        return self.val("select value from meta where key = ?", (key,), default)

    def _set_meta(self, key, value):
        self.conn.execute("insert or replace into meta (key, value) values (?, ?)", (key, value))

    def _log(self, action, details=None, amount=None):
        u = self.user or {}
        self.x("insert into activity_log (user_id, user_name, action, details, amount) values (?, ?, ?, ?, ?)",
               (u.get("id"), u.get("full_name"), action, details, amount or None))

    # ---------------------------------------------------------------
    #                          الصلاحيات
    # ---------------------------------------------------------------

    def _can(self, page, action="view"):
        u = self.user
        if not u:
            return False
        if u["is_admin"]:
            return True
        if action == "view":
            return page in u["pages"] or page in u["edit_pages"]
        if action == "edit":
            return page in u["edit_pages"]
        return page in u["delete_pages"]

    def _require(self, pages, action="edit"):
        pages = (pages,) if isinstance(pages, str) else pages
        if not any(self._can(p, action) for p in pages):
            raise AppError("مفيش صلاحية لك تعمل العملية دى")

    # ---------------------------------------------------------------
    #                          الترخيص
    # ---------------------------------------------------------------

    def license(self, force=False):
        cache = self._license_cache
        if not force and cache and time.time() - cache[0] < LICENSE_CACHE_SECONDS:
            return cache[1]
        last_seen = self._meta("last_seen")
        last_seen = datetime.strptime(last_seen, "%Y-%m-%d").date() if last_seen else None
        lic = licensing.evaluate(self._meta("license"), last_seen)
        if lic.get("last_seen") and lic["last_seen"] != self._meta("last_seen"):
            self._set_meta("last_seen", lic["last_seen"])
        lic.pop("last_seen", None)
        lic["active_users"] = self.val("select count(*) from users where is_active = 1", default=0)
        self._license_cache = (time.time(), lic)
        return lic

    def _apply_license(self, code):
        lic = licensing.verify(code)          # LicenseError لو الكود غلط
        self._set_meta("license", code.strip())
        self._license_cache = None
        state = self.license(force=True)
        if state["state"] == "expired":
            raise AppError("كود التفعيل ده صحيح بس مدته خلصت بالفعل — اطلب كود جديد")
        return lic

    def _check_user_limit(self):
        lic = self.license(force=True)
        limit = lic.get("users") or 0
        active = self.val("select count(*) from users where is_active = 1", default=0)
        if limit and active > limit:
            raise AppError(f"الترخيص بتاعك لـ {limit} مستخدم شغّال بس (المدير محسوب منهم). "
                           "وقّف مستخدم تانى الأول، أو اطلب ترخيص بعدد أكبر")

    # ===============================================================
    #                    من غير دخول (public)
    # ===============================================================

    @rpc("public")
    def status(self):
        company = self.q1("select name from company where id = 1")
        return {"app": "TailorMaster", "version": self.app_version, "has_company": company is not None,
                "company": company["name"] if company else None, "license": self.license(),
                "server_date": _today()}

    @rpc("public")
    def public_logo(self):
        """لوجو الشركة لشاشة الدخول."""
        row = self.q1("select logo from company where id = 1")
        return base64.b64encode(row["logo"]).decode() if row and row["logo"] else None

    @rpc("public", write=True, licensed=False)
    def activate(self, code):
        current = self.license(force=True)
        if current["state"] not in ("none", "invalid"):
            raise AppError("البرنامج متفعّل بالفعل — التجديد بيتعمل من الإعدادات بحساب المدير")
        try:
            self._apply_license(code)
        except licensing.LicenseError as e:
            raise AppError(str(e))
        self._log("تفعيل البرنامج", self.license()["plan_label"])
        return self.license()

    @rpc("public", write=True)
    def create_company(self, company_name, full_name, username, password, phone=None, logo_b64=None,
                       logo_type=None):
        if self.q1("select id from company where id = 1"):
            raise AppError("الشركة اتعملت قبل كده — ادخل بحساب المدير")
        name = _need(company_name, "اسم الشركة مطلوب")
        logo = _decode_b64(logo_b64, MAX_LOGO_MB, "اللوجو") if logo_b64 else None
        self.x("insert into company (id, name, phone, logo, logo_type) values (1, ?, ?, ?, ?)",
               (name, _t(phone), logo, logo_type if logo else None))
        self.x("insert into branches (name, is_main) values ('الفرع الرئيسى', 1)")
        for i, (pm, channel) in enumerate(dbmod.DEFAULT_PAYMENT_METHODS, 1):
            self.x("insert into payment_methods (name, channel, sort) values (?, ?, ?)", (pm, channel, i))
        for i, g in enumerate(dbmod.DEFAULT_GARMENT_TYPES, 1):
            self.x("insert into garment_types (name, sort) values (?, ?)", (g, i))
        for i, (d, is_sales, in_profit, role) in enumerate(dbmod.DEFAULT_DEPARTMENTS, 1):
            self.x("insert into departments (name, is_sales, in_profit, role, sort) values (?, ?, ?, ?, ?)",
                   (d, is_sales, in_profit, role, i))
        sort = 0
        for grp, fields in dbmod.DEFAULT_MEASURE_FIELDS.items():
            for f in fields:
                sort += 1
                self.x("insert into measure_fields (grp, name, sort) values (?, ?, ?)", (grp, f, sort))
        for i, (opt, choices) in enumerate(dbmod.DEFAULT_STYLE_OPTIONS, 1):
            self.x("insert into style_options (name, choices, sort) values (?, ?, ?)", (opt, choices, i))
        user_id = self._insert_user(full_name or "المدير", username, password, "مدير", True, True, [], [], [])
        self.user = self._user_dict(self.q1("select * from users where id = ?", (user_id,)))
        self._seed_bom(self.conn)
        self._log("إنشاء الشركة", name)
        return self._start_session(user_id)

    @rpc("public", write=True, licensed=False)
    def login(self, username, password):
        username = _need(username, "اكتب اسم المستخدم")
        if not password:
            raise AppError("اكتب الباسورد")
        key = username.lower()
        fails, last = self._failed_logins.get(key, (0, 0))
        if fails >= 6 and time.time() - last < 60:
            raise AppError("محاولات غلط كتير — استنى دقيقة وجرّب تانى")
        row = self.q1("select * from users where username = ?", (username,))
        if not row or not _check_password(password, row["password_hash"]):
            self._failed_logins[key] = (fails + 1, time.time())
            raise AppError("اسم المستخدم أو الباسورد غلط")
        self._failed_logins.pop(key, None)
        if not row["is_active"]:
            raise AppError("حسابك موقوف — كلّم مدير الشركة")
        self.conn.execute("update users set last_login = ? where id = ?", (_now(), row["id"]))
        self.user = self._user_dict(row)
        return self._start_session(row["id"])

    def _start_session(self, user_id):
        token = secrets.token_urlsafe(32)
        self.sessions[token] = (user_id, time.time() + SESSION_HOURS * 3600)
        self.user = self._user_dict(self.q1("select * from users where id = ?", (user_id,)))
        return {"token": token, "me": self._me_payload()}

    # ===============================================================
    #                    المستخدم الحالى
    # ===============================================================

    def _company(self):
        c = self.q1("select id, name, phone, address, receipt_note, logo_type, profit_start_date, "
                    "require_attachment, created_at, logo is not null as has_logo from company where id = 1")
        if c:
            c["has_logo"] = bool(c["has_logo"])
            c["require_attachment"] = bool(c["require_attachment"])
        return c or {}

    def _me_payload(self):
        return {"user": self.user, "company": self._company(), "license": self.license(),
                "server_version": self.app_version}

    @rpc()
    def me(self):
        return self._me_payload()

    @rpc()
    def logout(self):
        for token, (uid, _exp) in list(self.sessions.items()):
            if uid == self.user["id"]:
                self.sessions.pop(token, None)
        return True

    @rpc(write=True, licensed=False)
    def change_my_password(self, old_password, new_password):
        row = self.q1("select password_hash from users where id = ?", (self.user["id"],))
        if not _check_password(old_password or "", row["password_hash"]):
            raise AppError("الباسورد القديم غلط")
        self._validate_password(new_password)
        self.conn.execute("update users set password_hash = ? where id = ?",
                          (_hash_password(new_password), self.user["id"]))
        self._log("تغيير الباسورد")
        return True

    @staticmethod
    def _validate_password(password):
        if len(password or "") < 4:
            raise AppError("الباسورد لازم يكون 4 حروف أو أرقام على الأقل")

    @rpc()
    def lookups(self):
        order = "order by sort, name"
        return {
            "branches": self.q("select * from branches order by is_main desc, name"),
            "payment_methods": self.q(f"select * from payment_methods {order}"),
            "garment_types": self.q(f"select * from garment_types {order}"),
            "departments": self.q(f"select * from departments {order}"),
            "measure_fields": self.q("select * from measure_fields order by sort, id"),
            "style_options": self.q(f"select * from style_options {order}"),
            "piece_rates": self.q("select * from piece_rates"),
            "staff": self.q("select id, name, mobile, kind, craft, pay_type, hired_on, is_active from staff "
                            "order by name"),
            "materials": self._materials_with_reserved("select id, name, category, unit, qty, is_active "
                                                       "from materials order by name"),
            "bom_lines": self.q("select b.*, m.name as material_name, m.unit from bom_lines b "
                                "left join materials m on m.id = b.material_id order by b.garment_type_id, b.sort, b.id"),
            "products": self.q("select p.id, p.name, p.size, p.color, p.qty, p.price, p.is_active, "
                               "g.name as garment_type from products p "
                               "left join garment_types g on g.id = p.garment_type_id order by p.name"),
            "suppliers": self.q("select id, name from suppliers order by name"),
        }

    # ===============================================================
    #                 الإعدادات والمستخدمين (المدير)
    # ===============================================================

    @rpc("admin", write=True)
    def update_company(self, name, profit_start_date=None, phone=None, address=None, receipt_note=None,
                       require_attachment=False):
        self.conn.execute("update company set name = ?, profit_start_date = ?, phone = ?, address = ?, "
                          "receipt_note = ?, require_attachment = ? where id = 1",
                          (_need(name, "اسم الشركة مطلوب"), _date(profit_start_date), _t(phone), _t(address),
                           _t(receipt_note), 1 if require_attachment else 0))
        self._log("تعديل بيانات الشركة", name)
        return self._company()

    @rpc("admin", write=True)
    def set_logo(self, data_b64, mime="image/png"):
        if mime not in ("image/png", "image/jpeg"):
            raise AppError("اللوجو لازم يكون صورة PNG أو JPG")
        raw = _decode_b64(data_b64, MAX_LOGO_MB, "اللوجو")
        self.conn.execute("update company set logo = ?, logo_type = ? where id = 1", (raw, mime))
        self._log("تغيير اللوجو")
        return True

    @rpc("admin", write=True)
    def remove_logo(self):
        self.conn.execute("update company set logo = null, logo_type = null where id = 1")
        self._log("إزالة اللوجو")
        return True

    @rpc()
    def company_logo(self):
        row = self.q1("select logo from company where id = 1")
        return base64.b64encode(row["logo"]).decode() if row and row["logo"] else None

    @rpc("admin")
    def users(self):
        return [self._user_dict(r) for r in self.q("select * from users order by is_active desc, full_name")]

    def _clean_pages(self, pages):
        return json.dumps([p for p in (pages or []) if p in PAGE_KEYS])

    def _insert_user(self, full_name, username, password, role_title, is_active, is_admin, pages, edit_pages,
                     delete_pages):
        full_name = _need(full_name, "اسم الموظف مطلوب")
        username = _need(username, "اسم المستخدم (اللى بيدخل بيه) مطلوب")
        if " " in username:
            raise AppError("اسم المستخدم من غير مسافات (مثال: ahmed أو ahmed1)")
        if self.q1("select id from users where username = ?", (username,)):
            raise AppError(f"اسم المستخدم «{username}» موجود قبل كده — اختار اسم تانى")
        self._validate_password(password)
        return self.x("insert into users (username, full_name, password_hash, role_title, is_active, is_admin, "
                      "pages, edit_pages, delete_pages) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (username, full_name, _hash_password(password), _t(role_title), 1 if is_active else 0,
                       1 if is_admin else 0, self._clean_pages(pages), self._clean_pages(edit_pages),
                       self._clean_pages(delete_pages)))

    @rpc("admin", write=True)
    def create_user(self, full_name, username, password, role_title=None, is_admin=False, pages=(),
                    edit_pages=(), delete_pages=()):
        uid = self._insert_user(full_name, username, password, role_title, True, is_admin, pages, edit_pages,
                                delete_pages)
        self._check_user_limit()
        self._log("إضافة مستخدم", f"{full_name} ({username})")
        return uid

    @rpc("admin", write=True)
    def set_member(self, user_id, is_active, is_admin, pages, edit_pages, delete_pages, role_title=None,
                   full_name=None):
        row = self.q1("select * from users where id = ?", (user_id,))
        if not row:
            raise AppError("المستخدم ده مش موجود")
        if user_id == self.user["id"] and (not is_admin or not is_active):
            raise AppError("مينفعش تشيل صلاحية المدير من نفسك أو توقف نفسك")
        self.conn.execute("update users set is_active = ?, is_admin = ?, pages = ?, edit_pages = ?, "
                          "delete_pages = ?, role_title = ?, full_name = ? where id = ?",
                          (1 if is_active else 0, 1 if is_admin else 0, self._clean_pages(pages),
                           self._clean_pages(edit_pages), self._clean_pages(delete_pages),
                           _t(role_title), _t(full_name) or row["full_name"], user_id))
        if is_active and not row["is_active"]:
            self._check_user_limit()
        if not is_active:
            self._drop_sessions(user_id)
        self._license_cache = None
        self._log("تعديل صلاحيات مستخدم", row["full_name"])
        return True

    @rpc("admin", write=True, licensed=False)
    def reset_password(self, user_id, new_password):
        row = self.q1("select full_name from users where id = ?", (user_id,))
        if not row:
            raise AppError("المستخدم ده مش موجود")
        self._validate_password(new_password)
        self.conn.execute("update users set password_hash = ? where id = ?", (_hash_password(new_password), user_id))
        self._drop_sessions(user_id)
        self._log("تغيير باسورد مستخدم", row["full_name"])
        return True

    @rpc("admin", write=True)
    def remove_member(self, user_id):
        if user_id == self.user["id"]:
            raise AppError("مينفعش تمسح حسابك إنت")
        row = self.q1("select full_name from users where id = ?", (user_id,))
        if not row:
            raise AppError("المستخدم ده مش موجود")
        self.conn.execute("delete from users where id = ?", (user_id,))
        self._drop_sessions(user_id)
        self._license_cache = None
        self._log("حذف مستخدم", row["full_name"])
        return True

    def _drop_sessions(self, user_id):
        for token, (uid, _exp) in list(self.sessions.items()):
            if uid == user_id:
                self.sessions.pop(token, None)

    # كل قايمة: الأعمدة المسموح تتعدّل ونوعها
    SETTINGS = {
        "branches": {"name": "text", "is_main": "bool"},
        "payment_methods": {"name": "text", "channel": "channel", "sort": "int", "is_active": "bool"},
        "garment_types": {"name": "text", "default_price": "money", "sort": "int", "is_active": "bool"},
        "departments": {"name": "text", "is_sales": "bool", "in_profit": "bool", "role": "role", "sort": "int",
                        "is_active": "bool"},
        "measure_fields": {"grp": "text", "name": "text", "sort": "int", "is_active": "bool"},
        "style_options": {"name": "text", "choices": "lines", "sort": "int", "is_active": "bool"},
    }

    @rpc("admin", write=True)
    def save_setting(self, table, values, row_id=None):
        spec = self.SETTINGS.get(table)
        if not spec:
            raise AppError("جدول غير معروف")
        data = {}
        for col, kind in spec.items():
            if col not in values:
                continue
            v = values[col]
            if kind == "text":
                v = _need(v, "الاسم مطلوب" if col == "name" else "المجموعة مطلوبة")
            elif kind == "bool":
                v = 1 if v else 0
            elif kind == "int":
                try:
                    v = int(v or 0)
                except (TypeError, ValueError):
                    raise AppError("الترتيب لازم يكون رقم")
            elif kind == "money":
                v = _amount(v or 0, "السعر", allow_zero=True)
            elif kind == "channel":
                if v not in CHANNELS:
                    raise AppError("اختار القناة")
            elif kind == "role":
                v = v if v in ("sales", "payroll", "purchases") else ""
            elif kind == "lines":
                v = "\n".join(line.strip() for line in str(v or "").replace("،", "\n").replace(",", "\n")
                              .splitlines() if line.strip())
            data[col] = v
        if not row_id and "name" in spec and "name" not in data:
            raise AppError("الاسم مطلوب")
        if data.get("role"):                         # كل استخدام أوتوماتيك لإدارة واحدة بس
            self.conn.execute("update departments set role = '' where role = ? and id <> ?",
                              (data["role"], row_id or 0))
        if table == "branches" and data.get("is_main"):
            self.conn.execute("update branches set is_main = 0 where id <> ?", (row_id or 0,))
        try:
            if row_id:
                if not data:
                    return row_id
                sets = ", ".join(f"{c} = ?" for c in data)
                cur = self.conn.execute(f"update {table} set {sets} where id = ?", (*data.values(), row_id))
                if cur.rowcount == 0:
                    raise AppError("الصف ده مش موجود")
                result = row_id
            else:
                cols = ", ".join(data)
                marks = ", ".join("?" for _ in data)
                result = self.x(f"insert into {table} ({cols}) values ({marks})", tuple(data.values()))
        except sqlite3.IntegrityError:
            raise AppError("الاسم ده موجود قبل كده")
        if table == "branches" and not self.val("select count(*) from branches where is_main = 1"):
            self.conn.execute("update branches set is_main = 1 where id = (select min(id) from branches)")
        self._log("تعديل الإعدادات", f"{table}: {data.get('name', row_id)}")
        return result

    @rpc("admin", write=True)
    def save_piece_rate(self, garment_type_id, stage, rate):
        if stage not in ("cutting", "sewing", "finishing"):
            raise AppError("المرحلة غير صحيحة")
        if not self.q1("select id from garment_types where id = ?", (garment_type_id,)):
            raise AppError("اختار النوع")
        rate = _amount(rate or 0, "الأجر", allow_zero=True)
        self.conn.execute("insert into piece_rates (garment_type_id, stage, rate) values (?, ?, ?) "
                          "on conflict (garment_type_id, stage) do update set rate = excluded.rate",
                          (garment_type_id, stage, rate))
        return True

    @rpc("admin")
    def activity(self, limit=500):
        return self.q("select * from activity_log order by id desc limit ?", (min(int(limit), 5000),))

    @rpc("admin", write=True, licensed=False)
    def renew_license(self, code):
        old = self.license(force=True)
        try:
            lic = self._apply_license(code)
        except licensing.LicenseError as e:
            raise AppError(str(e))
        if old.get("serial") == lic.serial and old["state"] not in ("none", "invalid"):
            raise AppError("الكود ده متفعّل بالفعل")
        self._log("تجديد الترخيص", f"{lic.plan_label} — {lic.users} مستخدم")
        return self.license()

    # ---------- النسخ الاحتياطى ----------

    def _snapshot(self, dest):
        target = sqlite3.connect(dest)
        try:
            self.conn.backup(target)
        finally:
            target.close()

    def auto_backup(self):
        """نسخة يومية أوتوماتيك على جهاز السيرفر (آخر 30 يوم)."""
        with self.lock:
            if not self.q1("select id from company where id = 1"):
                return None
            path = os.path.join(self.backups_dir, f"auto-{_today()}.db")
            if not os.path.exists(path):
                self._snapshot(path)
            autos = sorted(f for f in os.listdir(self.backups_dir) if f.startswith("auto-") and f.endswith(".db"))
            for old in autos[:-AUTO_BACKUPS_KEPT]:
                try:
                    os.remove(os.path.join(self.backups_dir, old))
                except OSError:
                    pass
            return path

    @rpc("admin")
    def backup_data(self):
        """نسخة كاملة من البيانات (بتتحفظ على الجهاز اللى طلبها: فلاشة أو فولدر)."""
        tmp = os.path.join(self.backups_dir, f".download-{secrets.token_hex(4)}.db")
        try:
            self._snapshot(tmp)
            with open(tmp, "rb") as f:
                data = f.read()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        self._log("نسخة احتياطية")
        return base64.b64encode(data).decode()

    @rpc("admin")
    def backups(self):
        out = []
        for name in sorted(os.listdir(self.backups_dir), reverse=True):
            if name.endswith(".db") and not name.startswith("."):
                path = os.path.join(self.backups_dir, name)
                out.append({"name": name, "size": os.path.getsize(path),
                            "modified": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")})
        return out

    @rpc("admin", licensed=False)
    def restore_backup(self, data_b64=None, server_file=None):
        """بيرجّع نسخة قديمة مكان البيانات الحالية. قبلها بيحفظ نسخة من الحالية (للأمان).
           الترخيص الحالى بيفضل زى ما هو (النسخة القديمة مش بترجّع ترخيص قديم)."""
        if server_file:
            src = os.path.join(self.backups_dir, os.path.basename(server_file))
            if not os.path.isfile(src):
                raise AppError("النسخة دى مش موجودة")
            with open(src, "rb") as f:
                raw = f.read()
        else:
            raw = _decode_b64(data_b64, 2048, "ملف النسخة")
        tmp = os.path.join(self.backups_dir, f".restore-{secrets.token_hex(4)}.db")
        with open(tmp, "wb") as f:
            f.write(raw)
        if not dbmod.is_our_database(tmp):
            os.remove(tmp)
            raise AppError("الملف ده مش نسخة احتياطية من البرنامج ده (أو من إصدار أحدث)")
        keep = {k: self._meta(k) for k in ("license", "last_seen")}
        self._snapshot(os.path.join(self.backups_dir, f"before-restore-{datetime.now():%Y-%m-%d_%H%M%S}.db"))
        who = self.user["full_name"]
        self.conn.close()
        for suffix in ("-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass
        os.replace(tmp, self.db_path)
        self.conn = self._open()
        for k, v in keep.items():
            if v is not None:
                self._set_meta(k, v)
        self.sessions.clear()
        self._license_cache = None
        self.user = None
        self._log("استرجاع نسخة احتياطية", who)
        return True

    @rpc("admin")
    def server_info(self):
        size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        return {"data_dir": self.data_dir, "db_size": size, "port": self.port,
                "counts": {t: self.val(f"select count(*) from {t}", default=0)
                           for t in ("customers", "orders", "treasury_entries", "users")}}

    # ===============================================================
    #                         أدوات داخلية
    # ===============================================================

    def _branch(self, branch_id=None):
        if branch_id:
            row = self.q1("select id from branches where id = ?", (branch_id,))
        else:
            row = self.q1("select id from branches where is_main = 1 order by id limit 1") or \
                self.q1("select id from branches order by id limit 1")
        if not row:
            raise AppError("الفرع غير صحيح")
        return row["id"]

    def _check_exists(self, table, row_id, label):
        if row_id in (None, ""):
            return None
        if not self.q1(f"select id from {table} where id = ?", (row_id,)):
            raise AppError(f"{label} غير صحيح")
        return row_id

    def _dept(self, role):
        return self.val("select id from departments where role = ? and is_active = 1 order by sort limit 1", (role,))

    def _method_by_channel(self, channel):
        return self.val("select id from payment_methods where channel = ? and is_active = 1 order by sort, name "
                        "limit 1", (channel,))

    def _treasury(self, amount_in, amount_out, description, method_id=None, department_id=None, entry_date=None,
                  branch_id=None, counterparty=None, supplier_id=None, order_id=None, source="manual"):
        return self.x("insert into treasury_entries (branch_id, entry_date, amount_in, amount_out, description, "
                      "payment_method_id, department_id, counterparty, supplier_id, order_id, source, created_by) "
                      "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (self._branch(branch_id), entry_date or _today(), amount_in or 0, amount_out or 0,
                       description, method_id, department_id, counterparty, supplier_id, order_id, source,
                       self.user["id"]))

    def _customer(self, name=None, mobile=None, customer_id=None, address=None):
        if customer_id:
            if not self.q1("select id from customers where id = ?", (customer_id,)):
                raise AppError("العميل ده مش موجود")
            return customer_id
        name = _need(name, "اسم العميل مطلوب")
        mobile = _t(mobile)
        if mobile:
            row = self.q1("select id from customers where mobile = ? order by id limit 1", (mobile,))
            if row:
                return row["id"]
        return self.x("insert into customers (name, mobile, address) values (?, ?, ?)", (name, mobile, _t(address)))

    def _save_files(self, files):
        ids = []
        for f in files or []:
            name = _need(f.get("name"), "اسم الملف ناقص")
            raw = _decode_b64(f.get("data"), MAX_FILE_MB, f"الملف {name}")
            ids.append(self.x("insert into files (name, mime, data) values (?, ?, ?)", (name, _t(f.get("mime")), raw)))
        return ids

    @staticmethod
    def _clean_measurements(data):
        out = {}
        for k, v in (data or {}).items():
            text = _t(v)
            if text:
                out[str(k)] = text
        return out

    # ===============================================================
    #                           العملاء
    # ===============================================================

    @rpc()
    def customers(self):
        self._require(("customers", "orders", "sales"), "view")
        rows = self.q("""
            select c.id, c.name, c.mobile, c.address, c.notes, c.measured_at, c.created_at,
                   (select count(*) from orders o where o.customer_id = c.id) as orders_count,
                   (select coalesce(sum(o.price), 0) from orders o where o.customer_id = c.id) as orders_value,
                   (select coalesce(sum(o.price - o.deposit - case when o.status = 'completed'
                        then coalesce(o.final_collected, 0) else 0 end), 0)
                    from orders o where o.customer_id = c.id) as remaining,
                   (select max(o.created_at) from orders o where o.customer_id = c.id) as last_order
            from customers c order by c.name""")
        return rows

    @rpc()
    def customer_detail(self, customer_id):
        self._require(("customers", "orders", "sales"), "view")
        c = self.q1("select * from customers where id = ?", (customer_id,))
        if not c:
            raise AppError("العميل ده مش موجود")
        c["measurements"] = _jload(c["measurements"], {})
        history = self.q("select h.id, h.data, h.created_at, u.full_name as created_by_name "
                         "from measurements_history h left join users u on u.id = h.created_by "
                         "where h.customer_id = ? order by h.id desc", (customer_id,))
        for h in history:
            h["data"] = _jload(h["data"], {})
        return {"customer": c, "history": history, "orders": self._orders("o.customer_id = ?", (customer_id,))}

    @rpc(write=True)
    def save_customer(self, name, mobile=None, address=None, notes=None, customer_id=None):
        self._require(("customers", "orders"))
        name = _need(name, "اسم العميل مطلوب")
        mobile = _t(mobile)
        if mobile:
            other = self.q1("select id, name from customers where mobile = ? and id <> ?", (mobile, customer_id or 0))
            if other:
                raise AppError(f"الموبايل ده مسجّل قبل كده باسم «{other['name']}»")
        if customer_id:
            cur = self.conn.execute("update customers set name = ?, mobile = ?, address = ?, notes = ? where id = ?",
                                    (name, mobile, _t(address), _t(notes), customer_id))
            if cur.rowcount == 0:
                raise AppError("العميل ده مش موجود")
            self._log("تعديل عميل", name)
            return customer_id
        cid = self.x("insert into customers (name, mobile, address, notes) values (?, ?, ?, ?)",
                     (name, mobile, _t(address), _t(notes)))
        self._log("إضافة عميل", name)
        return cid

    @rpc(write=True)
    def save_measurements(self, customer_id, data):
        self._require(("customers", "orders"))
        if not self.q1("select id from customers where id = ?", (customer_id,)):
            raise AppError("العميل ده مش موجود")
        clean = self._clean_measurements(data)
        if not clean:
            raise AppError("اكتب مقاس واحد على الأقل")
        self._store_measurements(customer_id, clean)
        return True

    def _store_measurements(self, customer_id, clean):
        text = json.dumps(clean, ensure_ascii=False)
        current = self.val("select measurements from customers where id = ?", (customer_id,), "{}")
        if _jload(current, {}) == clean:
            return
        self.conn.execute("update customers set measurements = ?, measured_at = ? where id = ?",
                          (text, _now(), customer_id))
        self.x("insert into measurements_history (customer_id, data, created_by) values (?, ?, ?)",
               (customer_id, text, self.user["id"]))

    @rpc(write=True)
    def delete_customer(self, customer_id):
        self._require("customers", "delete")
        if self.q1("select id from orders where customer_id = ? limit 1", (customer_id,)) or \
                self.q1("select id from ready_sales where customer_id = ? limit 1", (customer_id,)):
            raise AppError("العميل ده ليه طلبات أو مبيعات ومينفعش يتمسح")
        row = self.q1("select name from customers where id = ?", (customer_id,))
        if not row:
            raise AppError("العميل ده مش موجود")
        self.conn.execute("delete from customers where id = ?", (customer_id,))
        self._log("مسح عميل", row["name"])
        return True

    # ===============================================================
    #                        الطلبات (التفصيل)
    # ===============================================================

    ORDER_SELECT = """
        select o.*, b.name as branch_name, b.is_main as is_main_branch, c.name as customer_name,
               c.mobile as customer_mobile, g.name as garment_type, dm.name as deposit_method,
               fm.name as final_method, s.name as seller_name, u.full_name as created_by_name,
               o.price - o.deposit - case when o.status = 'completed' then coalesce(o.final_collected, 0) else 0 end
                   as remaining
        from orders o
        join branches b on b.id = o.branch_id
        join customers c on c.id = o.customer_id
        left join garment_types g on g.id = o.garment_type_id
        left join payment_methods dm on dm.id = o.deposit_method_id
        left join payment_methods fm on fm.id = o.final_method_id
        left join staff s on s.id = o.seller_id
        left join users u on u.id = o.created_by
    """

    def _orders(self, where="1 = 1", args=()):
        rows = self.q(f"{self.ORDER_SELECT} where {where} order by o.id desc", args)
        info = {m["id"]: m for m in self.q("select id, name, unit from materials")} if rows else {}
        for r in rows:
            r["measurements"] = _jload(r["measurements"], {})
            r["style"] = _jload(r["style"], {})
            r["attachments"] = _jload(r["attachments"], [])
            r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
            r["needs_fitting"] = bool(r["needs_fitting"])
            r["materials_plan"] = self._plan_with_names(_jload(r["materials_plan"], []), info)
        return rows

    def _order(self, order_id):
        rows = self._orders("o.id = ?", (order_id,))
        if not rows:
            raise AppError("الطلب ده مش موجود")
        return rows[0]

    def _event(self, order_id, action, details=None):
        self.x("insert into order_events (order_id, action, details, created_by) values (?, ?, ?, ?)",
               (order_id, action, details, self.user["id"]))

    @rpc()
    def orders(self, statuses=None, customer_id=None, branch_id=None):
        self._require(ORDER_PAGES, "view")
        where, args = ["1 = 1"], []
        if statuses:
            bad = [s for s in statuses if s not in STATUSES]
            if bad:
                raise AppError("حالة غير معروفة")
            where.append(f"o.status in ({', '.join('?' for _ in statuses)})")
            args += list(statuses)
        if customer_id:
            where.append("o.customer_id = ?")
            args.append(customer_id)
        if branch_id:
            where.append("o.branch_id = ?")
            args.append(branch_id)
        return self._orders(" and ".join(where), tuple(args))

    @rpc()
    def order_detail(self, order_id):
        self._require(ORDER_PAGES, "view")
        o = self._order(order_id)
        o["events"] = self.q("select e.*, u.full_name as user_name from order_events e "
                             "left join users u on u.id = e.created_by where e.order_id = ? order by e.id",
                             (order_id,))
        o["materials_used"] = self.q("select m.name, m.unit, -mm.qty as qty, mm.unit_cost, mm.move_date "
                                     "from material_moves mm join materials m on m.id = mm.material_id "
                                     "where mm.order_id = ? order by mm.id", (order_id,))
        o["work"] = self.q("select w.*, s.name as staff_name from work_log w join staff s on s.id = w.staff_id "
                           "where w.order_id = ? order by w.id", (order_id,))
        o["files"] = self.q(f"select id, name, mime from files where id in "
                            f"({', '.join('?' for _ in o['attachments']) or 'null'})", tuple(o["attachments"]))
        return o

    @rpc(write=True)
    def add_order(self, price, garment_type_id=None, quantity=1, customer_id=None, customer_name=None, mobile=None,
                  address=None, deposit=0, deposit_method_id=None, seller_id=None, fabric_source="factory",
                  fabric_desc=None, measurements=None, style=None, notes=None, needs_fitting=True, due_date=None,
                  fitting_date=None, branch_id=None, files=None, save_measurements=True, fabric_material_id=None):
        self._require("orders")
        price = _amount(price, "السعر الإجمالى")
        deposit = _amount(deposit or 0, "العربون", allow_zero=True)
        if deposit > price:
            raise AppError("العربون لازم يكون أقل من أو يساوى السعر الإجمالى")
        if deposit > 0 and not deposit_method_id:
            raise AppError("اختار طريقة دفع العربون")
        try:
            quantity = int(quantity or 1)
        except (TypeError, ValueError):
            raise AppError("العدد لازم يكون رقم")
        if quantity <= 0:
            raise AppError("العدد لازم يكون 1 أو أكتر")
        if fabric_source not in ("factory", "customer"):
            raise AppError("اختار القماش من المصنع ولا من العميل")
        self._check_exists("garment_types", garment_type_id, "النوع")
        self._check_exists("payment_methods", deposit_method_id, "طريقة الدفع")
        self._check_exists("staff", seller_id, "السيلز")
        if not customer_id and not _t(mobile):
            raise AppError("رقم موبايل العميل مطلوب")
        if self.val("select require_attachment from company where id = 1") and not files:
            raise AppError("لازم ترفع ملف واحد على الأقل مع الطلب (الإعدادات بتقول كده)")
        self._check_exists("materials", fabric_material_id, "القماش")
        cid = self._customer(customer_name, mobile, customer_id, address)
        clean = self._clean_measurements(measurements)
        style = {k: v for k, v in (style or {}).items() if _t(v)}
        plan = self._calc_plan(garment_type_id, quantity, clean, style, fabric_source, fabric_material_id)
        if clean and save_measurements:
            self._store_measurements(cid, clean)
        file_ids = self._save_files(files)
        oid = self.x("""insert into orders (branch_id, customer_id, garment_type_id, quantity, price, deposit,
                        deposit_method_id, seller_id, fabric_source, fabric_desc, measurements, style, notes,
                        needs_fitting, due_date, fitting_date, status, attachments, created_by, fabric_material_id,
                        materials_plan)
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'awaiting_deposit', ?, ?, ?, ?)""",
                     (self._branch(branch_id), cid, garment_type_id, quantity, price, deposit,
                      deposit_method_id if deposit else None, seller_id, fabric_source, _t(fabric_desc),
                      json.dumps(clean, ensure_ascii=False),
                      json.dumps(style, ensure_ascii=False),
                      _t(notes), 1 if needs_fitting else 0, _date(due_date, "ميعاد التسليم"),
                      _date(fitting_date, "ميعاد البروفة"), json.dumps(file_ids), self.user["id"],
                      fabric_material_id or None, self._plan_json(plan)))
        self._event(oid, "طلب جديد", f"السعر {price:g} — العربون {deposit:g}")
        self._log("طلب تفصيل جديد", f"#{oid}", price)
        return oid

    def _order_for_update(self, order_id, pages=None, action="edit"):
        o = self.q1("select * from orders where id = ?", (order_id,))
        if not o:
            raise AppError("الطلب ده مش موجود")
        self._require(pages or ("orders", STAGE_PAGE[o["status"]]), action)
        return o

    @rpc(write=True)
    def update_order(self, order_id, price=None, deposit=None, quantity=None, due_date=None, fitting_date=None,
                     notes=None, fabric_desc=None, measurements=None, style=None, needs_fitting=None,
                     garment_type_id=None, seller_id=None, deposit_method_id=None, fabric_source=None,
                     fabric_material_id=None):
        o = self._order_for_update(order_id)
        if o["status"] == "completed":
            raise AppError("الطلب ده اتسلّم واتقفل ومينفعش يتعدّل")
        new_price = _amount(price, "السعر") if price is not None else o["price"]
        new_deposit = _amount(deposit, "العربون", allow_zero=True) if deposit is not None else o["deposit"]
        if new_deposit != o["deposit"] and o["status"] != "awaiting_deposit":
            raise AppError("العربون اتأكد واترحّل للخزينة خلاص، ومينفعش يتعدّل")
        if new_deposit > new_price:
            raise AppError("العربون لازم يكون أقل من أو يساوى السعر")
        sets = {"price": new_price, "deposit": new_deposit}
        if deposit_method_id is not None and o["status"] == "awaiting_deposit":
            sets["deposit_method_id"] = self._check_exists("payment_methods", deposit_method_id, "طريقة الدفع")
        if new_deposit > 0 and not sets.get("deposit_method_id", o["deposit_method_id"]):
            raise AppError("اختار طريقة دفع العربون")
        if quantity is not None:
            try:
                q = int(quantity)
            except (TypeError, ValueError):
                raise AppError("العدد لازم يكون رقم")
            if q <= 0:
                raise AppError("العدد لازم يكون 1 أو أكتر")
            sets["quantity"] = q
        if due_date is not None:
            sets["due_date"] = _date(due_date, "ميعاد التسليم")
        if fitting_date is not None:
            sets["fitting_date"] = _date(fitting_date, "ميعاد البروفة")
        if notes is not None:
            sets["notes"] = _t(notes)
        if fabric_desc is not None:
            sets["fabric_desc"] = _t(fabric_desc)
        if measurements is not None:
            sets["measurements"] = json.dumps(self._clean_measurements(measurements), ensure_ascii=False)
        if style is not None:
            sets["style"] = json.dumps({k: v for k, v in style.items() if _t(v)}, ensure_ascii=False)
        if needs_fitting is not None:
            sets["needs_fitting"] = 1 if needs_fitting else 0
        if garment_type_id is not None:
            sets["garment_type_id"] = self._check_exists("garment_types", garment_type_id, "النوع")
        if seller_id is not None:
            sets["seller_id"] = self._check_exists("staff", seller_id, "السيلز") or None
        if fabric_source is not None:
            if fabric_source not in ("factory", "customer"):
                raise AppError("اختار القماش من المصنع ولا من العميل")
            sets["fabric_source"] = fabric_source
        if fabric_material_id is not None:
            sets["fabric_material_id"] = self._check_exists("materials", fabric_material_id, "القماش") or None
        if not o["cut_at"]:       # لسه متقصش ← الخامات المحجوزة بتتحسب من جديد بالبيانات الجديدة
            new = {**o, **sets}
            sets["materials_plan"] = self._plan_json(self._calc_plan(
                new["garment_type_id"], new["quantity"], _jload(new["measurements"], {}), _jload(new["style"], {}),
                new["fabric_source"], new["fabric_material_id"]))
        self.conn.execute(f"update orders set {', '.join(f'{k} = ?' for k in sets)} where id = ?",
                          (*sets.values(), order_id))
        self._event(order_id, "تعديل الطلب")
        self._log("تعديل طلب", f"#{order_id}")
        return True

    @rpc(write=True)
    def set_order_note(self, order_id, note):
        o = self._order_for_update(order_id, (STAGE_PAGE[self._status(order_id)], "orders"))
        self.conn.execute("update orders set note = ? where id = ?", (_t(note), o["id"]))
        self._event(order_id, "ملاحظة", _t(note))
        return True

    def _status(self, order_id):
        status = self.val("select status from orders where id = ?", (order_id,))
        if not status:
            raise AppError("الطلب ده مش موجود")
        return status

    @rpc(write=True)
    def add_order_files(self, order_id, files):
        o = self._order_for_update(order_id)
        ids = _jload(o["attachments"], []) + self._save_files(files)
        self.conn.execute("update orders set attachments = ? where id = ?", (json.dumps(ids), order_id))
        self._event(order_id, "إضافة ملفات", f"{len(files or [])} ملف")
        return ids

    @rpc()
    def get_file(self, file_id):
        row = self.q1("select name, mime, data from files where id = ?", (file_id,))
        if not row:
            raise AppError("الملف ده مش موجود")
        return {"name": row["name"], "mime": row["mime"], "data": base64.b64encode(row["data"]).decode()}

    @rpc(write=True)
    def delete_order(self, order_id):
        o = self._order_for_update(order_id, ("orders", STAGE_PAGE[self._status(order_id)]), "delete")
        if self.q1("select id from treasury_entries where order_id = ? limit 1", (order_id,)):
            raise AppError("الطلب ده ليه فلوس مترحّلة للخزينة ومينفعش يتمسح")
        if self.q1("select id from work_log where order_id = ? limit 1", (order_id,)) or \
                self.q1("select id from material_moves where order_id = ? limit 1", (order_id,)):
            raise AppError("الطلب ده اتصرف عليه خامات أو اتسجّل عليه أجور عمال ومينفعش يتمسح")
        files = _jload(o["attachments"], [])
        self.conn.execute("delete from orders where id = ?", (order_id,))
        if files:
            self.conn.execute(f"delete from files where id in ({', '.join('?' for _ in files)})", tuple(files))
        self._log("مسح طلب", f"#{order_id}", o["price"])
        return True

    # ---------- مراحل الطلب ----------

    def _move(self, order_id, page, expected, new_status, stamp, action, details=None):
        o = self.q1("select * from orders where id = ?", (order_id,))
        if not o:
            raise AppError("الطلب ده مش موجود")
        self._require(page)
        if o["status"] != expected:
            raise AppError(f"الطلب ده مش فى مرحلة «{STATUS_LABELS[expected]}» "
                           f"(مرحلته دلوقتى: {STATUS_LABELS.get(o['status'])}) — دوس تحديث")
        self.conn.execute(f"update orders set status = ?{', ' + stamp + ' = ?' if stamp else ''} where id = ?",
                          (new_status, _now(), order_id) if stamp else (new_status, order_id))
        self._event(order_id, action, details)
        return o

    def _customer_name(self, customer_id):
        return self.val("select name from customers where id = ?", (customer_id,), "")

    def _record_work(self, o, stage, worker_id):
        """العامل اللى خلّص المرحلة: لو بيتحاسب بالقطعة، أجره بيتسجل أوتوماتيك."""
        if not worker_id:
            return None
        w = self.q1("select * from staff where id = ?", (worker_id,))
        if not w:
            raise AppError("اختار العامل")
        rate = self.val("select rate from piece_rates where garment_type_id = ? and stage = ?",
                        (o["garment_type_id"], stage), 0) if o["garment_type_id"] else 0
        if w["pay_type"] in ("piece", "both") and rate > 0:
            amount = round(rate * o["quantity"], 2)
            self.x("insert into work_log (staff_id, order_id, stage, description, qty, rate, amount, work_month, "
                   "created_by) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (w["id"], o["id"], stage, f"{STATUS_LABELS[stage]} طلب #{o['id']}", o["quantity"], rate, amount,
                    _month(), self.user["id"]))
            self.conn.execute("update orders set labor_cost = labor_cost + ? where id = ?", (amount, o["id"]))
        return w["name"]

    @rpc(write=True)
    def confirm_deposit(self, order_id):
        o = self._move(order_id, "accounts", "awaiting_deposit", "cutting", "deposit_confirmed_at",
                       "تأكيد العربون ودخول القص")
        name = self._customer_name(o["customer_id"])
        entry = None
        if o["deposit"] > 0:
            entry = self._treasury(o["deposit"], 0, f"عربون طلب #{order_id} من العميل {name}",
                                   o["deposit_method_id"], self._dept("sales"), branch_id=o["branch_id"],
                                   counterparty=name, order_id=order_id, source="order_deposit")
        self._log("تأكيد عربون", f"#{order_id} {name}", o["deposit"])
        return entry

    @rpc(write=True)
    def finish_cutting(self, order_id, worker_id=None, materials=None, allow_short=False):
        """allow_short: المستخدم وافق يكمل حتى لو المخزن مش مكفّى (الرصيد بيبقى بالسالب لحد ما يستلم)."""
        o = self._move(order_id, "cutting", "cutting", "sewing", "cut_at", "تم القص")
        cost = 0.0
        used = []
        for item in materials or []:
            mid = item.get("material_id")
            qty = _amount(item.get("qty"), "الكمية")
            m = self.q1("select * from materials where id = ?", (mid,))
            if not m:
                raise AppError("اختار الخامة")
            if m["qty"] + 1e-9 < qty and not allow_short:
                raise AppError(f"الكمية الموجودة من «{m['name']}» {m['qty']:g} {m['unit']} بس")
            self.conn.execute("update materials set qty = qty - ? where id = ?", (qty, mid))
            self.x("insert into material_moves (material_id, move_type, qty, unit_cost, order_id, note, created_by) "
                   "values (?, 'out', ?, ?, ?, ?, ?)",
                   (mid, -qty, m["avg_cost"], order_id, f"قص طلب #{order_id}", self.user["id"]))
            cost += qty * m["avg_cost"]
            used.append(f"{m['name']} {qty:g} {m['unit']}")
        if cost:
            self.conn.execute("update orders set material_cost = material_cost + ? where id = ?",
                              (round(cost, 2), order_id))
        worker = self._record_work(o, "cutting", worker_id)
        details = " — ".join(x for x in (f"القصاص: {worker}" if worker else None, "، ".join(used) or None) if x)
        if details:
            self.conn.execute("update order_events set details = ? where id = (select max(id) from order_events "
                              "where order_id = ?)", (details, order_id))
        self._log("تم القص", f"#{order_id}")
        return True

    @rpc(write=True)
    def finish_sewing(self, order_id, worker_id=None):
        o = self.q1("select needs_fitting from orders where id = ?", (order_id,))
        if not o:
            raise AppError("الطلب ده مش موجود")
        nxt = "fitting" if o["needs_fitting"] else "finishing"
        o = self._move(order_id, "sewing", "sewing", nxt, "sewn_at", "تم الخياطة")
        worker = self._record_work(o, "sewing", worker_id)
        if worker:
            self.conn.execute("update order_events set details = ? where id = (select max(id) from order_events "
                              "where order_id = ?)", (f"الخياط: {worker}", order_id))
        self._log("تم الخياطة", f"#{order_id}")
        return nxt

    @rpc(write=True)
    def fitting_result(self, order_id, ok, note=None):
        if ok:
            self._move(order_id, "fitting", "fitting", "finishing", "fitted_at", "البروفة تمام", _t(note))
        else:
            self._move(order_id, "fitting", "fitting", "sewing", None, "البروفة محتاجة تعديل — رجع للخياطة",
                       _t(note))
            self.conn.execute("update orders set fitting_count = fitting_count + 1, note = coalesce(?, note) "
                              "where id = ?", (_t(note), order_id))
        self._log("نتيجة البروفة", f"#{order_id} {'تمام' if ok else 'تعديل'}")
        return True

    @rpc(write=True)
    def finish_finishing(self, order_id, worker_id=None):
        o = self._move(order_id, "finishing", "finishing", "ready", "finished_at", "تم التشطيب — جاهز للتسليم")
        worker = self._record_work(o, "finishing", worker_id)
        if worker:
            self.conn.execute("update order_events set details = ? where id = (select max(id) from order_events "
                              "where order_id = ?)", (f"التشطيب: {worker}", order_id))
        self._log("تم التشطيب", f"#{order_id}")
        return True

    @rpc(write=True)
    def deliver_order(self, order_id, collected, method_id=None):
        collected = _amount(collected, "المحصّل", allow_zero=True)
        o = self.q1("select price, deposit from orders where id = ?", (order_id,))
        if not o:
            raise AppError("الطلب ده مش موجود")
        if collected > 0 and not method_id:
            raise AppError("اختار طريقة الدفع")
        self._check_exists("payment_methods", method_id, "طريقة الدفع")
        self._move(order_id, "delivery", "ready", "awaiting_accounts", "delivered_at", "اتسلّم للعميل",
                   f"المحصّل {collected:g}")
        self.conn.execute("update orders set final_collected = ?, final_method_id = ? where id = ?",
                          (collected, method_id if collected else None, order_id))
        self._log("تسليم طلب", f"#{order_id}", collected)
        return True

    @rpc(write=True)
    def confirm_final(self, order_id):
        o = self._move(order_id, "accounts", "awaiting_accounts", "completed", "completed_at", "تأكيد الحساب النهائى")
        self.conn.execute("update orders set completed_by = ? where id = ?", (self.user["id"], order_id))
        name = self._customer_name(o["customer_id"])
        entry = None
        if (o["final_collected"] or 0) > 0:
            entry = self._treasury(o["final_collected"], 0, f"تحصيل طلب #{order_id} من العميل {name} عند التسليم",
                                   o["final_method_id"], self._dept("sales"), branch_id=o["branch_id"],
                                   counterparty=name, order_id=order_id, source="order_final")
        self._log("تأكيد الحساب النهائى", f"#{order_id} {name}", o["final_collected"])
        return entry

    @rpc(write=True)
    def step_back(self, order_id):
        """رجوع الطلب للمرحلة اللى قبلها (لو حد داس غلط). مسموح للمدير بس، وقبل أى فلوس."""
        if not self.user["is_admin"]:
            raise AppError("المدير بس يقدر يرجّع طلب لمرحلة قبلها")
        o = self.q1("select * from orders where id = ?", (order_id,))
        if not o:
            raise AppError("الطلب ده مش موجود")
        back = {"sewing": "cutting", "fitting": "sewing", "finishing": "fitting" if o["needs_fitting"] else "sewing",
                "ready": "finishing", "awaiting_accounts": "ready"}
        if o["status"] not in back:
            raise AppError("الطلب ده مينفعش يرجع من المرحلة دى")
        self.conn.execute("update orders set status = ?, final_collected = case when ? = 'ready' then null "
                          "else final_collected end, final_method_id = case when ? = 'ready' then null "
                          "else final_method_id end where id = ?",
                          (back[o["status"]], back[o["status"]], back[o["status"]], order_id))
        self._event(order_id, f"رجوع لمرحلة «{STATUS_LABELS[back[o['status']]]}»")
        self._log("رجوع طلب لمرحلة قبلها", f"#{order_id}")
        return back[o["status"]]

    # ===============================================================
    #                  معادلات الخامات (التركيبة)
    # ===============================================================

    def _formula_names(self):
        return formulas.measure_names(self.q("select grp, name from measure_fields"))

    def _style_extra(self, style):
        """القماش الزيادة من تفاصيل الموديل (اختيار مكتوب جنبه = +0.3 مثلاً)."""
        extra = 0.0
        for opt in self.q("select name, choices from style_options where is_active = 1"):
            chosen = (style or {}).get(opt["name"])
            if not chosen:
                continue
            for line in str(opt["choices"] or "").splitlines():
                name, value = formulas.split_choice(line)
                if name == chosen:
                    extra += value
        return extra

    def _calc_plan(self, garment_type_id, quantity, measurements, style, fabric_source, fabric_material_id):
        """الخامات اللى الطلب محتاجها: [{material_id, qty, note}] (الكمية للطلب كله)."""
        if not garment_type_id:
            return []
        names = self._formula_names()
        totals, notes = {}, {}
        for line in self.q("select * from bom_lines where garment_type_id = ? and is_active = 1 order by sort, id",
                           (garment_type_id,)):
            if line["is_fabric"]:
                if fabric_source == "customer" or not fabric_material_id:
                    continue
                material = fabric_material_id
            else:
                material = line["material_id"]
            if not material:
                continue
            note = ""
            try:
                qty = formulas.evaluate(line["formula"], names, measurements)
            except formulas.MissingMeasure as e:
                qty, note = line["fallback_qty"], f"مقاس «{e}» ناقص — اتحسبت بالكمية الافتراضية"
            except formulas.FormulaError as e:
                qty, note = line["fallback_qty"], f"المعادلة فيها غلط ({e}) — اتحسبت بالكمية الافتراضية"
            if line["is_fabric"]:
                qty += self._style_extra(style)
            total = round(qty * int(quantity or 1), 3)
            if total <= 0:
                continue
            totals[material] = round(totals.get(material, 0) + total, 3)
            if note:
                notes[material] = note
        return [{"material_id": m, "qty": q, "note": notes.get(m, "")} for m, q in totals.items()]

    @staticmethod
    def _plan_json(plan):
        return json.dumps([{"material_id": p["material_id"], "qty": p["qty"]} for p in plan])

    def _reserved(self, exclude_order=None):
        """الخامات المحجوزة للطلبات اللى لسه متقصتش."""
        out = {}
        for r in self.q("select id, materials_plan from orders where cut_at is null and status <> 'completed' "
                        "and materials_plan <> '[]'"):
            if r["id"] == exclude_order:
                continue
            for p in _jload(r["materials_plan"], []):
                try:
                    out[p["material_id"]] = out.get(p["material_id"], 0) + float(p["qty"])
                except (KeyError, TypeError, ValueError):
                    pass
        return out

    def _materials_with_reserved(self, sql, args=()):
        rows = self.q(sql, args)
        reserved = self._reserved()
        for m in rows:
            m["reserved"] = round(reserved.get(m["id"], 0), 3)
            m["available"] = round(m["qty"] - m["reserved"], 3)
        return rows

    def _plan_with_names(self, plan, info):
        if not plan:
            return []
        out = []
        for p in plan:
            m = info.get(p.get("material_id"))
            if m:
                out.append({"material_id": m["id"], "name": m["name"], "unit": m["unit"], "qty": p["qty"],
                            "note": p.get("note", "")})
        return out

    @rpc()
    def calc_materials(self, garment_type_id=None, quantity=1, measurements=None, style=None, fabric_source="factory",
                       fabric_material_id=None, order_id=None):
        """حساب الخامات قبل الحفظ (للفورم): الكمية + الموجود فى المخزن بعد المحجوز لطلبات تانية."""
        self._require(ORDER_PAGES, "view")
        try:
            quantity = max(int(quantity or 1), 1)
        except (TypeError, ValueError):
            quantity = 1
        plan = self._calc_plan(garment_type_id, quantity, self._clean_measurements(measurements), style or {},
                               fabric_source, fabric_material_id)
        reserved = self._reserved(exclude_order=order_id)
        info = {m["id"]: m for m in self.q("select id, name, unit, qty from materials")}
        out = []
        for p in plan:
            m = info.get(p["material_id"])
            if not m:
                continue
            available = round(m["qty"] - reserved.get(m["id"], 0), 3)
            out.append({"material_id": m["id"], "name": m["name"], "unit": m["unit"], "qty": p["qty"],
                        "available": available, "short": p["qty"] > available + 1e-9, "note": p["note"]})
        return out

    @rpc("admin", write=True)
    def save_bom_line(self, garment_type_id, formula, material_id=None, is_fabric=False, fallback_qty=0, sort=0,
                      is_active=True, line_id=None):
        self._check_exists("garment_types", garment_type_id, "النوع")
        if not garment_type_id:
            raise AppError("اختار النوع")
        if not is_fabric:
            if not material_id:
                raise AppError("اختار الخامة")
            self._check_exists("materials", material_id, "الخامة")
        try:
            formulas.compile_formula(formula, self._formula_names())
        except formulas.FormulaError as e:
            raise AppError(str(e))
        values = (garment_type_id, None if is_fabric else material_id, 1 if is_fabric else 0, str(formula).strip(),
                  _amount(fallback_qty or 0, "الكمية الافتراضية", allow_zero=True), int(sort or 0),
                  1 if is_active else 0)
        if line_id:
            cur = self.conn.execute("update bom_lines set garment_type_id = ?, material_id = ?, is_fabric = ?, "
                                    "formula = ?, fallback_qty = ?, sort = ?, is_active = ? where id = ?",
                                    (*values, line_id))
            if cur.rowcount == 0:
                raise AppError("السطر ده مش موجود")
            result = line_id
        else:
            result = self.x("insert into bom_lines (garment_type_id, material_id, is_fabric, formula, fallback_qty, "
                            "sort, is_active) values (?, ?, ?, ?, ?, ?, ?)", values)
        self._log("تعديل معادلة خامات", str(formula))
        return result

    @rpc("admin", write=True)
    def delete_bom_line(self, line_id):
        cur = self.conn.execute("delete from bom_lines where id = ?", (line_id,))
        if cur.rowcount == 0:
            raise AppError("السطر ده مش موجود")
        return True

    @rpc("admin")
    def test_formula(self, formula, measurements=None):
        """تجربة معادلة بمقاسات (للإعدادات): بيرجّع الكمية أو رسالة الغلط."""
        try:
            return {"ok": True, "qty": round(formulas.evaluate(formula, self._formula_names(), measurements or {}), 3)}
        except formulas.MissingMeasure as e:
            return {"ok": False, "error": f"محتاج مقاس «{e}» عشان تتحسب"}
        except formulas.FormulaError as e:
            return {"ok": False, "error": str(e)}

    # ===============================================================
    #                     البيع الجاهز (البدل الجاهزة)
    # ===============================================================

    @rpc(write=True)
    def add_ready_sale(self, items, method_id, customer_name=None, mobile=None, seller_id=None, note=None,
                       branch_id=None):
        self._require("orders")
        if not items:
            raise AppError("ضيف صنف واحد على الأقل")
        self._check_exists("payment_methods", method_id, "طريقة الدفع")
        if not method_id:
            raise AppError("اختار طريقة الدفع")
        self._check_exists("staff", seller_id, "السيلز")
        cid = self._customer(customer_name, mobile) if _t(customer_name) else None
        total = 0.0
        lines = []
        for it in items:
            p = self.q1("select * from products where id = ?", (it.get("product_id"),))
            if not p:
                raise AppError("اختار الصنف")
            try:
                qty = int(it.get("qty") or 0)
            except (TypeError, ValueError):
                raise AppError("الكمية لازم تكون رقم صحيح")
            if qty <= 0:
                raise AppError("الكمية لازم تكون 1 أو أكتر")
            price = _amount(it.get("price") if it.get("price") not in (None, "") else p["price"], "سعر البيع",
                            allow_zero=True)
            if p["qty"] < qty:
                raise AppError(f"المتاح من «{p['name']}» {p['qty']} بس")
            total += qty * price
            lines.append((p, qty, price))
        total = round(total, 2)
        if total <= 0:
            raise AppError("إجمالى البيع لازم يكون أكبر من صفر")
        branch = self._branch(branch_id)
        sale_id = self.x("insert into ready_sales (branch_id, customer_id, total, method_id, seller_id, note, "
                         "created_by) values (?, ?, ?, ?, ?, ?, ?)",
                         (branch, cid, total, method_id, seller_id, _t(note), self.user["id"]))
        for p, qty, price in lines:
            self.x("insert into ready_sale_items (sale_id, product_id, qty, price) values (?, ?, ?, ?)",
                   (sale_id, p["id"], qty, price))
            self.conn.execute("update products set qty = qty - ? where id = ?", (qty, p["id"]))
            self.x("insert into product_moves (product_id, move_type, qty, unit_price, sale_id, created_by) "
                   "values (?, 'sale', ?, ?, ?, ?)", (p["id"], -qty, price, sale_id, self.user["id"]))
        who = _t(customer_name) or "عميل"
        entry = self._treasury(total, 0, f"بيع جاهز #{sale_id} — {who}", method_id, self._dept("sales"),
                               branch_id=branch, counterparty=_t(customer_name), source="ready_sale")
        self.conn.execute("update ready_sales set treasury_entry_id = ? where id = ?", (entry, sale_id))
        self._log("بيع جاهز", f"#{sale_id}", total)
        return sale_id

    @rpc()
    def ready_sales(self):
        self._require(("sales", "orders"), "view")
        rows = self.q("""select r.*, c.name as customer_name, c.mobile as customer_mobile, pm.name as method,
                                s.name as seller_name, b.name as branch_name
                         from ready_sales r left join customers c on c.id = r.customer_id
                         left join payment_methods pm on pm.id = r.method_id
                         left join staff s on s.id = r.seller_id
                         join branches b on b.id = r.branch_id order by r.id desc""")
        items = self.q("select i.*, p.name, p.size, p.color, p.cost from ready_sale_items i "
                       "join products p on p.id = i.product_id")
        by_sale = {}
        for it in items:
            by_sale.setdefault(it["sale_id"], []).append(it)
        for r in rows:
            r["items"] = by_sale.get(r["id"], [])
        return rows

    @rpc(write=True)
    def delete_ready_sale(self, sale_id):
        self._require("sales", "delete")
        sale = self.q1("select * from ready_sales where id = ?", (sale_id,))
        if not sale:
            raise AppError("البيعة دى مش موجودة")
        for it in self.q("select * from ready_sale_items where sale_id = ?", (sale_id,)):
            self.conn.execute("update products set qty = qty + ? where id = ?", (it["qty"], it["product_id"]))
            self.x("insert into product_moves (product_id, move_type, qty, unit_price, sale_id, note, created_by) "
                   "values (?, 'return', ?, ?, ?, ?, ?)",
                   (it["product_id"], it["qty"], it["price"], sale_id, f"إلغاء بيع #{sale_id}", self.user["id"]))
        entry = sale["treasury_entry_id"]
        self.conn.execute("delete from ready_sales where id = ?", (sale_id,))
        if entry:
            self.conn.execute("delete from treasury_entries where id = ?", (entry,))
        self._log("إلغاء بيع جاهز", f"#{sale_id}", sale["total"])
        return True

    # ===============================================================
    #                           المخزن
    # ===============================================================

    @rpc()
    def materials(self):
        self._require(("inventory", "cutting"), "view")
        rows = self._materials_with_reserved("""select m.*, m.qty * m.avg_cost as value
                         from materials m order by m.is_active desc, m.category, m.name""")
        for m in rows:      # "قربت تخلص" بتتحسب على المتاح بعد الحجز
            m["low"] = bool(m["reorder_level"] > 0 and m["available"] <= m["reorder_level"])
        return rows

    @rpc(write=True)
    def save_material(self, name, unit="متر", category=None, reorder_level=0, is_active=True, material_id=None):
        self._require("inventory")
        data = (_need(name, "اسم الخامة مطلوب"), _t(category), _need(unit, "الوحدة مطلوبة"),
                _amount(reorder_level or 0, "حد الطلب", allow_zero=True), 1 if is_active else 0)
        try:
            if material_id:
                cur = self.conn.execute("update materials set name = ?, category = ?, unit = ?, reorder_level = ?, "
                                        "is_active = ? where id = ?", (*data, material_id))
                if cur.rowcount == 0:
                    raise AppError("الخامة دى مش موجودة")
                return material_id
            mid = self.x("insert into materials (name, category, unit, reorder_level, is_active) "
                         "values (?, ?, ?, ?, ?)", data)
        except sqlite3.IntegrityError:
            raise AppError("الخامة دى موجودة قبل كده")
        self._log("إضافة خامة", name)
        return mid

    def _material(self, material_id):
        m = self.q1("select * from materials where id = ?", (material_id,))
        if not m:
            raise AppError("اختار الخامة")
        return m

    @rpc(write=True)
    def receive_material(self, material_id, qty, unit_cost=0, supplier_id=None, note=None, move_date=None,
                         add_supplier_invoice=True):
        """استلام خامات: الكمية بتزيد، ومتوسط السعر بيتحسب من جديد. لو فيه مورد،
           فاتورة بالمبلغ بتتسجل على حسابه أوتوماتيك."""
        self._require("inventory")
        m = self._material(material_id)
        qty = _amount(qty, "الكمية")
        unit_cost = _amount(unit_cost or 0, "سعر الوحدة", allow_zero=True)
        self._check_exists("suppliers", supplier_id, "المورد")
        total_qty = max(m["qty"], 0) + qty
        new_avg = ((max(m["qty"], 0) * m["avg_cost"]) + qty * unit_cost) / total_qty if total_qty else unit_cost
        self.conn.execute("update materials set qty = qty + ?, avg_cost = ? where id = ?",
                          (qty, round(new_avg, 4), material_id))
        d = _date(move_date) or _today()
        self.x("insert into material_moves (material_id, move_type, qty, unit_cost, supplier_id, note, move_date, "
               "created_by) values (?, 'in', ?, ?, ?, ?, ?, ?)",
               (material_id, qty, unit_cost, supplier_id, _t(note), d, self.user["id"]))
        if supplier_id and add_supplier_invoice and qty * unit_cost > 0:
            self.x("insert into supplier_txns (supplier_id, txn_date, txn_type, description, amount, created_by) "
                   "values (?, ?, 'invoice', ?, ?, ?)",
                   (supplier_id, d, f"استلام {m['name']} {qty:g} {m['unit']} × {unit_cost:g}",
                    round(qty * unit_cost, 2), self.user["id"]))
        self._log("استلام خامات", f"{m['name']} {qty:g}", qty * unit_cost)
        return True

    @rpc(write=True)
    def issue_material(self, material_id, qty, note=None, order_id=None):
        """صرف خامات بإيدك (هالك، عينات، أو لطلب)."""
        self._require("inventory")
        m = self._material(material_id)
        qty = _amount(qty, "الكمية")
        if m["qty"] + 1e-9 < qty:
            raise AppError(f"الكمية المتاحة {m['qty']:g} {m['unit']} بس")
        self._check_exists("orders", order_id, "رقم الطلب")
        self.conn.execute("update materials set qty = qty - ? where id = ?", (qty, material_id))
        self.x("insert into material_moves (material_id, move_type, qty, unit_cost, order_id, note, created_by) "
               "values (?, 'out', ?, ?, ?, ?, ?)", (material_id, -qty, m["avg_cost"], order_id, _t(note), self.user["id"]))
        if order_id:
            self.conn.execute("update orders set material_cost = material_cost + ? where id = ?",
                              (round(qty * m["avg_cost"], 2), order_id))
        self._log("صرف خامات", f"{m['name']} {qty:g}")
        return True

    @rpc(write=True)
    def adjust_material(self, material_id, new_qty, note=None):
        """جرد: الكمية الفعلية اللى على الرف."""
        self._require("inventory")
        m = self._material(material_id)
        new_qty = _amount(new_qty, "الكمية الفعلية", allow_zero=True)
        diff = round(new_qty - m["qty"], 4)
        if diff == 0:
            raise AppError("الكمية زى ما هى — مفيش تعديل")
        self.conn.execute("update materials set qty = ? where id = ?", (new_qty, material_id))
        self.x("insert into material_moves (material_id, move_type, qty, unit_cost, note, created_by) "
               "values (?, 'adjust', ?, ?, ?, ?)", (material_id, diff, m["avg_cost"], _t(note) or "جرد", self.user["id"]))
        self._log("جرد خامة", f"{m['name']}: {m['qty']:g} ← {new_qty:g}")
        return True

    @rpc()
    def material_moves(self, material_id):
        self._require("inventory", "view")
        return self.q("""select mm.*, s.name as supplier_name, u.full_name as user_name
                         from material_moves mm left join suppliers s on s.id = mm.supplier_id
                         left join users u on u.id = mm.created_by
                         where mm.material_id = ? order by mm.id desc""", (material_id,))

    @rpc()
    def products(self):
        self._require(("inventory", "orders"), "view")
        return self.q("""select p.*, g.name as garment_type, p.qty * p.cost as value
                         from products p left join garment_types g on g.id = p.garment_type_id
                         order by p.is_active desc, p.name, p.size""")

    @rpc(write=True)
    def save_product(self, name, price=0, garment_type_id=None, size=None, color=None, is_active=True,
                     product_id=None):
        self._require("inventory")
        self._check_exists("garment_types", garment_type_id, "النوع")
        data = (_need(name, "اسم الصنف مطلوب"), garment_type_id, _t(size), _t(color),
                _amount(price or 0, "سعر البيع", allow_zero=True), 1 if is_active else 0)
        try:
            if product_id:
                cur = self.conn.execute("update products set name = ?, garment_type_id = ?, size = ?, color = ?, "
                                        "price = ?, is_active = ? where id = ?", (*data, product_id))
                if cur.rowcount == 0:
                    raise AppError("الصنف ده مش موجود")
                return product_id
            pid = self.x("insert into products (name, garment_type_id, size, color, price, is_active) "
                         "values (?, ?, ?, ?, ?, ?)", data)
        except sqlite3.IntegrityError:
            raise AppError("الصنف ده (بنفس المقاس واللون) موجود قبل كده")
        self._log("إضافة صنف جاهز", name)
        return pid

    @rpc(write=True)
    def product_in(self, product_id, qty, unit_cost=0, note=None):
        self._require("inventory")
        p = self.q1("select * from products where id = ?", (product_id,))
        if not p:
            raise AppError("اختار الصنف")
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            raise AppError("الكمية لازم تكون رقم صحيح")
        if qty <= 0:
            raise AppError("الكمية لازم تكون 1 أو أكتر")
        unit_cost = _amount(unit_cost or 0, "التكلفة", allow_zero=True)
        old = max(p["qty"], 0)
        new_cost = ((old * p["cost"]) + qty * unit_cost) / (old + qty)
        self.conn.execute("update products set qty = qty + ?, cost = ? where id = ?", (qty, round(new_cost, 2), product_id))
        self.x("insert into product_moves (product_id, move_type, qty, unit_price, note, created_by) "
               "values (?, 'in', ?, ?, ?, ?)", (product_id, qty, unit_cost, _t(note), self.user["id"]))
        self._log("إضافة بضاعة جاهزة", f"{p['name']} {qty}")
        return True

    @rpc(write=True)
    def adjust_product(self, product_id, new_qty, note=None):
        self._require("inventory")
        p = self.q1("select * from products where id = ?", (product_id,))
        if not p:
            raise AppError("اختار الصنف")
        try:
            new_qty = int(new_qty)
        except (TypeError, ValueError):
            raise AppError("الكمية لازم تكون رقم صحيح")
        if new_qty < 0:
            raise AppError("الكمية مينفعش تبقى سالب")
        diff = new_qty - p["qty"]
        if diff == 0:
            raise AppError("الكمية زى ما هى — مفيش تعديل")
        self.conn.execute("update products set qty = ? where id = ?", (new_qty, product_id))
        self.x("insert into product_moves (product_id, move_type, qty, note, created_by) values (?, 'adjust', ?, ?, ?)",
               (product_id, diff, _t(note) or "جرد", self.user["id"]))
        self._log("جرد صنف جاهز", f"{p['name']}: {p['qty']} ← {new_qty}")
        return True

    @rpc()
    def product_moves(self, product_id):
        self._require("inventory", "view")
        return self.q("select pm.*, u.full_name as user_name from product_moves pm "
                      "left join users u on u.id = pm.created_by where pm.product_id = ? order by pm.id desc",
                      (product_id,))

    # ===============================================================
    #                           الخزينة
    # ===============================================================

    TREASURY_SELECT = """
        select t.*, b.name as branch_name, pm.name as payment_method, pm.channel, d.name as department,
               coalesce(d.is_sales, 0) as is_sales, coalesce(d.in_profit, 0) as in_profit, u.full_name as user_name
        from treasury_entries t
        join branches b on b.id = t.branch_id
        left join payment_methods pm on pm.id = t.payment_method_id
        left join departments d on d.id = t.department_id
        left join users u on u.id = t.created_by
    """

    def _treasury_rows(self, branch_id=None):
        where, args = ("where t.branch_id = ?", (branch_id,)) if branch_id else ("", ())
        return self.q(f"{self.TREASURY_SELECT} {where} order by t.entry_date desc, t.id desc", args)

    @rpc()
    def treasury(self, branch_id=None):
        self._require("treasury", "view")
        return self._treasury_rows(branch_id)

    @rpc(write=True)
    def add_treasury_entry(self, direction, amount, description, payment_method_id=None, department_id=None,
                           entry_date=None, branch_id=None, counterparty=None):
        self._require("treasury")
        if direction not in ("in", "out"):
            raise AppError("اختار وارد أو منصرف")
        amount = _amount(amount)
        description = _need(description, "وصف القيد مطلوب")
        self._check_exists("payment_methods", payment_method_id, "طريقة الدفع")
        self._check_exists("departments", department_id, "الإدارة")
        entry = self._treasury(amount if direction == "in" else 0, amount if direction == "out" else 0, description,
                               payment_method_id, department_id, _date(entry_date) or _today(), branch_id,
                               _t(counterparty))
        self._log("قيد خزينة", description, amount)
        return entry

    @rpc(write=True)
    def update_treasury_department(self, entry_id, department_id):
        self._require("treasury")
        self._check_exists("departments", department_id, "الإدارة")
        cur = self.conn.execute("update treasury_entries set department_id = ? where id = ?", (department_id, entry_id))
        if cur.rowcount == 0:
            raise AppError("القيد ده مش موجود")
        return True

    @rpc(write=True)
    def delete_treasury_entry(self, entry_id):
        """بيرجّع عدد الحركات المرتبطة اللى اتمسحت معاه (مورد / أجور)."""
        self._require("treasury", "delete")
        r = self.q1("select * from treasury_entries where id = ?", (entry_id,))
        if not r:
            raise AppError("القيد ده مش موجود")
        if r["source"] in ("order_deposit", "order_final"):
            raise AppError(f"القيد ده جاى من تحصيل الطلب #{r['order_id']} — عدّل الطلب نفسه بدل ما تمسح القيد")
        if r["source"] == "ready_sale":
            raise AppError("القيد ده جاى من بيع جاهز — ألغِ البيعة من صفحة المبيعات")
        # الشيك اللى اتصرف بالقيد ده يرجع "مستحق"؛ ودفعات الموردين والأجور بتتمسح معاه
        self.conn.execute("update supplier_txns set cheque_status = 'due', treasury_entry_id = null "
                          "where treasury_entry_id = ? and txn_type = 'cheque'", (entry_id,))
        linked = self.val("select count(*) from supplier_txns where treasury_entry_id = ?", (entry_id,), 0) + \
            self.val("select count(*) from staff_txns where treasury_entry_id = ?", (entry_id,), 0)
        self.conn.execute("delete from treasury_entries where id = ?", (entry_id,))
        self._log("مسح قيد خزينة", r["description"], r["amount_in"] + r["amount_out"])
        return linked

    # ===============================================================
    #                       الموردين والشيكات
    # ===============================================================

    @rpc()
    def supplier_balances(self):
        self._require(("suppliers", "inventory"), "view")
        return self.q("""
            select s.*,
              coalesce(sum(case when t.txn_type = 'invoice' then t.amount end), 0) as invoices,
              coalesce(sum(case when t.txn_type = 'return' then t.amount end), 0) as returns,
              coalesce(sum(case when t.txn_type = 'cash_payment' then t.amount end), 0) as cash_paid,
              coalesce(sum(case when t.txn_type = 'bank_payment' then t.amount end), 0) as bank_paid,
              coalesce(sum(case when t.txn_type = 'cheque' and t.cheque_status = 'due' then t.amount end), 0)
                  as cheques_due,
              coalesce(sum(case when t.txn_type = 'cheque' and t.cheque_status = 'cashed' then t.amount end), 0)
                  as cheques_cashed,
              coalesce(sum(case when t.txn_type = 'invoice' then t.amount
                                when t.txn_type in ('return', 'cash_payment', 'bank_payment', 'cheque') then -t.amount
                                else 0 end), 0) as remaining
            from suppliers s left join supplier_txns t on t.supplier_id = s.id
            group by s.id order by s.name""")

    @rpc()
    def supplier_txns(self, supplier_id):
        self._require("suppliers", "view")
        return self.q("select * from supplier_txns where supplier_id = ? order by txn_date desc, id desc", (supplier_id,))

    @rpc(write=True)
    def add_supplier(self, name, material=None, mobile=None, supplier_type=None):
        self._require(("suppliers", "inventory"))
        name = _need(name, "اسم المورد مطلوب")
        if self.q1("select id from suppliers where name = ?", (name,)):
            raise AppError(f"المورد «{name}» موجود بالفعل")
        sid = self.x("insert into suppliers (name, material, mobile, supplier_type) values (?, ?, ?, ?)",
                     (name, _t(material), _t(mobile), _t(supplier_type) or "أخرى"))
        self._log("إضافة مورد", name)
        return sid

    @rpc(write=True)
    def add_supplier_txn(self, supplier_id, txn_type, amount, description=None, cheque_no=None, due_date=None,
                         branch_id=None):
        self._require("suppliers")
        s = self.q1("select * from suppliers where id = ?", (supplier_id,))
        if not s:
            raise AppError("اختار المورد")
        if txn_type not in SUPPLIER_TXN_TYPES:
            raise AppError("اختار نوع الحركة")
        amount = _amount(amount)
        due = _date(due_date, "تاريخ الاستحقاق")
        if txn_type == "cheque" and not due:
            raise AppError("تاريخ استحقاق الشيك مطلوب")
        entry = None
        if txn_type in ("cash_payment", "bank_payment"):
            entry = self._treasury(0, amount, _t(description) or f"دفعة للمورد {s['name']}",
                                   self._method_by_channel("cash" if txn_type == "cash_payment" else "bank"),
                                   self._dept("purchases"), branch_id=branch_id, counterparty=s["name"],
                                   supplier_id=s["id"], source="supplier_payment")
        tid = self.x("insert into supplier_txns (supplier_id, txn_type, description, amount, cheque_no, due_date, "
                     "cheque_status, treasury_entry_id, created_by) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (s["id"], txn_type, _t(description), amount,
                      _t(cheque_no) if txn_type == "cheque" else None, due if txn_type == "cheque" else None,
                      "due" if txn_type == "cheque" else None, entry, self.user["id"]))
        self._log(f"حركة مورد: {txn_type}", s["name"], amount)
        return tid

    @rpc()
    def due_cheques(self):
        self._require(("cheques", "suppliers"), "view")
        rows = self.q("""select t.id, t.supplier_id, s.name as supplier_name, t.cheque_no, t.amount, t.due_date
                         from supplier_txns t join suppliers s on s.id = t.supplier_id
                         where t.txn_type = 'cheque' and t.cheque_status = 'due' order by t.due_date""")
        today = date.today()
        for r in rows:
            r["days_left"] = (datetime.strptime(r["due_date"], "%Y-%m-%d").date() - today).days
        return rows

    @rpc(write=True)
    def cash_due_cheques(self, branch_id=None):
        self._require("cheques")
        method = self._method_by_channel("cheque")
        n = 0
        for c in self.q("""select t.id, t.amount, t.cheque_no, t.due_date, s.id as supplier_id, s.name
                           from supplier_txns t join suppliers s on s.id = t.supplier_id
                           where t.txn_type = 'cheque' and t.cheque_status = 'due' and t.due_date <= ?
                           order by t.due_date""", (_today(),)):
            entry = self._treasury(0, c["amount"], f"صرف شيك رقم {c['cheque_no'] or '—'} - {c['name']}", method,
                                   self._dept("purchases"), c["due_date"], branch_id, c["name"], c["supplier_id"],
                                   source="cheque")
            self.conn.execute("update supplier_txns set cheque_status = 'cashed', treasury_entry_id = ? where id = ?",
                              (entry, c["id"]))
            n += 1
        if n:
            self._log("صرف شيكات مستحقة", f"{n} شيك")
        return n

    # ===============================================================
    #                        العمال والأجور
    # ===============================================================

    @rpc()
    def staff_list(self):
        self._require(("workers", "dashboard"), "view")
        return self.q("select * from staff order by is_active desc, kind, name")

    def _staff_values(self, name, mobile, kind, craft, pay_type, salary, hired_on):
        if kind not in ("sales", "worker", "other"):
            raise AppError("اختار النوع")
        if pay_type not in ("piece", "salary", "both"):
            raise AppError("اختار طريقة الحساب")
        return (_need(name, "الاسم مطلوب"), _t(mobile), kind, _t(craft), pay_type,
                _amount(salary or 0, "المرتب", allow_zero=True), _date(hired_on, "تاريخ التعيين") or _today())

    @rpc(write=True)
    def add_staff(self, name, mobile=None, kind="worker", craft=None, pay_type="piece", salary=0, hired_on=None):
        self._require("workers")
        values = self._staff_values(name, mobile, kind, craft, pay_type, salary, hired_on)
        try:
            sid = self.x("insert into staff (name, mobile, kind, craft, pay_type, salary, hired_on) "
                         "values (?, ?, ?, ?, ?, ?, ?)", values)
        except sqlite3.IntegrityError:
            raise AppError("الاسم ده موجود قبل كده")
        self._log("إضافة عامل/موظف", name)
        return sid

    @rpc(write=True)
    def update_staff(self, staff_id, name, mobile=None, kind="worker", craft=None, pay_type="piece", salary=0,
                     hired_on=None, is_active=True):
        self._require("workers")
        values = self._staff_values(name, mobile, kind, craft, pay_type, salary, hired_on)
        try:
            cur = self.conn.execute("update staff set name = ?, mobile = ?, kind = ?, craft = ?, pay_type = ?, "
                                    "salary = ?, hired_on = ?, is_active = ? where id = ?",
                                    (*values, 1 if is_active else 0, staff_id))
        except sqlite3.IntegrityError:
            raise AppError("الاسم ده موجود قبل كده")
        if cur.rowcount == 0:
            raise AppError("الشخص ده مش موجود")
        self._log("تعديل عامل/موظف", name)
        return True

    @rpc(write=True)
    def add_work(self, staff_id, description, amount=None, qty=1, rate=None, work_month=None, order_id=None):
        """شغل بالقطعة متسجلش أوتوماتيك (مثلاً تصليح أو شغل خارجى)."""
        self._require("workers")
        if not self.q1("select id from staff where id = ?", (staff_id,)):
            raise AppError("اختار العامل")
        qty = _amount(qty or 1, "العدد")
        if rate not in (None, ""):
            rate = _amount(rate, "سعر القطعة", allow_zero=True)
            amount = round(rate * qty, 2)
        else:
            amount = _amount(amount, "المبلغ")
            rate = round(amount / qty, 2)
        if amount <= 0:
            raise AppError("المبلغ لازم يكون أكبر من صفر")
        self._check_exists("orders", order_id, "رقم الطلب")
        wid = self.x("insert into work_log (staff_id, order_id, description, qty, rate, amount, work_month, created_by) "
                     "values (?, ?, ?, ?, ?, ?, ?, ?)",
                     (staff_id, order_id, _need(description, "اكتب الشغل اتعمل إيه"), qty, rate, amount,
                      _month(work_month), self.user["id"]))
        self._log("تسجيل شغل لعامل", description, amount)
        return wid

    @rpc(write=True)
    def delete_work(self, work_id):
        self._require("workers", "delete")
        w = self.q1("select * from work_log where id = ?", (work_id,))
        if not w:
            raise AppError("السطر ده مش موجود")
        self.conn.execute("delete from work_log where id = ?", (work_id,))
        if w["order_id"]:
            self.conn.execute("update orders set labor_cost = max(labor_cost - ?, 0) where id = ?",
                              (w["amount"], w["order_id"]))
        self._log("مسح شغل عامل", w["description"], w["amount"])
        return True

    @rpc(write=True)
    def add_staff_txn(self, staff_id, txn_type, amount, for_month=None, description=None, method_id=None,
                      branch_id=None):
        """السلفة والصرف بينزلوا منصرف فى الخزينة أوتوماتيك. المكافأة والخصم بيتسجلوا بس."""
        self._require("workers")
        s = self.q1("select * from staff where id = ?", (staff_id,))
        if not s:
            raise AppError("اختار العامل")
        if txn_type not in STAFF_TXN_TYPES:
            raise AppError("اختار نوع الحركة")
        amount = _amount(amount)
        month = _month(for_month)
        entry = None
        labels = {"advance": "سلفة", "payment": "صرف أجر", "bonus": "مكافأة", "deduction": "خصم"}
        if txn_type in ("advance", "payment"):
            self._check_exists("payment_methods", method_id, "طريقة الدفع")
            entry = self._treasury(0, amount, f"{labels[txn_type]} — {s['name']} ({month})" +
                                   (f" — {_t(description)}" if _t(description) else ""),
                                   method_id or self._method_by_channel("cash"), self._dept("payroll"),
                                   branch_id=branch_id, counterparty=s["name"], source="payroll")
        tid = self.x("insert into staff_txns (staff_id, txn_type, amount, for_month, description, treasury_entry_id, "
                     "created_by) values (?, ?, ?, ?, ?, ?, ?)",
                     (staff_id, txn_type, amount, month, _t(description), entry, self.user["id"]))
        self._log(labels[txn_type], s["name"], amount)
        return tid

    @rpc(write=True)
    def delete_staff_txn(self, txn_id):
        self._require("workers", "delete")
        t = self.q1("select * from staff_txns where id = ?", (txn_id,))
        if not t:
            raise AppError("الحركة دى مش موجودة")
        self.conn.execute("delete from staff_txns where id = ?", (txn_id,))
        if t["treasury_entry_id"]:
            self.conn.execute("delete from treasury_entries where id = ?", (t["treasury_entry_id"],))
        self._log("مسح حركة عامل", t["txn_type"], t["amount"])
        return True

    @rpc()
    def payroll(self, month=None):
        """كشف الأجور لشهر: المستحق (مرتب + قطعة + مكافآت − خصومات) − المصروف (سلف + صرف)."""
        self._require("workers", "view")
        month = _month(month)
        month_end = (datetime.strptime(month + "-01", "%Y-%m-%d").date().replace(day=28) + timedelta(days=4))
        month_end = (month_end - timedelta(days=month_end.day)).isoformat()
        work = {r["staff_id"]: r for r in self.q(
            "select staff_id, sum(amount) as pieces, sum(qty) as pieces_qty from work_log where work_month = ? "
            "group by staff_id", (month,))}
        txns = {}
        for r in self.q("select staff_id, txn_type, sum(amount) as total from staff_txns where for_month = ? "
                        "group by staff_id, txn_type", (month,)):
            txns.setdefault(r["staff_id"], {})[r["txn_type"]] = r["total"]
        out = []
        for s in self.q("select * from staff order by kind, name"):
            t = txns.get(s["id"], {})
            w = work.get(s["id"], {})
            salary = s["salary"] if s["pay_type"] in ("salary", "both") and s["is_active"] and \
                (not s["hired_on"] or s["hired_on"] <= month_end) else 0
            if not (s["is_active"] or t or w):
                continue
            if s["kind"] == "sales" and not (salary or t or w):
                continue
            earned = salary + (w.get("pieces") or 0) + t.get("bonus", 0) - t.get("deduction", 0)
            paid = t.get("advance", 0) + t.get("payment", 0)
            out.append({"staff_id": s["id"], "name": s["name"], "kind": s["kind"], "craft": s["craft"],
                        "pay_type": s["pay_type"], "is_active": s["is_active"], "salary": salary,
                        "pieces": w.get("pieces") or 0, "pieces_qty": w.get("pieces_qty") or 0,
                        "bonus": t.get("bonus", 0), "deduction": t.get("deduction", 0),
                        "advance": t.get("advance", 0), "payment": t.get("payment", 0),
                        "earned": round(earned, 2), "paid": round(paid, 2), "remaining": round(earned - paid, 2)})
        return {"month": month, "rows": out}

    @rpc()
    def staff_statement(self, staff_id, month=None):
        self._require("workers", "view")
        month = _month(month)
        return {
            "work": self.q("select w.*, g.name as garment_type from work_log w left join orders o on o.id = w.order_id "
                           "left join garment_types g on g.id = o.garment_type_id "
                           "where w.staff_id = ? and w.work_month = ? order by w.id desc", (staff_id, month)),
            "txns": self.q("select * from staff_txns where staff_id = ? and for_month = ? order by id desc",
                           (staff_id, month)),
        }

    # ===============================================================
    #                          الداش بورد
    # ===============================================================

    @rpc()
    def dashboard(self, branch_id=None):
        self._require("dashboard", "view")
        bwhere = "and t.branch_id = ?" if branch_id else ""
        bargs = (branch_id,) if branch_id else ()
        start = self.val("select profit_start_date from company where id = 1") or "1900-01-01"
        k = self.q1(f"""
            select coalesce(sum(t.amount_in), 0) as wared, coalesce(sum(t.amount_out), 0) as monsaref,
                   count(*) as amaliyat,
                   coalesce(sum(case when d.is_sales = 1 and t.entry_date >= ? then t.amount_in end), 0) as sales,
                   coalesce(sum(case when d.in_profit = 1 and t.entry_date >= ? then t.amount_out end), 0) as expenses
            from treasury_entries t left join departments d on d.id = t.department_id
            where 1 = 1 {bwhere}""", (start, start, *bargs))
        k["raseed"] = k["wared"] - k["monsaref"]
        k["rebh"] = k["sales"] - k["expenses"]

        owhere = "and o.branch_id = ?" if branch_id else ""
        orders = self.q(f"""select o.status, o.price, o.deposit, o.due_date, o.created_at, o.seller_id,
                                  o.price - o.deposit as remaining
                           from orders o where o.status <> 'completed' {owhere}""", bargs)
        today = _today()
        week = (date.today() + timedelta(days=7)).isoformat()
        not_done = ("awaiting_deposit", "cutting", "sewing", "fitting", "finishing")
        k.update({
            "open_orders": len(orders),
            "open_value": sum(o["price"] for o in orders),
            "customers_remaining": sum(o["remaining"] for o in orders),
            "late_orders": sum(1 for o in orders if o["due_date"] and o["due_date"] < today and o["status"] in not_done),
            "due_week": sum(1 for o in orders if o["due_date"] and today <= o["due_date"] <= week
                            and o["status"] in not_done),
            "ready_orders": sum(1 for o in orders if o["status"] == "ready"),
            "stages": {s: sum(1 for o in orders if o["status"] == s) for s in STATUSES[:-1]},
        })
        sup = self.q1("""select coalesce(sum(case when txn_type = 'invoice' then amount
                              when txn_type in ('return', 'cash_payment', 'bank_payment', 'cheque') then -amount end), 0)
                              as suppliers_due,
                              coalesce(sum(case when txn_type = 'cheque' and cheque_status = 'due' then amount end), 0)
                              as cheques_due from supplier_txns""")
        k.update(sup)
        k["low_stock"] = sum(1 for m in self._materials_with_reserved(
            "select id, qty, reorder_level from materials where is_active = 1 and reorder_level > 0")
            if m["available"] <= m["reorder_level"])
        k["stock_value"] = self.val("select sum(qty * avg_cost) from materials where qty > 0", default=0) + \
            self.val("select sum(qty * cost) from products where qty > 0", default=0)

        profit = self.q(f"""
            select substr(t.entry_date, 1, 7) as month,
                   coalesce(sum(case when d.is_sales = 1 then t.amount_in end), 0) as sales,
                   coalesce(sum(case when d.in_profit = 1 then t.amount_out end), 0) as expenses
            from treasury_entries t left join departments d on d.id = t.department_id
            where t.entry_date >= ? {bwhere} group by 1 order by 1""", (start, *bargs))
        for m in profit:
            m["profit"] = m["sales"] - m["expenses"]
        monthly = self.q(f"""select substr(o.created_at, 1, 7) as month, count(*) as orders,
                                    coalesce(sum(o.price), 0) as total_value
                             from orders o where 1 = 1 {owhere} group by 1 order by 1""", bargs)
        this_month = date.today().strftime("%Y-%m")
        sellers = self.q(f"""select s.name, count(o.id) as orders, coalesce(sum(o.price), 0) as total
                             from orders o join staff s on s.id = o.seller_id
                             where substr(o.created_at, 1, 7) = ? {owhere}
                             group by s.id order by total desc""", (this_month, *bargs))
        late = self._orders(f"o.due_date is not null and o.due_date < ? and o.status in "
                            f"({', '.join('?' for _ in not_done)}) {owhere}", (today, *not_done, *bargs))
        return {"kpis": k, "profit": profit, "orders_by_month": monthly, "sellers": sellers,
                "late": late, "treasury": self._treasury_rows(branch_id)}
