import json
import textwrap
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.pipeline.downloader import detect_media_type
from app.pipeline.media import MediaError, _font_size, _srt_seconds, probe, run
from app.pipeline.scenes import scene_title


MIN_REAL_MEDIA_RATIO = 0.80


class RealMediaScene(BaseModel):
    kind: Literal["real_video", "real_image", "graphic"]
    source_type: Literal["producer", "generic", "owned_gameplay", "synthetic"]
    source_path: str = ""
    context: str = Field(min_length=3, max_length=300)
    source_url: str = ""
    policy_url: str = ""
    rights_holder: str = Field(min_length=2, max_length=300)
    rights_evidence: str = Field(min_length=10, max_length=3000)
    attribution: str = ""
    start_seconds: float = Field(default=0, ge=0)
    effect: Literal["static", "zoom_in", "zoom_out", "pan_left", "pan_right"] = "static"
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    contains_people: bool = False
    ages_verified: bool = False
    ai_generated: bool = False

    @model_validator(mode="after")
    def valid_source(self):
        if self.ai_generated and self.kind != "graphic":
            raise ValueError("ai_generated_cannot_count_as_real")
        if self.kind == "graphic":
            if self.source_type != "synthetic":
                raise ValueError("graphic_must_be_synthetic")
        else:
            if self.source_type == "synthetic" or not self.source_path:
                raise ValueError("real_media_source_required")
            if not self.source_url.startswith("https://") or not self.policy_url.startswith("https://"):
                raise ValueError("real_media_https_evidence_required")
            if self.kind == "real_video" and self.effect != "static":
                raise ValueError("video_effects_require_static_source_effect")
        return self


class RealMediaPlan(BaseModel):
    platform: Literal["youtube", "instagram", "tiktok", "facebook"] = "youtube"
    minimum_real_ratio: float = Field(default=MIN_REAL_MEDIA_RATIO, ge=MIN_REAL_MEDIA_RATIO, le=1)
    scenes: list[RealMediaScene] = Field(min_length=1, max_length=30)


class PreparedMedia(BaseModel):
    scene: RealMediaScene
    path: Path
    media_type: str
    source_duration_seconds: float

    @property
    def is_real(self) -> bool:
        return self.scene.kind != "graphic"


def load_media_plan(path: Path) -> RealMediaPlan:
    return RealMediaPlan.model_validate_json(path.read_text(encoding="utf-8"))


def media_coverage(plan: RealMediaPlan, durations: list[float], prepared: list[PreparedMedia]) -> dict:
    if len(durations) != len(prepared) or len(prepared) != len(plan.scenes):
        raise ValueError("media_scene_caption_count_mismatch")
    if any(duration <= 0 for duration in durations):
        raise ValueError("media_scene_duration_must_be_positive")
    total = sum(durations)
    real_seconds = sum(duration for duration, item in zip(durations, prepared) if item.is_real)
    ratio = real_seconds / total if total else 0
    allowed = ratio + 0.000001 >= plan.minimum_real_ratio
    return {
        "decision": "ALLOW" if allowed else "BLOCK",
        "reasons": [] if allowed else ["real_media_coverage_below_required_ratio"],
        "real_media_seconds": round(real_seconds, 3),
        "timeline_seconds": round(total, 3),
        "real_media_ratio": round(ratio, 6),
        "real_media_percent": round(ratio * 100, 2),
        "minimum_required_ratio": plan.minimum_real_ratio,
        "minimum_required_percent": round(plan.minimum_real_ratio * 100, 2),
        "real_scene_count": sum(item.is_real for item in prepared),
        "real_video_scenes": sum(item.scene.kind == "real_video" for item in prepared),
        "real_image_scenes": sum(item.scene.kind == "real_image" for item in prepared),
        "graphic_scene_count": sum(not item.is_real for item in prepared),
        "measurement": "duration_weighted_not_scene_count",
        "ai_generated_counts_as_real": False,
        "contexts": [{"kind": item.scene.kind, "source_type": item.scene.source_type, "context": item.scene.context, "effect": item.scene.effect} for item in prepared],
    }


