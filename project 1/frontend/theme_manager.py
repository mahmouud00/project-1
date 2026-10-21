import sys
import platform
from PySide6.QtGui import QPalette, QColor

def get_theme_palette(theme_name):
    # كشف الوضع التلقائي للنظام
    if theme_name == "System Adaptive":
        theme_name = "Dark Mode" if is_windows_dark_mode() else "Odoo Soft"

    palette = QPalette()

    if theme_name == "Odoo Soft":
        # ألوان أودو الكلاسيكية: أبيض، رمادي فاتح، أزرق هادئ
        palette.setColor(QPalette.Window, QColor("#F8F9FA"))
        palette.setColor(QPalette.WindowText, QColor("#212529"))
        palette.setColor(QPalette.Base, QColor("#FFFFFF"))
        palette.setColor(QPalette.AlternateBase, QColor("#E9ECEF"))
        palette.setColor(QPalette.Button, QColor("#FFFFFF"))
        palette.setColor(QPalette.ButtonText, QColor("#343A40"))
        palette.setColor(QPalette.Highlight, QColor("#714B67")) # لون أودو المميز

    elif theme_name == "Navy & Amber":
        # ألوان داكنة فخمة: أزرق كحلي وبرتقالي غامق
        palette.setColor(QPalette.Window, QColor("#E9ECEF"))
        palette.setColor(QPalette.WindowText, QColor("#1A237E"))
        palette.setColor(QPalette.Base, QColor("#FFFFFF"))
        palette.setColor(QPalette.Button, QColor("#1A237E"))
        palette.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Highlight, QColor("#FF6D00"))

    elif theme_name == "Dark Mode":
        # وضع داكن مريح للعين
        palette.setColor(QPalette.Window, QColor("#121212"))
        palette.setColor(QPalette.WindowText, QColor("#E0E0E0"))
        palette.setColor(QPalette.Base, QColor("#1E1E1E"))
        palette.setColor(QPalette.Button, QColor("#1E1E1E"))
        palette.setColor(QPalette.ButtonText, QColor("#E0E0E0"))
        palette.setColor(QPalette.Highlight, QColor("#BB86FC"))

    return palette

def is_windows_dark_mode():
    if platform.system() == "Windows":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
        except:
            return False
    return False
