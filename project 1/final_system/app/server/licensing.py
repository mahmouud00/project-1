"""
licensing.py — الترخيص (من غير إنترنت)
---------------------------------------
الفكرة:
  1) البرنامج بيطلّع "كود الجهاز" (بصمة جهاز السيرفر).
  2) العميل بيبعتهولك، وإنت بتعمل "كود تفعيل" من أداة license_tool (عندك إنت بس).
  3) كود التفعيل متوقّع بمفتاحك السرى (Ed25519)، والبرنامج معاه المفتاح العام بس:
     يقدر يتأكد إن الكود منك، بس مايقدرش يعمل كود جديد. فمحدش يقدر يزوّر ترخيص.

جوه الكود: بصمة الجهاز + الباقة + عدد المستخدمين + تاريخ البداية والنهاية + رقم مسلسل.
الملف ده هو كمان اللى أداة التراخيص بتستخدمه عشان تكتب الكود بنفس الشكل بالظبط.
"""

import base64
import hashlib
import os
import struct
import sys
import uuid
from datetime import date, timedelta

from .license_key import PUBLIC_KEY_HEX

FORMAT_VERSION = 1
EPOCH = date(2024, 1, 1)
# version, machine(8 bytes), plan, users, issued(days), expires(days, 0 = مدى الحياة), serial
_LAYOUT = struct.Struct(">B8sBHHHI")
SIGNATURE_SIZE = 64

PLANS = {0: "مدى الحياة", 1: "شهر", 2: "6 شهور", 3: "سنة", 4: "تجربة"}
WARN_DAYS = 7           # التنبيه قبل الانتهاء
CLOCK_TOLERANCE = 2     # أيام: لو تاريخ الجهاز رجع لورا أكتر من كده يبقى حد بيلعب فى التاريخ


class LicenseError(Exception):
    pass


# ========================= بصمة الجهاز =========================

def _raw_machine_guid() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                 winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
        except OSError:
            pass
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path) as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            pass
    return f"mac-{uuid.getnode():012x}"


def machine_bytes() -> bytes:
    return hashlib.sha256(("TailorMaster|" + _raw_machine_guid()).encode()).digest()[:8]


def format_machine(raw: bytes) -> str:
    h = raw.hex().upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def parse_machine(text: str) -> bytes:
    h = "".join(ch for ch in str(text or "") if ch.isalnum()).lower()
    if len(h) != 16:
        raise LicenseError("كود الجهاز لازم يكون 16 حرف/رقم (زى ABCD-1234-EF56-7890)")
    try:
        return bytes.fromhex(h)
    except ValueError:
        raise LicenseError("كود الجهاز فيه حروف غلط")


def machine_code() -> str:
    return format_machine(machine_bytes())


# ========================= شكل الكود =========================

def _days(d):
    return (d - EPOCH).days if d else 0


def _from_days(n):
    return EPOCH + timedelta(days=n) if n else None


def pack(machine: bytes, plan: int, users: int, issued: date, expires, serial: int) -> bytes:
    return _LAYOUT.pack(FORMAT_VERSION, machine, plan, users, _days(issued), _days(expires), serial)


def to_code(payload: bytes, signature: bytes) -> str:
    text = base64.b32encode(payload + signature).decode().rstrip("=")
    return "-".join(text[i:i + 5] for i in range(0, len(text), 5))


def from_code(code: str):
    text = "".join(ch for ch in str(code or "").upper() if ch.isalnum())
    if not text:
        raise LicenseError("اكتب كود التفعيل")
    try:
        raw = base64.b32decode(text + "=" * (-len(text) % 8))
    except Exception:  # noqa: BLE001
        raise LicenseError("كود التفعيل مكتوب غلط — انسخه تانى بالظبط زى ما وصلك")
    if len(raw) != _LAYOUT.size + SIGNATURE_SIZE:
        raise LicenseError("كود التفعيل ناقص أو زيادة — انسخه تانى بالظبط زى ما وصلك")
    return raw[:_LAYOUT.size], raw[_LAYOUT.size:]


class License:
    def __init__(self, payload: bytes):
        version, machine, plan, users, issued, expires, serial = _LAYOUT.unpack(payload)
        if version != FORMAT_VERSION:
            raise LicenseError("كود التفعيل ده لإصدار تانى من البرنامج")
        self.machine = machine
        self.plan = plan
        self.users = users
        self.issued = _from_days(issued)
        self.expires = _from_days(expires)
        self.serial = serial

    @property
    def plan_label(self):
        return PLANS.get(self.plan, "—")

    def to_dict(self):
        return {"plan": self.plan, "plan_label": self.plan_label, "users": self.users,
                "issued": self.issued.isoformat() if self.issued else None,
                "expires": self.expires.isoformat() if self.expires else None,
                "serial": self.serial, "machine": format_machine(self.machine)}


def public_key_ready() -> bool:
    return bool(PUBLIC_KEY_HEX) and "PUT" not in PUBLIC_KEY_HEX


