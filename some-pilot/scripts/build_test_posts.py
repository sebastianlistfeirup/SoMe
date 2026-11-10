from __future__ import annotations

import json
import math
import shutil
import subprocess
import textwrap
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.pipeline.voice import VoiceSegment, prepare_voice


DATA = Path("/data")
ASSETS = DATA / "production_assets"
OUTPUT = DATA / "outputs" / "test-posts-2026-11-09"
SOURCE_TIMINGS = json.loads(Path(__file__).with_name("test_post_scripts.json").read_text(encoding="utf-8"))
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FPS = 30


@dataclass(frozen=True)
class Scene:
    title: str
    source: Path
    source_kind: str
    source_start: float = 0.0
    visual_mode: str = "pip"


POSTS = {
    "gaming": {
        "label": "PILOT // GAMING",
        "accent": "58efff",
        "scenes": [
            Scene("BEST NOSTALGIC GAMES", ASSETS / "gaming-nostalgia" / "hades.mp4", "video", 5, "opening"),
            Scene("#5  TRANSISTOR", ASSETS / "gaming-nostalgia" / "transistor.mp4", "video", 10),
            Scene("#4  CELESTE", ASSETS / "gaming-nostalgia" / "celeste.mp4", "video", 20),
            Scene("#3  HOLLOW KNIGHT", ASSETS / "gaming-nostalgia" / "hollow-knight.mp4", "video", 15),
            Scene("#2  STARDEW VALLEY", ASSETS / "gaming-nostalgia" / "stardew-valley.mp4", "video", 30),
            Scene("#1  HADES", ASSETS / "gaming-nostalgia" / "hades.mp4", "video", 25),
            Scene("WHAT LIVES ON YOUR HANDHELD?", ASSETS / "gaming-nostalgia" / "hades.mp4", "video", 45, "closing"),
        ],
        "tiktok_scenes": [0, 2, 4, 5, 6],
        "reels_scenes": list(range(7)),
        "music": "gaming",
    },
    "ai": {
        "label": "PILOT // LOCAL AI",
        "accent": "7df9c8",
        "scenes": [
            Scene("STOP BUYING TOPS", ASSETS / "ai-hardware" / "cards" / "start-with-memory.png", "image", 0, "opening"),
            Scene("70B @ 4-BIT ≈ 35 GB", ASSETS / "ai-hardware" / "cards" / "model-math.png", "image"),
            Scene("MEMORY. BANDWIDTH. SOFTWARE.", ASSETS / "ai-hardware" / "cards" / "three-specs.png", "image"),
            Scene("RTX 5090 // CUDA SPEED", ASSETS / "ai-hardware" / "rtx5090-official-clip-hq.mp4", "video", 3),
            Scene("FRAMEWORK // 192 GB", ASSETS / "ai-hardware" / "cards" / "framework.png", "image"),
            Scene("MAC STUDIO // TURNKEY", ASSETS / "ai-hardware" / "mac-studio-official-clip-h264.mp4", "video", 5),
            Scene("DGX SPARK // NVIDIA STACK", ASSETS / "ai-hardware" / "dgx-spark-official-clip-h264.mp4", "video", 5),
            Scene("MATCH THE MODEL", ASSETS / "ai-hardware" / "cards" / "match-the-model.png", "image", 0, "closing"),
        ],
        "tiktok_scenes": [0, 2, 3, 4, 7],
        "reels_scenes": [0, 2, 3, 4, 5, 6, 7],
        "music": "ai",
    },
}


def run(args: list[str], timeout: int = 900) -> None:
    print("RUN", " ".join(args[:8]), "...", flush=True)
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])


def gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        p = y / max(1, height - 1)
        color = tuple(round(top[i] * (1 - p) + bottom[i] * p) for i in range(3))
        draw.line((0, y, width, y), fill=color)
    return image