def prepare_media(plan: RealMediaPlan, plan_path: Path, output: Path) -> list[PreparedMedia]:
    root = plan_path.parent.resolve()
    prepared = []
    for index, scene in enumerate(plan.scenes, 1):
        if scene.kind == "graphic":
            path = output / f"graphic-{index}.png"
            scene_title().save(path, format="PNG", optimize=True)
            prepared.append(PreparedMedia(scene=scene, path=path, media_type="image/png", source_duration_seconds=0))
            continue
        relative = Path(scene.source_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("media_source_outside_plan_directory")
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError("media_source_missing_or_outside_plan_directory")
        media_type = detect_media_type(path)
        if scene.kind == "real_image":
            if media_type not in {"image/jpeg", "image/png"}:
                raise ValueError("real_image_signature_mismatch")
            prepared.append(PreparedMedia(scene=scene, path=path, media_type=media_type, source_duration_seconds=0))
        else:
            if media_type not in {"video/mp4", "video/webm"}:
                raise ValueError("real_video_signature_mismatch")
            metadata = probe(path)
            if not any(stream.get("codec_type") == "video" for stream in metadata.get("streams", [])):
                raise ValueError("real_video_stream_missing")
            duration = float(metadata.get("format", {}).get("duration", 0))
            if duration <= scene.start_seconds + 0.2:
                raise ValueError("real_video_start_exceeds_source")
            prepared.append(PreparedMedia(scene=scene, path=path, media_type=media_type, source_duration_seconds=duration))
    return prepared


def _image_motion(scene: RealMediaScene, duration: float) -> str:
    frames = max(1, round(duration * 30))
    if scene.effect == "zoom_out":
        expression = "if(eq(on,0),1.08,max(zoom-0.0008,1.0))"
    elif scene.effect == "pan_left":
        expression = "1.06"
    elif scene.effect == "pan_right":
        expression = "1.06"
    else:
        expression = "min(zoom+0.0008,1.08)" if scene.effect == "zoom_in" else "1.0"
    if scene.effect == "pan_left":
        x = f"(iw-iw/zoom)*(1-on/{frames})"
    elif scene.effect == "pan_right":
        x = f"(iw-iw/zoom)*on/{frames}"
    else:
        x = "iw/2-(iw/zoom/2)"
    return f"zoompan=z='{expression}':x='{x}':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"


def render_real_media(prepared: list[PreparedMedia], narration: Path, captions: Path, title: str, output: Path, coverage: dict) -> dict:
    if not prepared or coverage.get("decision") != "ALLOW":
        raise MediaError("real_media_coverage_not_allowed")
    caption_blocks = [block for block in captions.read_text(encoding="utf-8").strip().split("\n\n") if block.strip()]
    if len(prepared) != len(caption_blocks):
        raise MediaError("media_scene_caption_count_mismatch")
    title_lines = textwrap.wrap(title, width=36)[:2]
    title_file = output.parent / "title.txt"
    title_file.write_text("\n".join(title_lines), encoding="utf-8")
    inputs = []
    filters = []
    durations = []
    for index, (item, block) in enumerate(zip(prepared, caption_blocks)):
        timing = block.splitlines()[1].split(" --> ")
        duration = max(0.2, _srt_seconds(timing[1]) - _srt_seconds(timing[0]))
        durations.append(duration)
        if item.scene.kind == "real_video":
            if item.scene.start_seconds + duration > item.source_duration_seconds + 0.05:
                raise MediaError("real_video_segment_exceeds_source_duration")
            inputs.extend(["-ss", f"{item.scene.start_seconds:.3f}", "-t", f"{duration:.3f}", "-i", str(item.path)])
        else:
            inputs.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(item.path)])
        crop = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:x='(in_w-1080)*{item.scene.focus_x:.3f}':y='(in_h-1920)*{item.scene.focus_y:.3f}'"
        motion = _image_motion(item.scene, duration) if item.scene.kind != "real_video" else "null"
        filters.append(f"[{index}:v]{crop},{motion},trim=duration={duration:.3f},setpts=PTS-STARTPTS,setsar=1[v{index}]")
    filters.append(f"{''.join(f'[v{index}]' for index in range(len(prepared)))}concat=n={len(prepared)}:v=1:a=0[scenes]")
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
                f"fontcolor=white:fontsize={size}:line_spacing=10:x=(w-text_w)/2:y=h-390:borderw=2:bordercolor=black:"
                f"box=1:boxcolor=black@0.58:boxborderw=14:enable='between(t,{chunk_start:.3f},{chunk_end:.3f})'"
            )
    title_size = _font_size(title_lines, 48, 920)
    caption_filters.append(
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile={title_file}:"
        f"fontcolor=white:fontsize={title_size}:line_spacing=8:x=(w-text_w)/2:y=100:borderw=2:bordercolor=black:"
        f"box=1:boxcolor=black@0.65:boxborderw=16:enable='lt(t,2.5)'"
    )
    filters.append(f"[scenes]{','.join(caption_filters)},scale=out_range=tv,format=yuv420p[final]")
    inputs.extend(["-i", str(narration)])
    run([
        "ffmpeg", "-y", *inputs,
        "-threads", "2", "-filter_threads", "2",
        "-filter_complex", ";".join(filters), "-map", "[final]", "-map", f"{len(prepared)}:a",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", str(output),
    ])
    return {
        "decision": "ALLOW",
        "reasons": [],
        "scene_count": len(prepared),
        "caption_blocks": caption_count,
        "real_media_ratio": coverage["real_media_ratio"],
        "real_media_percent": coverage["real_media_percent"],
        "real_video_scenes": sum(item.scene.kind == "real_video" for item in prepared),
        "real_image_scenes": sum(item.scene.kind == "real_image" for item in prepared),
        "graphic_scenes": sum(item.scene.kind == "graphic" for item in prepared),
        "image_effects": [item.scene.effect for item in prepared if item.scene.kind == "real_image"],
        "max_estimated_text_width": max_estimated_width,
        "caption_bottom_margin_px": 390,
        "synthetic_slide_fallback": False,
    }


