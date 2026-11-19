"""Ten extra AI graphics, one file per image, 16:9 and 9:16. Names, logos and numbers only.

  extras/vram-tetris-<fmt>.png          3D: 8B + 32B fit a 32 GB card, 70B does not   (renders3d/vram)
  hardware/gpu/<fmt>/...                3D exploded graphics card, GPU + VRAM highlights (compose_hardware.py)
  extras/price-vs-score-<fmt>.png       score against cost per task, log scale         (AI_RATINGS.json catalog)
  extras/speed-<fmt>[-transparent].png  time per task, fastest first
  extras/duel-<a>-vs-<b>-<fmt>.png      head-to-head card (pairs in AI_RATINGS.json "duels")
  extras/context-books-<fmt>.png        3D: 128K / 1M / 10M tokens as books           (renders3d/books)
  extras/agent-team-<fmt>.png           3D: Planner / Coder / Reviewer                (renders3d/agents)
  extras/open-vs-closed-<fmt>.png       3D padlocks + best open / closed models       (renders3d/locks)
  extras/timeline-2026-<fmt>.png        release months
  extras/podium-top3-<fmt>.png          3D podium + top 3 by score                    (renders3d/podium)

    python scripts/blender/compose_ai_extras.py
"""

import json
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_ai_cards as cards  # noqa: E402

GFX = cards.GFX
OUT = GFX / "extras"
R3D = GFX / "renders3d"
CYAN, CORAL, WHITE, MUTED, NAVY = cards.CYAN, (242, 92, 60), cards.WHITE, cards.MUTED, cards.NAVY
DATA = json.loads((cards.ROOT / "content" / "AI_RATINGS.json").read_text(encoding="utf-8"))
CATALOG = {m["name"]: m for m in DATA["catalog"]}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def bold(size):
    return cards.bold(size)


def text_font(size):
    return cards.font(cards.FONT_TEXT, size)


def geometry(canvas):
    w, h = canvas.size
    portrait = h > w
    return w, h, portrait, (w / 1080) if portrait else (w / 1920)


def save(canvas, name, keep_alpha=False):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    (canvas if keep_alpha else canvas.convert("RGB")).save(path, optimize=True)
    return path


def source_line(canvas, text, x, y, scale):
    if DATA.get("show_source", True):
        ImageDraw.Draw(canvas).text((x, y), text, font=text_font(20 * scale), fill=MUTED + (255,))


def load_render(scene, fmt):
    folder = R3D / scene / fmt
    image = Image.open(folder / "clean.png").convert("RGBA")
    meta = json.loads((folder / "anchors.json").read_text(encoding="utf-8"))
    factor = image.width / meta["size"][0]
    anchors = {name: (x * factor, y * factor) for name, (x, y) in meta["anchors"].items()}
    return image, anchors


def pill(canvas, center, text, size, color=WHITE, anchor="mm", pad=(22, 10), fill=(6, 14, 34, 200), outline=None):
    """Label on a dark frosted pill, so it reads over bright 3D objects."""
    draw = ImageDraw.Draw(canvas)
    face = bold(size)
    box = draw.textbbox((0, 0), text, font=face)
    tw, th = box[2] - box[0], box[3] - box[1]
    pw, ph = tw + pad[0] * 2, th + pad[1] * 2
    x, y = center
    x0 = {"m": x - pw / 2, "l": x, "r": x - pw}[anchor[0]]
    y0 = {"m": y - ph / 2, "t": y, "b": y - ph}[anchor[1]]
    cards.frosted(canvas, (x0, y0, x0 + pw, y0 + ph), int(ph / 2), tint=fill[:3], alpha=fill[3], outline=outline)
    ImageDraw.Draw(canvas).text((x0 + pad[0] - box[0], y0 + pad[1] - box[1]), text, font=face, fill=color + (255,))
    return (x0, y0, x0 + pw, y0 + ph)