def card(title: str, subtitle: str, metrics: list[tuple[str, str]], target: Path, accent: str = "#7df9c8") -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image = gradient((1920, 1080), (5, 12, 28), (14, 32, 56))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1350, -260, 2050, 440), fill="#153f55")
    draw.ellipse((-250, 660, 500, 1410), fill="#162b5f")
    draw.rounded_rectangle((82, 72, 1838, 1008), radius=46, fill="#07101fdd", outline=accent, width=4)
    draw.text((140, 118), "LOCAL AI // FIELD GUIDE", font=ImageFont.truetype(FONT_BOLD, 34), fill=accent)
    wrapped = textwrap.wrap(title, width=24)
    y = 195
    for line in wrapped[:2]:
        draw.text((135, y), line, font=ImageFont.truetype(FONT_BOLD, 88), fill="white")
        y += 105
    draw.text((140, y + 12), subtitle, font=ImageFont.truetype(FONT_REGULAR, 36), fill="#bac8dc")
    box_y = 600
    box_w = (1620 - 36 * (len(metrics) - 1)) // max(1, len(metrics))
    for index, (value, label) in enumerate(metrics):
        x = 150 + index * (box_w + 36)
        draw.rounded_rectangle((x, box_y, x + box_w, 900), radius=32, fill="#12233d", outline="#29435f", width=3)
        draw.text((x + 32, box_y + 55), value, font=ImageFont.truetype(FONT_BOLD, 65 if len(value) < 12 else 49), fill=accent)
        for line_index, line in enumerate(textwrap.wrap(label, width=19)[:2]):
            draw.text((x + 34, box_y + 160 + line_index * 42), line, font=ImageFont.truetype(FONT_REGULAR, 31), fill="white")
    image.save(target, quality=95)


def make_cards() -> None:
    root = ASSETS / "ai-hardware" / "cards"
    card("START WITH MEMORY", "The TOPS badge is not the buying decision.", [("VRAM", "What can load"), ("GB/s", "How fast weights move"), ("STACK", "What actually runs")], root / "start-with-memory.png")
    card("70B @ 4-BIT ≈ 35 GB", "Before context and runtime overhead.", [("32 GB", "RTX 5090 VRAM"), ("35 GB+", "Raw model weight"), ("OVERFLOW", "It will not fit fully")], root / "model-math.png", "#ffcf5a")
    card("THE THREE SPECS", "Size first. Speed second. Compatibility always.", [("MEMORY", "Model capacity"), ("BANDWIDTH", "Inference flow"), ("SOFTWARE", "CUDA / MLX / runtime")], root / "three-specs.png")
    card("FRAMEWORK DESKTOP", "A compact, Linux-focused memory monster.", [("192 GB", "LPDDR5X-8533"), ("273 GB/s", "Memory bandwidth"), ("300B", "Vendor 4-bit claim")], root / "framework.png", "#f4a261")
    card("MATCH THE MODEL", "Choose the machine for the workload you run.", [("SIZE", "Memory headroom"), ("SPEED", "Bandwidth"), ("FIT", "Software ecosystem")], root / "match-the-model.png")


