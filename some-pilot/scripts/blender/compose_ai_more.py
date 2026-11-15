"""Ten more AI graphics (one file per image). Names, logos and numbers only.

  extras/thumbnails/thumb-*.png                   1280x720 YouTube thumbnail backgrounds (models, duel, topics)
  extras/nameplates/<model>-<fmt>.png             transparent lower-third name plates, one per model
  extras/quant-ladder-<fmt>.png                   3D: one 32B model at FP16 / Q8 / Q4 / Q2 (file sizes)
  hardware/handheld/<fmt>/...                     3D open handheld (compose_hardware.py)
  extras/local-vs-cloud-<fmt>.png                 3D: mini PC on a desk vs server racks
  extras/cost-100-tasks-<fmt>[-transparent].png   cost per task x 100
  extras/token-conveyor-<fmt>.png                 3D: tokens in, tokens out (no text)
  extras/retro-ai-<fmt>.png                       3D: CRT with a pixel-art AI chip (no text)
  extras/glitch-<fmt>.png                         glitched AI chip frame for "AI got it wrong" posts (no text)
  extras/local-tokens-per-second-<fmt>[-transparent].png   llama.cpp speed by machine

    python scripts/blender/compose_ai_more.py
"""

import math
import random
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_ai_cards as cards  # noqa: E402
import compose_ai_extras as ex  # noqa: E402

GFX = cards.GFX
OUT = GFX / "extras"
DATA = ex.DATA
CATALOG = ex.CATALOG
CYAN, CORAL, WHITE, MUTED, NAVY = cards.CYAN, (242, 92, 60), cards.WHITE, cards.MUTED, cards.NAVY
SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def save(canvas, rel, keep_alpha=False):
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    (canvas if keep_alpha else canvas.convert("RGB")).save(path, optimize=True)
    return path


def geometry(canvas):
    return ex.geometry(canvas)


# --- 1. thumbnails ------------------------------------------------------------------------------------

THUMB = (1280, 720)


def cover(image, size):
    """Scale to cover and centre-crop."""
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((int(image.width * scale + 0.5), int(image.height * scale + 0.5)), Image.LANCZOS)
    x0, y0 = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return image.crop((x0, y0, x0 + size[0], y0 + size[1]))


def grade(image):
    """Thumbnail punch: a bit more contrast and colour, soft vignette."""
    image = ImageEnhance.Contrast(image.convert("RGB")).enhance(1.12)
    image = ImageEnhance.Color(image).enhance(1.15).convert("RGBA")
    w, h = image.size
    yy, xx = np.mgrid[0:h, 0:w]
    v = np.clip(np.hypot((xx - w / 2) / (w * 0.62), (yy - h / 2) / (h * 0.62)), 0, 1) ** 2.2
    shade = Image.fromarray((v * 150).astype(np.uint8))
    layer = Image.new("RGBA", image.size, (2, 4, 12, 0))
    layer.putalpha(shade)
    image.alpha_composite(layer)
    return image


def hardware_glow(machine):
    folder = GFX / "hardware" / machine / "16x9"
    base = Image.open(folder / "clean.png").convert("RGBA")
    for glow in sorted(folder.glob("glow-*.png")):
        base.alpha_composite(Image.open(glow).convert("RGBA"))
    return base


