"""Turn Blender beauty renders + component mattes into video-ready hardware graphics.

For every machine/format folder (clean.png, mask-ram.png, mask-ssd.png, mask-cpu.png):
  highlight-ram / -ssd / -cpu / -all .png   rest dimmed, component glowing, labelled callout
  glow-<part>.png                            transparent glow outline only (for editors)
  matte-<part>.png                           clean white-on-black matte (track/animate in editors)

    python scripts/blender/compose_hardware.py [renders_dir] [out_dir]
"""

import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

CYAN = (0, 196, 232)
CORAL = (242, 92, 60)
WHITE = (240, 246, 255)
LABELS = {"ram": ("RAM", ""), "cpu": ("CPU", ""), "ssd": ("SSD", "")}  # names only: the edit adds any copy
ORDER = ("ram", "cpu", "ssd")
FONT_BOLD = "C:/Windows/Fonts/bahnschrift.ttf"
FONT_TEXT = "C:/Windows/Fonts/segoeui.ttf"


def font(path, size, variation=None):
    face = ImageFont.truetype(path, size)
    if variation:
        try:
            face.set_variation_by_name(variation)
        except Exception:
            pass
    return face


def load_mask(path, size):
    mask = Image.open(path).convert("L").resize(size, Image.LANCZOS)
    return mask.point(lambda value: 255 if value > 127 else 0)


