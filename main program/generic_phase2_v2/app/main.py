"""
main.py — تشغيل البرنامج
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app_config import SUPABASE_URL, SUPABASE_KEY
from backend import Backend
from qt_main import AppController


def set_windows_taskbar_id():
    """من غيرها ويندوز بيحط أيقونة بايثون فى شريط المهام بدل أيقونة البرنامج."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Workshop.Manager.Desktop")
        except Exception:
            pass


def main() -> int:
    set_windows_taskbar_id()
    qt = QApplication.instance() or QApplication(sys.argv)
    if "PUT-YOUR" in SUPABASE_URL or "PUT-YOUR" in SUPABASE_KEY:
        QMessageBox.critical(None, "الإعدادات ناقصة",
                             "افتح ملف app_config.py وحط فيه Project URL والمفتاح (publishable أو anon) "
                             "من مشروعك على Supabase.")
        return 1
    try:
        backend = Backend(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, "خطأ فى الاتصال",
                             f"مش قادر أجهّز الاتصال بـ Supabase.\nاتأكد من البيانات فى app_config.py\n\n{e}")
        return 1
    return AppController(backend).run()


if __name__ == "__main__":
    sys.exit(main())
