import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import get_settings
from app.pipeline.approvals import sha256_file
from app.pipeline.downloader import detect_media_type
from app.pipeline.media import probe, run

SEGMENT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
KOKORO_EVIDENCE = {"model": "Kokoro-82M", "runtime": "kokoro-onnx 0.6.1", "license": "Apache-2.0", "source": "https://huggingface.co/hexgrad/Kokoro-82M"}


@dataclass(frozen=True)
class VoiceSegment:
    segment_id: str
    text: str
    language: str = "en"


def ranking_voice_segments(plan) -> list[VoiceSegment]:
    ordered = sorted(plan.scenes, key=lambda scene: scene.rank, reverse=True)
    return [VoiceSegment("hook", plan.hook), *[VoiceSegment(f"rank-{scene.rank:02d}", scene.narration) for scene in ordered]]


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _base_report(provider: str, reasons: list[str], files: list[dict], **extra) -> dict:
    return {
        "decision": "ALLOW" if not reasons else "BLOCK",
        "reasons": reasons,
        "provider": provider,
        "voice_only": True,
        "avatar_present": False,
        "files": files,
        **extra,
    }


def _audio_file(segment: VoiceSegment, path: Path, reasons: list[str], **extra) -> dict:
    row = {
        "segment_id": segment.segment_id,
        "path": str(path),
        "text_sha256": text_sha256(segment.text),
        **extra,
    }
    try:
        media_type = detect_media_type(path)
        metadata = probe(path)
        audio = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"), None)
        duration = float(metadata.get("format", {}).get("duration", 0) or 0)
        sample_rate = int(audio.get("sample_rate", 0)) if audio else 0
        if media_type != "audio/wav":
            reasons.append(f"voice_segment_type_invalid:{segment.segment_id}")
        if audio is None:
            reasons.append(f"voice_segment_audio_missing:{segment.segment_id}")
        if duration < 1:
            reasons.append(f"voice_segment_too_short:{segment.segment_id}")
        if sample_rate <= 0:
            reasons.append(f"voice_segment_sample_rate_missing:{segment.segment_id}")
        row.update({
            "sha256": sha256_file(str(path)),
            "duration_seconds": round(duration, 3),
            "sample_rate": sample_rate,
            "channels": audio.get("channels") if audio else None,
        })
    except Exception as exc:
        reasons.append(f"voice_segment_unreadable:{segment.segment_id}:{type(exc).__name__}")
    return row


def _existing_kokoro(segments: list[VoiceSegment], directory: Path) -> dict:
    reasons = []
    files = []
    metadata_path = directory / "metadata.json"
    metadata = {}
    if not directory.is_dir():
        reasons.append("voice_directory_missing")
    elif not metadata_path.is_file():
        reasons.append("voice_metadata_missing")
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reasons.append("voice_metadata_invalid")
    expected_text = {row.get("file"): row for row in metadata.get("voice", [])}
    for segment in segments:
        path = directory / f"{segment.segment_id}.wav"
        expected = expected_text.get(path.name)
        if not path.is_file():
            reasons.append(f"voice_segment_missing:{segment.segment_id}")
            continue
        if not expected:
            reasons.append(f"voice_provenance_missing:{segment.segment_id}")
        elif text_sha256(str(expected.get("text", ""))) != text_sha256(segment.text):
            reasons.append(f"voice_text_mismatch:{segment.segment_id}")
        files.append(_audio_file(segment, path, reasons, voice=expected.get("voice") if expected else None, speed=expected.get("speed") if expected else None, reused=True))
    return _base_report("kokoro", reasons, files, paid_call=False, cost_dkk=0, model_evidence=metadata.get("model", {}))


def voice_asset_report(segment: VoiceSegment, path: Path, provider: str, **extra) -> dict:
    reasons = []
    row = _audio_file(segment, path, reasons, **extra)
    return _base_report(provider, reasons, [row], paid_call=False, cost_dkk=0)


@lru_cache(maxsize=1)
def _kokoro_engine():
    from kokoro_onnx import Kokoro
    from scripts.prepare_kokoro import ensure_models

    model, voices, _ = ensure_models()
    return Kokoro(str(model), str(voices))


def _generate_kokoro_file(segment: VoiceSegment, path: Path, voice: str, speed: float) -> None:
    import soundfile as sf

    samples, sample_rate = _kokoro_engine().create(segment.text.strip(), voice=voice, speed=speed, lang="en-us")
    sf.write(path, samples, sample_rate)


