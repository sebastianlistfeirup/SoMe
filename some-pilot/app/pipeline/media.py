import gc
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

from app.config import get_settings


class MediaError(RuntimeError):
    pass


def run(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout or get_settings().render_max_seconds, check=False)
    if result.returncode != 0:
        raise MediaError(f"command_failed:{args[0]}:{result.stderr[-5000:]}")
    return result


def require_tools() -> None:
    for tool in ("ffmpeg", "ffprobe", "espeak-ng"):
        if not shutil.which(tool):
            raise MediaError(f"missing_tool:{tool}")


def probe(path: Path) -> dict:
    result = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    return json.loads(result.stdout)


def make_background(path: Path) -> None:
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1D4ED8:s=1080x1920:r=30", "-frames:v", "1", str(path)])


def synthesize(text: str, path: Path, language: str = "en") -> None:
    voice = "en-us" if language.startswith("en") else "da"
    run(["espeak-ng", "-v", voice, "-s", "155", "-w", str(path), text])


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def write_srt(segments: list[dict], path: Path) -> None:
    blocks = []
    for index, segment in enumerate(segments, 1):
        text = segment["text"].strip()
        blocks.append(f"{index}\n{srt_timestamp(segment['start'])} --> {srt_timestamp(segment['end'])}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def transcribe(audio: Path, output: Path) -> dict:
    from faster_whisper import WhisperModel

    settings = get_settings()
    model = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(settings.model_cache_dir / "whisper"))
    segments_iter, info = model.transcribe(str(audio), word_timestamps=True, vad_filter=True)
    segments = [{"start": segment.start, "end": segment.end, "text": segment.text} for segment in segments_iter]
    if not segments:
        raise MediaError("transcription_empty")
    write_srt(segments, output)
    result = {"language": info.language, "language_probability": info.language_probability, "segments": len(segments), "model": "small/int8", "segments_detail": segments}
    del model
    gc.collect()
    return result


def _font_size(lines: list[str], base: int, max_width: int) -> int:
    longest = max((len(line) for line in lines), default=1)
    return max(24, min(base, int(max_width / max(1, longest) / 0.62)))


def render(backgrounds: list[Path], narration: Path, captions: Path, title: str, output: Path) -> dict:
    if not backgrounds:
        raise MediaError("scene_assets_missing")
    caption_blocks = [block for block in captions.read_text(encoding="utf-8").strip().split("\n\n") if block.strip()]
    if len(backgrounds) != len(caption_blocks):
        raise MediaError("scene_and_caption_count_mismatch")
    title_lines = textwrap.wrap(title, width=32)[:2]
    title_file = output.parent / "title.txt"
    title_file.write_text("\n".join(title_lines), encoding="utf-8")
    title_size = _font_size(title_lines, 64, 900)
    input_args = []
    scene_filters = []
    for index, (background, block) in enumerate(zip(backgrounds, caption_blocks)):
        timing = block.splitlines()[1].split(" --> ")
        start = _srt_seconds(timing[0])
        end = _srt_seconds(timing[1])
        duration = max(0.2, end - start)
        input_args.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(background)])
        scene_filters.append(f"[{index}:v]scale=1080:1920,zoompan=z='min(zoom+0.0004,1.04)':d={max(1, round(duration * 30))}:s=1080x1920:fps=30,trim=duration={duration:.3f},setpts=PTS-STARTPTS[v{index}]")
    filters = [
        ";".join(scene_filters),
        f"{''.join(f'[v{index}]' for index in range(len(backgrounds)))}concat=n={len(backgrounds)}:v=1:a=0[scenes]",
    ]
    caption_count = 0
    max_estimated_width = 0
    caption_filters = []
    for block_index, block in enumerate(caption_blocks, 1):
        lines = block.splitlines()
        timing = lines[1].split(" --> ")
        start = _srt_seconds(timing[0])
        end = _srt_seconds(timing[1])
        wrapped = textwrap.wrap(" ".join(lines[2:]), width=36)
        chunks = [wrapped[index:index + 2] for index in range(0, len(wrapped), 2)]
        for chunk_index, chunk in enumerate(chunks, 1):
            caption_count += 1
            caption_file = output.parent / f"caption-{block_index}-{chunk_index}.txt"
            caption_file.write_text("\n".join(chunk), encoding="utf-8")
            size = _font_size(chunk, 48, 920)
            max_estimated_width = max(max_estimated_width, round(max(len(line) for line in chunk) * size * 0.62))
            chunk_start = start + (end - start) * (chunk_index - 1) / len(chunks)
            chunk_end = start + (end - start) * chunk_index / len(chunks)
            caption_filters.append(
                f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile={caption_file}:"
                f"fontcolor=white:fontsize={size}:line_spacing=10:x=(w-text_w)/2:y=h-450:borderw=2:bordercolor=black:"
                f"enable='between(t,{chunk_start:.3f},{chunk_end:.3f})'"
            )
    filters.append(f"[scenes]{','.join(caption_filters)}")
    input_args.extend(["-i", str(narration)])
    run([
        "ffmpeg", "-y", *input_args,
        "-threads", "2", "-filter_threads", "2",
        "-filter_complex", ";".join(filters), "-af", "loudnorm=I=-16:TP=-1:LRA=11", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(output),
    ])
    return {"decision": "ALLOW", "reasons": [], "title_lines": len(title_lines), "caption_blocks": caption_count, "scene_count": len(backgrounds), "animated_scenes": True, "max_estimated_text_width": max_estimated_width, "safe_horizontal_margin_px": 80, "title_y_px": 180, "caption_bottom_margin_px": 450}


