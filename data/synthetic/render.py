"""Turns the synthetic text documents into PNG photos and PDFs for testing the LIVE reader (images and PDFs need Muse Spark).

    python data/synthetic/render.py            # writes data/synthetic/rendered/<id>.png, <id>_photo.png and <id>.pdf

Fixed random seeds make the output repeatable. The "photo" variants add a tilt, an uneven shadow, blur and noise to mimic a phone
picture of a paper. Every page keeps the SYNTHETIC marker line from the source text. Requires Pillow (a dev dependency)."""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "rendered"
W, H, MARGIN, LINE = 1240, 1754, 90, 44           # roughly A4 at 150 dpi
PAPER, INK = (246, 242, 233), (24, 28, 36)

FONTS = ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/Library/Fonts/Courier New.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


def page_image(lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f, small = font(30), font(22)
    y = MARGIN
    for i, ln in enumerate(lines):
        is_marker = ln.startswith("SYNTHETIC")
        d.text((MARGIN, y), ln, fill=(150, 40, 30) if is_marker else INK, font=small if is_marker else f)
        y += LINE if i else LINE + 6
        if i == 1:
            d.line([(MARGIN, y - 8), (W - MARGIN, y - 8)], fill=(170, 165, 150), width=2)
    return img


def photo(img: Image.Image, seed: int) -> Image.Image:
    """Tilt, uneven light, blur and noise, with a fixed seed."""
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W + 240, H + 240), (58, 54, 50))
    bg.paste(img.rotate(rnd.uniform(-3.5, 3.5), expand=True, fillcolor=PAPER, resample=Image.BICUBIC), (rnd.randint(40, 120), rnd.randint(40, 120)))
    shade = Image.linear_gradient("L").resize(bg.size).rotate(rnd.choice([0, 90, 180, 270]))
    dark = Image.new("RGB", bg.size, (0, 0, 0))
    bg = Image.composite(dark, bg, shade.point(lambda v: int(v * 0.35)))
    bg = bg.filter(ImageFilter.GaussianBlur(rnd.uniform(0.6, 1.4)))
    px = bg.load()
    for _ in range(bg.size[0] * bg.size[1] // 40):
        x, y = rnd.randrange(bg.size[0]), rnd.randrange(bg.size[1])
        r, g, b = px[x, y]
        n = rnd.randint(-18, 18)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return bg.resize((W, int(bg.size[1] * W / bg.size[0])))


def main() -> int:
    OUT.mkdir(exist_ok=True)
    count = 0
    for txt in sorted(ROOT.glob("*/docs/*.txt")):
        doc_id = txt.stem.split("_")[0]
        pages = [[ln for ln in chunk.splitlines() if ln.strip()] for chunk in txt.read_text(encoding="utf-8").split("\f")]
        imgs = [page_image(p) for p in pages]
        imgs[0].save(OUT / f"{doc_id}.png")
        photo(imgs[0], seed=sum(map(ord, doc_id))).save(OUT / f"{doc_id}_photo.png")
        imgs[0].save(OUT / f"{doc_id}.pdf", save_all=True, append_images=imgs[1:], resolution=150.0)
        count += 1
    print(f"rendered {count} documents into {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
