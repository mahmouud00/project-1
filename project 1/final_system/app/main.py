"""
main.py — تشغيل البرنامج
   python main.py          ← البرنامج العادى
   python main.py --tray   ← السيرفر بس جنب الساعة (بيتشغل كده مع ويندوز لو فعّلتها من الإعدادات)
   TailorMaster.exe --selftest  ← بيتأكد إن الـ exe فيه كل حاجة (بيستخدمه الـ build) وبيكتب النتيجة فى ملف
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


def selftest() -> int:
    """بيشغّل كل أجزاء البرنامج من غير شاشة: لو حاجة ناقصة فى الـ exe بتبان هنا قبل ما توصل للعميل."""
    import tempfile
    import traceback
    out = os.path.join(tempfile.gettempdir(), "tailormaster_selftest.txt")
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["TM_DATA_DIR"] = tempfile.mkdtemp()
        from PySide6.QtWidgets import QApplication
        QApplication(sys.argv)
        import qt_main  # noqa: F401  (كل الصفحات)
        import printing  # noqa: F401
        from server import licensing
        from server.service import Service
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not licensing.public_key_ready():
            raise RuntimeError("المفتاح العام مش موجود فى license_key.py")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(licensing.PUBLIC_KEY_HEX))
        svc = Service(os.environ["TM_DATA_DIR"], "selftest")
        status = svc.call("status")
        svc.close()
        result = f"OK machine={status['license']['machine']}"
        code = 0
    except Exception:  # noqa: BLE001
        result = "FAIL\n" + traceback.format_exc()
        code = 1
    with open(out, "w", encoding="utf-8") as f:
        f.write(result)
    return code


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    set_windows_taskbar_id()
    from qt_main import AppController
    return AppController(tray_only="--tray" in sys.argv).run()


if __name__ == "__main__":
    sys.exit(main())