def make_music(duration: float, target: Path, style: str, boundaries: list[float]) -> None:
    sample_rate = 48_000
    count = math.ceil(duration * sample_rate)
    t = np.arange(count, dtype=np.float64) / sample_rate
    bpm = 96 if style == "gaming" else 88
    beat = 60 / bpm
    chord_roots = np.array([55.0, 65.406, 73.416, 49.0] if style == "gaming" else [43.654, 55.0, 65.406, 49.0])
    chord_index = (t // (beat * 8)).astype(int) % len(chord_roots)
    roots = chord_roots[chord_index]
    signal = 0.14 * np.sin(2 * np.pi * roots * t)
    signal += 0.055 * np.sin(2 * np.pi * roots * 1.5 * t + 0.3)
    signal += 0.035 * np.sin(2 * np.pi * roots * 2.0 * t + 1.1)
    phase = np.mod(t, beat)
    pulse = np.exp(-phase * (22 if style == "gaming" else 30))
    signal += pulse * (0.045 * np.sin(2 * np.pi * (110 if style == "gaming" else 82) * t))
    rng = np.random.default_rng(2609 if style == "gaming" else 1109)
    for boundary in boundaries[1:-1]:
        start = max(0, int((boundary - 0.18) * sample_rate))
        length = min(int(0.42 * sample_rate), count - start)
        local = np.arange(length) / sample_rate
        noise = rng.standard_normal(length) * np.exp(-local * 6)
        chirp = np.sin(2 * np.pi * (240 * local + 1400 * local * local))
        signal[start:start + length] += 0.055 * noise + 0.04 * chirp * np.exp(-local * 5)
    signal = np.tanh(signal * 1.6) * 0.55
    left = signal * (0.94 + 0.06 * np.sin(2 * np.pi * 0.07 * t))
    right = signal * (0.94 + 0.06 * np.sin(2 * np.pi * 0.09 * t + 1.7))
    stereo = np.column_stack((left, right))
    pcm = np.int16(np.clip(stereo, -1, 1) * 32767)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def caption_chunks(text: str, width: int) -> list[str]:
    lines = textwrap.wrap(text, width=width, break_long_words=False)
    return ["\n".join(lines[index:index + 2]) for index in range(0, len(lines), 2)]


def esc(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def render_segment(post_key: str, mode: str, index: int, work: Path, timing: dict) -> Path:
    post = POSTS[post_key]
    scene: Scene = post["scenes"][index]
    duration = float(timing["duration"])
    landscape = mode == "landscape"
    width, height = ((1920, 1080) if landscape else (1080, 1920))
    output = work / f"scene-{index:02d}.mp4"
    title_file = work / f"scene-{index:02d}-title.txt"
    label_file = work / f"scene-{index:02d}-label.txt"
    title_file.write_text(scene.title, encoding="utf-8")
    label_file.write_text(post["label"], encoding="utf-8")

    if scene.source_kind == "image":
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(scene.source)]
    else:
        inputs = ["-stream_loop", "-1", "-ss", f"{scene.source_start:.3f}", "-i", str(scene.source)]

    if landscape:
        base = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={FPS}[base]"
        caption_y, caption_size, top_h, title_size = height - 150, 42, 175, 52
    elif mode == "zoom":
        base = f"[0:v]scale=-2:{height},crop={width}:{height},setsar=1,fps={FPS}[base]"
        caption_y, caption_size, top_h, title_size = height - 330, 48, 245, 58
    else:
        base = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},gblur=sigma=32,eq=brightness=-0.18[bg];"
            f"[0:v]scale={width - 40}:-2,setsar=1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS}[base]"
        )
        caption_y, caption_size, top_h, title_size = height - 390, 46, 245, 56

    if scene.visual_mode in {"opening", "closing"}:
        full_for = 4.0 if scene.visual_mode == "opening" else min(6.0, duration)
        enable = f"between(t,0,{full_for:.3f})" if scene.visual_mode == "opening" else f"between(t,{max(0, duration - full_for):.3f},{duration:.3f})"
        foreground = min(width - (100 if landscape else 70), height - (80 if landscape else 500))
        source_crop = "[0:v]crop=ih:ih:(iw-ih)/2:0,setsar=1"
        visual_graph = (
            source_crop + ",split[avbg][avfg];"
            f"[avbg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},gblur=sigma=38,eq=brightness=-0.22[fullbg];"
            f"[avfg]scale={foreground}:{foreground}[fullfg];[fullbg][fullfg]overlay=(W-w)/2:(H-h)/2[fullav];"
            f"[base][fullav]overlay=0:0:enable='{enable}'[presented]"
        )
    else:
        visual_graph = "[base]null[presented]"

    filters = [base, visual_graph]
    accent = post["accent"]
    overlay = (
        f"[presented]drawbox=x=0:y=0:w=iw:h={top_h}:color=0x07101f@0.78:t=fill,"
        f"drawbox=x={55 if landscape else 46}:y={top_h - 9}:w={width - (110 if landscape else 92)}:h=4:color=0x{accent}:t=fill,"
        f"drawtext=fontfile={FONT_BOLD}:textfile={esc(label_file)}:fontsize={27 if landscape else 29}:fontcolor=0x{accent}:x={55 if landscape else 46}:y={28 if landscape else 35},"
        f"drawtext=fontfile={FONT_BOLD}:textfile={esc(title_file)}:fontsize={title_size}:fontcolor=white:x={55 if landscape else 46}:y={68 if landscape else 88}:borderw=2:bordercolor=black@0.6"
    )
    chunks = caption_chunks(timing["text"], 42 if landscape else 33)
    for chunk_index, chunk in enumerate(chunks):
        chunk_file = work / f"scene-{index:02d}-caption-{chunk_index:02d}.txt"
        chunk_file.write_text(chunk, encoding="utf-8")
        chunk_start = duration * chunk_index / len(chunks)
        chunk_end = duration * (chunk_index + 1) / len(chunks)
        overlay += (
            f",drawtext=fontfile={FONT_BOLD}:textfile={esc(chunk_file)}:fontsize={caption_size}:fontcolor=white:line_spacing=9:"
            f"x=(w-text_w)/2:y={caption_y}:box=1:boxcolor=0x07101fe8:boxborderw={18 if landscape else 22}:"
            f"enable='between(t,{chunk_start:.3f},{chunk_end:.3f})'"
        )
    overlay += f",drawbox=x=0:y=h-8:w='iw*t/{duration:.6f}':h=8:color=0x{accent}@0.9:t=fill,vignette=PI/6,fade=t=in:st=0:d=0.12,fade=t=out:st={max(0, duration - 0.12):.3f}:d=0.12,format=yuv420p[out]"
    filters.append(overlay)

    run([
        "ffmpeg", "-y", *inputs, "-t", f"{duration:.3f}", "-filter_complex", ";".join(filters),
        "-map", "[out]", "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ])
    return output


def concat_visual(segments: list[Path], target: Path, work: Path) -> None:
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)])