def thumbnail_from_source(prepared: list[PreparedMedia], durations: list[float], output: Path) -> dict:
    if len(prepared) != len(durations):
        raise ValueError("thumbnail_scene_duration_mismatch")
    target = sum(durations) * 0.65
    elapsed = 0.0
    selected_index = next((index for index, item in enumerate(prepared) if item.scene.kind == "real_video"), None)
    for index, (item, duration) in enumerate(zip(prepared, durations)):
        if item.scene.kind == "real_video" and elapsed + duration >= target:
            selected_index = index
            break
        elapsed += duration
    if selected_index is None:
        selected_index = next((index for index, item in enumerate(prepared) if item.scene.kind == "real_image"), None)
    if selected_index is None:
        raise MediaError("real_thumbnail_source_missing")
    item = prepared[selected_index]
    source_seconds = item.scene.start_seconds + durations[selected_index] * 0.65
    inputs = ["-ss", f"{source_seconds:.3f}"] if item.scene.kind == "real_video" else []
    crop = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:x='(in_w-1080)*{item.scene.focus_x:.3f}':y='(in_h-1920)*{item.scene.focus_y:.3f}',scale=out_range=tv,format=yuv420p"
    run(["ffmpeg", "-y", *inputs, "-i", str(item.path), "-vf", crop, "-frames:v", "1", "-q:v", "2", str(output)])
    return {"scene_index": selected_index + 1, "source_seconds": round(source_seconds, 3), "source_type": item.scene.source_type, "clean_frame_without_captions": True}


def write_media_composition(output: Path, plan: RealMediaPlan, coverage: dict) -> None:
    payload = {"platform": plan.platform, **coverage}
    (output / "media_composition.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
