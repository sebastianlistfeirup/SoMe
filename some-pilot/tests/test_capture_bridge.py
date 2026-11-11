import json
from pathlib import Path

import pytest

from scripts.capture_bridge import load_config, process_capture, process_pending, run, tool_path


def config(tmp_path):
    return {
        "capture_dir": str(tmp_path / "captures"),
        "processed_dir": str(tmp_path / "processed"),
        "default_game": "hades",
        "stable_pause_seconds": 0,
        "games": {
            "hades": {
                "source_url": "https://publisher.example/hades",
                "policy_url": "https://publisher.example/policy",
                "rights_holder": "Publisher",
                "rights_evidence": "Official publisher policy permits monetized gameplay commentary.",
                "attribution": "Official game page",
                "context": "Own gameplay recorded with OBS.",
            }
        },
    }


def test_capture_config_requires_https_evidence(tmp_path):
    payload = config(tmp_path)
    payload["games"]["hades"]["policy_url"] = "http://insecure.example"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="https"):
        load_config(path)


def make_capture(tmp_path):
    capture = tmp_path / "captures"
    capture.mkdir()
    source = capture / "obs-test.mkv"
    ffmpeg = tool_path("ffmpeg", config(tmp_path))
    run([ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)])
    return source


def test_process_capture_creates_mp4_contact_sheet_and_manifest(tmp_path, monkeypatch):
    source = make_capture(tmp_path)
    monkeypatch.setattr("scripts.capture_bridge.wait_until_stable", lambda *_args, **_kwargs: None)
    result = process_capture(source, config(tmp_path), "hades", upload=False)
    output = Path(result["directory"])
    manifest = json.loads((output / "capture-manifest.json").read_text())
    assert result["status"] == "processed"
    assert result["uploaded"] is False
    assert (output / "gameplay.mp4").stat().st_size > 1000
    assert (output / "contact-sheet.jpg").stat().st_size > 1000
    assert manifest["source_type"] == "owned_gameplay"
    assert manifest["ai_generated"] is False
    assert manifest["publication_allowed"] is False
    assert len(manifest["capture"]["sha256"]) == 64
    assert manifest["capture"]["duration_seconds"] == pytest.approx(2, abs=0.2)


def test_pending_is_idempotent(tmp_path, monkeypatch):
    source = make_capture(tmp_path)
    monkeypatch.setattr("scripts.capture_bridge.process_capture", lambda path, config, game, upload: {"status": "processed", "directory": str(tmp_path / "result"), "uploaded": False})
    first = process_pending(config(tmp_path), upload=False)
    second = process_pending(config(tmp_path), upload=False)
    assert len(first) == 1
    assert first[0]["status"] == "processed"
    assert second == []
    assert source.exists()


def test_process_capture_rejects_unknown_game(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"not-empty")
    with pytest.raises(ValueError, match="unknown_game_profile"):
        process_capture(source, config(tmp_path), "unknown")


def test_filename_selects_game_profile(tmp_path):
    from scripts.capture_bridge import game_for_path
    payload = config(tmp_path)
    payload["games"]["celeste"] = dict(payload["games"]["hades"])
    assert game_for_path(Path("celeste-run-01.mkv"), payload) == "celeste"
    assert game_for_path(Path("hades-boss.mkv"), payload) == "hades"
    assert game_for_path(Path("unlabelled.mkv"), payload) == "hades"
