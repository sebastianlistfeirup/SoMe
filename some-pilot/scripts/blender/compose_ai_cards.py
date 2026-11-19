"""AI graphics with names, logos and numbers only (no explanatory copy): the channel adds its own titles in the edit.

  cards/models-lineup-<fmt>.png            frontier models: logo + name (content/AI_MODELS_LINEUP.json)
  cards/ratings-models-<fmt>.png           top 10 models by score       (content/AI_RATINGS.json)
  cards/ratings-labs-<fmt>.png             best score per lab           (content/AI_RATINGS.json)
  cards/checklist-local-ai-<fmt>.png       RAM / CPU / SSD on the mini PC
  ...-transparent.png                      ratings without background, for animating in the editor

Logos: assets/brand/ai-logos/<model-slug>.png, else <lab-slug>.png, else a monogram tile.
9:16 output keeps the right-hand platform buttons and the bottom fifth clear.

    python scripts/blender/compose_ai_cards.py
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_hardware as hw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GFX = ROOT / "assets" / "graphics" / "ai"
LOGOS = ROOT / "assets" / "brand" / "ai-logos"
CYAN = (0, 196, 232)
WHITE = (240, 246, 255)
MUTED = (150, 178, 198)
NAVY = (6, 14, 34)
FONT_BOLD = "C:/Windows/Fonts/bahnschrift.ttf"
FONT_TEXT = "C:/Windows/Fonts/segoeui.ttf"
FONT_TEXT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"


def font(path, size, variation=None):
    face = ImageFont.truetype(path, int(size))
    if variation:
        try:
            face.set_variation_by_name(variation)
        except Exception:
            pass
    return face


def bold(size):
    return font(FONT_BOLD, size, "Bold")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def fit_font(draw, text, size, max_width, maker=bold, floor=14):
    face = maker(size)
    while draw.textlength(text, font=face) > max_width and face.size > floor:
        face = maker(face.size - 2)
    return face


def frosted(canvas, box, radius, tint=NAVY, alpha=170, outline=None, width=2):
    """Frosted-glass card: blurred backdrop + tint + hairline outline."""
    x0, y0, x1, y1 = [int(v) for v in box]
    region = canvas.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(18))
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, region.width - 1, region.height - 1], radius=radius, fill=255)
    canvas.paste(region, (x0, y0), mask)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=tint + (alpha,),
                                              outline=(outline + (255,)) if outline else (255, 255, 255, 38), width=width)
    canvas.alpha_composite(overlay)


# Model name prefix -> logo file of that model family (assets/brand/ai-logos/<slug>.png).
FAMILIES = [("Claude", "claude"), ("Gemini", "gemini"), ("GPT", "openai"), ("Grok", "xai"), ("Qwen", "qwen"), ("Kimi", "kimi"),
            ("GLM", "z-ai"), ("Muse", "meta-ai"), ("Mistral", "mistral-ai"), ("DeepSeek", "deepseek")]


def family(model):
    return next((name for prefix, name in FAMILIES if model and model.startswith(prefix)), None)


def logo_path(lab, model=None, prefer="model"):
    """Models: model file, family logo, lab logo. Labs (prefer='lab'): lab logo, then the family of its best model
    (labs whose only logo is a wide wordmark use their model family's symbol)."""
    model_files = ([slug(model)] if model else []) + ([family(model)] if family(model) else [])
    names = [slug(lab)] + model_files if prefer == "lab" else model_files + [slug(lab)]
    return next((LOGOS / f"{name}.png" for name in names if (LOGOS / f"{name}.png").exists()), None)


def logo_tile(canvas, x, y, size, lab, model=None, prefer="model"):
    """White rounded tile (works for dark and light logos alike) with the logo, or a monogram fallback."""
    tile = Image.new("RGBA", (int(size), int(size)), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.rounded_rectangle([0, 0, tile.width - 1, tile.height - 1], radius=int(size * 0.24), fill=(246, 249, 252, 255))
    path = logo_path(lab, model, prefer)
    if path:
        logo = Image.open(path).convert("RGBA")
        logo.thumbnail((int(size * 0.68), int(size * 0.68)), Image.LANCZOS)
        tile.alpha_composite(logo, ((tile.width - logo.width) // 2, (tile.height - logo.height) // 2))
    else:
        initials = "".join(word[0] for word in re.split(r"[\s.\-]+", lab) if word)[:2].upper()
        face = bold(size * (0.46 if len(initials) < 2 else 0.38))
        box = td.textbbox((0, 0), initials, font=face)
        td.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), initials, font=face, fill=NAVY + (255,))
    canvas.alpha_composite(tile, (int(x), int(y)))


def backdrop(name, fmt, blur, darken):
    """Blurred, darkened backdrop so names and bars carry the frame."""
    image = Image.open(GFX / "backdrops" / f"{name}-{fmt}.png").convert("RGB")
    scale = image.width / (1080 if image.height > image.width else 1920)
    image = image.filter(ImageFilter.GaussianBlur(blur * scale)).convert("RGBA")
    image.alpha_composite(Image.new("RGBA", image.size, (2, 6, 18, darken)))
    return image


def safe_area(w, h, portrait, scale):
    """(left, top, right, bottom) usable for content."""
    if portrait:
        return 64 * scale, h * 0.12, w * 0.86, h * 0.78
    return 110 * scale, 90 * scale, w - 110 * scale, h - 90 * scale


def save(canvas, name, keep_alpha=False):
    out = GFX / "cards" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    (canvas if keep_alpha else canvas.convert("RGB")).save(out, optimize=True)
    return out


# --- model line-up ---------------------------------------------------------------------------

def models_lineup(fmt):
    data = json.loads((ROOT / "content" / "AI_MODELS_LINEUP.json").read_text(encoding="utf-8"))
    canvas = backdrop("glass_panels", fmt, 6, 110)
    w, h = canvas.size
    portrait = h > w
    scale = (w / 1080) if portrait else (w / 1920)
    left, top, right, bottom = safe_area(w, h, portrait, scale)
    columns = 2 if portrait else 5
    rows = (len(data["models"]) + columns - 1) // columns
    gap = 24 * scale
    card_w = (right - left - gap * (columns - 1)) / columns
    card_h = min(250 * scale, (bottom - top - gap * (rows - 1)) / rows)
    y_start = top + ((bottom - top) - (rows * card_h + (rows - 1) * gap)) / 2
    for index, item in enumerate(data["models"]):
        col, row = index % columns, index // columns
        x0 = left + col * (card_w + gap)
        y0 = y_start + row * (card_h + gap)
        frosted(canvas, (x0, y0, x0 + card_w, y0 + card_h), int(22 * scale))
        draw = ImageDraw.Draw(canvas)
        if portrait:
            tile = card_h * 0.52
            logo_tile(canvas, x0 + 22 * scale, y0 + (card_h - tile) / 2, tile, item["lab"], item["model"])
            tx = x0 + 22 * scale + tile + 20 * scale
            name_font = fit_font(draw, item["model"], 36 * scale, x0 + card_w - tx - 18 * scale)
            box = draw.textbbox((0, 0), item["model"], font=name_font)
            draw.text((tx, y0 + (card_h - (box[3] - box[1])) / 2 - box[1]), item["model"], font=name_font, fill=WHITE + (255,))
        else:
            tile = card_h * 0.42
            logo_tile(canvas, x0 + (card_w - tile) / 2, y0 + card_h * 0.16, tile, item["lab"], item["model"])
            name_font = fit_font(draw, item["model"], 38 * scale, card_w - 40 * scale)
            tw = draw.textlength(item["model"], font=name_font)
            draw.text((x0 + (card_w - tw) / 2, y0 + card_h * 0.68), item["model"], font=name_font, fill=WHITE + (255,))
    return save(canvas, f"models-lineup-{fmt}.png")


# --- ratings ---------------------------------------------------------------------------------

def rating_rows(canvas, rows, area, scale, portrait, source_label=None, logos=True):
    """Ranked horizontal bars from a zero baseline. Single series: one hue, no legend, value at the bar end."""
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = area
    row_h = (bottom - top) / len(rows)
    axis_max = max(row["score"] for row in rows)
    rank_w = 56 * scale
    tile = min(row_h * 0.62, 70 * scale)
    score_font = bold(36 * scale if portrait else 40 * scale)
    value_text = [row.get("value_label", str(row["score"])) for row in rows]
    score_w = max(draw.textlength(text, font=score_font) for text in value_text + ["00"]) + 20 * scale
    name_w = 430 * scale
    rank_font = bold(30 * scale)
    sub_font = font(FONT_TEXT, 22 * scale)
    for index, row in enumerate(rows):
        cy = top + index * row_h + row_h / 2
        rb = draw.textbbox((0, 0), str(index + 1), font=rank_font)
        draw.text((left, cy - (rb[3] - rb[1]) / 2 - rb[1]), str(index + 1), font=rank_font, fill=MUTED + (255,))
        tx = left + rank_w
        if logos:
            logo_tile(canvas, tx, cy - tile / 2, tile, row["lab"], row.get("model"), row.get("prefer", "model"))
            tx += tile + 22 * scale
        label = row["name"]
        if portrait:
            name_font = fit_font(draw, label, 34 * scale, right - tx - score_w)
            nb = draw.textbbox((0, 0), label, font=name_font)
            name_y = cy - row_h * 0.36 - nb[1]
            draw.text((tx, name_y), label, font=name_font, fill=WHITE + (255,))
            if row.get("sub"):
                draw.text((tx + draw.textlength(label, font=name_font) + 14 * scale, name_y + nb[1] + (nb[3] - nb[1]) - 24 * scale),
                          row["sub"], font=sub_font, fill=MUTED + (255,))
            bar_h = max(10 * scale, row_h * 0.20)
            bar_y0 = cy + row_h * 0.08
            bar_x0 = tx
        else:
            name_font = fit_font(draw, label, 38 * scale, name_w - 20 * scale)
            nb = draw.textbbox((0, 0), label, font=name_font)
            name_y = cy - (nb[3] - nb[1]) / 2 - nb[1] - (13 * scale if row.get("sub") else 0)
            draw.text((tx, name_y), label, font=name_font, fill=WHITE + (255,))
            if row.get("sub"):
                draw.text((tx, name_y + nb[3] + 6 * scale), row["sub"], font=sub_font, fill=MUTED + (255,))
            bar_h = max(12 * scale, row_h * 0.34)
            bar_y0 = cy - bar_h / 2
            bar_x0 = tx + name_w
        bar_w_max = right - score_w - bar_x0
        length = bar_w_max * row["score"] / axis_max
        radius = min(6 * scale, bar_h / 2)
        track = Image.new("RGBA", canvas.size, (0, 0, 0, 0))  # translucent: must be blended, not written
        ImageDraw.Draw(track).rounded_rectangle([bar_x0, bar_y0, bar_x0 + bar_w_max, bar_y0 + bar_h], radius=radius, fill=(255, 255, 255, 22))
        canvas.alpha_composite(track)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([bar_x0, bar_y0, bar_x0 + length, bar_y0 + bar_h], radius=radius, fill=CYAN + (255,))
        sb = draw.textbbox((0, 0), value_text[index], font=score_font)
        draw.text((bar_x0 + length + 14 * scale, bar_y0 + bar_h / 2 - (sb[3] - sb[1]) / 2 - sb[1]), value_text[index],
                  font=score_font, fill=WHITE + (255,))
    if source_label:
        draw.text((left, bottom + 26 * scale), source_label, font=font(FONT_TEXT, 20 * scale), fill=MUTED + (255,))


def ratings(fmt, kind):
    data = json.loads((ROOT / "content" / "AI_RATINGS.json").read_text(encoding="utf-8"))
    if kind == "models":
        rows = [{"name": m["name"], "lab": m["lab"], "model": m["name"], "score": m["score"]} for m in data["models"]]
        source, bg = data["source_label_models"], "datacenter"
    else:
        rows = [{"name": lab["name"], "lab": lab["name"], "sub": lab["best_model"], "model": lab["best_model"], "prefer": "lab",
                 "score": lab["score"]} for lab in data["labs"]]
        source, bg = data["source_label_labs"], "ai_core"
    source = source if data.get("show_source", True) else None
    canvas = backdrop(bg, fmt, 10, 175)
    w, h = canvas.size
    portrait = h > w
    scale = (w / 1080) if portrait else (w / 1920)
    left, top, right, bottom = safe_area(w, h, portrait, scale)
    if not portrait:
        left, right = w * 0.10, w * 0.90
    area = (left, top, right, bottom - 50 * scale)
    rating_rows(canvas, rows, area, scale, portrait, source)
    out = save(canvas, f"ratings-{kind}-{fmt}.png")
    clear = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rating_rows(clear, rows, area, scale, portrait, None)
    save(clear, f"ratings-{kind}-{fmt}-transparent.png", keep_alpha=True)
    return out


# --- local AI checklist -----------------------------------------------------------------------

CHECKLIST = [("RAM", "32 GB+"), ("CPU", "NPU / iGPU"), ("SSD", "NVMe · 1 TB+")]


def number_badge(canvas, x, y, number, scale):
    draw = ImageDraw.Draw(canvas)
    r = 30 * scale
    draw.ellipse([x - r - 5 * scale, y - r - 5 * scale, x + r + 5 * scale, y + r + 5 * scale], fill=NAVY + (200,))
    draw.ellipse([x - r, y - r, x + r, y + r], fill=CYAN + (255,))
    face = bold(38 * scale)
    box = draw.textbbox((0, 0), str(number), font=face)
    draw.text((x - (box[2] - box[0]) / 2 - box[0], y - (box[3] - box[1]) / 2 - box[1]), str(number), font=face, fill=NAVY + (255,))


def checklist(fmt):
    src = GFX / "hardware" / "mini_pc" / fmt
    clean = Image.open(src / "clean.png").convert("RGB")
    w, h = clean.size
    portrait = h > w
    scale = (w / 1080) if portrait else (w / 1920)
    parts = ("ram", "cpu", "ssd")
    masks = {part: Image.open(src / f"matte-{part}.png").convert("L") for part in parts}
    keep = Image.new("L", clean.size, 0)
    for mask in masks.values():
        keep = Image.composite(mask, keep, mask)
    lit = hw.dimmed(clean, keep, 0.62).convert("RGBA")
    for part in parts:
        lit.alpha_composite(Image.open(src / f"glow-{part}.png").convert("RGBA"))
    # Move the machine out from under the list column.
    dx, dy = (0, int(h * 0.08)) if portrait else (int(w * 0.24), 0)
    canvas = Image.new("RGBA", (w, h), (4, 8, 20, 255))
    strip = lit.crop((0, 0, 4, h)).resize((max(dx, 1), h)) if dx else lit.crop((0, 0, w, 4)).resize((w, max(dy, 1)))
    canvas.paste(strip.filter(ImageFilter.GaussianBlur(20)), (0, 0))
    canvas.paste(lit, (dx, dy))
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    if portrait:
        depth = h * 0.40
        for i in range(int(depth)):
            sd.line([(0, i), (w, i)], fill=(2, 6, 18, int(235 * (1 - i / depth) ** 0.9)))
    else:
        for i in range(int(w * 0.48)):
            sd.line([(i, 0), (i, h)], fill=(2, 6, 18, int(240 * (1 - i / (w * 0.48)) ** 0.85)))
    canvas.alpha_composite(shade)
    for number, part in enumerate(parts, start=1):
        x0, y0, _x1, _y1 = masks[part].getbbox()
        number_badge(canvas, x0 + dx + 6 * scale, y0 + dy + 6 * scale, number, scale)
    left = 90 * scale if not portrait else 64 * scale
    row_h, gap = 132 * scale, 22 * scale
    panel_w = w * (0.74 if portrait else 0.34)
    total = len(CHECKLIST) * row_h + (len(CHECKLIST) - 1) * gap
    y = h * 0.12 if portrait else (h - total) / 2
    for index, (part, spec) in enumerate(CHECKLIST):
        y0 = y + index * (row_h + gap)
        frosted(canvas, (left, y0, left + panel_w, y0 + row_h), int(22 * scale))
        draw = ImageDraw.Draw(canvas)
        box = 64 * scale
        bx, by = left + 30 * scale, y0 + (row_h - box) / 2
        draw.rounded_rectangle([bx, by, bx + box, by + box], radius=14 * scale, fill=CYAN + (255,))
        num = bold(42 * scale)
        nb = draw.textbbox((0, 0), str(index + 1), font=num)
        draw.text((bx + (box - (nb[2] - nb[0])) / 2 - nb[0], by + (box - (nb[3] - nb[1])) / 2 - nb[1]), str(index + 1), font=num, fill=NAVY + (255,))
        tx = bx + box + 30 * scale
        head = bold(58 * scale)
        hb = draw.textbbox((0, 0), part, font=head)
        draw.text((tx, y0 + (row_h - (hb[3] - hb[1])) / 2 - hb[1]), part, font=head, fill=WHITE + (255,))
        spec_x = tx + draw.textlength(part, font=head) + 26 * scale
        spec_font = fit_font(draw, spec, 40 * scale, left + panel_w - spec_x - 24 * scale, maker=lambda s: font(FONT_TEXT_BOLD, s))
        sb = draw.textbbox((0, 0), spec, font=spec_font)
        draw.text((spec_x, y0 + (row_h - (sb[3] - sb[1])) / 2 - sb[1]), spec, font=spec_font, fill=CYAN + (255,))
    return save(canvas, f"checklist-local-ai-{fmt}.png")


if __name__ == "__main__":
    for fmt in ("16x9", "9x16"):
        for builder in (models_lineup, lambda f: ratings(f, "models"), lambda f: ratings(f, "labs"), checklist):
            print(builder(fmt))