def model_row(canvas, x, y, height, model, scale, max_width, value=None):
    """Logo tile + name (+ value) in one line; returns the right edge."""
    item = CATALOG.get(model, {"lab": model})
    tile = height
    cards.logo_tile(canvas, x, y, tile, item["lab"], model)
    draw = ImageDraw.Draw(canvas)
    name_x = x + tile + 16 * scale
    value_w = 0
    if value is not None:
        vf = bold(height * 0.62)
        value_w = draw.textlength(str(value), font=vf) + 18 * scale
        vb = draw.textbbox((0, 0), str(value), font=vf)
        draw.text((x + max_width - (vb[2] - vb[0]) - vb[0], y + (tile - (vb[3] - vb[1])) / 2 - vb[1]), str(value), font=vf, fill=WHITE + (255,))
    face = cards.fit_font(draw, model, height * 0.5, max_width - tile - 16 * scale - value_w)
    nb = draw.textbbox((0, 0), model, font=face)
    draw.text((name_x, y + (tile - (nb[3] - nb[1])) / 2 - nb[1]), model, font=face, fill=WHITE + (255,))


# --- 1. VRAM tetris ------------------------------------------------------------------------------

def vram_tetris(fmt):
    canvas, a = load_render("vram", fmt)
    w, h, portrait, scale = geometry(canvas)
    labels = {m["label"]: m for m in DATA["vram"]["models"]}
    pill(canvas, a["b8"], "8B", 44 * scale)
    pill(canvas, a["b32"], "32B", 44 * scale)
    pill(canvas, a["b70"], "70B", 52 * scale, color=WHITE, outline=CORAL)
    for gb in (8, 16, 24, 32):
        x, y = a[f"gb{gb}"]
        pill(canvas, (x, y), f"{gb} GB", (40 if gb == 32 else 28) * scale, color=CORAL if gb == 32 else MUTED, anchor="rm", pad=(16, 7))
    del labels
    return save(canvas, f"vram-tetris-{fmt}.png")


# --- 3. price vs score -----------------------------------------------------------------------------

def price_vs_score(fmt):
    canvas = cards.backdrop("datacenter", fmt, 12, 195)
    w, h, portrait, scale = geometry(canvas)
    draw = ImageDraw.Draw(canvas)
    if portrait:
        left, right, top, bottom = 150 * scale, w * 0.86, h * 0.13, h * 0.72
    else:
        left, right, top, bottom = 230 * scale, w - 120 * scale, 110 * scale, h - 170 * scale
    xmin, xmax, ymin, ymax = 0.5, 30.0, 20, 70

    def px(cost):
        return left + (math.log(cost) - math.log(xmin)) / (math.log(xmax) - math.log(xmin)) * (right - left)

    def py(score):
        return bottom - (score - ymin) / (ymax - ymin) * (bottom - top)

    grid = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    tick = text_font(24 * scale)
    for score in range(30, 71, 10):
        gd.line([(left, py(score)), (right, py(score))], fill=(255, 255, 255, 26), width=max(1, int(2 * scale)))
        draw.text((left - 16 * scale, py(score)), str(score), font=tick, fill=MUTED + (255,), anchor="rm")
    for cost in (1, 3, 10, 30):
        gd.line([(px(cost), top), (px(cost), bottom)], fill=(255, 255, 255, 26), width=max(1, int(2 * scale)))
        draw.text((px(cost), bottom + 16 * scale), f"${cost}", font=tick, fill=MUTED + (255,), anchor="mt")
    gd.line([(left, bottom), (right, bottom)], fill=(255, 255, 255, 70), width=max(1, int(2 * scale)))
    canvas.alpha_composite(grid)
    draw = ImageDraw.Draw(canvas)
    axis = bold(26 * scale)
    draw.text((left - 16 * scale, top - 30 * scale), "Score", font=axis, fill=WHITE + (255,), anchor="rb")
    draw.text((right, bottom + 56 * scale), "Cost per task", font=axis, fill=WHITE + (255,), anchor="rt")

    points = sorted((m for m in DATA["catalog"] if m.get("cost_per_task_usd")), key=lambda m: -m["score"])
    tile = (46 if portrait else 52) * scale
    taken = []
    for m in points:
        x, y = px(m["cost_per_task_usd"]), py(m["score"])
        taken.append((x - tile / 2, y - tile / 2, x + tile / 2, y + tile / 2))
    name_font = bold(22 * scale)
    for m in points:
        x, y = px(m["cost_per_task_usd"]), py(m["score"])
        cards.logo_tile(canvas, x - tile / 2, y - tile / 2, tile, m["lab"], m["name"])
        tw = draw.textlength(m["name"], font=name_font)
        th = 26 * scale
        options = [(x + tile / 2 + 10 * scale, y - th / 2), (x - tile / 2 - 10 * scale - tw, y - th / 2),
                   (x - tw / 2, y + tile / 2 + 6 * scale), (x - tw / 2, y - tile / 2 - 6 * scale - th)]
        best = None
        for ox, oy in options:
            box = (ox, oy, ox + tw, oy + th)
            inside = box[0] >= left + 6 * scale and box[2] <= w - 20 * scale and box[1] >= top - 40 * scale and box[3] <= bottom
            overlap = sum(max(0, min(box[2], t[2]) - max(box[0], t[0])) * max(0, min(box[3], t[3]) - max(box[1], t[1])) for t in taken)
            score = overlap + (0 if inside else 1e9)
            if best is None or score < best[0]:
                best = (score, box)
        taken.append(best[1])
        ImageDraw.Draw(canvas).text((best[1][0], best[1][1]), m["name"], font=name_font, fill=WHITE + (255,))
    source_line(canvas, "Source: Artificial Analysis · Intelligence Index & cost per task · Nov 2026", left, h - (60 if not portrait else 300) * scale, scale)
    return save(canvas, f"price-vs-score-{fmt}.png")


