import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


GAME_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".mov"}
PLATFORM_FOLDERS = {"amiga", "commodore-64", "game-boy", "gameboy-advance", "gamecube", "mega-drive", "sega-mega-drive", "nes", "nintendo-64", "pc-games", "playstation-1", "playstation-2", "ps3", "ps4", "ps5", "snes", "switch", "switch-2", "wii", "wii-u", "x-box-series-x", "xbox-360"}


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = ("capture_dir", "processed_dir", "games")
    if any(not config.get(name) for name in required):
        raise ValueError("capture_config_missing_required_fields")
    for key, game in config["games"].items():
        if not GAME_KEY.fullmatch(key):
            raise ValueError("invalid_game_key")
        if not game["source_url"].startswith("https://") or not game["policy_url"].startswith("https://"):
            raise ValueError("game_evidence_requires_https")
        if not game.get("rights_evidence") or not game.get("rights_holder"):
            raise ValueError("game_rights_evidence_required")
    return config


def tool_path(name: str, config: dict) -> str:
    configured = config.get("tools", {}).get(name)
    if configured:
        if not Path(configured).is_file():
            raise RuntimeError(f"{name}_configured_path_missing")
        return configured
    discovered = shutil.which(name)
    if discovered:
        return discovered
    package_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    candidates = sorted(package_root.glob(f"Gyan.FFmpeg_*/ffmpeg-*/bin/{name}.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise RuntimeError(f"{name}_not_found")


def run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"capture_command_failed:{args[0]}:{result.stderr[-2000:]}")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wait_until_stable(path: Path, checks: int = 2, pause_seconds: float = 1.0, timeout_seconds: float = 60) -> None:
    started = time.monotonic()
    previous = -1
    stable = 0
    while stable < checks:
        if time.monotonic() - started > timeout_seconds:
            raise TimeoutError("capture_file_is_still_changing")
        size = path.stat().st_size if path.exists() else -1
        stable = stable + 1 if size == previous and size > 0 else 0
        previous = size
        if stable < checks:
            time.sleep(pause_seconds)


def probe(path: Path, config: dict) -> dict:
    result = run([tool_path("ffprobe", config), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    return json.loads(result.stdout)


def upload_directory(directory: Path, config: dict, game: str) -> str:
    ssh_config = Path(config["ssh_config"]).expanduser()
    if not ssh_config.is_file():
        raise RuntimeError("ssh_config_missing")
    remote = f"{config.get('remote_root', '/opt/some/data/media-library').rstrip('/')}/{game}/{directory.name}"
    ssh = [tool_path("ssh", config), "-F", str(ssh_config), config["ssh_alias"]]
    scp = [tool_path("scp", config), "-F", str(ssh_config)]
    run([*ssh, f"sudo install -d -o \"$(id -un)\" -g \"$(id -gn)\" {remote}"])
    files = [path for path in directory.iterdir() if path.is_file()]
    run([*scp, *map(str, files), f"{config['ssh_alias']}:{remote}/"], timeout=7200)
    run([*ssh, f"sudo chown -R 10001:10001 {remote}"])
    return remote


def footage_platform_for_path(path: Path, config: dict) -> str | None:
    capture_root = Path(config["capture_dir"]).resolve()
    parent = path.parent.resolve()
    while parent != capture_root and capture_root in parent.parents:
        folder_key = re.sub(r"[^a-z0-9]+", "-", parent.name.lower()).strip("-")
        if folder_key in PLATFORM_FOLDERS:
            return parent.name
        parent = parent.parent
    return None


def process_capture(input_path: Path, config: dict, game_key: str, upload: bool = False) -> dict:
    game = config["games"].get(game_key)
    if not game:
        raise ValueError("unknown_game_profile")
    if input_path.suffix.lower() not in VIDEO_EXTENSIONS or not input_path.is_file():
        raise ValueError("capture_file_missing_or_unsupported")
    wait_until_stable(input_path, pause_seconds=config.get("stable_pause_seconds", 1))
    metadata = probe(input_path, config)
    if not any(stream.get("codec_type") == "video" for stream in metadata.get("streams", [])):
        raise ValueError("capture_has_no_video_stream")
    timestamp = datetime.fromtimestamp(input_path.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", input_path.stem).strip("-")[:60] or "capture"
    directory = Path(config["processed_dir"]) / game_key / f"{timestamp}-{safe_stem}"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "gameplay.mp4"
    run([tool_path("ffmpeg", config), "-y", "-i", str(input_path), "-map", "0", "-c", "copy", "-movflags", "+faststart", str(output)])
    output_metadata = probe(output, config)
    duration = float(output_metadata.get("format", {}).get("duration", 0))
    contact_sheet = directory / "contact-sheet.jpg"
    run([tool_path("ffmpeg", config), "-y", "-i", str(output), "-vf", f"fps={10 / max(duration, 0.1):.6f},scale=320:-2,tile=5x2:margin=4:padding=4", "-frames:v", "1", "-q:v", "2", str(contact_sheet)])
    manifest = {
        "schema": "some-capture-v1",
        "game": game_key,
        "footage_platform": footage_platform_for_path(input_path, config),
        "release_platforms_require_separate_verification": True,
        "kind": "real_video",
        "source_type": game.get("source_type", "owned_gameplay"),
        "context": game.get("context", f"Own gameplay from {game_key}"),
        "source_path": output.name,
        "source_url": game["source_url"],
        "policy_url": game["policy_url"],
        "rights_holder": game["rights_holder"],
        "rights_evidence": game["rights_evidence"],
        "attribution": game.get("attribution", game["source_url"]),
        "contains_people": False,
        "ages_verified": False,
        "ai_generated": False,
        "capture": {
            "application": "OBS Studio",
            "original_filename": input_path.name,
            "duration_seconds": duration,
            "bytes": output.stat().st_size,
            "sha256": sha256(output),
            "ffprobe": output_metadata,
        },
        "contact_sheet": contact_sheet.name,
        "rights_review_required": True,
        "publication_allowed": False,
    }
    (directory / "capture-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    result = {"status": "processed", "directory": str(directory), "duration_seconds": duration, "contact_sheet": str(contact_sheet), "uploaded": False}
    if upload:
        result["remote_directory"] = upload_directory(directory, config, game_key)
        result["uploaded"] = True
    (directory / "process-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def state_path(config: dict) -> Path:
    return Path(config["processed_dir"]) / "capture-bridge-state.json"


def load_state(config: dict) -> dict:
    path = state_path(config)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(config: dict, state: dict) -> None:
    path = state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def game_for_path(path: Path, config: dict) -> str:
    capture_root = Path(config["capture_dir"]).resolve()
    parent = path.parent.resolve()
    platform_folder = footage_platform_for_path(path, config)
    if parent != capture_root and capture_root in parent.parents:
        for candidate in reversed(path.parent.parts):
            folder_key = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
            if folder_key in config["games"]:
                return folder_key
        if not platform_folder:
            return re.sub(r"[^a-z0-9]+", "-", path.parent.name.lower()).strip("-")
    name = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    match = next((key for key in config["games"] if f"-{key.replace('_', '-')}-" in f"-{name}-"), None)
    if match:
        return match
    return "unknown" if platform_folder else config.get("default_game", "hades")


def process_pending(config: dict, upload: bool = False) -> list[dict]:
    capture_dir = Path(config["capture_dir"])
    capture_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(config)
    results = []
    for path in sorted(capture_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        game = game_for_path(path, config)
        state_key = str(path.resolve())
        fingerprint = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
        if state.get(state_key, {}).get("fingerprint") == fingerprint and state[state_key].get("status") in {"processed", "error"}:
            continue
        try:
            result = process_capture(path, config, game, upload)
            state[state_key] = {"fingerprint": fingerprint, "status": "processed", "result": result}
            results.append(result)
        except Exception as exc:
            state[state_key] = {"fingerprint": fingerprint, "status": "error", "error": f"{type(exc).__name__}:{str(exc)[:300]}"}
            results.append({"status": "error", "file": str(path), "error": state[state_key]["error"]})
        save_state(config, state)
    return results


def watch(config: dict, upload: bool = False) -> None:
    poll_seconds = config.get("poll_seconds", 5)
    print(json.dumps({"status": "watching", "capture_dir": config["capture_dir"], "upload": upload, "default_game": config.get("default_game", "hades")}), flush=True)
    while True:
        for result in process_pending(config, upload):
            print(json.dumps(result, ensure_ascii=False), flush=True)
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local OBS capture processing and optional SSH upload")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--game", default="hades")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.input:
        result = process_capture(args.input, config, args.game, args.upload)
        print(json.dumps(result, ensure_ascii=False))
    elif args.once:
        print(json.dumps(process_pending(config, args.upload), ensure_ascii=False))
    elif args.watch:
        watch(config, args.upload)
    else:
        parser.error("choose --input, --once or --watch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
