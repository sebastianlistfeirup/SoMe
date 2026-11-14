"""Texture generation for the Blender scenes. Runs in the normal Python (Pillow); Blender only loads the PNGs.

    python scripts/blender/pp_textures.py      # writes every texture the scenes use
"""

import os
import random
import tempfile

TEX_DIR = os.path.join(tempfile.gettempdir(), "pp_textures")
os.makedirs(TEX_DIR, exist_ok=True)


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # inside Blender: textures must be pre-generated
        raise RuntimeError("run scripts/blender/pp_textures.py first (texture missing)") from exc
    return Image, ImageDraw, ImageFont


def pcb_texture(name, size_px=(2048, 2048), base=(18, 70, 52), trace=(30, 104, 76), seed=1, dark=False, silk=True):
    """Solder-mask PCB with routed traces, vias, pads and silkscreen boxes."""
    path = os.path.join(TEX_DIR, f"{name}.png")
    if os.path.exists(path):
        return path
    Image, ImageDraw, ImageFont = _pil()
    rng = random.Random(seed)
    w, h = size_px
    img = Image.new("RGB", size_px, base)
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x, y = rng.randrange(w), rng.randrange(h)
        pts = [(x, y)]
        for _ in range(rng.randint(2, 6)):
            if rng.random() < 0.5:
                x += rng.choice([-1, 1]) * rng.randint(20, 240)
            else:
                y += rng.choice([-1, 1]) * rng.randint(20, 240)
            if rng.random() < 0.3:
                k = rng.randint(10, 60)
                x += rng.choice([-1, 1]) * k
                y += rng.choice([-1, 1]) * k
            pts.append((x, y))
        d.line(pts, fill=trace, width=rng.choice([2, 2, 3, 4, 6]))
        if rng.random() < 0.5:
            r = rng.randint(4, 7)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(150, 150, 140) if not dark else (90, 90, 90))
    for _ in range(2500):
        x, y = rng.randrange(w), rng.randrange(h)
        r = rng.choice([2, 3, 3, 4])
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(min(255, c + 25) for c in trace))
    if silk:
        silk_col = (225, 228, 222)
        for _ in range(90):
            x, y = rng.randrange(w - 80), rng.randrange(h - 60)
            bw, bh = rng.randint(14, 80), rng.randint(8, 50)
            d.rectangle([x, y, x + bw, y + bh], outline=silk_col, width=2)
            if rng.random() < 0.6:
                d.text((x, y - 14), rng.choice(["C", "R", "U", "L", "Q", "J"]) + str(rng.randint(1, 499)), fill=silk_col)
    img.save(path)
    return path


def label_texture(name, lines, size_px=(1024, 300), bg=(20, 20, 22), fg=(230, 230, 230), accent=None):
    path = os.path.join(TEX_DIR, f"{name}.png")
    if os.path.exists(path):
        return path
    Image, ImageDraw, ImageFont = _pil()
    img = Image.new("RGB", size_px, bg)
    d = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("arialbd.ttf", int(size_px[1] * 0.26))
        font_small = ImageFont.truetype("arial.ttf", int(size_px[1] * 0.11))
    except OSError:
        font_big = font_small = ImageFont.load_default()
    y = int(size_px[1] * 0.12)
    for index, line in enumerate(lines):
        font = font_big if index == 0 else font_small
        d.text((int(size_px[0] * 0.06), y), line, fill=fg, font=font)
        y += int(size_px[1] * (0.34 if index == 0 else 0.15))
    if accent:
        d.rectangle([0, size_px[1] - int(size_px[1] * 0.08), size_px[0], size_px[1]], fill=accent)
    img.save(path)
    return path


def chip_marking_texture(name, text, size_px=(512, 512)):
    path = os.path.join(TEX_DIR, f"{name}.png")
    if os.path.exists(path):
        return path
    Image, ImageDraw, ImageFont = _pil()
    img = Image.new("RGB", size_px, (6, 6, 7))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", int(size_px[1] * 0.11))
    except OSError:
        font = ImageFont.load_default()
    for index, line in enumerate(text.split("\n")):
        d.text((int(size_px[0] * 0.1), int(size_px[1] * (0.3 + index * 0.16))), line, fill=(70, 70, 72), font=font)
    d.ellipse([int(size_px[0] * 0.07), int(size_px[1] * 0.07), int(size_px[0] * 0.14), int(size_px[1] * 0.14)], fill=(30, 30, 32))
    img.save(path)
    return path


def contacts_texture(name, count, size_px=(4096, 128), gap_ratio=0.35):
    """Gold edge-connector fingers on PCB."""
    path = os.path.join(TEX_DIR, f"{name}.png")
    if os.path.exists(path):
        return path
    Image, ImageDraw, ImageFont = _pil()
    img = Image.new("RGB", size_px, (16, 60, 44))
    d = ImageDraw.Draw(img)
    pitch = size_px[0] / count
    for i in range(count):
        x = i * pitch
        d.rectangle([x + pitch * gap_ratio / 2, 0, x + pitch * (1 - gap_ratio / 2), size_px[1]], fill=(232, 178, 84))
    img.save(path)
    return path




def generate_all() -> list[str]:
    """Every texture the scenes load. Keep names/arguments identical to the calls in pp_lib and the scenes."""
    made = [
        pcb_texture("ram_pcb", seed=7),
        contacts_texture("ram_contacts_69", 130),
        contacts_texture("ram_contacts_133", 130),
        chip_marking_texture("ram_chip", "D8BPK\nM16G 4C3A\n2547"),
        pcb_texture("ssd_pcb", base=(12, 12, 14), trace=(26, 26, 30), seed=3, dark=True),
        contacts_texture("m2_contacts", 67),
        label_texture("ssd_label", ["NVMe SSD", "2 TB · PCIe 4.0 x4 · M.2 2280", "S/N 7F42C19A0D · Made in TW"], size_px=(1400, 380), bg=(18, 18, 20), fg=(225, 228, 232), accent=(0, 170, 210)),
        pcb_texture("mini_board", base=(20, 74, 60), trace=(34, 104, 84), seed=11),
        pcb_texture("laptop_board", base=(10, 14, 22), trace=(22, 30, 44), seed=21, dark=True),
        pcb_texture("desktop_board", base=(9, 10, 12), trace=(22, 24, 28), seed=31, dark=True),
        chip_marking_texture("cpu_die", "AI 9 HX\n100-000001\n2546 SUS"),
        chip_marking_texture("gpu_die", "GN22-X6\nA1 2544\nTAIWAN"),
        label_texture("battery_label", ["Li-ion Battery", "15.48V · 4840mAh · 75Wh", "Do not puncture · Recycle properly"], size_px=(1600, 420), bg=(14, 14, 16), fg=(200, 202, 206)),
        label_texture("ihs_mark", ["", "", ""], size_px=(512, 512), bg=(196, 198, 202), fg=(150, 152, 156)),
    ]
    return made


if __name__ == "__main__":
    for path in generate_all():
        print(path)