# --- 4. speed ------------------------------------------------------------------------------------------

def speed(fmt):
    rows = sorted((m for m in DATA["catalog"] if m.get("time_per_task_min")), key=lambda m: m["time_per_task_min"])[:10]
    rows = [{"name": m["name"], "lab": m["lab"], "model": m["name"], "score": m["time_per_task_min"],
             "value_label": f"{m['time_per_task_min']:.1f} min"} for m in rows]
    canvas = cards.backdrop("glass_panels", fmt, 12, 185)
    w, h, portrait, scale = geometry(canvas)
    left, top, right, bottom = cards.safe_area(w, h, portrait, scale)
    if not portrait:
        left, right = w * 0.10, w * 0.90
    area = (left, top, right, bottom - 50 * scale)
    label = "Source: Artificial Analysis · time per task · Nov 2026"
    cards.rating_rows(canvas, rows, area, scale, portrait, label if DATA.get("show_source", True) else None)
    out = save(canvas, f"speed-{fmt}.png")
    clear = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cards.rating_rows(clear, rows, area, scale, portrait, None)
    save(clear, f"speed-{fmt}-transparent.png", keep_alpha=True)
    return out


# --- 5. duel ---------------------------------------------------------------------------------------------

V = ["10001", "10001", "10001", "10001", "01010", "01010", "00100"]
S = ["01111", "10000", "10000", "01110", "00001", "00001", "11110"]


def pixel_vs(canvas, cx, cy, cell):
    draw = ImageDraw.Draw(canvas)
    width = (5 + 2 + 5) * cell
    x0, y0 = cx - width / 2, cy - 7 * cell / 2
    for shadow, color in ((cell * 0.35, CORAL), (0, WHITE)):
        for glyph, gx in ((V, 0), (S, 7)):
            for r, row in enumerate(glyph):
                for c, bit in enumerate(row):
                    if bit == "1":
                        x = x0 + (gx + c) * cell + shadow
                        y = y0 + r * cell + shadow
                        draw.rectangle([x, y, x + cell * 0.94, y + cell * 0.94], fill=color + (255,))


def glow(canvas, center, radius, color, strength):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius], fill=color + (strength,))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius * 0.45)))


