import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import get_settings
from app.pipeline.approvals import sha256_file
from app.pipeline.downloader import detect_media_type
from app.pipeline.media import probe


@dataclass(frozen=True)
class AvatarProfile:
    content_type: str
    display_name: str
    voice_id: str
    look_id: str | None
    provider: str = "heygen"
    operator_method: str = "subscription_ui"


@dataclass(frozen=True)
class AvatarSegment:
    segment_id: str
    script: str


def profile_for(content_type: str) -> AvatarProfile:
    settings = get_settings()
    normalized = content_type.strip().lower()
    if normalized == "ai":
        return AvatarProfile(
            content_type="ai",
            display_name=settings.heygen_ai_avatar_name,
            voice_id=settings.heygen_ai_voice_id,
            look_id=settings.heygen_ai_avatar_look_id or None,
        )
    if normalized == "gaming":
        return AvatarProfile(
            content_type="gaming",
            display_name=settings.heygen_gaming_avatar_name,
            voice_id=settings.heygen_gaming_voice_id,
            look_id=settings.heygen_gaming_avatar_look_id or None,
        )
    raise ValueError(f"unsupported_avatar_content_type:{content_type}")


def write_avatar_request(output: Path, content_type: str, segments: list[AvatarSegment]) -> Path:
    if not segments or any(not segment.script.strip() for segment in segments):
        raise ValueError("avatar_segments_require_script")
    if len({segment.segment_id for segment in segments}) != len(segments):
        raise ValueError("avatar_segment_ids_must_be_unique")
    output.mkdir(parents=True, exist_ok=True)
    scripts_dir = output / "avatar_scripts"
    scripts_dir.mkdir(exist_ok=True)
    profile = profile_for(content_type)
    segment_rows = []
    for segment in segments:
        script_path = scripts_dir / f"{segment.segment_id}.txt"
        script_path.write_text(segment.script.strip() + "\n", encoding="utf-8")
        segment_rows.append(
            {
                "segment_id": segment.segment_id,
                "script_file": str(script_path.relative_to(output)),
                "expected_video_file": f"{segment.segment_id}.mp4",
            }
        )
    payload = {
        "schema_version": 1,
        "status": "AWAITING_AVATAR_RENDER",
        "provider": "heygen",
        "operator_method": "subscription_ui",
        "profile": asdict(profile),
        "instructions": [
            "Use the named private avatar profile in the HeyGen subscription UI; do not substitute another avatar.",
            "Use the exact voice_id and the exact UTF-8 script for every segment.",
            "Export one MP4 per segment with the expected filename and keep the avatar visible and speaking throughout that segment.",
            "Place the exported MP4 files together in one directory and resume the ranking command with --avatar-dir.",
        ],
        "segments": segment_rows,
    }
    request_path = output / "avatar_request.json"
    request_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return request_path


def validate_avatar_assets(avatar_dir: Path, request_path: Path) -> dict:
    if not avatar_dir.is_dir():
        return {"decision": "BLOCK", "reasons": ["avatar_directory_missing"], "files": []}
    request = json.loads(request_path.read_text(encoding="utf-8"))
    reasons = []
    files = []
    for segment in request.get("segments", []):
        expected = avatar_dir / segment["expected_video_file"]
        if not expected.is_file():
            reasons.append(f"avatar_segment_missing:{segment['segment_id']}")
            continue
        try:
            media_type = detect_media_type(expected)
            metadata = probe(expected)
        except Exception as exc:
            reasons.append(f"avatar_segment_unreadable:{segment['segment_id']}:{type(exc).__name__}")
            continue
        streams = metadata.get("streams", [])
        has_video = any(stream.get("codec_type") == "video" for stream in streams)
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        duration = float(metadata.get("format", {}).get("duration", 0) or 0)
        if media_type not in {"video/mp4", "video/webm"}:
            reasons.append(f"avatar_segment_type_invalid:{segment['segment_id']}")
        if not has_video:
            reasons.append(f"avatar_segment_video_missing:{segment['segment_id']}")
        if not has_audio:
            reasons.append(f"avatar_segment_audio_missing:{segment['segment_id']}")
        if duration < 1:
            reasons.append(f"avatar_segment_too_short:{segment['segment_id']}")
        files.append(
            {
                "segment_id": segment["segment_id"],
                "path": str(expected),
                "sha256": sha256_file(str(expected)),
                "duration_seconds": round(duration, 3),
                "has_video": has_video,
                "has_audio": has_audio,
            }
        )
    return {
        "decision": "ALLOW" if not reasons else "BLOCK",
        "reasons": reasons,
        "provider": request.get("provider"),
        "operator_method": request.get("operator_method"),
        "profile": request.get("profile", {}),
        "files": files,
    }


def ranking_segments(plan) -> list[AvatarSegment]:
    ordered = sorted(plan.scenes, key=lambda scene: scene.rank, reverse=True)
    return [AvatarSegment("hook", plan.hook), *[AvatarSegment(f"rank-{scene.rank:02d}", scene.narration) for scene in ordered]]
