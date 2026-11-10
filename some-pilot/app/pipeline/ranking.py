import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.pipeline.downloader import detect_media_type
from app.pipeline.media import MediaError, probe, run, srt_timestamp, synthesize, technical_checks
from app.pipeline.mobile import mobile_filter

WIDTH = 1080
HEIGHT = 1920
FPS = 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@dataclass(frozen=True)
class PlatformSpec:
    width: int
    height: int
    landscape: bool
    title_size: int
    subtitle_size: int
    caption_size: int
    caption_bottom: int
    tempo: float = 1.0


PLATFORMS = {
    "tiktok": PlatformSpec(1080, 1920, False, 64, 28, 50, 245),
    "reels": PlatformSpec(1080, 1920, False, 64, 28, 46, 325),
    "youtube": PlatformSpec(1920, 1080, True, 50, 28, 42, 105, 1.07),
}


class RankingScene(BaseModel):
    rank: int = Field(ge=1, le=10)
    game: str = Field(min_length=1, max_length=80)
    kicker: str = Field(min_length=3, max_length=70)
    narration: str = Field(min_length=10, max_length=700)
    clip_url: HttpUrl
    policy_url: HttpUrl
    source_path: str = Field(min_length=1)
    start_seconds: float = Field(ge=0, default=0)
    source_duration_seconds: float = Field(gt=0)
    focus_x: float = Field(ge=0.1, le=0.9, default=0.5)
    focus_y: float = Field(ge=0.1, le=0.9, default=0.5)
    zoom: float = Field(ge=1.0, le=1.6, default=1.0)
    rights_holder: str = Field(min_length=1, max_length=300)
    rights_evidence: str = Field(min_length=1, max_length=1500)
    music_allowed: bool = False
    attribution: str = Field(min_length=1, max_length=500)


class RankingClaim(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=5, max_length=500)
    source_url: HttpUrl
    evidence_note: str = Field(min_length=5, max_length=1000)
    game: str | None = Field(default=None, max_length=80)
    verified: bool = False
    verified_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class RankingPlan(BaseModel):
    title: str = Field(min_length=10, max_length=120)
    hook: str = Field(min_length=10, max_length=300)
    post_text: str = Field(min_length=10, max_length=2200)
    voice_dir: str | None = None
    voice_model: str | None = None
    claims: list[RankingClaim] = Field(default_factory=list, max_length=100)
    scenes: list[RankingScene] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def valid_ranking(self):
        if sorted(scene.rank for scene in self.scenes) != list(range(1, 11)):
            raise ValueError("ranks_must_be_unique_one_through_ten")
        return self


def get_platform(name: str) -> PlatformSpec:
    if name not in PLATFORMS:
        raise ValueError(f"unsupported_platform:{name}")
    return PLATFORMS[name]


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
    border = "borderw=3:bordercolor=black@0.8" if not box else "box=1:boxcolor=0x07101fe6:boxborderw=18"
    return f"drawtext=fontfile={FONT_BOLD if bold else FONT_REGULAR}:textfile={path}:fontsize={size}:fontcolor={color}:x={x}:y={y}:{border}"


def _crop_filter(scene: RankingScene, source_width: int, source_height: int, spec: PlatformSpec) -> str:
    if spec.landscape:
        return f"[0:v]scale={spec.width}:{spec.height}:force_original_aspect_ratio=increase,crop={spec.width}:{spec.height},setsar=1[composite];"
    crop_height = max(2, round(source_height / scene.zoom / 2) * 2)
    crop_width = max(2, round(crop_height * spec.width / spec.height / 2) * 2)
    if crop_width > source_width:
        raise MediaError(f"crop_wider_than_source:{scene.game}")
    x = (source_width - crop_width) * scene.focus_x
    y = (source_height - crop_height) * scene.focus_y
    return f"[0:v]crop={crop_width}:{crop_height}:{x:.3f}:{y:.3f},scale={spec.width}:{spec.height},setsar=1[composite];"


