"""Handheld graphics from content/HANDHELDS.json + official product images (assets/brand/handhelds/).

  handhelds/lineup-<fmt>.png                  all models: product image, maker logo, name
  handhelds/specs-<fmt>.png                   spec sheet for every model
  handhelds/ranking-<fmt>[-transparent].png   ranked by Notebookcheck score
  handhelds/<id>-<fmt>.png                    one per model: device left (top on 9:16), specs right (below)

    python scripts/blender/compose_handhelds.py
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_ai_cards as cards  # noqa: E402

ROOT = cards.ROOT
OUT = cards.GFX.parent / "handhelds"
PHOTOS = ROOT / "assets" / "brand" / "handhelds"
LOGOS = ROOT / "assets" / "brand" / "handheld-logos"
DATA = json.loads((ROOT / "content" / "HANDHELDS.json").read_text(encoding="utf-8"))
MAKER_LOGO = {"Valve": "valve", "ASUS": "rog", "MSI": "msi", "Lenovo": "legion", "AYANEO": "ayaneo", "AMD": "amd", "Intel": "intel"}
CYAN, CORAL, WHITE, MUTED, NAVY = cards.CYAN, (242, 92, 60), cards.WHITE, cards.MUTED, cards.NAVY
SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def bold(size):
    return cards.bold(size)


def text_font(size):
    return cards.font(cards.FONT_TEXT, size)


def text_bold(size):
    return cards.font(cards.FONT_TEXT_BOLD, size)


def geometry(size):
    w, h = size
    portrait = h > w
    return w, h, portrait, (w / 1080) if portrait else (w / 1920)


def save(canvas, name, keep_alpha=False):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    (canvas if keep_alpha else canvas.convert("RGB")).save(path, optimize=True)
    return path


def stage(size, accent=CYAN, focus=(0.5, 0.45), floor=0.72):
    """Dark studio: gradient, soft spotlight, faint pixel grid, glossy floor band."""
    w, h = size
    y = np.linspace(0, 1, h)[:, None]
    base = np.zeros((h, w, 3), dtype=np.float32)
    top, bottom = np.array([8, 14, 32]), np.array([2, 4, 11])
    base[:] = (top * (1 - y) + bottom * y)[:, :, :] if False else (top[None, None, :] * (1 - y[..., None]) + bottom[None, None, :] * y[..., None])
    canvas = Image.fromarray(base.clip(0, 255).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    fx, fy = focus[0] * w, focus[1] * h
    r = max(w, h) * 0.34
    gd.ellipse([fx - r, fy - r * 0.75, fx + r, fy + r * 0.75], fill=accent + (70,))
    gd.ellipse([fx - r * 0.45, fy - r * 0.32, fx + r * 0.45, fy + r * 0.32], fill=(255, 255, 255, 26))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r * 0.35)))
    # floor band with a thin horizon highlight
    fl = Image.new("RGBA", size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    fy0 = int(h * floor)
    for i in range(h - fy0):
        fd.line([(0, fy0 + i), (w, fy0 + i)], fill=(14, 24, 48, int(120 * (1 - i / (h - fy0)) ** 1.5)))
    fd.line([(w * 0.08, fy0), (w * 0.92, fy0)], fill=accent + (90,), width=2)
    canvas.alpha_composite(fl.filter(ImageFilter.GaussianBlur(2)))
    # pixel grid (brand squares), fading out from the focus
    grid = Image.new("L", size, 0)
    gdraw = ImageDraw.Draw(grid)
    step = int(54 * (w / 1920 if w > h else w / 1080))
    for gx in range(0, w, step):
        for gy in range(0, int(h * floor), step):
            gdraw.rectangle([gx, gy, gx + 3, gy + 3], fill=255)
    yy, xx = np.mgrid[0:h, 0:w]
    fade = np.clip(1 - np.hypot((xx - fx) / (w * 0.6), (yy - fy) / (h * 0.6)), 0, 1)
    alpha = (np.asarray(grid, dtype=np.float32) * fade * 0.07).astype(np.uint8)
    dots = Image.new("RGBA", size, WHITE + (0,))
    dots.putalpha(Image.fromarray(alpha))
    canvas.alpha_composite(dots)
    return canvas


def photo(item):
    return Image.open(PHOTOS / f"{item['id']}.png").convert("RGBA")


def place_device(canvas, item, box, reflection=True, shadow=True, align="bottom"):
    """Fit the product image into box (x0, y0, x1, y1), with contact shadow and a fading floor reflection."""
    x0, y0, x1, y1 = box
    img = photo(item)
    scale = min((x1 - x0) / img.width, (y1 - y0) / img.height)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    px = int(x0 + (x1 - x0 - img.width) / 2)
    py = int(y1 - img.height) if align == "bottom" else int(y0 + (y1 - y0 - img.height) / 2)
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([px + img.width * 0.08, py + img.height - img.height * 0.06, px + img.width * 0.92, py + img.height + img.height * 0.08], fill=(0, 0, 0, 170))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(img.height * 0.06 + 2)))
    if reflection:
        ref = img.transpose(Image.FLIP_TOP_BOTTOM)
        fade = np.linspace(0.28, 0, ref.height)[:, None]
        a = np.asarray(ref.getchannel("A"), dtype=np.float32) * fade
        ref.putalpha(Image.fromarray(a.astype(np.uint8)))
        canvas.alpha_composite(ref.filter(ImageFilter.GaussianBlur(1.5)), (px, py + img.height + 2))
    canvas.alpha_composite(img, (px, py))
    return (px, py, px + img.width, py + img.height)


def logo_chip(canvas, maker, x, y, height, anchor="l"):
    """White rounded chip with the maker logo (wordmarks need width, so the chip follows the logo's aspect)."""
    logo = Image.open(LOGOS / f"{MAKER_LOGO[maker]}.png").convert("RGBA")
    aspect = logo.width / logo.height
    inner_h = height * (0.82 if aspect < 1.8 else 0.56)  # near-square marks (ROG eye) need more height
    lw = logo.width * inner_h / logo.height
    width = max(height * 1.6, min(lw + height * 0.7, height * 4.2))
    if lw > width - height * 0.5:
        inner_h *= (width - height * 0.5) / lw
        lw = width - height * 0.5
    logo = logo.resize((max(1, int(lw)), max(1, int(inner_h))), Image.LANCZOS)
    x0 = x - width if anchor == "r" else (x - width / 2 if anchor == "m" else x)
    chip = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle([0, 0, chip.width - 1, chip.height - 1], radius=int(height * 0.28), fill=(246, 249, 252, 255))
    chip.alpha_composite(logo, ((chip.width - logo.width) // 2, (chip.height - logo.height) // 2))
    canvas.alpha_composite(chip, (int(x0), int(y)))
    return (x0, y, x0 + width, y + height)


def full_name(item):
    return item["name"] + (f" ({item['variant']})" if item.get("variant") else "")


def price_text(item):
    if item.get("price_eur") is not None:
        return f"€{item['price_eur']:,}"
    return f"${item['price_usd']:,}"


def weight_text(item):
    if not item.get("weight_g"):
        return "—"
    return ("~" if item.get("weight_approx") else "") + f"{item['weight_g']:,} g"


def spec_rows(item):
    ram_main, _, ram_sub = item["ram"].partition(" GB")
    ram_main, ram_sub = ram_main + " GB", ram_sub.strip()
    chip = item["chip"].replace("AMD ", "").replace("Intel ", "")
    return [
        ("Chip", chip, item["cpu"]),
        ("Graphics", item["gpu"], ""),
        ("Memory", ram_main, ram_sub),
        ("Storage", item["storage"] or "—", ""),
        ("Display", item["display"], f"{item['resolution']} · {item['refresh']}"),
        ("Battery", f"{item['battery_wh']:g} Wh", ""),
        ("Weight", weight_text(item), ""),
        ("Price", price_text(item), "list price"),
    ]


def source_line(canvas, x, y, scale, label=None):
    if DATA.get("show_source", True):
        ImageDraw.Draw(canvas).text((x, y), label or DATA["source_label"], font=text_font(20 * scale), fill=MUTED + (255,))


def mixed_source_label():
    """Notebookcheck plus any maker-sourced specs, named by model."""
    extra = [f"{i['maker']} ({i['name']})" for i in DATA["handhelds"] if i.get("source_label")]
    return "Source: Notebookcheck reviews" + (" · " + ", ".join(extra) if extra else "") + " · Nov 2026"


def score_badge(canvas, x, y, score, scale, anchor="l"):
    if score is None:
        return (x, y, x, y)
    draw = ImageDraw.Draw(canvas)
    big = bold(64 * scale)
    text = f"{score}%"
    tw = draw.textlength(text, font=big)
    small = text_bold(17 * scale)
    lw = draw.textlength("NOTEBOOKCHECK", font=small)
    width = max(tw, lw) + 44 * scale
    height = 112 * scale
    x0 = x - width if anchor == "r" else x
    cards.frosted(canvas, (x0, y, x0 + width, y + height), int(20 * scale), alpha=200, outline=CORAL, width=max(2, int(3 * scale)))
    draw = ImageDraw.Draw(canvas)
    draw.text((x0 + width / 2, y + 12 * scale), text, font=big, fill=WHITE + (255,), anchor="mt")
    draw.text((x0 + width / 2, y + height - 16 * scale), "NOTEBOOKCHECK", font=small, fill=MUTED + (255,), anchor="mb")
    return (x0, y, x0 + width, y + height)


# --- per-device cards -------------------------------------------------------------------------------

def device_card(item, fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = geometry(size)
    canvas = stage(size, CYAN, focus=(0.5, 0.22) if portrait else (0.30, 0.46), floor=0.305 if portrait else 0.76)
    if portrait:
        place_device(canvas, item, (w * 0.08, h * 0.12, w * 0.92, h * 0.30))
        x = 64 * scale
        y = h * 0.355
        chip = logo_chip(canvas, item["maker"], x, y + (24 if item.get("score") else 0) * scale, 64 * scale)
        badge = score_badge(canvas, w * 0.86, y, item["score"], scale, anchor="r")
        draw = ImageDraw.Draw(canvas)
        name_font = cards.fit_font(draw, full_name(item), 78 * scale, w * 0.86 - x)
        name_y = max(chip[3], badge[3]) + 20 * scale
        draw.text((x, name_y), full_name(item), font=name_font, fill=WHITE + (255,))
        top = name_y + name_font.size * 1.3
        rows_area = (x, top, w * 0.86, h * 0.80)
    else:
        place_device(canvas, item, (w * 0.04, h * 0.20, w * 0.56, h * 0.74))
        x = w * 0.60
        y = h * 0.11
        chip = logo_chip(canvas, item["maker"], x, y + (21 if item.get("score") else 0) * scale, 70 * scale)
        badge = score_badge(canvas, w - 90 * scale, y, item["score"], scale, anchor="r")
        draw = ImageDraw.Draw(canvas)
        name_font = cards.fit_font(draw, full_name(item), 84 * scale, w - 90 * scale - x)
        name_y = max(chip[3], badge[3]) + 18 * scale
        draw.text((x, name_y), full_name(item), font=name_font, fill=WHITE + (255,))
        top = name_y + name_font.size * 1.3
        rows_area = (x, top, w - 90 * scale, h * 0.90)
    x0, y0, x1, y1 = rows_area
    rows = spec_rows(item)
    row_h = (y1 - y0) / len(rows)
    cards.frosted(canvas, (x0 - 24 * scale, y0 - 10 * scale, x1 + 4 * scale, y1 + 6 * scale), int(24 * scale), alpha=150)
    draw = ImageDraw.Draw(canvas)
    label_w = (210 if not portrait else 230) * scale
    for k, (label, main, sub) in enumerate(rows):
        ry = y0 + k * row_h
        if k:
            line = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(line).line([(x0, ry), (x1 - 20 * scale, ry)], fill=(255, 255, 255, 22), width=max(1, int(1.5 * scale)))
            canvas.alpha_composite(line)
            draw = ImageDraw.Draw(canvas)
        cy = ry + row_h / 2
        draw.text((x0 + 4 * scale, cy), label.upper(), font=text_bold(21 * scale), fill=CYAN + (255,), anchor="lm")
        mf = cards.fit_font(draw, main, 36 * scale, x1 - x0 - label_w - 30 * scale)
        if sub:
            draw.text((x0 + label_w, cy - 4 * scale), main, font=mf, fill=WHITE + (255,), anchor="ls")
            draw.text((x0 + label_w, cy + 6 * scale), sub, font=text_font(22 * scale), fill=MUTED + (255,), anchor="lt")
        else:
            draw.text((x0 + label_w, cy), main, font=mf, fill=WHITE + (255,), anchor="lm")
    source_line(canvas, 64 * scale if portrait else x0, h - (300 if portrait else 46) * scale, scale, item.get("source_label"))
    return save(canvas, f"{item['id']}-{fmt}.png")


# --- line-up -----------------------------------------------------------------------------------------

def lineup(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = geometry(size)
    canvas = stage(size, CYAN, focus=(0.5, 0.45), floor=0.97)
    items = DATA["handhelds"]
    cols = 3 if portrait else 4
    rows = (len(items) + cols - 1) // cols
    if portrait:
        left, top, right, bottom = 56 * scale, h * 0.12, w * 0.88, h * 0.78
    else:
        left, top, right, bottom = 90 * scale, 70 * scale, w - 90 * scale, h - 70 * scale
    gap = 22 * scale
    cw = (right - left - gap * (cols - 1)) / cols
    ch = (bottom - top - gap * (rows - 1)) / rows
    for k, item in enumerate(items):
        c, r = k % cols, k // cols
        in_row = min(cols, len(items) - r * cols)
        shift = (cols - in_row) * (cw + gap) / 2  # centre an incomplete last row
        x0, y0 = left + shift + c * (cw + gap), top + r * (ch + gap)
        cards.frosted(canvas, (x0, y0, x0 + cw, y0 + ch), int(22 * scale), alpha=135)
        photo_box = (x0 + 18 * scale, y0 + 16 * scale, x0 + cw - 18 * scale, y0 + ch * 0.64)
        place_device(canvas, item, photo_box, reflection=False, align="center")
        chip_h = (44 if not portrait else 40) * scale
        chip = logo_chip(canvas, item["maker"], x0 + cw / 2, y0 + ch * 0.68, chip_h, anchor="m")
        draw = ImageDraw.Draw(canvas)
        nf = cards.fit_font(draw, full_name(item), (32 if not portrait else 28) * scale, cw - 30 * scale)
        draw.text((x0 + cw / 2, chip[3] + 12 * scale), full_name(item), font=nf, fill=WHITE + (255,), anchor="mt")
    return save(canvas, f"lineup-{fmt}.png")


# --- ranking -----------------------------------------------------------------------------------------

def ranking_rows(canvas, items, area, scale, portrait):
    left, top, right, bottom = area
    draw = ImageDraw.Draw(canvas)
    row_h = (bottom - top) / len(items)
    thumb_w, thumb_h = (190 if not portrait else 170) * scale, row_h * 0.74
    value_font = bold((40 if not portrait else 36) * scale)
    value_w = draw.textlength("100%", font=value_font) + 18 * scale
    name_w = 400 * scale
    for k, item in enumerate(items):
        y = top + k * row_h
        cy = y + row_h / 2
        draw = ImageDraw.Draw(canvas)
        draw.text((left, cy), str(k + 1), font=bold(30 * scale), fill=MUTED + (255,), anchor="lm")
        tx = left + 52 * scale
        place_device(canvas, item, (tx, cy - thumb_h / 2, tx + thumb_w, cy + thumb_h / 2), reflection=False, shadow=False)
        nx = tx + thumb_w + 22 * scale
        draw = ImageDraw.Draw(canvas)
        if portrait:
            nf = cards.fit_font(draw, full_name(item), 32 * scale, right - nx - value_w)
            draw.text((nx, cy - row_h * 0.10), full_name(item), font=nf, fill=WHITE + (255,), anchor="ls")
            bar_x0, bar_y0, bar_h = nx, cy + row_h * 0.06, max(10 * scale, row_h * 0.18)
        else:
            nf = cards.fit_font(draw, full_name(item), 36 * scale, name_w - 20 * scale)
            draw.text((nx, cy - 6 * scale), full_name(item), font=nf, fill=WHITE + (255,), anchor="ls")
            draw.text((nx, cy + 6 * scale), item["maker"], font=text_font(22 * scale), fill=MUTED + (255,), anchor="lt")
            bar_h = max(12 * scale, row_h * 0.30)
            bar_x0, bar_y0 = nx + name_w, cy - bar_h / 2
        bar_w = right - value_w - bar_x0
        length = bar_w * item["score"] / 100
        radius = min(6 * scale, bar_h / 2)
        track = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(track).rounded_rectangle([bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h], radius=radius, fill=(255, 255, 255, 22))
        canvas.alpha_composite(track)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([bar_x0, bar_y0, bar_x0 + length, bar_y0 + bar_h], radius=radius, fill=CYAN + (255,))
        draw.text((bar_x0 + length + 14 * scale, bar_y0 + bar_h / 2), f"{item['score']}%", font=value_font, fill=WHITE + (255,), anchor="lm")


def ranking(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = geometry(size)
    items = sorted((i for i in DATA["handhelds"] if i.get("score") is not None), key=lambda i: -i["score"])
    canvas = stage(size, CYAN, focus=(0.5, 0.4), floor=0.97)
    area = (64 * scale, h * 0.12, w * 0.86, h * 0.76) if portrait else (w * 0.07, 80 * scale, w * 0.93, h - 120 * scale)
    ranking_rows(canvas, items, area, scale, portrait)
    source_line(canvas, area[0], area[3] + 30 * scale, scale)
    out = save(canvas, f"ranking-{fmt}.png")
    clear = Image.new("RGBA", size, (0, 0, 0, 0))
    ranking_rows(clear, items, area, scale, portrait)
    save(clear, f"ranking-{fmt}-transparent.png", keep_alpha=True)
    return out


# --- spec sheet --------------------------------------------------------------------------------------

def specs(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = geometry(size)
    items = DATA["handhelds"]
    canvas = stage(size, CYAN, focus=(0.5, 0.4), floor=0.98)
    draw = ImageDraw.Draw(canvas)
    if not portrait:
        left, top, right, bottom = 60 * scale, 70 * scale, w - 60 * scale, h - 90 * scale
        cols = [("", 470), ("Chip", 300), ("Graphics", 190), ("Memory", 160), ("Storage", 105), ("Display", 260), ("Battery", 105), ("Weight", 100), ("Price", 110)]
        total = sum(c[1] for c in cols)
        widths = [c[1] * (right - left) / total for c in cols]
        header_h = 50 * scale
        row_h = (bottom - top - header_h) / len(items)
        x = left
        for (label, _), cw in zip(cols, widths):
            if label:
                draw.text((x, top + header_h / 2), label.upper(), font=text_bold(20 * scale), fill=CYAN + (255,), anchor="lm")
            x += cw
        for k, item in enumerate(items):
            y = top + header_h + k * row_h
            if k % 2 == 0:
                band = Image.new("RGBA", size, (0, 0, 0, 0))
                ImageDraw.Draw(band).rounded_rectangle([left - 16 * scale, y + 3, right + 10 * scale, y + row_h - 3], radius=int(16 * scale), fill=(255, 255, 255, 12))
                canvas.alpha_composite(band)
            cy = y + row_h / 2
            place_device(canvas, item, (left, y + row_h * 0.14, left + 170 * scale, y + row_h * 0.86), reflection=False, shadow=False)
            draw = ImageDraw.Draw(canvas)
            nf = cards.fit_font(draw, full_name(item), 30 * scale, widths[0] - 200 * scale)
            draw.text((left + 190 * scale, cy - 4 * scale), full_name(item), font=nf, fill=WHITE + (255,), anchor="ls")
            draw.text((left + 190 * scale, cy + 6 * scale), item["maker"], font=text_font(20 * scale), fill=MUTED + (255,), anchor="lt")
            rows = {r[0]: r for r in spec_rows(item)}
            x = left + widths[0]
            for (label, _), cw in zip(cols[1:], widths[1:]):
                _, main, sub = rows[label]
                if label == "Price":
                    sub = ""
                mf = cards.fit_font(draw, main, 25 * scale, cw - 12 * scale, maker=text_bold)
                if sub:
                    draw.text((x, cy - 3 * scale), main, font=mf, fill=WHITE + (255,), anchor="ls")
                    sf = cards.fit_font(draw, sub, 18 * scale, cw - 12 * scale, maker=text_font)
                    draw.text((x, cy + 5 * scale), sub, font=sf, fill=MUTED + (255,), anchor="lt")
                else:
                    draw.text((x, cy), main, font=mf, fill=WHITE + (255,), anchor="lm")
                x += cw
        source_line(canvas, left, h - 52 * scale, scale, mixed_source_label())
    else:
        left, top, right, bottom = 48 * scale, h * 0.10, w * 0.88, h * 0.80
        row_h = (bottom - top) / len(items)
        for k, item in enumerate(items):
            y = top + k * row_h
            cards.frosted(canvas, (left, y + 5 * scale, right, y + row_h - 5 * scale), int(18 * scale), alpha=130)
            place_device(canvas, item, (left + 14 * scale, y + row_h * 0.18, left + 230 * scale, y + row_h * 0.82), reflection=False, shadow=False)
            draw = ImageDraw.Draw(canvas)
            tx = left + 248 * scale
            r = {row[0]: row for row in spec_rows(item)}
            nf = cards.fit_font(draw, full_name(item), 30 * scale, right - tx - 16 * scale)
            draw.text((tx, y + row_h * 0.30), full_name(item), font=nf, fill=WHITE + (255,), anchor="lm")
            line1 = f"{r['Chip'][1]} · {r['Graphics'][1]}"
            line2 = f"{r['Memory'][1]} · {r['Storage'][1]} · {item['display']} {item['refresh'].replace(' VRR', '')}"
            line3 = f"{r['Battery'][1]} · {r['Weight'][1]} · {r['Price'][1]}"
            for j, line in enumerate((line1, line2, line3)):
                lf = cards.fit_font(draw, line, 21 * scale, right - tx - 16 * scale, maker=text_font if j else text_bold)
                draw.text((tx, y + row_h * (0.52 + 0.18 * j)), line, font=lf, fill=(CYAN if j == 0 else MUTED) + (255,), anchor="lm")
        source_line(canvas, left, bottom + 20 * scale, scale, mixed_source_label())
    return save(canvas, f"specs-{fmt}.png")


def main():
    for fmt in ("16x9", "9x16"):
        print(lineup(fmt))
        print(specs(fmt))
        print(ranking(fmt))
        for item in DATA["handhelds"]:
            print(device_card(item, fmt))


if __name__ == "__main__":
    main()
