"""
keygen.py — بيتشغل مرة واحدة بس فى العمر
-----------------------------------------
بيعمل زوج مفاتيح التراخيص:
  - seller_private_key.pem  ← السرى: عندك إنت بس. اعمله نسخة على فلاشة + Google Drive.
                               لو ضاع: مش هتقدر تجدد للعملاء اللى اشتروا قبل كده.
                               لو اتسرق: أى حد يقدر يعمل تراخيص لبرنامجك.
  - المفتاح العام             ← بيتكتب أوتوماتيك فى app/server/license_key.py جوه البرنامج.

التشغيل (من فولدر final_system):   python license_tool/keygen.py
"""

import os
import re
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE = os.path.join(HERE, "seller_private_key.pem")
KEY_FILE = os.path.join(os.path.dirname(HERE), "app", "server", "license_key.py")


def main():
    if os.path.exists(PRIVATE):
        print("⚠️ المفتاح السرى موجود بالفعل:", PRIVATE)
        print("   مش هعمل واحد جديد (لو عملت، كل التراخيص القديمة هتبطل).")
        return 1
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    public_hex = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    with open(PRIVATE, "wb") as f:
        f.write(pem)
    with open(KEY_FILE, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'PUBLIC_KEY_HEX = ".*"', f'PUBLIC_KEY_HEX = "{public_hex}"', text)
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print("✅ اتعمل المفتاح السرى:", PRIVATE)
    print("✅ اتكتب المفتاح العام فى:", KEY_FILE)
    print()
    print("مهم جدًا:")
    print(" 1) اعمل نسخة من seller_private_key.pem على فلاشة وعلى Google Drive.")
    print(" 2) متبعتوش لحد ومترفعوش على GitHub (الـ .gitignore بيمنعه).")
    print(" 3) اعمل build للبرنامج من جديد عشان المفتاح العام يدخل جوه الـ Setup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
