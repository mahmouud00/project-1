"""
license_core.py — عمل كود التفعيل (عندك إنت بس)
-------------------------------------------------
بيستخدم نفس شكل الكود اللى البرنامج بيفهمه (app/server/licensing.py)،
وبيمضيه بالمفتاح السرى seller_private_key.pem.
"""

import csv
import os
import secrets
import sys
from datetime import date, datetime

FROZEN = getattr(sys, "frozen", False)
# من exe: الفولدر اللى فيه الـ exe. من بايثون: فولدر license_tool
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), "app")
if not FROZEN and APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from server import licensing  # noqa: E402

KEY_NAME = "seller_private_key.pem"
PRIVATE_KEY_PATH = os.path.join(HERE, KEY_NAME)
LOG_PATH = os.path.join(HERE, "licenses_log.csv")


def use_key_file(path):
    """المفتاح السرى ممكن يكون فى أى فولدر: سجل التراخيص بيتحفظ جنبه."""
    global PRIVATE_KEY_PATH, LOG_PATH
    PRIVATE_KEY_PATH = path
    LOG_PATH = os.path.join(os.path.dirname(path), "licenses_log.csv")
LOG_HEADER = ["التاريخ", "العميل", "الموبايل", "كود الجهاز", "الباقة", "المستخدمين", "يبدأ", "ينتهى",
              "المسلسل", "كود التفعيل", "ملاحظات"]


def load_private_key(path=None):
    from cryptography.hazmat.primitives import serialization
    path = path or PRIVATE_KEY_PATH
    if not os.path.exists(path):
        raise FileNotFoundError("مفيش مفتاح سرى — شغّل keygen.py الأول (مرة واحدة بس)")
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def make_code(private_key, machine_text, plan, users, start=None, trial_days=14, serial=None):
    """بيرجّع (الكود، تاريخ الانتهاء أو None، المسلسل)."""
    machine = licensing.parse_machine(machine_text)
    if plan not in licensing.PLANS:
        raise ValueError("الباقة غير معروفة")
    users = int(users)
    if not 1 <= users <= 999:
        raise ValueError("عدد المستخدمين لازم يكون من 1 لـ 999")
    start = start or date.today()
    expires = licensing.plan_expiry(plan, start, trial_days)
    serial = serial if serial is not None else secrets.randbelow(2 ** 32)
    payload = licensing.pack(machine, plan, users, start, expires, serial)
    return licensing.to_code(payload, private_key.sign(payload)), expires, serial


def log_license(customer, mobile, machine, plan, users, start, expires, serial, code, notes=""):
    new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(LOG_HEADER)
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), customer, mobile, machine, licensing.PLANS[plan],
                    users, start.isoformat(), expires.isoformat() if expires else "مدى الحياة", serial, code, notes])


def read_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[1:]
