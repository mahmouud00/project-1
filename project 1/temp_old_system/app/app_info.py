"""بيانات البرنامج + أماكن الملفات (شغالة سواء من .py أو من .exe)."""
import os
import sys

APP_NAME = "نظام إدارة الورش"     # غيّره لاسم البراند لما تختاره
APP_VERSION = "0.1.0"


def app_folder() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
