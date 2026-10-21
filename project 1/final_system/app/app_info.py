"""بيانات البرنامج + أماكن الملفات (شغالة سواء من .py أو من .exe)."""
import os
import sys

APP_NAME = "SUITES"                 # غيّره لاسم البراند لما تختاره (وغيّره كمان فى installer.iss)
APP_SUBTITLE = "نظام إدارة مصانع البدل"
APP_VERSION = "1.0.0"
# بياناتك إنت (اللى بتبيع البرنامج): بتظهر للعميل فى شاشة التفعيل والتجديد
SELLER_NAME = "م. محمود — MYTECH Solutions"
SELLER_PHONE = "01033603385"
COMPANY = "MYTECH Solutions"
APP_ID = "TailorMaster"                    # اسم الفولدر اللى البيانات بتتحفظ فيه — متغيّروش بعد البيع


# شغّال من exe (PyInstaller بيحط sys.frozen، و Nuitka بيحط __compiled__)
FROZEN = bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def app_folder() -> str:
    if FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def data_dir() -> str:
    """فولدر بيانات البرنامج على الجهاز (مش جوه فولدر التثبيت، عشان التحديث ميمسحهاش)."""
    base = os.environ.get("TM_DATA_DIR") or os.environ.get("LOCALAPPDATA") or \
        os.path.join(os.path.expanduser("~"), ".local", "share")
    path = base if os.environ.get("TM_DATA_DIR") else os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


def server_data_dir() -> str:
    """قاعدة البيانات والنسخ الاحتياطية (على جهاز السيرفر بس)."""
    path = os.path.join(data_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path
