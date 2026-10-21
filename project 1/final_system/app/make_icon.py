"""
make_icon.py
------------
بيعمل لوجو مؤقت (assets/logo.png) لو مش موجود، وبيعمل أيقونة البرنامج (assets/app.ico) منه.
لو عندك لوجو البراند: حطه مكان assets/logo.png (PNG مربع بخلفية شفافة) وشغّل:
    python make_icon.py
وبعدين اعمل build تانى. محتاج مكتبة Pillow:  python -m pip install pillow
"""
import os
import sys

# شاشة ويندوز القديمة مش بتعرف تطبع العربى والإيموجى ← منغير ما البرنامج يقع
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "assets", "logo.png")
BRAND = (113, 75, 103, 255)      # نفس لون البرنامج
GOLD = (234, 179, 8, 255)
WHITE = (255, 255, 255, 255)


def draw_default_logo(path, size=512):
    """شماعة عليها جاكيت — لوجو مؤقت لحد ما تختار لوجو البراند."""
    s = size / 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(110 * s), fill=BRAND)
    w = int(18 * s)
    # الشماعة
    d.arc([226 * s, 70 * s, 286 * s, 130 * s], start=180, end=90, fill=WHITE, width=w)
    d.line([256 * s, 128 * s, 256 * s, 150 * s], fill=WHITE, width=w)
    d.line([256 * s, 150 * s, 110 * s, 230 * s], fill=WHITE, width=w)
    d.line([256 * s, 150 * s, 402 * s, 230 * s], fill=WHITE, width=w)
    # الجاكيت
    jacket = [(140 * s, 220 * s), (210 * s, 190 * s), (256 * s, 300 * s), (302 * s, 190 * s), (372 * s, 220 * s),
              (392 * s, 440 * s), (120 * s, 440 * s)]
    d.polygon(jacket, fill=WHITE)
    # الياقة (V) والزراير
    d.polygon([(210 * s, 190 * s), (256 * s, 300 * s), (232 * s, 330 * s), (196 * s, 240 * s)], fill=BRAND)
    d.polygon([(302 * s, 190 * s), (256 * s, 300 * s), (280 * s, 330 * s), (316 * s, 240 * s)], fill=BRAND)
    d.line([256 * s, 300 * s, 256 * s, 440 * s], fill=BRAND, width=int(6 * s))
    for y in (350, 395):
        d.ellipse([244 * s, (y - 10) * s, 268 * s, (y + 14) * s], fill=GOLD)
    img.save(path)


def main():
    if not os.path.exists(LOGO) or "--new-logo" in sys.argv:
        draw_default_logo(LOGO)
        print("✅ اتعمل لوجو مؤقت: assets/logo.png")
    src = Image.open(LOGO).convert("RGBA")
    logo = src.crop(src.getbbox())
    size = 512
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    scale = min(size / logo.width, size / logo.height)
    w, h = int(logo.width * scale), int(logo.height * scale)
    icon.alpha_composite(logo.resize((w, h), Image.LANCZOS), ((size - w) // 2, (size - h) // 2))
    icon.save(os.path.join(HERE, "assets", "app_icon.png"))
    icon.save(os.path.join(HERE, "assets", "app.ico"),
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("✅ اتعملت assets/app.ico")


if __name__ == "__main__":
    main()
