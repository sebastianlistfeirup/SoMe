import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import get_settings
from app.pipeline.approvals import sha256_file

ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "assets" / "brand" / "pixel-and-parameters-primary-logo-v1.png"
OUT = get_settings().data_dir / "brand-idents"
TARGET = OUT / "approved-ident.mp4"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf").is_file() else str(ROOT.parent / ".codex_tmp" / "DejaVuSans-Bold.ttf")
FPS = 30
DURATION = 3.5
W, H = 1080, 1920
IMPACT = 1.05


def centered(draw, text, y, face, fill):
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((draw._image.width - (box[2] - box[0])) // 2, y), text, font=face, fill=fill)


def extract_p_sprites():
    source = Image.open(LOGO).convert("RGBA")
    pixels = np.array(source)
    alpha = pixels[:, :, 3] > 20
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    yy, xx = np.mgrid[0:source.height, 0:source.width]
    white_cyan_slider = (red > 170) & (green > 170) & (blue > 170) & (yy > 420) & (yy < 650) & (xx > 475) & (xx < 950)
    cyan_color = (blue > 100) & (green > 100) & (red < 100)
    coral = (red > 150) & (green < 200) & (blue < 180) & (xx < 650) & (yy < 975)
    cyan = alpha & (xx > 350) & (yy > 335) & (yy < 975) & (cyan_color | white_cyan_slider | ((yy >= 730) & ~coral))
    dark = alpha & ~cyan & ~coral & (yy < 730)
    sprites = []
    origins = []
    for mask in (dark, cyan, coral & (yy < 500), coral & (yy >= 500)):
        layer = source.copy()
        layer.putalpha(Image.fromarray((mask * 255).astype("uint8")))
        box = layer.getbbox()
        sprites.append(layer.crop(box))
        origins.append((box[0] - 150, box[1] - 65))
    return sprites, origins


(DARK, CYAN, CORAL_TOP, CORAL_BOTTOM), (DARK_ORIGIN, CYAN_ORIGIN, CORAL_TOP_ORIGIN, CORAL_BOTTOM_ORIGIN) = extract_p_sprites()
FULL_LOGO = Image.open(LOGO).convert("RGBA").crop((150, 65, 1100, 975))


def resize_sprite(sprite, factor):
    return sprite.resize((max(1, round(sprite.width * factor)), max(1, round(sprite.height * factor))), Image.Resampling.LANCZOS)


def paste_with_alpha(image, sprite, position, alpha):
    if alpha <= 0:
        return
    sprite.putalpha(sprite.getchannel("A").point(lambda value: round(value * alpha)))
    image.paste(sprite, (round(position[0]), round(position[1])), sprite)


def collision_offsets(t):
    start, duration = 0.12, IMPACT - 0.12
    if t < IMPACT:
        p = min(1.0, max(0.0, (t - start) / duration))
        eased = 1 - (1 - p) ** 5
        return (-900 * (1 - eased) + 26 * eased, 900 * (1 - eased) - 26 * eased)
    settle = min(1.0, (t - IMPACT) / 0.52)
    spring = math.sin(settle * math.pi * 3) * (1 - settle) * 23
    return (26 * (1 - settle) - spring, -26 * (1 - settle) + spring)


def impact_effect(image, t):
    p = (t - IMPACT) / 0.52
    if not 0 < p < 1:
        return
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay, "RGBA")
    radius = round(24 + p * 150)
    alpha = round(180 * (1 - p) ** 2)
    center = (557, 687) if W == 1080 else (round(W * 0.515), round(H * 0.358))
    draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=(70, 235, 255, alpha), width=max(2, round(7 * (1 - p))))
    for index in range(10):
        angle = index * math.tau / 10
        distance = 30 + p * (105 + (index % 2) * 35)
        x = center[0] + math.cos(angle) * distance
        y = center[1] + math.sin(angle) * distance
        size = 5 + index % 3 * 2
        draw.rectangle((x - size / 2, y - size / 2, x + size / 2, y + size / 2), fill=(255, 111, 88, alpha))
    image.paste(overlay, (0, 0), overlay)