def _new_kokoro(segments: list[VoiceSegment], output_dir: Path) -> dict:
    settings = get_settings()
    reasons = []
    files = []
    if not 0.8 <= settings.voice_speed <= 1.3:
        return _base_report("kokoro", ["voice_speed_outside_reviewed_range"], files, paid_call=False, cost_dkk=0)
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
        for segment in segments:
            path = output_dir / f"{segment.segment_id}.wav"
            _generate_kokoro_file(segment, path, settings.voice_preset, settings.voice_speed)
            files.append(_audio_file(segment, path, reasons, voice=settings.voice_preset, speed=settings.voice_speed, reused=False))
    except Exception as exc:
        reasons.append(f"voice_generation_failed:{type(exc).__name__}")
    return _base_report("kokoro", reasons, files, paid_call=False, cost_dkk=0, model_evidence=KOKORO_EVIDENCE)


def _new_elevenlabs(segments: list[VoiceSegment], output_dir: Path) -> dict:
    settings = get_settings()
    reasons = []
    files = []
    if not settings.paid_jobs_enabled:
        reasons.append("paid_jobs_disabled")
    if not settings.elevenlabs_api_key:
        reasons.append("elevenlabs_api_key_missing")
    if not settings.elevenlabs_voice_id:
        reasons.append("elevenlabs_voice_id_missing")
    if not settings.elevenlabs_voice_rights_confirmed:
        reasons.append("elevenlabs_voice_rights_confirmation_required")
    if settings.elevenlabs_cost_per_1000_chars_dkk <= 0:
        reasons.append("elevenlabs_verified_unit_price_required")
    if not settings.elevenlabs_pricing_verified_at:
        reasons.append("elevenlabs_pricing_verification_date_required")
    estimated_cost = round(sum(len(segment.text.strip()) for segment in segments) * settings.elevenlabs_cost_per_1000_chars_dkk / 1000, 6)
    if estimated_cost > settings.max_job_ai_cost_dkk:
        reasons.append("elevenlabs_cost_above_job_limit")
    if reasons:
        return _base_report("elevenlabs", reasons, files, paid_call=False, estimated_cost_dkk=estimated_cost, actual_cost_dkk=None)
    output_dir.mkdir(parents=True, exist_ok=False)
    successful_calls = 0
    for segment in segments:
        raw_path = output_dir / f"{segment.segment_id}.pcm"
        path = output_dir / f"{segment.segment_id}.wav"
        try:
            response = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                params={"output_format": "pcm_24000"},
                headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
                json={"text": segment.text.strip(), "model_id": settings.elevenlabs_model_id},
                timeout=45,
            )
            response.raise_for_status()
            successful_calls += 1
            raw_path.write_bytes(response.content)
            run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw_path), "-ar", "48000", str(path)])
            files.append(_audio_file(segment, path, reasons, voice=settings.elevenlabs_voice_id, model=settings.elevenlabs_model_id, request_id=response.headers.get("x-request-id"), reused=False))
        except Exception as exc:
            reasons.append(f"voice_provider_request_failed:{segment.segment_id}:{type(exc).__name__}")
    paid_call = successful_calls > 0
    return _base_report("elevenlabs", reasons, files, paid_call=paid_call, estimated_cost_dkk=estimated_cost, actual_cost_dkk=estimated_cost if paid_call else None, successful_provider_calls=successful_calls, cost_basis="configured_verified_character_unit_price")


def prepare_voice(segments: list[VoiceSegment], provider: str, output_dir: Path, existing_dir: Path | None = None) -> dict:
    reasons = []
    if not segments:
        reasons.append("voice_segments_required")
    if len({segment.segment_id for segment in segments}) != len(segments):
        reasons.append("voice_segment_ids_must_be_unique")
    for segment in segments:
        if not SEGMENT_ID.fullmatch(segment.segment_id):
            reasons.append(f"voice_segment_id_invalid:{segment.segment_id}")
        if not segment.text.strip():
            reasons.append(f"voice_text_empty:{segment.segment_id}")
    if reasons:
        return _base_report(provider, reasons, [])
    if existing_dir is not None:
        if provider != "kokoro":
            return _base_report(provider, ["existing_voice_reuse_only_supported_for_kokoro"], [])
        return _existing_kokoro(segments, existing_dir)
    if provider == "kokoro":
        return _new_kokoro(segments, output_dir)
    if provider == "elevenlabs":
        return _new_elevenlabs(segments, output_dir)
    return _base_report(provider, ["unsupported_voice_provider"], [])


def voice_file_map(report: dict) -> dict[str, Path]:
    return {row["segment_id"]: Path(row["path"]) for row in report.get("files", []) if row.get("path") and "sha256" in row}