def _srt_seconds(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def thumbnail(video: Path, output: Path) -> None:
    run(["ffmpeg", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", str(output)])


def storyboard(video: Path, output: Path) -> None:
    duration = float(probe(video)["format"]["duration"])
    interval = max(duration / 6, 0.1)
    run(["ffmpeg", "-y", "-i", str(video), "-vf", f"fps=1/{interval:.6f},scale=216:384,tile=6x1", "-frames:v", "1", str(output)])


def technical_checks(video: Path, captions: Path, expected_max_lines: int = 2, expected_dimensions: tuple[int, int] = (1080, 1920)) -> dict:
    metadata = probe(video)
    streams = metadata.get("streams", [])
    visual = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    duration = float(metadata.get("format", {}).get("duration", 0))
    loudness = run(["ffmpeg", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"])
    black = run(["ffmpeg", "-i", str(video), "-vf", "blackdetect=d=0.5:pix_th=0.05", "-an", "-f", "null", "-"])
    caption_blocks = [block for block in captions.read_text(encoding="utf-8").strip().split("\n\n") if block.strip()]
    caption_lines = [len(block.splitlines()[2:]) for block in caption_blocks]
    caption_texts = [" ".join(block.splitlines()[2:]).strip().lower() for block in caption_blocks]
    integrated = _last_float(loudness.stderr, "I:")
    peak = _last_float(loudness.stderr, "Peak:")
    reasons = []
    if (visual.get("width"), visual.get("height")) != expected_dimensions:
        reasons.append("dimensions")
    if visual.get("codec_name") != "h264" or visual.get("pix_fmt") != "yuv420p":
        reasons.append("video_codec_or_pixel_format")
    if audio.get("codec_name") != "aac":
        reasons.append("audio_codec")
    if not 0 < duration <= 180:
        reasons.append("duration")
    if integrated is None or not -18 <= integrated <= -14:
        reasons.append("integrated_loudness")
    if peak is None or peak > -0.5:
        reasons.append("true_peak")
    if "black_start:" in black.stderr:
        reasons.append("black_frames")
    if any(lines > expected_max_lines for lines in caption_lines):
        reasons.append("caption_line_count")
    if len(caption_texts) != len(set(caption_texts)):
        reasons.append("duplicate_captions")
    return {"decision": "ALLOW" if not reasons else "BLOCK", "reasons": reasons, "duration_seconds": duration, "integrated_lufs": integrated, "true_peak_dbtp": peak, "streams": streams}


def _last_float(log: str, label: str) -> float | None:
    values = []
    for line in log.splitlines():
        if label in line:
            tail = line.split(label, 1)[1].strip().split()
            if tail:
                try:
                    values.append(float(tail[0]))
                except ValueError:
                    pass
    return values[-1] if values else None