def glow_layer(mask, color, width):
    """Outline + soft bloom built from the matte edge."""
    grow = mask.filter(ImageFilter.MaxFilter(int(width * 0.6) * 2 + 1))
    shrink = mask.filter(ImageFilter.MinFilter(3))
    edge = ImageChops.subtract(grow, shrink)
    alpha = np.asarray(edge, dtype=np.float32) / 255
    for radius, amount in ((width * 0.6, 0.9), (width * 2.0, 0.6), (width * 5.0, 0.35)):
        blurred = np.asarray(edge.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255
        alpha = alpha + blurred * amount
    inner = np.asarray(mask.filter(ImageFilter.GaussianBlur(width * 2)), dtype=np.float32) / 255 * 0.07
    alpha = np.clip(alpha + inner, 0, 1)
    rgba = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    rgba[..., :3] = color
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def dimmed(image, keep_mask, amount=0.38):
    """Darken and slightly desaturate everything outside the highlighted parts."""
    base = np.asarray(image, dtype=np.float32)
    grey = base.mean(axis=2, keepdims=True)
    dim = (base * 0.7 + grey * 0.3) * amount
    keep = np.asarray(keep_mask.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)[..., None] / 255
    return Image.fromarray(np.clip(base * keep + dim * (1 - keep), 0, 255).astype(np.uint8))


def bbox_center(mask):
    box = mask.getbbox()
    return box, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def card_size(part, scale, numbered):
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    title, subtitle = LABELS[part]
    big = font(FONT_BOLD, int(54 * scale), "Bold")
    small = font(FONT_TEXT, int(24 * scale))
    pad = 22 * scale
    badge = (46 * scale) if numbered else 0
    return max(probe.textlength(title, font=big) + badge, probe.textlength(subtitle, font=small)) + pad * 2, (104 if subtitle else 80) * scale


def _overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def place_card(size, target, card, obstacles, taken, portrait):
    """Search positions around the target; avoid every component, other cards and platform UI zones."""
    w, h = size
    cw, ch = card
    tx0, ty0, tx1, ty1 = target
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    safe = (w * 0.05, h * (0.12 if portrait else 0.06), w * (0.86 if portrait else 0.95), h * (0.76 if portrait else 0.92))
    best = None
    for gap in (0.03, 0.06, 0.10, 0.16, 0.24):
        for angle in range(0, 360, 15):
            import math as _m

            dx, dy = _m.cos(_m.radians(angle)), _m.sin(_m.radians(angle))
            reach_x = (tx1 - tx0) / 2 + cw / 2 + gap * w
            reach_y = (ty1 - ty0) / 2 + ch / 2 + gap * h
            cx, cy = tcx + dx * reach_x, tcy + dy * reach_y
            box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
            penalty = 0.0
            if box[0] < safe[0] or box[1] < safe[1] or box[2] > safe[2] or box[3] > safe[3]:
                penalty += 1e9
            penalty += sum(_overlap(box, other) for other in obstacles) * 50
            penalty += sum(_overlap(box, other) for other in taken) * 200
            distance = _m.hypot(cx - tcx, cy - tcy)
            score = penalty + distance
            if best is None or score < best[0]:
                best = (score, box)
    return best[1]


def draw_callout(canvas, target, box, part, color, scale, index=None):
    draw = ImageDraw.Draw(canvas)
    title, subtitle = LABELS[part]
    left, top, right, bottom = box
    big = font(FONT_BOLD, int(54 * scale), "Bold")
    small = font(FONT_TEXT, int(24 * scale))
    pad = 22 * scale
    # Leader: from the card edge nearest the component to the component edge.
    tcx, tcy = (target[0] + target[2]) / 2, (target[1] + target[3]) / 2
    ccx, ccy = (left + right) / 2, (top + bottom) / 2
    end_x = min(max(ccx, target[0]), target[2])
    end_y = min(max(ccy, target[1]), target[3])
    start_x = min(max(tcx, left), right)
    start_y = min(max(tcy, top), bottom)
    draw.line([(start_x, start_y), (end_x, end_y)], fill=color + (230,), width=max(2, int(3 * scale)))
    r = 7 * scale
    draw.ellipse([end_x - r, end_y - r, end_x + r, end_y + r], fill=color + (255,))
    draw.rounded_rectangle([left, top, right, bottom], radius=18 * scale, fill=(6, 14, 34, 230), outline=color + (255,), width=max(2, int(3 * scale)))
    tx = left + pad
    if index is not None:
        badge_top = (top + bottom) / 2 - 17 * scale if not subtitle else top + pad * 0.85
        draw.rounded_rectangle([tx, badge_top, tx + 34 * scale, badge_top + 34 * scale], radius=8 * scale, fill=color + (255,))
        num = font(FONT_BOLD, int(26 * scale), "Bold")
        nw = draw.textlength(str(index), font=num)
        draw.text((tx + 17 * scale - nw / 2, badge_top + 2 * scale), str(index), font=num, fill=(6, 14, 34, 255))
        tx += 46 * scale
    title_y = top + pad * 0.55 if subtitle else (top + bottom) / 2 - 31 * scale
    draw.text((tx, title_y), title, font=big, fill=WHITE + (255,))
    if subtitle:
        draw.text((left + pad, top + pad * 0.55 + 60 * scale), subtitle, font=small, fill=(190, 214, 230, 255))


def compose(folder: Path, out: Path):
    clean = Image.open(folder / "clean.png").convert("RGB")
    size = clean.size
    portrait = size[1] > size[0]
    scale = size[0] / 1920 if not portrait else size[0] / 1080 * 0.82
    masks = {part: load_mask(folder / f"mask-{part}.png", size) for part in ORDER if (folder / f"mask-{part}.png").exists()}
    out.mkdir(parents=True, exist_ok=True)
    clean.save(out / "clean.png")
    width = max(4, size[0] / 260)
    for part, mask in masks.items():
        mask.save(out / f"matte-{part}.png")
        glow_layer(mask, CYAN, width).save(out / f"glow-{part}.png")
    for selection in [(part,) for part in masks] + [tuple(masks)]:
        keep = Image.new("L", size, 0)
        for part in selection:
            keep = ImageChops.lighter(keep, masks[part])
        canvas = dimmed(clean, keep, 0.42 if len(selection) == 1 else 0.55).convert("RGBA")
        for part in selection:
            canvas = Image.alpha_composite(canvas, glow_layer(masks[part], CYAN, width))
        taken = []
        obstacles = [masks[part].getbbox() for part in masks]
        for part in sorted(selection, key=ORDER.index):
            target = masks[part].getbbox()
            numbered = len(selection) > 1
            box = place_card(size, target, card_size(part, scale, numbered), obstacles, taken, portrait)
            taken.append(box)
            draw_callout(canvas, target, box, part, CYAN, scale, index=(ORDER.index(part) + 1) if numbered else None)
        name = "highlight-all" if len(selection) > 1 else f"highlight-{selection[0]}"
        canvas.convert("RGB").save(out / f"{name}.png", optimize=True)


def main():
    here = Path(__file__).resolve().parent
    renders = Path(sys.argv[1]) if len(sys.argv) > 1 else here.parents[1] / "assets" / "graphics" / "ai" / "hardware" / "renders"
    out_root = Path(sys.argv[2]) if len(sys.argv) > 2 else here.parents[1] / "assets" / "graphics" / "ai" / "hardware"
    for folder in sorted(path for path in renders.glob("*/*") if (path / "clean.png").exists()):
        machine, fmt = folder.parent.name, folder.name
        compose(folder, out_root / machine / fmt)
        print(out_root / machine / fmt)


if __name__ == "__main__":
    main()
