"""تشغيل السيرفر أوتوماتيك مع ويندوز (من غير صلاحيات Administrator)."""

import sys

from app_info import FROZEN

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "TailorMasterServer"


def supported() -> bool:
    return sys.platform == "win32" and FROZEN


def _command():
    return f'"{sys.executable}" --tray'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool):
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, VALUE)
            except OSError:
                pass