def prepare_post_voice(post_key: str, post_dir: Path) -> tuple[list[dict], float, Path]:
    paragraphs = SOURCE_TIMINGS[post_key]["paragraphs"]
    segments = [VoiceSegment(f"scene-{paragraph['index']:02d}", paragraph["text"]) for paragraph in paragraphs]
    directory = post_dir / "voice-assets"
    existing = directory if (directory / "metadata.json").is_file() else None
    report = prepare_voice(segments, "kokoro", directory, existing)
    (post_dir / "voice_assets.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if report["decision"] != "ALLOW":
        raise RuntimeError("voice_assets_blocked:" + ",".join(report["reasons"]))
    by_id = {row["segment_id"]: row for row in report["files"]}
    timings = []
    elapsed = 0.0
    for paragraph, segment in zip(paragraphs, segments):
        duration = float(by_id[segment.segment_id]["duration_seconds"])
        timings.append({"index": paragraph["index"], "start": elapsed, "end": elapsed + duration, "duration": duration, "text": paragraph["text"]})
        elapsed += duration
    metadata = {
        "model": {"model": "Kokoro-82M", "license": "Apache-2.0", "source": "https://huggingface.co/hexgrad/Kokoro-82M"},
        "voice": [{"file": f"{segment.segment_id}.wav", "text": segment.text, "voice": "af_bella", "speed": 1.08} for segment in segments],
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return timings, elapsed, directory


def concat_narration(directory: Path, timings: list[dict], target: Path) -> None:
    listing = target.with_suffix(".concat.txt")
    paths = [directory / f"scene-{timing['index']:02d}.wav" for timing in timings]
    listing.write_text("".join(f"file '{path.as_posix()}'\n" for path in paths), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "pcm_s16le", str(target)])


def mux_master(visual: Path, narration: Path, music: Path, target: Path) -> None:
    run([
        "ffmpeg", "-y", "-i", str(narration), "-i", str(music), "-i", str(visual),
        "-filter_complex", "[0:a]volume=1.0[n];[1:a]volume=0.16[m];[n][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1:LRA=7,aresample=48000[a]",
        "-map", "2:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(target),
    ])


def cut_scenes(master: Path, timings: list[dict], selected: list[int], target: Path) -> None:
    # Cut one scene at a time. A single filter graph with several 1080x1920
    # decoders can exhaust the worker's memory on social-platform compilations.
    cut_dir = target.parent / f".{target.stem}-cuts"
    cut_dir.mkdir(parents=True, exist_ok=True)
    cut_files: list[Path] = []
    for output_index, scene_index in enumerate(selected):
        timing = timings[scene_index]
        cut_file = cut_dir / f"{output_index:02d}.mp4"
        run([
            "ffmpeg", "-y", "-ss", str(timing["start"]), "-i", str(master),
            "-t", str(float(timing["end"]) - float(timing["start"])),
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac",
            "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(cut_file),
        ])
        cut_files.append(cut_file)
    listing = cut_dir / "concat.txt"
    listing.write_text("".join(f"file '{item.as_posix()}'\n" for item in cut_files), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(target)])


