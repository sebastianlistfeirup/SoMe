from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


DATA = Path("/data")
ROOT = DATA / "outputs" / "test-posts-2026-11-09"
FINAL = ROOT / "final"
WORK = FINAL / ".work"
BRAND = DATA / "production_assets" / "brand" / "pixel-and-parameters"
LOGO = BRAND / "pixel-and-parameters-primary-logo-v1.png"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FPS = 30
IDENT_DURATION = 3.5

POSTS = {
    "gaming": {"host": "KIVO ROOK", "accent": "58efff", "topic": "GAMING"},
    "ai": {"host": "ELIAN QUILL", "accent": "7df9c8", "topic": "LOCAL AI"},
}

PLATFORMS = {
    "youtube-16x9.mp4": ("youtube-16x9", "landscape"),
    "tiktok-9x16.mp4": ("tiktok-9x16", "vertical"),
    "instagram-reels-9x16.mp4": ("instagram-reels-9x16", "vertical"),
}


def run(args: list[str]) -> None:
    print("RUN", " ".join(args[:10]), "...", flush=True)
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])


def ident_audio(target: Path, outro: bool) -> None:
    sample_rate = 48_000
    t = np.arange(math.ceil(IDENT_DURATION * sample_rate), dtype=np.float64) / sample_rate
    rng = np.random.default_rng(1701 if not outro else 1702)
    rise = np.clip(t / 0.55, 0, 1)
    fall = np.clip((IDENT_DURATION - t) / 0.45, 0, 1)
    envelope = np.minimum(rise, fall)
    root = 55.0 if not outro else 65.406
    tone = (
        0.18 * np.sin(2 * np.pi * root * t)
        + 0.10 * np.sin(2 * np.pi * root * 1.5 * t + 0.2)
        + 0.06 * np.sin(2 * np.pi * root * 2.0 * t + 0.7)
    ) * envelope
    whoosh_env = np.exp(-((t - (0.75 if not outro else 2.65)) / 0.42) ** 2)
    whoosh = rng.standard_normal(len(t)) * whoosh_env * 0.055
    impact_at = 1.05 if not outro else 2.25
    impact_t = np.maximum(0, t - impact_at)
    impact = (t >= impact_at) * np.sin(2 * np.pi * 78 * impact_t) * np.exp(-impact_t * 8) * 0.22
    blips = np.zeros_like(t)
    for at, frequency in ((0.38, 880), (0.62, 1320), (2.72, 660)):
        local = np.maximum(0, t - at)
        blips += (t >= at) * np.sin(2 * np.pi * frequency * local) * np.exp(-local * 28) * 0.07
    mono = np.tanh((tone + whoosh + impact + blips) * 1.7) * 0.72
    stereo = np.column_stack((mono * 0.97, mono))
    pcm = np.int16(np.clip(stereo, -1, 1) * 32767)
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.FreeTypeFont, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw.text(((draw._image.width - width) // 2, y), text, font=font, fill=fill)


def render_ident(mode: str, outro: bool, target: Path) -> None:
    from app.pipeline.brand_ident import render_ident as render_approved_ident

    render_approved_ident(mode, outro, target)


def brand_content(post: str, source: Path, target: Path, mode: str) -> None:
    landscape = mode == "landscape"
    top = 62 if landscape else 78
    x = 55 if landscape else 46
    y = 24 if landscape else 31
    size = 26 if landscape else 28
    label = WORK / f"{post}-label.txt"
    label.write_text(f"PIXEL & PARAMETERS  //  {POSTS[post]['host']}", encoding="utf-8")
    text_path = str(label).replace(":", "\\:")
    vf = (
        f"drawbox=x=0:y=0:w=iw:h={top}:color=0x07101f@0.96:t=fill,"
        f"drawtext=fontfile={FONT}:textfile={text_path}:fontsize={size}:"
        f"fontcolor=0x{POSTS[post]['accent']}:x={x}:y={y},fps={FPS},format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-i", str(source), "-vf", vf, "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(target),
    ])


def concat(intro: Path, content: Path, outro: Path, target: Path) -> None:
    listing = WORK / f"{target.stem}-concat.txt"
    listing.write_text(
        f"file '{intro.as_posix()}'\nfile '{content.as_posix()}'\nfile '{outro.as_posix()}'\n",
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
        "-metadata", "artist=Pixel & Parameters", "-movflags", "+faststart", str(target),
    ])


def main() -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    idents: dict[tuple[str, str], Path] = {}
    for mode in ("landscape", "vertical"):
        for kind, outro in (("intro", False), ("outro", True)):
            target = WORK / f"ident-{mode}-{kind}.mp4"
            print(f"BUILD IDENT {mode} {kind}", flush=True)
            render_ident(mode, outro, target)
            idents[(mode, kind)] = target
    manifest = {
        "brand": "Pixel & Parameters",
        "intro_seconds": IDENT_DURATION,
        "outro_seconds": IDENT_DURATION,
        "publish_authorized": False,
        "deliverables": [],
    }
    for post, config in POSTS.items():
        for source_name, (platform, mode) in PLATFORMS.items():
            source = ROOT / post / source_name
            content = WORK / f"{post}-{platform}-content.mp4"
            target = FINAL / f"pixel-and-parameters-{post}-{platform}.mp4"
            brand_content(post, source, content, mode)
            concat(idents[(mode, "intro")], content, idents[(mode, "outro")], target)
            manifest["deliverables"].append(
                {"post": post, "host": config["host"].title(), "platform": platform, "file": str(target)}
            )
    (FINAL / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
