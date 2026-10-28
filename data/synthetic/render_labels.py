"""Draws synthetic medicine packaging for testing the LABEL CHECK with the live reader (C4).

    python data/synthetic/render_labels.py     # writes data/synthetic/rendered/labels/*.png

Everything is fictional. Three kinds of picture: a strip with printed text, a box with a brand and ingredient, and a loose pill with no
text at all (the live reader must answer "cannot read", never guess)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "rendered" / "labels"
FONTS = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size: int):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


def strip(name: str, lines: list[str]) -> None:
    img = Image.new("RGB", (1000, 560), (205, 208, 214))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, 940, 500), radius=28, fill=(236, 238, 242), outline=(150, 155, 165), width=4)
    for i in range(6):                                                   # blister pockets
        d.ellipse((100 + i * 140, 360, 200 + i * 140, 460), fill=(250, 250, 252), outline=(160, 165, 175), width=3)
    y = 90
    for i, ln in enumerate(lines):
        d.text((100, y), ln, fill=(20, 40, 90), font=font(46 if i == 0 else 30))
        y += 62 if i == 0 else 42
    img.save(OUT / f"{name}.png")


def box(name: str, brand: str, lines: list[str]) -> None:
    img = Image.new("RGB", (900, 600), (90, 120, 150))
    d = ImageDraw.Draw(img)
    d.rectangle((70, 70, 830, 530), fill=(245, 245, 240), outline=(30, 50, 80), width=6)
    d.rectangle((70, 70, 830, 180), fill=(30, 90, 140))
    d.text((110, 98), brand, fill=(255, 255, 255), font=font(56))
    y = 215
    for ln in lines:
        d.text((110, y), ln, fill=(30, 30, 40), font=font(32))
        y += 48
    img.save(OUT / f"{name}.png")


def loose_pill() -> None:
    img = Image.new("RGB", (800, 500), (225, 220, 205))
    d = ImageDraw.Draw(img)
    d.ellipse((290, 150, 510, 330), fill=(245, 245, 245), outline=(190, 190, 190), width=4)
    d.line((300, 240, 500, 240), fill=(200, 200, 200), width=4)
    img.save(OUT / "loose_pill.png")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    strip("strip_amlodipine_5", ["Amlodipine Tablets IP", "5 mg", "Batch B2231   Mfg 02/2026   Exp 01/2028", "SYNTHETIC - FICTIONAL"])
    strip("strip_amlodipine_10", ["Amlodipine Tablets IP", "10 mg", "Batch B9910   Exp 06/2027", "SYNTHETIC - FICTIONAL"])
    box("box_amoxicillin", "AMOXYLONG", ["Amoxicillin Capsules 500 mg", "10 capsules   Batch A771   Exp 09/2027", "SYNTHETIC - FICTIONAL"])
    box("box_ibuprofen", "PAINEZ 400", ["Ibuprofen Tablets IP 400 mg", "Batch P118   Exp 11/2027", "SYNTHETIC - FICTIONAL"])
    loose_pill()
    print(f"drew 5 label pictures into {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
