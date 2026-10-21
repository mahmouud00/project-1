"""
make_icon.py
------------
بيعمل أيقونة البرنامج (assets/app.ico) من اللوجو (assets/logo.png).
لو عندك اللوجو بجودة أعلى: حطه مكان assets/logo.png (PNG بخلفية شفافة)
وشغّل:  python make_icon.py   وبعدين اعمل build تانى.
محتاج مكتبة Pillow:  python -m pip install pillow
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
src = Image.open(os.path.join(HERE, "assets", "logo.png")).convert("RGBA")
logo = src.crop(src.getbbox())

SIZE, PAD = 512, 40
icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=96, fill=255)
icon.paste(Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255)), (0, 0), mask)
w = SIZE - 2 * PAD
h = int(logo.height * w / logo.width)
icon.alpha_composite(logo.resize((w, h), Image.LANCZOS), (PAD, (SIZE - h) // 2))
icon.save(os.path.join(HERE, "assets", "app_icon.png"))
icon.save(os.path.join(HERE, "assets", "app.ico"),
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("✅ اتعملت assets/app.ico")
