#!/usr/bin/env python3
"""Make the app icon (icon.png, icon.ico) from a Lucide icon on a rounded dark square.
Run once and commit the results; builds don't need ImageMagick. Needs `magick` + Pillow."""
import io
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
LUCIDE = HERE / "clipboard-list.svg"
SIZE = 512

svg = LUCIDE.read_text().replace("currentColor", "#FFFFFF").replace('stroke-width="2"', 'stroke-width="1.6"')
glyph = Image.open(io.BytesIO(subprocess.run(
    ["magick", "-background", "none", "-density", "2400", "svg:-", "-resize", f"{int(SIZE * .56)}x{int(SIZE * .56)}", "png:-"],
    input=svg.encode(), capture_output=True, check=True).stdout)).convert("RGBA")

bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
ImageDraw.Draw(bg).rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=96, fill="#4F4F4F")
bg.alpha_composite(glyph, ((SIZE - glyph.width) // 2, (SIZE - glyph.height) // 2))
bg.resize((256, 256), Image.LANCZOS).save(HERE / "icon.png")
bg.save(HERE / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.png, icon.ico written")