def thumbnail(post_key: str, master: Path, target: Path) -> None:
    frame = target.with_suffix(".frame.jpg")
    run(["ffmpeg", "-y", "-ss", "3", "-i", str(master), "-frames:v", "1", "-q:v", "2", str(frame)])
    image = Image.open(frame).convert("RGB")
    image = image.resize((1920, 1080), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, 1920, 1080), fill=(3, 8, 18, 90))
    draw.rounded_rectangle((70, 650, 1850, 1000), radius=42, fill=(7, 16, 31, 235), outline="#58efff" if post_key == "gaming" else "#7df9c8", width=5)
    title = "5 HANDHELD CLASSICS" if post_key == "gaming" else "THE LOCAL AI BUYER'S GUIDE"
    subtitle = "MODERN GAMES. PURE NOSTALGIA." if post_key == "gaming" else "MEMORY > TOPS"
    draw.text((125, 700), title, font=ImageFont.truetype(FONT_BOLD, 94 if post_key == "gaming" else 78), fill="white")
    draw.text((130, 850), subtitle, font=ImageFont.truetype(FONT_BOLD, 48), fill="#58efff" if post_key == "gaming" else "#7df9c8")
    image.save(target, quality=94)


def build_post(post_key: str) -> dict:
    post = POSTS[post_key]
    post_dir = OUTPUT / post_key
    post_dir.mkdir(parents=True, exist_ok=True)
    timings, total_duration, voice_dir = prepare_post_voice(post_key, post_dir)
    boundaries = [item["start"] for item in timings] + [timings[-1]["end"]]
    music = post_dir / "original-music.wav"
    make_music(total_duration, music, post["music"], boundaries)
    narration = post_dir / "narration.wav"
    concat_narration(voice_dir, timings, narration)
    masters: dict[str, Path] = {}
    for mode in ("landscape", "zoom", "safe"):
        master = post_dir / f"master-{mode}.mp4"
        work = post_dir / f"work-{mode}"
        work.mkdir(parents=True, exist_ok=True)
        print(f"BUILD {post_key} {mode}", flush=True)
        segments = [render_segment(post_key, mode, index, work, timings[index]) for index in range(len(post["scenes"]))]
        visual = work / "visual.mp4"
        concat_visual(segments, visual, work)
        mux_master(visual, narration, music, master)
        masters[mode] = master

    youtube = post_dir / "youtube-16x9.mp4"
    zoom_reference = post_dir / "vertical-zoom-reference.mp4"
    safe_reference = post_dir / "vertical-safe-reference.mp4"
    shutil.copyfile(masters["landscape"], youtube)
    shutil.copyfile(masters["zoom"], zoom_reference)
    shutil.copyfile(masters["safe"], safe_reference)
    tiktok = post_dir / "tiktok-9x16.mp4"
    reels = post_dir / "instagram-reels-9x16.mp4"
    cut_scenes(masters["zoom"], timings, post["tiktok_scenes"], tiktok)
    if post["reels_scenes"] == list(range(len(timings))):
        shutil.copyfile(masters["safe"], reels)
    else:
        cut_scenes(masters["safe"], timings, post["reels_scenes"], reels)
    thumb = post_dir / "thumbnail.jpg"
    thumbnail(post_key, youtube, thumb)
    deliverables = [youtube, tiktok, reels, zoom_reference, safe_reference]
    return {"post": post_key, "voice_only": True, "avatar_present": False, "voice_provider": "kokoro", "deliverables": [str(item) for item in deliverables], "thumbnail": str(thumb)}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    make_cards()
    manifest = {"voice_only": True, "avatar_present": False, "voice_provider": "kokoro", "publish_authorized": False, "posts": []}
    for post_key in ("gaming", "ai"):
        manifest["posts"].append(build_post(post_key))
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
