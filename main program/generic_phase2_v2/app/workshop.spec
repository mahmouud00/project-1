# -*- mode: python ; coding: utf-8 -*-
# وصفة PyInstaller: بتحوّل البرنامج لفولدر فيه WintagAccounts.exe
# بتتشغل من build.bat - مش محتاج تلمسها.
import os
import sys
from PyInstaller.utils.hooks import collect_all

# مكتبة cryptography (اللى جوجل بتستخدمها فى تسجيل الدخول) - بناخدها كاملة
try:
    crypto_datas, crypto_binaries, crypto_hidden = collect_all('cryptography')
except Exception:
    crypto_datas, crypto_binaries, crypto_hidden = [], [], []

# الجزء _rust فى cryptography محتاج python3.dll، و PyInstaller ساعات بينساه
# فبيطلع خطأ "DLL load failed while importing _rust" - فبنضيفه بإيدينا
extra_binaries = []
for dll in ('python3.dll',):
    path = os.path.join(sys.base_prefix, dll)
    if os.path.exists(path):
        extra_binaries.append((path, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=extra_binaries + crypto_binaries,
    datas=[('assets', 'assets')] + crypto_datas,     # اللوجو والأيقونة
    hiddenimports=crypto_hidden + ['supabase', 'postgrest', 'storage3'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtMultimedia', 'PySide6.Qt3DCore', 'PySide6.QtCharts'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WorkshopManager',
    debug=False,
    strip=False,
    upx=False,
    console=False,                         # من غير الشاشة السودا
    icon='assets/app.ico',
    version='file_version_info.txt',       # البيانات اللى بتظهر فى Properties
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='WorkshopManager')