def _render_scene(scene: RankingScene, source: Path, directory: Path, narration: str, voice_dir: str | None = None, hook: bool = False, platform: str = "reels", mobile_style: str = "zoom", voice_path: Path | None = None) -> tuple[Path, float, list[dict]]:
    spec = get_platform(platform)
    stem = "hook" if hook else f"rank-{scene.rank:02d}"
    audio = directory / f"{stem}.wav"
    supplied_voice = voice_path or (source.parent.parent / voice_dir / f"{stem}.wav" if voice_dir else None)
    if voice_dir or voice_path:
        if (voice_dir and (Path(voice_dir).name != voice_dir or voice_dir in {"", ".", ".."} or "\\" in voice_dir)) or supplied_voice is None or not supplied_voice.is_file():
            raise MediaError(f"approved_voice_missing:{stem}")
        shutil.copyfile(supplied_voice, audio)
    else:
        synthesize(narration, audio, "en")
    duration = max(4.0, math.ceil((float(probe(audio)["format"]["duration"]) / spec.tempo) * 10) / 10 + 0.5)
    processed_audio = directory / f"{stem}-narration.wav"
    run(["ffmpeg", "-y", "-i", str(audio), "-af", f"atempo={spec.tempo},apad=pad_dur={duration:.3f},atrim=duration={duration:.3f},aresample=48000", str(processed_audio)])
    audio = processed_audio
    source_metadata = probe(source)
    source_duration = float(source_metadata["format"]["duration"])
    video_stream = next(stream for stream in source_metadata["streams"] if stream["codec_type"] == "video")
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
        caption_filters.append("," + _drawtext(caption_path, spec.caption_size, "(w-text_w)/2", f"h-{spec.caption_bottom}", box=True, bold=False) + f":enable='between(t,{start_caption:.3f},{end_caption:.3f})'")
    if spec.landscape:
        title_y, subtitle_y, badge_y, title_size = 58, 124, 18, spec.title_size
        overlay = "drawbox=x=0:y=0:w=iw:h=184:color=0x07101f@0.72:t=fill,drawbox=x=60:y=176:w=1800:h=4:color=0x58efff:t=fill"
        badge_x, title_x, subtitle_x = 60, 60, 60
    else:
        title_y, subtitle_y, badge_y, title_size = 82, 170, 30, spec.title_size if len(scene.game) < 21 else 50
        overlay = "drawbox=x=0:y=0:w=iw:h=246:color=0x07101f@0.68:t=fill,drawbox=x=60:y=234:w=960:h=4:color=0x58efff:t=fill"
        badge_x, title_x, subtitle_x = 60, 60, 60
    base_filter = _crop_filter(scene, video_stream["width"], video_stream["height"], spec) if spec.landscape else mobile_filter(scene, video_stream["width"], video_stream["height"], spec, mobile_style, duration)
    filter_graph = (
        base_filter
        + f"[composite]{overlay},"
        + _drawtext(badge, 25 if spec.landscape else 27, str(badge_x), str(badge_y), "0x58efff") + ","
        + _drawtext(title, title_size, str(title_x), str(title_y)) + ","
        + _drawtext(subtitle, spec.subtitle_size, str(subtitle_x), str(subtitle_y), "0xffd54f", bold=False)
        + "".join(caption_filters) + ","
        + "fade=t=in:st=0:d=0.08,fade=t=out:st=" + f"{duration - 0.08:.2f}:d=0.08,format=yuv420p[v]"
    )
    audio_graph = f"[1:a]apad=pad_dur={duration:.3f},atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[narration]"
    if scene.music_allowed:
        audio_graph += f";[0:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,volume=0.04[gameaudio];[narration][gameaudio]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        audio_graph += ";[narration]anull[a]"
    args = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source), "-i", str(audio), "-threads", "2", "-filter_threads", "2", "-filter_complex", filter_graph + ";" + audio_graph, "-map", "[v]", "-map", "[a]", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-t", f"{duration:.3f}", str(directory / f"{stem}.mp4")]
    run(args)
    return directory / f"{stem}.mp4", duration, [{"start": 0.0, "end": duration, "text": narration}]


def render_ranking(plan_path: Path, output: Path, platform: str = "reels", mobile_style: str = "zoom", voice_files: dict[str, Path] | None = None) -> dict:
    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    spec = get_platform(platform)
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
        stem = "hook" if scene_index == 0 else f"rank-{scene.rank:02d}"
        voice_path = voice_files.get(stem) if voice_files else None
        segment, duration, scene_captions = _render_scene(scene, (plan_path.parent / scene.source_path).resolve(), work, plan.hook if scene_index == 0 else scene.narration, plan.voice_dir, scene_index == 0, platform, mobile_style, voice_path)
        segments.append(segment)
        durations.append(duration)
        captions.extend(scene_captions)
    transition = 0.22
    inputs = [argument for segment in segments for argument in ("-i", str(segment))]
    filters = []
    offsets = [sum(durations[:index]) - transition * index for index in range(1, len(segments))]
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
    concat = "".join(f"file '{segment.with_name(segment.stem + '-narration.wav').as_posix()}'\n" for segment in segments)
    concat_path = _text_file(work, "narration-concat.txt", concat)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c:a", "pcm_s16le", str(narration_audio)])
    timeline = []
    elapsed = 0.0
    for scene_index, duration in enumerate(durations):
        wrapped = _wrap_caption(captions[scene_index]["text"])
        speech_duration = max(1.0, duration - 0.5)
        for chunk_index, chunk in enumerate(wrapped):
            start = elapsed + speech_duration * chunk_index / len(wrapped)
            end = elapsed + speech_duration * (chunk_index + 1) / len(wrapped)
            timeline.append({"start": start, "end": end, "text": chunk})
        elapsed += duration - (transition if scene_index else 0)
    caption_path = output / "captions.srt"
    caption_path.write_text("\n\n".join(f"{index}\n{srt_timestamp(item['start'])} --> {srt_timestamp(item['end'])}\n{item['text']}" for index, item in enumerate(timeline, 1)), encoding="utf-8")
    (output / "editorial.json").write_text(json.dumps(plan.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    technical = technical_checks(video, caption_path, expected_dimensions=(spec.width, spec.height))
    return {"decision": "ALLOW" if technical["decision"] == "ALLOW" else "BLOCK", "video": str(video), "platform": platform, "mobile_style": mobile_style, "zooms_per_game": 2 if mobile_style == "zoom" and not spec.landscape else 0, "scenes": len(ordered), "real_video_clips": True, "synthetic_fallback": False, "full_bleed_action": not spec.landscape and mobile_style == "zoom", "transitions": len(offsets), "voice_only": True, "avatar_present": False, "technical": technical}


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
