from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path("/data/outputs/test-posts-2026-11-09")
FINAL = ROOT / "final"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

POSTS = {
    "gaming": {"host": "KIVO ROOK", "accent": "58efff"},
    "ai": {"host": "ELIAN QUILL", "accent": "7df9c8"},
}

PLATFORMS = {
    "youtube-16x9.mp4": "youtube-16x9",
    "tiktok-9x16.mp4": "tiktok-9x16",
    "instagram-reels-9x16.mp4": "instagram-reels-9x16",
}


def run(args: list[str]) -> None:
    print("RUN", " ".join(args[:9]), "...", flush=True)
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])


def dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def brand(post: str, source: Path, target: Path) -> None:
    width, height = dimensions(source)
    landscape = width > height
    top = 62 if landscape else 78
    x = 55 if landscape else 46
    y = 24 if landscape else 31
    size = 26 if landscape else 28
    label = FINAL / f".{post}-label.txt"
    label.write_text(f"PIXEL & PARAMETERS  //  {POSTS[post]['host']}", encoding="utf-8")
    text_path = str(label).replace(":", "\\:")
    vf = (
        f"drawbox=x=0:y=0:w=iw:h={top}:color=0x07101f@0.96:t=fill,"
        f"drawtext=fontfile={FONT}:textfile={text_path}:fontsize={size}:"
        f"fontcolor=0x{POSTS[post]['accent']}:x={x}:y={y}"
    )
    title = "Best Nostalgic Games for Handhelds" if post == "gaming" else "The Local AI Machine Buyer's Guide"
    run([
        "ffmpeg", "-y", "-i", str(source), "-vf", vf,
        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        "-metadata", f"title={title}", "-metadata", "artist=Pixel & Parameters",
        "-metadata", f"album_artist={POSTS[post]['host']}", str(target),
    ])


def main() -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    manifest = {"brand": "Pixel & Parameters", "publish_authorized": False, "deliverables": []}
    for post, config in POSTS.items():
        for source_name, platform_name in PLATFORMS.items():
            source = ROOT / post / source_name
            target = FINAL / f"pixel-and-parameters-{post}-{platform_name}.mp4"
            brand(post, source, target)
            manifest["deliverables"].append(
                {"post": post, "host": config["host"].title(), "platform": platform_name, "file": str(target)}
            )
    (FINAL / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