def verify(code: str, machine: bytes = None) -> License:
    """بيتأكد من التوقيع وإن الكود لنفس الجهاز. أى مشكلة ← LicenseError برسالة عربى."""
    if not public_key_ready():
        raise LicenseError("البرنامج لسه متجهزش للبيع: شغّل license_tool/keygen.py الأول (مرة واحدة)")
    payload, signature = from_code(code)
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX)).verify(signature, payload)
    except InvalidSignature:
        raise LicenseError("كود التفعيل غير صحيح")
    lic = License(payload)
    if lic.machine != (machine or machine_bytes()):
        raise LicenseError("كود التفعيل ده معمول لجهاز تانى — ابعت كود الجهاز ده بالظبط واطلب كود جديد")
    return lic


# ========================= آخر تاريخ شافه البرنامج =========================
# بيتحفظ فى قاعدة البيانات وكمان فى ملف تانى، عشان لو حد رجّع تاريخ الجهاز لورا
# (عشان يطوّل الاشتراك) البرنامج يعرف.

def _shadow_path():
    if os.environ.get("TM_SHADOW_PATH"):          # للاختبارات
        return os.environ["TM_SHADOW_PATH"]
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Microsoft", "TMCache", "ls.bin") if sys.platform == "win32" \
        else os.path.join(base, ".cache", ".tm_ls")


def _shadow_read():
    try:
        with open(_shadow_path(), "rb") as f:
            raw = f.read()
        days, check = struct.unpack(">I16s", raw)
        if hashlib.sha256(b"tm-ls" + struct.pack(">I", days)).digest()[:16] == check:
            return EPOCH + timedelta(days=days)
    except (OSError, struct.error):
        pass
    return None


def _shadow_write(d: date):
    try:
        path = _shadow_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        days = _days(d)
        with open(path, "wb") as f:
            f.write(struct.pack(">I16s", days, hashlib.sha256(b"tm-ls" + struct.pack(">I", days)).digest()[:16]))
    except OSError:
        pass


def check_clock(stored_last_seen, today: date = None):
    """بيرجّع (التاريخ الجديد اللى يتحفظ، هل التاريخ اترجع لورا؟)."""
    today = today or date.today()
    candidates = [d for d in (stored_last_seen, _shadow_read()) if d]
    last = max(candidates) if candidates else None
    if last and today < last - timedelta(days=CLOCK_TOLERANCE):
        return last, True
    newest = max(today, last) if last else today
    if not last or newest > last:
        _shadow_write(newest)
    return newest, False


def evaluate(code, last_seen, today: date = None, machine: bytes = None) -> dict:
    """حالة الترخيص اللى البرنامج كله بيمشى عليها:
       none = مفيش ترخيص، invalid = الكود مش صالح، tamper = التاريخ اترجع،
       expired = انتهى (للعرض بس)، expiring = فاضل أسبوع أو أقل، ok = تمام."""
    today = today or date.today()
    out = {"state": "none", "writable": False, "machine": format_machine(machine or machine_bytes()),
           "message": "البرنامج محتاج تفعيل"}
    if not code:
        return out
    try:
        lic = verify(code, machine)
    except LicenseError as e:
        out.update(state="invalid", message=str(e))
        return out
    out.update(lic.to_dict())
    out["machine"] = format_machine(machine or machine_bytes())
    new_seen, tampered = check_clock(last_seen, today)
    out["last_seen"] = new_seen.isoformat()
    if tampered:
        out.update(state="tamper", message="تاريخ الجهاز متأخر عن الحقيقى — صحّح التاريخ والساعة وافتح البرنامج تانى. "
                                           "البرنامج للعرض بس لحد ما التاريخ يتصلح.")
        return out
    if lic.expires is None:
        out.update(state="ok", writable=True, days_left=None, message="ترخيص مدى الحياة")
        return out
    days_left = (lic.expires - today).days
    out["days_left"] = days_left
    if days_left < 0:
        out.update(state="expired", message=f"الاشتراك انتهى يوم {lic.expires.strftime('%d/%m/%Y')} — "
                                            "البرنامج للعرض بس. كلّم الشركة اللى باعتلك البرنامج عشان تجدد.")
    elif days_left <= WARN_DAYS:
        out.update(state="expiring", writable=True,
                   message=f"الاشتراك هينتهى بعد {days_left} يوم ({lic.expires.strftime('%d/%m/%Y')}) — جدّد قبلها")
    else:
        out.update(state="ok", writable=True, message=f"الاشتراك شغّال لحد {lic.expires.strftime('%d/%m/%Y')}")
    return out


def add_months(d: date, months: int) -> date:
    """نفس اليوم بعد عدد شهور (31/1 + شهر = 28 أو 29/2)."""
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def plan_expiry(plan: int, start: date, trial_days: int = 14):
    if plan == 0:
        return None
    if plan == 1:
        return add_months(start, 1)
    if plan == 2:
        return add_months(start, 6)
    if plan == 3:
        return add_months(start, 12)
    return start + timedelta(days=max(1, int(trial_days)))