def duel(fmt, a_name, b_name):
    size = (1920, 1080) if fmt == "16x9" else (1080, 1920)
    canvas = Image.new("RGBA", size, (4, 8, 20, 255))
    w, h, portrait, scale = geometry(canvas)
    sides = [(CATALOG[a_name], CYAN), (CATALOG[b_name], CORAL)]
    centers = [(w * 0.5, h * 0.25), (w * 0.5, h * 0.67)] if portrait else [(w * 0.27, h * 0.46), (w * 0.73, h * 0.46)]
    for (model, color), center in zip(sides, centers):
        glow(canvas, center, (520 if portrait else 560) * scale, color, 120)
    # Split line
    split = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(split)
    if portrait:
        sd.line([(0, h * 0.47), (w, h * 0.43)], fill=(255, 255, 255, 120), width=int(4 * scale))
    else:
        sd.line([(w * 0.53, 0), (w * 0.47, h)], fill=(255, 255, 255, 120), width=int(4 * scale))
    canvas.alpha_composite(split.filter(ImageFilter.GaussianBlur(1.2)))
    tile = 260 * scale
    for (model, color), (cx, cy) in zip(sides, centers):
        cards.logo_tile(canvas, cx - tile / 2, cy - tile / 2 - (110 if not portrait else 150) * scale, tile, model["lab"], model["name"])
        draw = ImageDraw.Draw(canvas)
        name_font = cards.fit_font(draw, model["name"], 64 * scale, (w * 0.42) if not portrait else w * 0.8)
        name_y = cy + tile / 2 - (80 if not portrait else 120) * scale
        draw.text((cx, name_y), model["name"], font=name_font, fill=WHITE + (255,), anchor="mt")
        draw.text((cx, name_y + 86 * scale), str(model["score"]), font=bold(150 * scale), fill=WHITE + (255,), anchor="mt")
    pixel_vs(canvas, w / 2, h * 0.455 if portrait else h * 0.46, 22 * scale)
    source_line(canvas, "Source: Artificial Analysis Intelligence Index · Nov 2026", 64 * scale, h - (60 if not portrait else 330) * scale, scale)
    slug = lambda text: re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")  # noqa: E731
    return save(canvas, f"duel-{slug(a_name)}-vs-{slug(b_name)}-{fmt}.png")


# --- 6/7. books and agents --------------------------------------------------------------------------

def context_books(fmt):
    canvas, a = load_render("books", fmt)
    w, h, portrait, scale = geometry(canvas)
    for key, label in (("one", "128K"), ("eight", "1M"), ("shelf", "10M")):
        pill(canvas, a[key], f"{label} tokens", 46 * scale, anchor="mb", outline=CYAN if key == "shelf" else None)
    return save(canvas, f"context-books-{fmt}.png")


def agent_team(fmt):
    canvas, a = load_render("agents", fmt)
    w, h, portrait, scale = geometry(canvas)
    for key, label in (("planner", "Planner"), ("coder", "Coder"), ("reviewer", "Reviewer")):
        pill(canvas, a[key], label, 42 * scale, anchor="mt")
    return save(canvas, f"agent-team-{fmt}.png")


# --- 8. open vs closed --------------------------------------------------------------------------------

def best_per_lab(weights, count=4):
    seen, picked = set(), []
    for m in sorted(DATA["catalog"], key=lambda m: -m["score"]):
        if m["weights"] == weights and m["lab"] not in seen:
            seen.add(m["lab"])
            picked.append(m)
    return picked[:count]


def open_vs_closed(fmt):
    canvas, a = load_render("locks", fmt)
    w, h, portrait, scale = geometry(canvas)
    groups = (("open", best_per_lab("open")), ("closed", best_per_lab("proprietary")))
    row_h = (66 if portrait else 70) * scale
    gap = 18 * scale
    col_w = w * (0.42 if portrait else 0.34)
    for key, models in groups:
        ax, ay = a[key]
        x0 = min(max(ax - col_w / 2, 30 * scale), w - col_w - 30 * scale)
        y = ay + 40 * scale
        panel_h = len(models) * row_h + (len(models) - 1) * gap + 40 * scale
        cards.frosted(canvas, (x0 - 20 * scale, y - 20 * scale, x0 + col_w + 20 * scale, y - 20 * scale + panel_h), int(22 * scale), alpha=150)
        for k, m in enumerate(models):
            model_row(canvas, x0, y + k * (row_h + gap), row_h, m["name"], scale, col_w, value=m["score"])
    source_line(canvas, "Source: Artificial Analysis · weights & Intelligence Index · Nov 2026", 64 * scale, h - (50 if not portrait else 330) * scale, scale)
    return save(canvas, f"open-vs-closed-{fmt}.png")


# --- 9. timeline ---------------------------------------------------------------------------------------