def thumbnails():
    made = []
    backdrop = Image.open(GFX / "backdrops" / "ai_core-16x9.png").convert("RGB").filter(ImageFilter.GaussianBlur(6))
    for name in [m["model"] for m in __import__("json").loads((cards.ROOT / "content" / "AI_MODELS_LINEUP.json").read_text(encoding="utf-8"))["models"]]:
        lab = CATALOG.get(name, {"lab": next(m["lab"] for m in __import__("json").loads((cards.ROOT / "content" / "AI_MODELS_LINEUP.json").read_text(encoding="utf-8"))["models"] if m["model"] == name)})["lab"]
        canvas = grade(cover(backdrop, THUMB))
        cx, cy, tile = 920, 360, 420
        ex.glow(canvas, (cx, cy), 330, CYAN, 150)
        cards.logo_tile(canvas, cx - tile / 2, cy - tile / 2, tile, lab, name)
        made.append(save(canvas, f"thumbnails/thumb-{slug(name)}.png"))
    for a_name, b_name in DATA["duels"]:
        canvas = Image.new("RGBA", THUMB, (4, 8, 20, 255))
        ex.glow(canvas, (320, 360), 420, CYAN, 140)
        ex.glow(canvas, (960, 360), 420, CORAL, 140)
        line = Image.new("RGBA", THUMB, (0, 0, 0, 0))
        ImageDraw.Draw(line).line([(672, 0), (608, 720)], fill=(255, 255, 255, 140), width=4)
        canvas.alpha_composite(line)
        for (name, x) in ((a_name, 320), (b_name, 960)):
            cards.logo_tile(canvas, x - 170, 360 - 170, 340, CATALOG[name]["lab"], name)
        ex.pixel_vs(canvas, 640, 360, 20)
        made.append(save(canvas, f"thumbnails/thumb-duel-{slug(a_name)}-vs-{slug(b_name)}.png"))
    topics = {
        "local-ai": lambda: hardware_glow("mini_pc"),
        "gpu": lambda: hardware_glow("gpu"),
        "handheld-ai": lambda: hardware_glow("handheld"),
        "vram": lambda: Image.open(GFX / "renders3d" / "vram" / "16x9" / "clean.png"),
        "quantization": lambda: Image.open(GFX / "renders3d" / "quant" / "16x9" / "clean.png"),
        "context-window": lambda: Image.open(GFX / "renders3d" / "books" / "16x9" / "clean.png"),
        "agents": lambda: Image.open(GFX / "renders3d" / "agents" / "16x9" / "clean.png"),
        "open-vs-closed": lambda: Image.open(GFX / "renders3d" / "locks" / "16x9" / "clean.png"),
        "local-vs-cloud": lambda: Image.open(GFX / "renders3d" / "localcloud" / "16x9" / "clean.png"),
        "retro-ai": lambda: Image.open(GFX / "renders3d" / "retro" / "16x9" / "clean.png"),
        "datacenter": lambda: Image.open(GFX / "backdrops" / "datacenter-16x9.png"),
    }
    for key, loader in topics.items():
        try:
            made.append(save(grade(cover(loader().convert("RGB"), THUMB)), f"thumbnails/thumb-{key}.png"))
        except FileNotFoundError as exc:
            print("skip thumb", key, exc)
    return made


# --- 2. name plates -----------------------------------------------------------------------------------

def nameplate(model, fmt):
    size = SIZES[fmt]
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    w, h, portrait, scale = geometry(canvas)
    item = CATALOG[model]
    draw = ImageDraw.Draw(canvas)
    tile = 92 * scale
    name_font = cards.bold(52 * scale)
    lab_font = cards.font(cards.FONT_TEXT, 28 * scale)
    text_w = max(draw.textlength(model, font=name_font), draw.textlength(item["lab"], font=lab_font))
    pad = 22 * scale
    pw = pad + 8 * scale + 18 * scale + tile + 26 * scale + text_w + pad * 1.6
    ph = tile + pad * 2
    if portrait:
        x0, y0 = (w - pw) / 2, h * 0.64
    else:
        x0, y0 = 90 * scale, h - 120 * scale - ph
    plate = Image.new("RGBA", size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=int(26 * scale), fill=NAVY + (222,), outline=(255, 255, 255, 46), width=max(1, int(2 * scale)))
    pd.rounded_rectangle([x0 + pad * 0.6, y0 + pad, x0 + pad * 0.6 + 8 * scale, y0 + ph - pad], radius=int(4 * scale), fill=CYAN + (255,))
    canvas.alpha_composite(plate)
    tx = x0 + pad + 26 * scale
    cards.logo_tile(canvas, tx, y0 + pad, tile, item["lab"], model)
    nx = tx + tile + 26 * scale
    draw = ImageDraw.Draw(canvas)
    draw.text((nx, y0 + ph / 2 + 4 * scale), model, font=name_font, fill=WHITE + (255,), anchor="ls")
    draw.text((nx, y0 + ph / 2 + 12 * scale), item["lab"], font=lab_font, fill=MUTED + (255,), anchor="lt")
    return save(canvas, f"nameplates/{slug(model)}-{fmt}.png", keep_alpha=True)


