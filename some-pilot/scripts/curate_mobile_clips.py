import argparse
import hashlib
import json
from pathlib import Path

from app.pipeline.media import probe

START_SECONDS = {
    "Hades II": 77,
    "Hollow Knight: Silksong": 52,
    "Balatro": 18,
    "Stardew Valley": 27,
    "Slay the Spire 2": 18,
    "Hades": 78,
    "Hollow Knight": 72,
    "Slay the Spire": 10,
    "Celeste": 32,
    "Transistor": 59,
}


def main(root: Path) -> None:
    rights_path = root / "rights.json"
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    balatro = next(clip for clip in rights["clips"] if clip["game"] == "Balatro")
    source = root / "clips" / "balatro-launch.mp4"
    metadata = probe(source)
    video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    balatro.update({
        "clip_url": "https://www.youtube.com/watch?v=2n9pkiuSZLU",
        "clip_title": "Balatro - Launch Trailer | THE POKER ROGUELIKE",
        "download_page": "https://www.youtube.com/watch?v=2n9pkiuSZLU",
        "local_path": "clips/balatro-launch.mp4",
        "duration_seconds": float(metadata["format"]["duration"]),
        "rights_holder": "Playstack Ltd / LocalThunk",
        "download": {
            "source_url": "https://www.youtube.com/watch?v=2n9pkiuSZLU",
            "transport": "official_publisher_youtube",
            "bytes": source.stat().st_size,
        },
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "media": {"width": video["width"], "height": video["height"], "codec": video["codec_name"]},
        "resolution_note": "Official Playstack launch trailer; verified local copy is 640x360. A higher-resolution download was unavailable, so no quality claim is made.",
    })
    rights_path.write_text(json.dumps(rights, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for name in ("plan.json", "plan-tiktok.json", "plan-youtube.json"):
        path = root / name
        plan = json.loads(path.read_text(encoding="utf-8"))
        for scene in plan["scenes"]:
            scene["start_seconds"] = START_SECONDS[scene["game"]]
            if scene["game"] == "Balatro":
                for key in ("clip_url", "source_duration_seconds", "rights_holder"):
                    scene[key] = balatro[{"source_duration_seconds": "duration_seconds"}.get(key, key)]
                scene["source_path"] = balatro["local_path"]
                scene["attribution"] = "Official Balatro launch trailer by Playstack; Balatro official game page"
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"plans_updated": 3, "celeste_start_seconds": START_SECONDS["Celeste"], "balatro": balatro["media"], "duration_seconds": balatro["duration_seconds"], "sha256": balatro["sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    main(args.root)
