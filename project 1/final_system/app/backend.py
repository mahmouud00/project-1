"""
backend.py
----------
الطبقة الوحيدة اللى بتكلّم السيرفر. الواجهة مش بتعرف حاجة عن الشبكة خالص،
بتنادى دوال الكلاس ده وبس.

- كل عملية على السيرفر ليها نفس الاسم هنا: backend.add_order(price=..., ...)
  (الدوال اللى مش مكتوبة هنا صراحة بتتبعت للسيرفر بنفس اسمها أوتوماتيك).
- أى خطأ بيتحوّل لـ AppError برسالة عربى مفهومة.
- الاتصال على الشبكة المحلية بس (مفيش إنترنت ولا proxy).
"""

import base64
import json
import os
import socket
import urllib.error
import urllib.request

from models import AppError, Me, SessionExpired

NETWORK_MSG = ("مش قادر أوصل للسيرفر — اتأكد إن جهاز السيرفر مفتوح والبرنامج شغّال عليه، "
               "وإن الجهاز ده على نفس الشبكة")
MAX_FILE_MB = 15
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
FILE_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

# الشبكة المحلية بس: من غير أى proxy متظبط على الجهاز
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ping(host, port, timeout=2.0):
    """بيرجّع بيانات السيرفر لو لقاه، أو None."""
    try:
        with _OPENER.open(f"http://{host}:{port}/ping", timeout=timeout) as r:
            info = json.loads(r.read().decode("utf-8"))
        return info if info.get("app") == "TailorMaster" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def read_file_b64(path, max_mb=MAX_FILE_MB, types=FILE_TYPES):
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext not in types:
        raise AppError(f"نوع الملف مش مدعوم: {name} (PDF أو صورة بس)")
    if not os.path.isfile(path):
        raise AppError(f"الملف مش موجود: {name}")
    if os.path.getsize(path) > max_mb * 1024 * 1024:
        raise AppError(f"الملف أكبر من {max_mb} ميجا: {name}")
    with open(path, "rb") as f:
        return {"name": name, "mime": types[ext], "data": base64.b64encode(f.read()).decode()}


class Backend:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._url = f"http://{host}:{port}/rpc"
        self.token = None
        self.me = None

    # =========================================================
    #                       الاتصال
    # =========================================================

    def call(self, method, timeout=60, **params):
        body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": self.token or ""})
        try:
            with _OPENER.open(req, timeout=timeout) as r:
                payload = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError):
            raise AppError(NETWORK_MSG)
        except ValueError:
            raise AppError("رد السيرفر مش مفهوم — اتأكد إن العنوان ده بتاع سيرفر البرنامج")
        if payload.get("ok"):
            return payload.get("result")
        message = payload.get("error") or "حصل خطأ غير معروف"
        if payload.get("code") == "session":
            self.token = None
            raise SessionExpired(message)
        raise AppError(message)

    def __getattr__(self, name):
        """أى عملية مش مكتوبة تحت ← بتتبعت للسيرفر بنفس الاسم (بالـ keyword arguments)."""
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda **params: self.call(name, **params)

    # =========================================================
    #                  الدخول والحساب والشركة
    # =========================================================

    def status(self):
        return self.call("status", timeout=8)

    def _logged_in(self, res) -> Me:
        self.token = res["token"]
        self.me = Me(res["me"])
        return self.me

    def login(self, username, password) -> Me:
        return self._logged_in(self.call("login", username=(username or "").strip(), password=password or ""))

    def create_company(self, company_name, full_name, username, password, phone=None, logo_path=None) -> Me:
        logo = read_file_b64(logo_path, 2, LOGO_TYPES) if logo_path else None
        return self._logged_in(self.call(
            "create_company", company_name=company_name, full_name=full_name, username=username,
            password=password, phone=phone, logo_b64=logo["data"] if logo else None,
            logo_type=logo["mime"] if logo else None))

    def load_me(self) -> Me:
        self.me = Me(self.call("me"))
        return self.me

    def sign_out(self):
        try:
            if self.token:
                self.call("logout", timeout=5)
        except AppError:
            pass
        self.token = self.me = None

    # =========================================================
    #                    الملفات واللوجو
    # =========================================================

    def upload_logo(self, path) -> bytes:
        f = read_file_b64(path, 2, LOGO_TYPES)
        self.call("set_logo", data_b64=f["data"], mime=f["mime"])
        self.load_me()
        return base64.b64decode(f["data"])

    def remove_logo(self):
        self.call("remove_logo")
        self.load_me()

    def company_logo(self):
        data = self.call("company_logo")
        return base64.b64decode(data) if data else None

    @staticmethod
    def read_files(paths):
        return [read_file_b64(p) for p in paths or []]

    def download_file(self, file_id, folder):
        """بينزّل ملف الطلب فى فولدر مؤقت وبيرجّع مكانه (عشان يتفتح)."""
        f = self.call("get_file", file_id=file_id)
        safe = "".join(ch for ch in f["name"] if ch not in '\\/:*?"<>|') or f"file-{file_id}"
        path = os.path.join(folder, f"{file_id}-{safe}")
        with open(path, "wb") as out:
            out.write(base64.b64decode(f["data"]))
        return path

    def save_backup(self, path):
        data = base64.b64decode(self.call("backup_data", timeout=300))
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    def restore_from_file(self, path):
        if not os.path.isfile(path):
            raise AppError("الملف مش موجود")
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        self.call("restore_backup", data_b64=data, timeout=300)
        self.token = self.me = None
