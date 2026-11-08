import json
import math
import shutil
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.config import get_settings
from app.pipeline.downloader import detect_media_type
from app.pipeline.media import MediaError, probe, run, srt_timestamp, synthesize, technical_checks

WIDTH = 1080
HEIGHT = 1920
FPS = 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class RankingScene(BaseModel):
    rank: int = Field(ge=1, le=10)
    game: str = Field(min_length=1, max_length=80)
    kicker: str = Field(min_length=3, max_length=70)
    narration: str = Field(min_length=10, max_length=400)
    clip_url: HttpUrl
    policy_url: HttpUrl
    source_path: str = Field(min_length=1)
    start_seconds: float = Field(ge=0, default=0)
    source_duration_seconds: float = Field(gt=0)
    rights_holder: str = Field(min_length=1, max_length=300)
    rights_evidence: str = Field(min_length=1, max_length=1500)
    music_allowed: bool = False
    attribution: str = Field(min_length=1, max_length=500)


class RankingPlan(BaseModel):
    title: str = Field(min_length=10, max_length=120)
    hook: str = Field(min_length=10, max_length=250)
    post_text: str = Field(min_length=10, max_length=2200)
    voice_dir: str | None = None
    scenes: list[RankingScene] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def valid_ranking(self):
        if sorted(scene.rank for scene in self.scenes) != list(range(1, 11)):
            raise ValueError("ranks_must_be_unique_one_through_ten")
        return self


def validate_sources(plan_path: Path, plan: RankingPlan) -> None:
    root = plan_path.parent.resolve()
    for scene in plan.scenes:
        source = (root / scene.source_path).resolve()
        if root not in source.parents or not source.is_file():
            raise MediaError(f"source_missing_or_outside_research:{scene.game}")
        if detect_media_type(source) not in {"video/mp4", "video/webm"}:
            raise MediaError(f"invalid_video_signature:{scene.game}")
        metadata = probe(source)
        video = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
        if not video:
            raise MediaError(f"video_stream_missing:{scene.game}")
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration < 3 or scene.start_seconds + 3 > min(duration, scene.source_duration_seconds) + 0.05:
            raise MediaError(f"insufficient_source_duration:{scene.game}")


def _text_file(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _drawtext(path: Path, size: int, x: str, y: str, color: str = "white", box: bool = False, bold: bool = True) -> str:
    border = "borderw=3:bordercolor=black@0.8" if not box else "box=1:boxcolor=0x07101fe6:boxborderw=20"
    return f"drawtext=fontfile={FONT_BOLD if bold else FONT_REGULAR}:textfile={path}:fontsize={size}:fontcolor={color}:x={x}:y={y}:{border}"


def _render_scene(scene: RankingScene, source: Path, directory: Path, narration: str, voice_dir: str | None = None, hook: bool = False) -> tuple[Path, float, list[dict]]:
    stem = "hook" if hook else f"rank-{scene.rank:02d}"
    audio = directory / f"{stem}.wav"
    supplied_voice = source.parent.parent / voice_dir / f"{stem}.wav" if voice_dir else None
    if voice_dir:
        if Path(voice_dir).name != voice_dir or voice_dir in {"", ".", ".."} or "\\" in voice_dir or supplied_voice is None or not supplied_voice.is_file():
            raise MediaError(f"approved_voice_missing:{stem}")
        shutil.copyfile(supplied_voice, audio)
    else:
        synthesize(narration, audio, "en")
    duration = min(10.0, max(4.0, math.ceil(float(probe(audio)["format"]["duration"]) * 10) / 10 + 0.5))
    source_duration = float(probe(source)["format"]["duration"])
    start = min(scene.start_seconds, max(0, source_duration - duration - 0.1))
    title = _text_file(directory, f"{stem}-game.txt", "TOP 10: LEGION GO 2" if hook else f"#{scene.rank}  {scene.game.upper()}")
    subtitle = _text_file(directory, f"{stem}-kicker.txt", "10 GAMES WORTH YOUR TIME" if hook else scene.kicker.upper())
    badge = _text_file(directory, f"{stem}-badge.txt", "THE HANDHELD HIT LIST" if hook else f"{scene.rank:02d} / 10")
    caption_filters = []
    caption_chunks = _wrap_caption(narration)
    speech_duration = max(1.0, duration - 0.5)
    for index, chunk in enumerate(caption_chunks):
        caption_path = _text_file(directory, f"{stem}-caption-{index}.txt", chunk)
        start_caption = speech_duration * index / len(caption_chunks)
        end_caption = speech_duration * (index + 1) / len(caption_chunks)
        caption_filters.append("," + _drawtext(caption_path, 46, "(w-text_w)/2", "h-285", box=True, bold=False) + f":enable='between(t,{start_caption:.3f},{end_caption:.3f})'")
    filter_graph = (
        "[0:v]split=2[background][foreground];"
        "[background]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "gblur=sigma=38,eq=brightness=-0.22:saturation=0.75[bg];"
        "[foreground]scale=1080:1240:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:410:format=auto[composite];"
        "[composite]drawbox=x=0:y=0:w=iw:h=310:color=0x07101f@0.92:t=fill,"
        "drawbox=x=60:y=296:w=960:h=5:color=0x58efff:t=fill,"
        + _drawtext(badge, 30, "70", "55", "0x58efff") + ","
        + _drawtext(title, 62 if len(scene.game) < 21 else 48, "70", "118") + ","
        + _drawtext(subtitle, 31, "70", "220", "0xffd54f", bold=False)
        + "".join(caption_filters) + ","
        + "fade=t=in:st=0:d=0.12,fade=t=out:st=" + f"{duration - 0.12:.2f}:d=0.12,format=yuv420p[v]"
    )
    audio_graph = f"[1:a]apad=pad_dur={duration:.3f},atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[narration]"
    if scene.music_allowed:
        audio_graph += f";[0:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,volume=0.07[gameaudio];[narration][gameaudio]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        audio_graph += ";[narration]anull[a]"
    args = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source), "-i", str(audio), "-threads", "2", "-filter_threads", "2", "-filter_complex", filter_graph + ";" + audio_graph, "-map", "[v]", "-map", "[a]", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-t", f"{duration:.3f}", str(directory / f"{stem}.mp4")]
    run(args)
    caption = [{"start": 0.0, "end": duration, "text": narration}]
    return directory / f"{stem}.mp4", duration, caption


