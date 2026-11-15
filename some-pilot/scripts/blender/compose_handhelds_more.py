"""Ten more handheld graphics (one file per image, 16:9 + 9:16 unless noted). Names, logos and numbers only.

  value-<fmt>.png                    Notebookcheck score against list price (EUR)
  size-<fmt>.png                     every model to true relative width (mm)
  chips-<fmt>.png                    models grouped by chip, with AMD / Intel logos
  battery-weight-<fmt>.png           battery (Wh) and weight (g), two panels
  screens-<fmt>.png                  every display to true relative size (diagonal + aspect ratio)
  duel-<a>-vs-<b>-<fmt>.png          head-to-head cards (pairs in HANDHELDS.json "duels")
  generations-<fmt>.png              each maker's models in order, with scores
  fps-<game>-<fmt>[-transparent].png Notebookcheck game benchmarks
  local-ai-<fmt>[-transparent].png   llama.cpp tokens/s by handheld chip family
  thumbnails/thumb-<id>.png          1280x720 YouTube thumbnail backgrounds (+ duels)
  nameplates/<id>-<fmt>.png          transparent lower-third name plates

    python scripts/blender/compose_handhelds_more.py
"""

import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_ai_cards as cards  # noqa: E402
import compose_ai_extras as ex  # noqa: E402
import compose_handhelds as hh  # noqa: E402

DATA = hh.DATA
ITEMS = {i["id"]: i for i in DATA["handhelds"]}
SIZES = hh.SIZES
CYAN, CORAL, WHITE, MUTED, NAVY = hh.CYAN, hh.CORAL, hh.WHITE, hh.MUTED, hh.NAVY
bold, text_font, text_bold = hh.bold, hh.text_font, hh.text_bold


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def save(canvas, rel, keep_alpha=False):
    (hh.OUT / rel).parent.mkdir(parents=True, exist_ok=True)
    return hh.save(canvas, rel, keep_alpha)


def source(canvas, x, y, scale, label):
    hh.source_line(canvas, x, y, scale, label)


def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def fitted(item, max_w, max_h):
    img = hh.photo(item)
    s = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)


# --- generic bar rows (thumb or vendor logo + name, bar, value) -----------------------------------

def bar_rows(canvas, rows, area, scale, portrait, color=CYAN, axis_max=None):
    left, top, right, bottom = area
    draw = ImageDraw.Draw(canvas)
    row_h = (bottom - top) / len(rows)
    axis_max = axis_max or max(r["value"] for r in rows)
    value_font = bold((36 if portrait else 40) * scale)
    value_w = max(draw.textlength(r["label"], font=value_font) for r in rows) + 18 * scale
    thumb_w, thumb_h = (150 if portrait else 180) * scale, row_h * 0.72
    name_w = 470 * scale
    for k, r in enumerate(rows):
        cy = top + k * row_h + row_h / 2
        draw = ImageDraw.Draw(canvas)
        draw.text((left, cy), str(k + 1), font=bold(28 * scale), fill=MUTED + (255,), anchor="lm")
        tx = left + 48 * scale
        if r.get("item"):
            hh.place_device(canvas, r["item"], (tx, cy - thumb_h / 2, tx + thumb_w, cy + thumb_h / 2), reflection=False, shadow=False, align="center")
            nx = tx + thumb_w + 20 * scale
        elif r.get("vendor"):
            chip = hh.logo_chip(canvas, r["vendor"], tx, cy - 24 * scale, 48 * scale)
            nx = max(chip[2] + 20 * scale, tx + 175 * scale)
        else:
            nx = tx
        draw = ImageDraw.Draw(canvas)
        sub_font = text_font(21 * scale)
        if portrait:
            nf = cards.fit_font(draw, r["name"], 30 * scale, right - nx - value_w)
            draw.text((nx, cy - row_h * 0.08), r["name"], font=nf, fill=WHITE + (255,), anchor="ls")
            if r.get("sub"):
                sf = cards.fit_font(draw, r["sub"], 20 * scale, right - nx - value_w, maker=text_font)
                draw.text((nx + draw.textlength(r["name"], font=nf) + 12 * scale, cy - row_h * 0.08), r["sub"], font=sf, fill=MUTED + (255,), anchor="ls")
            bar_h = max(10 * scale, row_h * 0.17)
            bar_x0, bar_y0 = nx, cy + row_h * 0.05
        else:
            nf = cards.fit_font(draw, r["name"], 34 * scale, name_w - 16 * scale)
            draw.text((nx, cy - (5 if r.get("sub") else -12) * scale), r["name"], font=nf, fill=WHITE + (255,), anchor="ls")
            if r.get("sub"):
                sf = cards.fit_font(draw, r["sub"], 21 * scale, name_w - 16 * scale, maker=text_font)
                draw.text((nx, cy + 6 * scale), r["sub"], font=sf, fill=MUTED + (255,), anchor="lt")
            bar_h = max(12 * scale, row_h * 0.28)
            bar_x0, bar_y0 = nx + name_w, cy - bar_h / 2
        bar_w = right - value_w - bar_x0
        length = bar_w * r["value"] / axis_max
        radius = min(6 * scale, bar_h / 2)
        track = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(track).rounded_rectangle([bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h], radius=radius, fill=(255, 255, 255, 22))
        canvas.alpha_composite(track)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([bar_x0, bar_y0, bar_x0 + max(length, bar_h), bar_y0 + bar_h], radius=radius, fill=color + (255,))
        draw.text((bar_x0 + length + 14 * scale, bar_y0 + bar_h / 2), r["label"], font=value_font, fill=WHITE + (255,), anchor="lm")


