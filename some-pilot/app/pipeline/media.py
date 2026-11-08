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
        raise MediaError(f"command_failed:{args[0]}:{result.stderr[-1000:]}")
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
    return {"language": info.language, "language_probability": info.language_probability, "segments": len(segments), "model": "small/int8", "segments_detail": segments}


def render(background: Path, narration: Path, captions: Path, title: str, output: Path) -> None:
    title_file = output.parent / "title.txt"
    title_file.write_text("\n".join(textwrap.wrap(title, width=32)[:2]), encoding="utf-8")
    filters = (
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile={title_file}:"
        "fontcolor=white:fontsize=64:line_spacing=12:x=(w-text_w)/2:y=180:borderw=2:bordercolor=black,"
        f"subtitles={captions}:force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=280'"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(background), "-i", str(narration),
        "-vf", filters, "-af", "loudnorm=I=-16:TP=-1:LRA=11", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(output),
    ])


def thumbnail(video: Path, output: Path) -> None:
    run(["ffmpeg", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", str(output)])


def storyboard(video: Path, output: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(video), "-vf", "fps=1/5,scale=270:480,tile=3x1", "-frames:v", "1", str(output)])


def technical_checks(video: Path, captions: Path, expected_max_lines: int = 2) -> dict:
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
    if (visual.get("width"), visual.get("height")) != (1080, 1920):
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