def frame(frame_index):
    global OUTRO
    p = frame_index / round(DURATION * FPS - 1)
    t = frame_index / FPS
    landscape = W == 1920
    image = Image.new("RGB", (W, H), "#030814")
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(H):
        blend = y / (H - 1)
        color = (3 + round(8 * blend), 8 + round(17 * blend), 20 + round(27 * blend), 255)
        draw.line((0, y, W, y), fill=color)
    grid = 90 if landscape else 82
    shift = round((p * grid * (-1 if OUTRO else 1)) % grid)
    for x in range(-grid + shift, W, grid):
        draw.line((x, 0, x, H), fill=(25, 239, 255, 20), width=1)
    for y in range(-grid + shift, H, grid):
        draw.line((0, y, W, y), fill=(25, 239, 255, 15), width=1)
    for index in range(12):
        if index % 2 and t < 1.16:
            continue
        phase = (p * (1.3 + index * 0.03) + index * 0.083) % 1
        x = round(phase * (W + 180) - 90)
        y = round(H * (0.16 + 0.68 * ((index * 0.31) % 1)))
        size = 18 + (index % 3) * 10
        color = (255, 91, 76, 150) if index % 2 else (37, 231, 255, 145)
        draw.rectangle((x, y, x + size, y + size), fill=color)
    wave_y = round(H * (0.67 if landscape else 0.72))
    points = []
    for x in range(0, W + 1, 18):
        yy = wave_y + math.sin((x / W) * math.pi * 5 + p * math.pi * 4) * (25 if landscape else 34)
        points.append((x, yy))
    draw.line(points, fill=(37, 231, 255, 95), width=4)
    reveal = min(1.0, max(0.0, p / 0.18)) if OUTRO else min(1.0, max(0.0, (p - 0.08) / 0.24))
    fade = min(1.0, max(0.0, (1 - p) / 0.12))
    alpha = reveal * fade
    scale = 0.78 + 0.22 * (1 - (1 - reveal) ** 3)
    mark_y = round(H * (0.21 if landscape else 0.29))
    logo_width = 310 if landscape else 380
    factor = logo_width / 950 * scale
    if t >= 1.72:
        mark = FULL_LOGO.resize((round(FULL_LOGO.width * factor), round(FULL_LOGO.height * factor)), Image.Resampling.LANCZOS)
        paste_with_alpha(image, mark, ((W - mark.width) // 2, mark_y), alpha)
    else:
        dark_offset, cyan_offset = collision_offsets(t)
        dark_offset *= W / 1080
        cyan_offset *= W / 1080
        bump = 1 + math.sin(min(1.0, max(0.0, (t - IMPACT) / 0.35)) * math.pi) * 0.025 if t >= IMPACT else 1
        dark = resize_sprite(DARK, factor * bump)
        cyan = resize_sprite(CYAN, factor * bump)
        dark_x = (W - logo_width * scale) / 2 + DARK_ORIGIN[0] * factor + dark_offset
        dark_y = mark_y + DARK_ORIGIN[1] * factor
        cyan_x = (W - logo_width * scale) / 2 + CYAN_ORIGIN[0] * factor + cyan_offset
        cyan_y = mark_y + CYAN_ORIGIN[1] * factor
        paste_with_alpha(image, cyan, (cyan_x, cyan_y), alpha)
        paste_with_alpha(image, dark, (dark_x, dark_y), alpha)
        for sprite, origin, start, angle in ((CORAL_TOP, CORAL_TOP_ORIGIN, 1.16, -14), (CORAL_BOTTOM, CORAL_BOTTOM_ORIGIN, 1.25, 12)):
            pop = min(1.0, max(0.0, (t - start) / 0.48))
            if pop > 0:
                spring = 1 + 2.70158 * (pop - 1) ** 3 + 1.70158 * (pop - 1) ** 2
                hover = -12 * (1 - pop) + math.sin(pop * math.pi * 2) * (1 - pop) * 5
                base_width = sprite.width * factor
                base_height = sprite.height * factor
                coral = resize_sprite(sprite, factor * spring).rotate(angle * (1 - pop), resample=Image.Resampling.BICUBIC, expand=True)
                coral_x = (W - logo_width * scale) / 2 + origin[0] * factor + (base_width - coral.width) / 2
                coral_y = mark_y + origin[1] * factor + (base_height - coral.height) / 2 + hover
                glow = coral.copy()
                glow.putalpha(glow.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda value: round(value * 0.55)))
                paste_with_alpha(image, glow, (coral_x, coral_y), alpha * min(1.0, pop * 5) * 0.65)
                paste_with_alpha(image, coral, (coral_x, coral_y), alpha * min(1.0, pop * 5))
        impact_effect(image, t)
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = ImageFont.truetype(FONT, 74 if landscape else 61)
    sub_font = ImageFont.truetype(FONT, 26 if landscape else 30)
    title_y = round(H * (0.60 if landscape else 0.57))
    centered(draw, "PIXEL & PARAMETERS", title_y, title_font, (255, 255, 255, round(255 * alpha)))
    sub_y = title_y + (102 if landscape else 112)
    centered(draw, "FOLLOW FOR MORE" if OUTRO else "GAMING CULTURE  ×  AI", sub_y, sub_font, (88, 239, 255, round(235 * alpha)))
    track_y = sub_y + (70 if landscape else 86)
    track_w = 420 if landscape else 520
    left = (W - track_w) // 2
    draw.rounded_rectangle((left, track_y, left + track_w, track_y + 8), radius=4, fill=(255, 255, 255, 90))
    knob_x = left + round(track_w * (0.12 + 0.76 * (1 - (1 - min(1, p * 1.4)) ** 3)))
    draw.ellipse((knob_x - 13, track_y - 9, knob_x + 13, track_y + 17), fill=(255, 91, 76, 235))
    return image.convert("RGB")


def audio():
    rate = 48000
    t = np.arange(math.ceil(DURATION * rate), dtype=np.float64) / rate
    rng = np.random.default_rng(1701)
    envelope = np.minimum(np.clip(t / 0.55, 0, 1), np.clip((DURATION - t) / 0.45, 0, 1))
    root = 55.0
    tone = (
        0.025 * np.sin(2 * np.pi * root * t)
        + 0.015 * np.sin(2 * np.pi * root * 1.5 * t + 0.2)
        + 0.01 * np.sin(2 * np.pi * root * 2.0 * t + 0.7)
    ) * envelope
    whoosh = rng.standard_normal(len(t)) * np.exp(-((t - 0.75) / 0.42) ** 2) * 0.055
    local = np.maximum(0, t - IMPACT)
    impact = (t >= IMPACT) * np.sin(2 * np.pi * 78 * local) * np.exp(-local * 8) * 0.22
    blips = np.zeros_like(t)
    for at, frequency in ((0.38, 880), (0.62, 1320), (2.72, 660)):
        start = np.maximum(0, t - at)
        blips += (t >= at) * np.sin(2 * np.pi * frequency * start) * np.exp(-start * 28) * 0.07
    mono = np.tanh((tone + whoosh + impact + blips) * 1.7) * 0.72
    samples = np.column_stack((mono * 0.97, mono))
    click = (t >= IMPACT) * (
        0.16 * np.sin(2 * np.pi * 1180 * local) * np.exp(-local * 32)
        + 0.08 * np.sin(2 * np.pi * 1760 * local) * np.exp(-local * 46)
    )
    click += (t >= IMPACT) * np.random.default_rng(105).normal(0, 0.035, len(t)) * np.exp(-local * 80)
    samples[:, 0] += click * 0.96
    samples[:, 1] += click
    path = OUT / ".original-intro-collision.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def render_ident(mode: str, outro: bool, target: Path) -> Path:
    global W, H, TARGET, OUT, OUTRO
    if mode not in {"vertical", "landscape"}:
        raise ValueError("unsupported_ident_mode")
    W, H = ((1920, 1080) if mode == "landscape" else (1080, 1920))
    OUTRO = outro
    TARGET = target
    OUT = get_settings().data_dir / "brand-idents"
    OUT.mkdir(parents=True, exist_ok=True)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    sound = audio()
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(sound), "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac",
        "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart", str(TARGET),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in range(round(DURATION * FPS)):
        process.stdin.write(frame(index).tobytes())
    process.stdin.close()
    error = process.stderr.read().decode(errors="replace")
    if process.wait():
        raise RuntimeError(error)
    sound.unlink()
    return TARGET


def approved_ident(mode: str, outro: bool) -> Path:
    out = get_settings().data_dir / "brand-idents"
    out.mkdir(parents=True, exist_ok=True)
    version = sha256_file(str(LOGO))[:12] + sha256_file(str(Path(__file__)))[:12]
    target = out / f"{mode}-{'outro' if outro else 'intro'}-{version}.mp4"
    if not target.is_file():
        render_ident(mode, outro, target)
    return target


def concat_with_idents(content: Path, target: Path, landscape: bool = False) -> Path:
    mode = "landscape" if landscape else "vertical"
    intro = approved_ident(mode, False)
    outro = approved_ident(mode, True)
    target.parent.mkdir(parents=True, exist_ok=True)
    listing = target.parent / f"{target.stem}-approved-idents.txt"
    listing.write_text(f"file '{intro.as_posix()}'\nfile '{content.as_posix()}'\nfile '{outro.as_posix()}'\n", encoding="utf-8")
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-avoid_negative_ts", "make_zero", "-metadata", "artist=Pixel & Parameters", "-movflags", "+faststart", str(target),
    ], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return target


def ident_metadata(landscape: bool = False) -> dict:
    return {"approved_version": "original-collision-v1", "intro_seconds": DURATION, "outro_seconds": DURATION, "impact_seconds": IMPACT, "format": "16:9" if landscape else "9:16", "subtitle_intro": "GAMING CULTURE  ×  AI", "subtitle_outro": "FOLLOW FOR MORE"}