def chart_area(w, h, portrait, scale, header=False):
    if portrait:
        return (56 * scale, h * (0.15 if header else 0.11), w * 0.86, h * 0.76)
    return (w * 0.06, (150 if header else 80) * scale, w * 0.94, h - 120 * scale)


def header_pill(canvas, text, scale, portrait):
    w, h = canvas.size
    ex.pill(canvas, (w / 2, h * (0.105 if portrait else 0.065)), text, 34 * scale, color=WHITE, outline=CYAN)


def with_transparent(rows_fn, size, name):
    clear = Image.new("RGBA", size, (0, 0, 0, 0))
    rows_fn(clear)
    save(clear, name, keep_alpha=True)


# --- 1. value: score vs price ------------------------------------------------------------------------

def value(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    items = [i for i in DATA["handhelds"] if i.get("score") is not None and i.get("price_eur")]
    if portrait:
        left, right, top, bottom = 150 * scale, w * 0.86, h * 0.12, h * 0.74
    else:
        left, right, top, bottom = 200 * scale, w - 110 * scale, 90 * scale, h - 170 * scale
    xmin, xmax, ymin, ymax = 500, 1700, 62, 92

    def px(v):
        return left + (v - xmin) / (xmax - xmin) * (right - left)

    def py(v):
        return bottom - (v - ymin) / (ymax - ymin) * (bottom - top)

    grid = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    tick = text_font(24 * scale)
    draw = ImageDraw.Draw(canvas)
    for v in range(65, 91, 5):
        gd.line([(left, py(v)), (right, py(v))], fill=(255, 255, 255, 24), width=max(1, int(2 * scale)))
        draw.text((left - 16 * scale, py(v)), f"{v}%", font=tick, fill=MUTED + (255,), anchor="rm")
    for v in range(600, 1700, 200):
        gd.line([(px(v), top), (px(v), bottom)], fill=(255, 255, 255, 24), width=max(1, int(2 * scale)))
        draw.text((px(v), bottom + 16 * scale), f"€{v:,}", font=tick, fill=MUTED + (255,), anchor="mt")
    gd.line([(left, bottom), (right, bottom)], fill=(255, 255, 255, 70), width=max(1, int(2 * scale)))
    canvas.alpha_composite(grid)
    draw = ImageDraw.Draw(canvas)
    axis = bold(26 * scale)
    draw.text((left - 90 * scale, top - 34 * scale), "Notebookcheck", font=axis, fill=WHITE + (255,), anchor="lb")
    draw.text((right, bottom + 58 * scale), "List price", font=axis, fill=WHITE + (255,), anchor="rt")
    dots = [(px(i["price_eur"]), py(i["score"])) for i in items]
    taken = [(x - 12 * scale, y - 12 * scale, x + 12 * scale, y + 12 * scale) for x, y in dots]
    tw, th = (150 if portrait else 170) * scale, (62 if portrait else 70) * scale
    name_font = bold((22 if portrait else 24) * scale)
    for item, (x, y) in sorted(zip(items, dots), key=lambda t: -t[0]["score"]):
        nw = max(tw, draw.textlength(hh.full_name(item), font=name_font))
        bh = th + 30 * scale
        best = None
        for dist in (40, 70, 110, 160):
            for ang in range(0, 360, 30):
                cx = x + math.cos(math.radians(ang)) * (dist * scale + nw / 2)
                cy = y + math.sin(math.radians(ang)) * (dist * scale + bh / 2)
                box = (cx - nw / 2, cy - bh / 2, cx + nw / 2, cy + bh / 2)
                inside = box[0] >= 20 * scale and box[2] <= w - 20 * scale and box[1] >= top - 50 * scale and box[3] <= bottom - 4 * scale
                score = sum(overlap(box, t) for t in taken) * 10 + (0 if inside else 1e9) + dist
                if best is None or score < best[0]:
                    best = (score, box, cx, cy)
        _, box, cx, cy = best
        taken.append(box)
        line = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(line).line([(x, y), (cx, cy)], fill=CYAN + (150,), width=max(2, int(2 * scale)))
        canvas.alpha_composite(line)
        hh.place_device(canvas, item, (cx - tw / 2, box[1], cx + tw / 2, box[1] + th), reflection=False, shadow=False, align="center")
        draw = ImageDraw.Draw(canvas)
        draw.text((cx, box[3]), hh.full_name(item), font=name_font, fill=WHITE + (255,), anchor="mb")
    draw = ImageDraw.Draw(canvas)
    for x, y in dots:
        r = 9 * scale
        draw.ellipse([x - r - 3 * scale, y - r - 3 * scale, x + r + 3 * scale, y + r + 3 * scale], fill=NAVY + (255,))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=CYAN + (255,))
    source(canvas, 64 * scale, h - (300 if portrait else 46) * scale, scale, "Source: Notebookcheck reviews · list prices at review · Nov 2026")
    return save(canvas, f"value-{fmt}.png")


