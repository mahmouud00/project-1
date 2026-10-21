"""
main.py — تشغيل البرنامج
   python main.py          ← البرنامج العادى
   python main.py --tray   ← السيرفر بس جنب الساعة (بيتشغل كده مع ويندوز لو فعّلتها من الإعدادات)
"""

import os
import sys

# السيرفر والواجهة فى نفس الفولدر
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def set_windows_taskbar_id():
    """من غيرها ويندوز بيحط أيقونة بايثون فى شريط المهام بدل أيقونة البرنامج."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TailorMaster.Desktop")
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    set_windows_taskbar_id()
    from qt_main import AppController
    return AppController(tray_only="--tray" in sys.argv).run()


if __name__ == "__main__":
    sys.exit(main())