def render_ranking(plan_path: Path, output: Path) -> dict:
    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    validate_sources(plan_path, plan)
    if shutil.disk_usage(output.parent).used / shutil.disk_usage(output.parent).total >= 0.90:
        raise MediaError("render_blocked_disk_at_or_above_90_percent")
    work = output / "work"
    work.mkdir(parents=True, exist_ok=False)
    ordered = sorted(plan.scenes, key=lambda scene: scene.rank, reverse=True)
    first = next(scene for scene in ordered if scene.rank == 1)
    segments = []
    durations = []
    captions = []
    for scene_index, scene in enumerate([first, *ordered]):
        segment, duration, scene_captions = _render_scene(scene, (plan_path.parent / scene.source_path).resolve(), work, plan.hook if scene_index == 0 else scene.narration, plan.voice_dir, scene_index == 0)
        segments.append(segment)
        durations.append(duration)
        captions.extend(scene_captions)
    transition = 0.22
    inputs = [argument for segment in segments for argument in ("-i", str(segment))]
    filters = []
    offsets = []
    previous_offset = 0.0
    for index in range(1, len(segments)):
        offset = sum(durations[:index]) - transition * index
        offsets.append(offset)
        previous_offset = offset
    current_video = "[0:v]"
    current_audio = "[0:a]"
    transitions = ["smoothleft", "circleopen", "smoothup", "fade", "wiperight", "circleopen", "smoothleft", "fade", "smoothup", "wiperight"]
    for index, offset in enumerate(offsets, 1):
        next_video = f"[v{index}]"
        next_audio = f"[a{index}]"
        filters.append(f"{current_video}[{index}:v]xfade=transition={transitions[index - 1]}:duration={transition}:offset={offset:.3f}{next_video}")
        filters.append(f"{current_audio}[{index}:a]acrossfade=d={transition}:c1=tri:c2=tri{next_audio}")
        current_video = next_video
        current_audio = next_audio
    filters.append(f"{current_video}setsar=1,format=yuv420p[vout]")
    filters.append(f"{current_audio}loudnorm=I=-16:TP=-1:LRA=11,aresample=48000[aout]")
    output.mkdir(parents=True, exist_ok=True)
    video = output / "video.mp4"
    run(["ffmpeg", "-y", *inputs, "-threads", "2", "-filter_threads", "2", "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(video)])
    narration_audio = output / "narration.wav"
    concat = "".join(f"file '{segment.with_suffix('.wav').as_posix()}'\n" for segment in segments)
    concat_path = _text_file(work, "narration-concat.txt", concat)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c:a", "pcm_s16le", str(narration_audio)])
    timeline = []
    elapsed = 0.0
    index = 0
    for scene_index, duration in enumerate(durations):
        text = captions[scene_index]["text"]
        wrapped = _wrap_caption(text)
        speech_duration = max(1.0, duration - 0.5)
        for chunk_index, chunk in enumerate(wrapped):
            start = elapsed + speech_duration * chunk_index / len(wrapped)
            end = elapsed + speech_duration * (chunk_index + 1) / len(wrapped)
            timeline.append({"start": start, "end": end, "text": chunk})
            index += 1
        elapsed += duration - (transition if scene_index else 0)
    caption_path = output / "captions.srt"
    caption_path.write_text("\n\n".join(f"{index}\n{srt_timestamp(item['start'])} --> {srt_timestamp(item['end'])}\n{item['text']}" for index, item in enumerate(timeline, 1)), encoding="utf-8")
    (output / "editorial.json").write_text(json.dumps(plan.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    technical = technical_checks(video, caption_path)
    return {"decision": "ALLOW" if technical["decision"] == "ALLOW" else "BLOCK", "video": str(video), "scenes": len(ordered), "real_video_clips": True, "synthetic_fallback": False, "transitions": len(offsets), "technical": technical}


def _wrap_caption(text: str) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > 34 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return ["\n".join(lines[index:index + 2]) for index in range(0, len(lines), 2)]


def storyboard_frames(duration: float) -> list[float]:
    if duration <= 0:
        raise ValueError("duration_must_be_positive")
    return [round(duration * fraction, 3) for fraction in (0.01, 0.16, 0.31, 0.46, 0.61, 0.76, 0.94)]