# --- 2. size comparison --------------------------------------------------------------------------------

def size_compare(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.5), floor=0.99)
    items = sorted(DATA["handhelds"], key=lambda i: -i["width_mm"])
    per_row = 3 if portrait else 6
    rows = [items[k:k + per_row] for k in range(0, len(items), per_row)]
    gap = 22 * scale
    avail = (w * 0.86 - 56 * scale) if portrait else (w - 180 * scale)
    mm = min((avail - gap * (len(r) - 1)) / sum(i["width_mm"] for i in r) for r in rows)
    imgs = {i["id"]: hh.photo(i) for i in items}
    row_heights = [max(imgs[i["id"]].height * (i["width_mm"] * mm / imgs[i["id"]].width) for i in r) for r in rows]
    label_h = 78 * scale
    total = sum(row_heights) + len(rows) * label_h + (len(rows) - 1) * 26 * scale
    y = (h * 0.12 + (h * 0.78 - h * 0.12 - total) / 2) if portrait else (h - total) / 2
    for r, rh in zip(rows, row_heights):
        row_w = sum(i["width_mm"] * mm for i in r) + gap * (len(r) - 1)
        x = ((56 * scale + w * 0.86) / 2 - row_w / 2) if portrait else (w - row_w) / 2
        floor_y = y + rh
        for item in r:
            dw = item["width_mm"] * mm
            hh.place_device(canvas, item, (x, y, x + dw, floor_y), reflection=False)
            draw = ImageDraw.Draw(canvas)
            nf = cards.fit_font(draw, hh.full_name(item), (26 if not portrait else 24) * scale, dw + gap * 0.8)
            draw.text((x + dw / 2, floor_y + 12 * scale), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="mt")
            draw.text((x + dw / 2, floor_y + 44 * scale), f"{item['width_mm']:g} mm", font=text_bold(21 * scale), fill=CYAN + (255,), anchor="mt")
            x += dw + gap
        y = floor_y + label_h + 26 * scale
    source(canvas, 64 * scale, h - (300 if portrait else 46) * scale, scale, "Source: Notebookcheck reviews · width in mm · Nov 2026")
    return save(canvas, f"size-{fmt}.png")


