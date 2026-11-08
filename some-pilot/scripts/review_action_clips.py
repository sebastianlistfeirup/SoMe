import json
from pathlib import Path

from app.pipeline.media import probe, run


def main(root: Path) -> None:
    rights = json.loads((root / "rights.json").read_text(encoding="utf-8"))
    previews = root / "previews"
    previews.mkdir(exist_ok=True)
    for clip in rights["clips"]:
        source = root / clip["local_path"]
        duration = float(probe(source)["format"]["duration"])
        frames = min(20, max(4, int(duration // 5)))
        interval = duration / frames
        target = previews / f"{clip['app_id']}-action.jpg"
        run(["ffmpeg", "-y", "-i", str(source), "-vf", f"fps=1/{interval:.6f},scale=384:216,tile=5x4", "-frames:v", "1", "-q:v", "2", str(target)])
        print(json.dumps({"game": clip["game"], "frames": frames, "interval": round(interval, 2), "output": str(target)}), flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    main(args.root)
