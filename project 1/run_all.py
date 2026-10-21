import subprocess
import time
import sys
import os

def run():
    # المسارات الصحيحة للملفات
    backend_path = os.path.join("backend", "main.py")
    frontend_path = os.path.join("frontend", "main.py")

    print("--- جاري تشغيل نظام ERP بالكامل ---")

    # 1. تشغيل الخلفية (Backend) في عملية منفصلة
    print("جاري تشغيل خادم الخلفية (Backend)...")
    backend_proc = subprocess.Popen([sys.executable, backend_path])

    # انتظار بسيط لضمان عمل الخادم
    time.sleep(3)

    # 2. تشغيل الواجهة (Frontend)
    print("جاري تشغيل واجهة المستخدم...")
    frontend_proc = subprocess.Popen([sys.executable, frontend_path])

    try:
        # انتظار الواجهة حتى تغلقها أنت
        frontend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        # إغلاق الخلفية عند إغلاق الواجهة
        print("--- جاري إغلاق النظام ---")
        backend_proc.terminate()

if __name__ == "__main__":
    run()