def timeline(fmt):
    canvas = cards.backdrop("glass_panels", fmt, 14, 190)
    w, h, portrait, scale = geometry(canvas)
    models = [CATALOG[name] for name in DATA["timeline_models"]]
    months = sorted({m["released"] for m in models})
    by_month = {month: [m for m in models if m["released"] == month] for month in months}
    line = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(line)
    head = bold(40 * scale)
    if not portrait:
        axis_y = h * 0.20
        xs = [w * (0.10 + 0.80 * (k + 0.5) / len(months)) for k in range(len(months))]
        col_w = w * 0.80 / len(months) - 30 * scale
        ld.line([(w * 0.06, axis_y), (w * 0.94, axis_y)], fill=CYAN + (220,), width=int(4 * scale))
        canvas.alpha_composite(line.filter(ImageFilter.GaussianBlur(3)))
        canvas.alpha_composite(line)
        draw = ImageDraw.Draw(canvas)
        row_h, gap = 62 * scale, 20 * scale
        for month, x in zip(months, xs):
            r = 14 * scale
            draw.ellipse([x - r, axis_y - r, x + r, axis_y + r], fill=CYAN + (255,), outline=WHITE + (255,), width=int(3 * scale))
            year, mon = month.split("-")
            draw.text((x, axis_y - 34 * scale), f"{MONTHS[int(mon) - 1]} {year}", font=head, fill=WHITE + (255,), anchor="mb")
            for k, m in enumerate(by_month[month]):
                model_row(canvas, x - col_w / 2, axis_y + 60 * scale + k * (row_h + gap), row_h, m["name"], scale, col_w)
    else:
        axis_x = w * 0.11
        top, bottom = h * 0.12, h * 0.78
        units = sum(len(v) for v in by_month.values()) + len(months) * 1.1
        unit = (bottom - top) / units
        ld.line([(axis_x, top - 20 * scale), (axis_x, bottom)], fill=CYAN + (220,), width=int(4 * scale))
        canvas.alpha_composite(line.filter(ImageFilter.GaussianBlur(3)))
        canvas.alpha_composite(line)
        draw = ImageDraw.Draw(canvas)
        y = top
        row_h = min(64 * scale, unit * 0.78)
        for month in months:
            r = 13 * scale
            draw.ellipse([axis_x - r, y - r, axis_x + r, y + r], fill=CYAN + (255,), outline=WHITE + (255,), width=int(3 * scale))
            year, mon = month.split("-")
            draw.text((axis_x + 34 * scale, y), f"{MONTHS[int(mon) - 1]} {year}", font=bold(36 * scale), fill=WHITE + (255,), anchor="lm")
            y += unit * 1.1
            for m in by_month[month]:
                model_row(canvas, axis_x + 34 * scale, y - row_h / 2, row_h, m["name"], scale, w * 0.86 - axis_x - 34 * scale)
                y += unit
    source_line(canvas, "Source: Artificial Analysis · release dates · Nov 2026", 64 * scale, h - (50 if not portrait else 300) * scale, scale)
    return save(canvas, f"timeline-2026-{fmt}.png")


# --- 10. podium -----------------------------------------------------------------------------------------

def podium(fmt):
    canvas, a = load_render("podium", fmt)
    w, h, portrait, scale = geometry(canvas)
    top3 = DATA["models"][:3]
    tile = (150 if not portrait else 130) * scale
    for place, m in zip(("p1", "p2", "p3"), top3):
        ax, ay = a[place]
        tile_y = ay - tile - 36 * scale
        cards.logo_tile(canvas, ax - tile / 2, tile_y, tile, m["lab"], m["name"])
        draw = ImageDraw.Draw(canvas)
        name_font = cards.fit_font(draw, m["name"], 40 * scale, (w * 0.30) if portrait else 340 * scale)
        draw.text((ax, tile_y - 18 * scale), m["name"], font=name_font, fill=WHITE + (255,), anchor="mb")
        draw.text((ax, tile_y - 72 * scale), str(m["score"]), font=bold(96 * scale), fill=WHITE + (255,), anchor="mb")
    source_line(canvas, "Source: Artificial Analysis Intelligence Index · Nov 2026", 64 * scale, h - (50 if not portrait else 330) * scale, scale)
    return save(canvas, f"podium-top3-{fmt}.png")


def main():
    for fmt in ("16x9", "9x16"):
        builders = [vram_tetris, price_vs_score, speed, context_books, agent_team, open_vs_closed, timeline, podium]
        builders += [lambda f, pair=pair: duel(f, *pair) for pair in DATA["duels"]]
        for builder in builders:
            try:
                print(builder(fmt))
            except FileNotFoundError as exc:
                print("skip", getattr(builder, "__name__", "duel"), fmt, exc)


if __name__ == "__main__":
    main()