# --- 3/5/7/8. 3D composites ---------------------------------------------------------------------------

def quant_ladder(fmt):
    canvas, a = ex.load_render("quant", fmt)
    w, h, portrait, scale = geometry(canvas)
    for level in DATA["quant"]["levels"]:
        top = a[f"{level['label']}_top"]
        base = a[f"{level['label']}_base"]
        ex.pill(canvas, top, level["label"], 44 * scale, anchor="mb")
        ex.pill(canvas, (base[0], base[1] + 26 * scale), f"{level['gb']:.1f} GB", 32 * scale, anchor="mt", color=CYAN)
    ex.pill(canvas, (w / 2, h * (0.13 if portrait else 0.08)), DATA["quant"]["model"], 34 * scale, color=MUTED)
    return save(canvas, f"quant-ladder-{fmt}.png")


def local_vs_cloud(fmt):
    canvas, a = ex.load_render("localcloud", fmt)
    w, h, portrait, scale = geometry(canvas)
    ex.pill(canvas, a["local"], "Local", 46 * scale, anchor="mt", outline=CYAN)
    ex.pill(canvas, a["cloud"], "Cloud", 46 * scale, anchor="mt")
    return save(canvas, f"local-vs-cloud-{fmt}.png")


def plain_render(scene, name, fmt):
    canvas, _ = ex.load_render(scene, fmt)
    return save(canvas, f"{name}-{fmt}.png")


# --- 6. cost of 100 tasks ------------------------------------------------------------------------------

def cost_100(fmt):
    rows = []
    for name in DATA["cost100_models"]:
        m = CATALOG[name]
        total = m["cost_per_task_usd"] * 100
        rows.append({"name": name, "lab": m["lab"], "model": name, "score": total, "value_label": f"${total:,.0f}"})
    rows.sort(key=lambda r: -r["score"])
    canvas = cards.backdrop("glass_panels", fmt, 12, 185)
    w, h, portrait, scale = geometry(canvas)
    left, top, right, bottom = cards.safe_area(w, h, portrait, scale)
    if not portrait:
        left, right = w * 0.08, w * 0.92
    area = (left, top, right, bottom - 50 * scale)
    label = "Source: Artificial Analysis · cost per task × 100 · Nov 2026"
    cards.rating_rows(canvas, rows, area, scale, portrait, label if DATA.get("show_source", True) else None)
    out = save(canvas, f"cost-100-tasks-{fmt}.png")
    clear = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cards.rating_rows(clear, rows, area, scale, portrait, None)
    save(clear, f"cost-100-tasks-{fmt}-transparent.png", keep_alpha=True)
    return out


# --- 9. glitch frame -----------------------------------------------------------------------------------

