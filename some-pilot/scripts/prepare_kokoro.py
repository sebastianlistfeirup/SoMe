import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import httpx
import soundfile as sf

from app.config import get_settings
from app.pipeline.downloader import UnsafeDownload, validate_public_url
from app.pipeline.ranking import RankingPlan

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
MAX_BYTES = 400_000_000


def secure_download(url: str, target: Path) -> str:
    current = url
    redirects = 0
    with httpx.Client(follow_redirects=False, timeout=60) as client:
        while True:
            validate_public_url(current)
            with client.stream("GET", current, headers={"User-Agent": "SoMePilot/0.1"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirects >= 5 or "location" not in response.headers:
                        raise UnsafeDownload("invalid_model_redirect")
                    current = urljoin(current, response.headers["location"])
                    redirects += 1
                    continue
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length and int(length) > MAX_BYTES:
                    raise UnsafeDownload("model_too_large")
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            handle.close()
                            target.unlink(missing_ok=True)
                            raise UnsafeDownload("model_too_large_while_streaming")
                        digest.update(chunk)
                        handle.write(chunk)
                return digest.hexdigest()


def ensure_models() -> tuple[Path, Path, dict]:
    directory = get_settings().model_cache_dir / "kokoro"
    model = directory / "kokoro-v1.0.onnx"
    voices = directory / "voices-v1.0.bin"
    evidence = {"model": "Kokoro-82M", "runtime": "kokoro-onnx 0.6.1", "license": "Apache-2.0", "source": "https://huggingface.co/hexgrad/Kokoro-82M", "files": {}}
    for url, path, name in ((MODEL_URL, model, "kokoro-v1.0.onnx"), (VOICES_URL, voices, "voices-v1.0.bin")):
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else secure_download(url, path)
        evidence["files"][name] = {"url": url, "sha256": sha256, "bytes": path.stat().st_size}
    (directory / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return model, voices, evidence


def generate(plan_path: Path, voice: str, speed: float, output_name: str) -> None:
    from kokoro_onnx import Kokoro

    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    model, voices, evidence = ensure_models()
    engine = Kokoro(str(model), str(voices))
    output = plan_path.parent / output_name
    output.mkdir(exist_ok=True)
    items = [("hook", plan.hook), *[(f"rank-{scene.rank:02d}", scene.narration) for scene in plan.scenes]]
    metadata = []
    for name, text in items:
        target = output / f"{name}.wav"
        if target.exists():
            info = sf.info(target)
            metadata.append({"file": target.name, "text": text, "voice": voice, "speed": speed, "sample_rate": info.samplerate, "seconds": info.frames / info.samplerate, "reused": True})
            print(json.dumps(metadata[-1]), flush=True)
            continue
        samples, sample_rate = engine.create(text, voice=voice, speed=speed, lang="en-us")
        sf.write(target, samples, sample_rate)
        metadata.append({"file": target.name, "text": text, "voice": voice, "speed": speed, "sample_rate": sample_rate, "seconds": len(samples) / sample_rate})
        print(json.dumps(metadata[-1]), flush=True)
    payload = plan_path.read_text(encoding="utf-8")
    data = json.loads(payload)
    data["voice_dir"] = output_name
    data["voice_model"] = f"Kokoro-82M/{voice}/speed-{speed}"
    plan_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "metadata.json").write_text(json.dumps({"model": evidence, "voice": metadata}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--voice", default="af_bella")
    parser.add_argument("--speed", type=float, default=1.08)
    parser.add_argument("--output", default="voice-kokoro")
    args = parser.parse_args()
    if not 0.8 <= args.speed <= 1.3:
        raise ValueError("voice_speed_outside_reviewed_range")
    generate(args.plan, args.voice, args.speed, args.output)