# --- 3. chip families ------------------------------------------------------------------------------------

def chips(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    fams = DATA["chip_families"]
    left, top, right, bottom = (48 * scale, h * 0.10, w * 0.88, h * 0.79) if portrait else (70 * scale, 60 * scale, w - 70 * scale, h - 60 * scale)
    gap = 16 * scale
    row_h = (bottom - top - gap * (len(fams) - 1)) / len(fams)
    for k, fam in enumerate(fams):
        y0 = top + k * (row_h + gap)
        cards.frosted(canvas, (left, y0, right, y0 + row_h), int(20 * scale), alpha=135)
        vendor = "AMD" if fam["vendor"] == "amd" else "Intel"
        draw = ImageDraw.Draw(canvas)
        if portrait:
            chip = hh.logo_chip(canvas, vendor, left + 18 * scale, y0 + 14 * scale, 40 * scale)
            draw = ImageDraw.Draw(canvas)
            draw.text((chip[2] + 16 * scale, y0 + 14 * scale + 20 * scale), fam["chip"], font=bold(30 * scale), fill=WHITE + (255,), anchor="lm")
            draw.text((right - 18 * scale, y0 + 14 * scale + 20 * scale), fam["family"], font=text_font(22 * scale), fill=MUTED + (255,), anchor="rm")
            tx0, ty0, ty1 = left + 18 * scale, y0 + 64 * scale, y0 + row_h - 10 * scale
            tx1 = right - 18 * scale
        else:
            chip = hh.logo_chip(canvas, vendor, left + 24 * scale, y0 + row_h / 2 - 24 * scale, 48 * scale)
            draw = ImageDraw.Draw(canvas)
            draw.text((left + 200 * scale, y0 + row_h / 2 - 4 * scale), fam["chip"], font=bold(34 * scale), fill=WHITE + (255,), anchor="ls")
            draw.text((left + 200 * scale, y0 + row_h / 2 + 6 * scale), fam["family"], font=text_font(22 * scale), fill=MUTED + (255,), anchor="lt")
            tx0, ty0, ty1, tx1 = left + 640 * scale, y0 + 8 * scale, y0 + row_h - 8 * scale, right - 20 * scale
        n = len(fam["handhelds"])
        slot = (tx1 - tx0) / 4
        label_h = 26 * scale
        for j, hid in enumerate(fam["handhelds"]):
            item = ITEMS[hid]
            sx = tx0 + j * slot
            hh.place_device(canvas, item, (sx + 8 * scale, ty0, sx + slot - 8 * scale, ty1 - label_h), reflection=False, shadow=False, align="center")
            draw = ImageDraw.Draw(canvas)
            nf = cards.fit_font(draw, hh.full_name(item), 20 * scale, slot - 10 * scale, maker=text_bold)
            draw.text((sx + slot / 2, ty1), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="mb")
        del n
    return save(canvas, f"chips-{fmt}.png")


# --- 4. battery and weight ----------------------------------------------------------------------------------

def battery_weight(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    items = sorted(DATA["handhelds"], key=lambda i: -i["battery_wh"])
    if portrait:
        left, top, right, bottom = 56 * scale, h * 0.10, w * 0.86, h * 0.77
    else:
        left, top, right, bottom = w * 0.05, 120 * scale, w * 0.95, h - 100 * scale
    row_h = (bottom - top) / len(items)
    max_wh = max(i["battery_wh"] for i in items)
    max_g = max(i["weight_g"] for i in items if i.get("weight_g"))
    draw = ImageDraw.Draw(canvas)
    thumb_w = (130 if portrait else 160) * scale
    if not portrait:
        name_x = left + thumb_w + 20 * scale
        col1 = (left + 640 * scale, left + 640 * scale + (right - left - 640 * scale) / 2 - 40 * scale)
        col2 = (col1[1] + 80 * scale, right)
        for (x0, x1), label, color in ((col1, "Battery", CYAN), (col2, "Weight", CORAL)):
            draw.text((x0, top - 34 * scale), label.upper(), font=text_bold(24 * scale), fill=color + (255,), anchor="ls")
    vf = bold((30 if portrait else 34) * scale)
    for k, item in enumerate(items):
        cy = top + k * row_h + row_h / 2
        hh.place_device(canvas, item, (left, cy - row_h * 0.36, left + thumb_w, cy + row_h * 0.36), reflection=False, shadow=False, align="center")
        draw = ImageDraw.Draw(canvas)
        bars = [(item["battery_wh"], max_wh, f"{item['battery_wh']:g} Wh", CYAN),
                (item.get("weight_g") or 0, max_g, hh.weight_text(item), CORAL)]
        if portrait:
            nx = left + thumb_w + 18 * scale
            nf = cards.fit_font(draw, hh.full_name(item), 26 * scale, right - nx)
            draw.text((nx, cy - row_h * 0.16), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="ls")
            bh = max(8 * scale, row_h * 0.13)
            label_w = 170 * scale
            for j, (val, vmax, label, color) in enumerate(bars):
                by = cy - row_h * 0.06 + j * (bh + 8 * scale)
                bw = right - nx - label_w
                draw.rounded_rectangle([nx, by, nx + max(bh, bw * val / vmax), by + bh], radius=bh / 2, fill=color + (255,))
                draw.text((nx + bw * val / vmax + 12 * scale, by + bh / 2), label, font=bold(22 * scale), fill=WHITE + (255,), anchor="lm")
        else:
            nf = cards.fit_font(draw, hh.full_name(item), 32 * scale, col1[0] - name_x - 20 * scale)
            draw.text((name_x, cy), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="lm")
            bh = max(12 * scale, row_h * 0.30)
            for (x0, x1), (val, vmax, label, color) in zip((col1, col2), bars):
                lw = draw.textlength("~1,430 g", font=vf) + 16 * scale
                bw = x1 - x0 - lw
                draw.rounded_rectangle([x0, cy - bh / 2, x0 + max(bh, bw * val / vmax), cy + bh / 2], radius=min(6 * scale, bh / 2), fill=color + (255,))
                draw.text((x0 + bw * val / vmax + 12 * scale, cy), label, font=vf, fill=WHITE + (255,), anchor="lm")
    source(canvas, left, h - (300 if portrait else 52) * scale, scale, "Source: Notebookcheck reviews · AYANEO (NEXT 2) · Nov 2026")
    return save(canvas, f"battery-weight-{fmt}.png")


# --- 5. screens to scale ---------------------------------------------------------------------------------------

def screens(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    items = sorted(DATA["handhelds"], key=lambda i: -float(i["display"].split('"')[0]))
    cols = 3 if portrait else 4
    rows = (len(items) + cols - 1) // cols
    left, top, right, bottom = (48 * scale, h * 0.10, w * 0.88, h * 0.79) if portrait else (90 * scale, 60 * scale, w - 90 * scale, h - 60 * scale)
    cw = (right - left) / cols
    ch = (bottom - top) / rows
    label_h = 44 * scale

    def dims(item):
        d = float(item["display"].split('"')[0])
        rw, rh = [int(v) for v in item["resolution"].split("×")]
        diag = math.hypot(rw, rh)
        return d * rw / diag, d * rh / diag

    ppi = min(min((cw - 30 * scale) / dims(i)[0], (ch - label_h - 20 * scale) / dims(i)[1]) for i in items)
    for k, item in enumerate(items):
        c, r = k % cols, k // cols
        in_row = min(cols, len(items) - r * cols)
        shift = (cols - in_row) * cw / 2
        cx = left + shift + c * cw + cw / 2
        cy = top + r * ch + (ch - label_h) / 2
        sw, sh = [v * ppi for v in dims(item)]
        oled = "OLED" in item["display"]
        color = CORAL if oled else CYAN
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.rounded_rectangle([cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2], radius=int(10 * scale), outline=color + (200,), width=int(10 * scale))
        canvas.alpha_composite(glow.filter(hh.ImageFilter.GaussianBlur(12 * scale)))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2], radius=int(10 * scale), fill=(3, 8, 20, 255), outline=color + (255,), width=max(2, int(3 * scale)))
        diag_txt = item["display"].split(" ")[0]
        big = bold((52 if not portrait else 40) * scale)
        draw.text((cx, cy - 6 * scale), diag_txt, font=big, fill=WHITE + (255,), anchor="ms")
        sub = f"{'OLED' if oled else 'IPS'} · {item['refresh'].replace(' VRR', '')}"
        draw.text((cx, cy + 8 * scale), sub, font=text_bold((22 if not portrait else 18) * scale), fill=color + (255,), anchor="mt")
        nf = cards.fit_font(draw, hh.full_name(item), (26 if not portrait else 22) * scale, cw - 16 * scale)
        draw.text((cx, top + r * ch + ch - label_h + 8 * scale), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="mt")
    return save(canvas, f"screens-{fmt}.png")


# --- 6. duels -------------------------------------------------------------------------------------------------

def duel(fmt, a_id, b_id):
    size = SIZES[fmt]
    canvas = Image.new("RGBA", size, (4, 8, 20, 255))
    w, h, portrait, scale = hh.geometry(size)
    sides = [(ITEMS[a_id], CYAN), (ITEMS[b_id], CORAL)]
    centers = [(w * 0.5, h * 0.25), (w * 0.5, h * 0.66)] if portrait else [(w * 0.26, h * 0.47), (w * 0.74, h * 0.47)]
    for (item, color), c in zip(sides, centers):
        ex.glow(canvas, c, (520 if portrait else 560) * scale, color, 120)
    split = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(split)
    if portrait:
        sd.line([(0, h * 0.47), (w, h * 0.43)], fill=(255, 255, 255, 120), width=int(4 * scale))
    else:
        sd.line([(w * 0.53, 0), (w * 0.47, h)], fill=(255, 255, 255, 120), width=int(4 * scale))
    canvas.alpha_composite(split)
    pw, ph = (w * 0.84, h * 0.13) if portrait else (w * 0.40, h * 0.30)
    for (item, color), (cx, cy) in zip(sides, centers):
        box = hh.place_device(canvas, item, (cx - pw / 2, cy - ph - 40 * scale, cx + pw / 2, cy - 40 * scale), reflection=False)
        chip = hh.logo_chip(canvas, item["maker"], cx, box[3] + 26 * scale, 46 * scale, anchor="m")
        draw = ImageDraw.Draw(canvas)
        nf = cards.fit_font(draw, hh.full_name(item), 60 * scale, w * (0.84 if portrait else 0.42))
        draw.text((cx, chip[3] + 14 * scale), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="mt")
        if item.get("score") is not None:
            draw.text((cx, chip[3] + 14 * scale + nf.size * 1.15), f"{item['score']}%", font=bold(120 * scale), fill=WHITE + (255,), anchor="mt")
    ex.pixel_vs(canvas, w / 2, h * 0.455 if portrait else h * 0.47, 22 * scale)
    source(canvas, 64 * scale, h - (300 if portrait else 46) * scale, scale, "Source: Notebookcheck reviews · Nov 2026")
    return save(canvas, f"duel-{a_id}-vs-{b_id}-{fmt}.png")


# --- 7. generations ---------------------------------------------------------------------------------------------

def generations(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    fams = DATA["generations"]
    left, top, right, bottom = (48 * scale, h * 0.10, w * 0.88, h * 0.79) if portrait else (70 * scale, 60 * scale, w - 70 * scale, h - 60 * scale)
    gap = 22 * scale
    row_h = (bottom - top - gap * (len(fams) - 1)) / len(fams)
    for k, fam in enumerate(fams):
        y0 = top + k * (row_h + gap)
        cards.frosted(canvas, (left, y0, right, y0 + row_h), int(22 * scale), alpha=130)
        if portrait:
            hh.logo_chip(canvas, fam["maker"], left + 20 * scale, y0 + 16 * scale, 42 * scale)
            sx0, sy0 = left + 10 * scale, y0 + 70 * scale
        else:
            hh.logo_chip(canvas, fam["maker"], left + 26 * scale, y0 + row_h / 2 - 26 * scale, 52 * scale)
            sx0, sy0 = left + 260 * scale, y0 + 12 * scale
        slot = (right - 10 * scale - sx0) / len(fam["ids"])
        for j, hid in enumerate(fam["ids"]):
            item = ITEMS[hid]
            sx = sx0 + j * slot
            name_y = y0 + row_h - (52 if portrait else 58) * scale
            hh.place_device(canvas, item, (sx + 22 * scale, sy0, sx + slot - 22 * scale, name_y - 10 * scale), reflection=False, shadow=False, align="center")
            draw = ImageDraw.Draw(canvas)
            nf = cards.fit_font(draw, hh.full_name(item), (26 if not portrait else 22) * scale, slot - 70 * scale)
            draw.text((sx + slot / 2, name_y), hh.full_name(item), font=nf, fill=WHITE + (255,), anchor="mt")
            draw.text((sx + slot / 2, name_y + nf.size * 1.15), f"{item['score']}%", font=bold((30 if not portrait else 26) * scale), fill=CYAN + (255,), anchor="mt")
            if j:
                ax = sx
                ay = sy0 + (name_y - sy0) / 2
                r = 18 * scale
                draw.polygon([(ax - r * 0.6, ay - r), (ax + r * 0.8, ay), (ax - r * 0.6, ay + r)], fill=CYAN + (230,))
                delta = item["score"] - ITEMS[fam["ids"][j - 1]]["score"]
                pill_y = (name_y + nf.size * 0.6) if portrait else (ay - r - 34 * scale)
                ex.pill(canvas, (ax, pill_y), f"{delta:+d}", (24 if portrait else 30) * scale, color=CYAN if delta >= 0 else CORAL)
    source(canvas, left, h - (300 if portrait else 46) * scale, scale, "Source: Notebookcheck reviews · Nov 2026")
    return save(canvas, f"generations-{fmt}.png")


# --- 8. game fps -------------------------------------------------------------------------------------------------

def fps(fmt, key):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    game = DATA["game_fps"]["games"][key]
    rows = sorted(({"item": ITEMS[i], "name": hh.full_name(ITEMS[i]), "value": v, "label": f"{v:g} fps"} for i, v in game["values"].items()), key=lambda r: -r["value"])
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    area = chart_area(w, h, portrait, scale, header=True)
    header_pill(canvas, f"{game['label']} · {game['setting']}", scale, portrait)
    bar_rows(canvas, rows, area, scale, portrait)
    source(canvas, area[0], area[3] + 26 * scale, scale, DATA["game_fps"]["source_label"])
    out = save(canvas, f"fps-{key}-{fmt}.png")
    with_transparent(lambda c: bar_rows(c, rows, area, scale, portrait), size, f"fps-{key}-{fmt}-transparent.png")
    return out


# --- 9. local AI by chip ----------------------------------------------------------------------------------------

def local_ai(fmt):
    size = SIZES[fmt]
    w, h, portrait, scale = hh.geometry(size)
    rows = [{"vendor": "AMD" if f["vendor"] == "amd" else "Intel", "name": f["chip"],
             "sub": " · ".join(hh.full_name(ITEMS[i]) for i in f["handhelds"]), "value": f["tps"], "label": f"{f['tps']:.0f} t/s"}
            for f in sorted(DATA["chip_families"], key=lambda f: -f["tps"])]
    canvas = hh.stage(size, CYAN, focus=(0.5, 0.45), floor=0.99)
    area = chart_area(w, h, portrait, scale)
    if portrait:
        for r in rows:
            r["sub"] = ""
    bar_rows(canvas, rows, area, scale, portrait)
    source(canvas, area[0], area[3] + 26 * scale, scale, DATA["chip_tps_source_label"])
    out = save(canvas, f"local-ai-{fmt}.png")
    with_transparent(lambda c: bar_rows(c, rows, area, scale, portrait), size, f"local-ai-{fmt}-transparent.png")
    return out


# --- 10. thumbnails + name plates ------------------------------------------------------------------------------------

THUMB = (1280, 720)


def thumbnails():
    made = []
    for item in DATA["handhelds"]:
        canvas = hh.stage(THUMB, CYAN, focus=(0.68, 0.5), floor=0.80)
        ex.glow(canvas, (870, 380), 360, CYAN, 110)
        hh.place_device(canvas, item, (500, 140, 1250, 560))
        made.append(save(canvas, f"thumbnails/thumb-{item['id']}.png"))
    for a_id, b_id in DATA["duels"]:
        canvas = Image.new("RGBA", THUMB, (4, 8, 20, 255))
        ex.glow(canvas, (320, 360), 420, CYAN, 140)
        ex.glow(canvas, (960, 360), 420, CORAL, 140)
        line = Image.new("RGBA", THUMB, (0, 0, 0, 0))
        ImageDraw.Draw(line).line([(672, 0), (608, 720)], fill=(255, 255, 255, 140), width=4)
        canvas.alpha_composite(line)
        hh.place_device(canvas, ITEMS[a_id], (30, 200, 560, 520))
        hh.place_device(canvas, ITEMS[b_id], (720, 200, 1250, 520))
        ex.pixel_vs(canvas, 640, 360, 18)
        made.append(save(canvas, f"thumbnails/thumb-duel-{a_id}-vs-{b_id}.png"))
    return made


def nameplate(item, fmt):
    size = SIZES[fmt]
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    w, h, portrait, scale = hh.geometry(size)
    draw = ImageDraw.Draw(canvas)
    name_font = bold(52 * scale)
    chip_h = 60 * scale
    name = hh.full_name(item)
    pad = 22 * scale
    probe = Image.new("RGBA", (10, 10))
    chip_w = hh.logo_chip(probe, item["maker"], 0, 0, chip_h)[2]
    pw = pad * 2 + 26 * scale + chip_w + 24 * scale + draw.textlength(name, font=name_font)
    ph = chip_h + pad * 2
    x0, y0 = ((w - pw) / 2, h * 0.64) if portrait else (90 * scale, h - 120 * scale - ph)
    plate = Image.new("RGBA", size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=int(26 * scale), fill=NAVY + (222,), outline=(255, 255, 255, 46), width=max(1, int(2 * scale)))
    pd.rounded_rectangle([x0 + pad * 0.6, y0 + pad, x0 + pad * 0.6 + 8 * scale, y0 + ph - pad], radius=int(4 * scale), fill=CYAN + (255,))
    canvas.alpha_composite(plate)
    chip = hh.logo_chip(canvas, item["maker"], x0 + pad + 26 * scale, y0 + pad, chip_h)
    ImageDraw.Draw(canvas).text((chip[2] + 24 * scale, y0 + ph / 2), name, font=name_font, fill=WHITE + (255,), anchor="lm")
    return save(canvas, f"nameplates/{item['id']}-{fmt}.png", keep_alpha=True)


def main():
    for fmt in ("16x9", "9x16"):
        print(value(fmt))
        print(size_compare(fmt))
        print(chips(fmt))
        print(battery_weight(fmt))
        print(screens(fmt))
        for a_id, b_id in DATA["duels"]:
            print(duel(fmt, a_id, b_id))
        print(generations(fmt))
        for key in DATA["game_fps"]["games"]:
            print(fps(fmt, key))
        print(local_ai(fmt))
        for item in DATA["handhelds"]:
            print(nameplate(item, fmt))
    for path in thumbnails():
        print(path)


if __name__ == "__main__":
    main()