def glitch(fmt):
    rng = random.Random(13)
    base = Image.open(GFX / "backdrops" / f"ai_core-{fmt}.png").convert("RGB")
    w, h = base.size
    arr = np.asarray(base).astype(np.int16)
    out = arr.copy()
    shift = int(w * 0.008)
    out[..., 0] = np.roll(arr[..., 0], shift, axis=1)
    out[..., 2] = np.roll(arr[..., 2], -shift, axis=1)
    for _ in range(26):
        y0 = rng.randrange(0, h - 10)
        band = rng.randrange(4, int(h * 0.035))
        dx = rng.choice([-1, 1]) * rng.randrange(int(w * 0.01), int(w * 0.07))
        out[y0:y0 + band] = np.roll(out[y0:y0 + band], dx, axis=1)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")
    blocks = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd_ = ImageDraw.Draw(blocks)
    cell = int(w * 0.012)
    for _ in range(90):
        x, y = rng.randrange(0, w // cell) * cell, rng.randrange(0, h // cell) * cell
        col = rng.choice([CORAL, CYAN, (255, 40, 60), (255, 255, 255)])
        bd_.rectangle([x, y, x + cell * rng.randint(1, 4), y + cell], fill=col + (rng.randint(60, 170),))
    img.alpha_composite(blocks)
    # Cracks radiating from an impact point
    crack = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(crack)
    cx, cy = w * 0.5, h * 0.42
    for k in range(9):
        angle = k / 9 * math.tau + rng.uniform(-0.2, 0.2)
        x, y = cx, cy
        pts = [(x, y)]
        for _ in range(rng.randint(5, 9)):
            step = rng.uniform(w * 0.02, w * 0.06)
            angle += rng.uniform(-0.45, 0.45)
            x, y = x + math.cos(angle) * step, y + math.sin(angle) * step
            pts.append((x, y))
        cd.line(pts, fill=(255, 70, 60, 230), width=max(2, int(w * 0.0018)))
    img.alpha_composite(crack.filter(ImageFilter.GaussianBlur(6)))
    img.alpha_composite(crack)
    lines = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for y in range(0, h, 3):
        ld.line([(0, y), (w, y)], fill=(0, 0, 0, 46))
    img.alpha_composite(lines)
    noise = Image.fromarray((np.random.default_rng(3).random((h, w)) * 40).astype(np.uint8))
    img = ImageChops.add(img.convert("RGB"), Image.merge("RGB", (noise, noise, noise)), scale=1.0, offset=-12).convert("RGBA")
    return save(img, f"glitch-{fmt}.png")


# --- 10. local tokens per second -------------------------------------------------------------------------

def local_speed(fmt):
    spec = DATA["local_speed"]
    rows = [{"name": d["name"], "sub": d["sub"], "lab": d["name"], "score": d["tps"], "value_label": f"{d['tps']:.0f} t/s"} for d in spec["devices"]]
    rows.sort(key=lambda r: -r["score"])
    canvas = cards.backdrop("datacenter", fmt, 12, 190)
    w, h, portrait, scale = geometry(canvas)
    left, top, right, bottom = cards.safe_area(w, h, portrait, scale)
    if not portrait:
        left, right = w * 0.08, w * 0.92
    area = (left, top, right, bottom - 50 * scale)
    cards.rating_rows(canvas, rows, area, scale, portrait, spec["source_label"] if DATA.get("show_source", True) else None, logos=False)
    out = save(canvas, f"local-tokens-per-second-{fmt}.png")
    clear = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cards.rating_rows(clear, rows, area, scale, portrait, None, logos=False)
    save(clear, f"local-tokens-per-second-{fmt}-transparent.png", keep_alpha=True)
    return out


def main(only=None):
    jobs = []
    for fmt in ("16x9", "9x16"):
        jobs += [lambda f=fmt: cost_100(f), lambda f=fmt: glitch(f), lambda f=fmt: local_speed(f),
                 lambda f=fmt: quant_ladder(f), lambda f=fmt: local_vs_cloud(f),
                 lambda f=fmt: plain_render("tokens", "token-conveyor", f), lambda f=fmt: plain_render("retro", "retro-ai", f)]
        jobs += [lambda f=fmt, m=m: nameplate(m, f) for m in CATALOG]
    jobs.append(thumbnails)
    for job in jobs:
        try:
            result = job()
            for path in (result if isinstance(result, list) else [result]):
                print(path)
        except FileNotFoundError as exc:
            print("skip", exc)


if __name__ == "__main__":
    main()
