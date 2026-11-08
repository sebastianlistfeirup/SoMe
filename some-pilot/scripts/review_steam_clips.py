import argparse
import json
from pathlib import Path

from app.pipeline.media import probe, run
from app.pipeline.ranking import RankingPlan

RANKS = ["Transistor", "Celeste", "Slay the Spire", "Hollow Knight", "Hades", "Slay the Spire 2", "Stardew Valley", "Balatro", "Hollow Knight: Silksong", "Hades II"]
EDIT_STARTS = {"Hades II": 48, "Hollow Knight: Silksong": 8, "Balatro": 2, "Stardew Valley": 10, "Slay the Spire 2": 27, "Hades": 110, "Hollow Knight": 5, "Slay the Spire": 15, "Celeste": 5, "Transistor": 50}
KICKERS = {
    "Hades II": "THE COMPLETE HANDHELD PACKAGE",
    "Hollow Knight: Silksong": "PRECISION. SPEED. ATMOSPHERE.",
    "Balatro": "ONE MORE RUN, EVERY TIME",
    "Stardew Valley": "YOUR COZY ESCAPE",
    "Slay the Spire 2": "THE NEXT DECK-BUILDING OBSESSION",
    "Hades": "THE GOLD STANDARD",
    "Hollow Knight": "A WORLD WORTH GETTING LOST IN",
    "Slay the Spire": "THE DECK-BUILDING CLASSIC",
    "Celeste": "TIGHT CONTROLS. BIG HEART.",
    "Transistor": "TACTICAL STYLE ON THE GO",
}
NARRATION = {
    "Hades II": "Number one is Hades two. Supergiant's rich combat, controller-first design and Steam Deck Verified status make it our strongest all-round handheld pick.",
    "Hollow Knight: Silksong": "At number two, Silksong combines razor-sharp movement with a gorgeous world. Demanding fights reward a proper controller and a focused screen.",
    "Balatro": "Number three is Balatro. Its brilliant run-based strategy works beautifully in short sessions, and its distinctive visual twists make every build feel fresh.",
    "Stardew Valley": "At number four, Stardew Valley is the cozy essential. Farm for five minutes or lose an entire evening; it fits whatever time you have.",
    "Slay the Spire 2": "Number five is Slay the Spire two. New cards and combinations build on an already excellent handheld formula for strategic runs.",
    "Hades": "At number six, the original Hades still delivers superb action and storytelling. Responsive combat makes it an easy game to recommend on a handheld.",
    "Hollow Knight": "Number seven is Hollow Knight. Its intricate world and exact platforming remain a fantastic match for focused, portable exploration.",
    "Slay the Spire": "At number eight, Slay the Spire remains endlessly replayable. Clear choices and quick restarts make it ideal for playing anywhere.",
    "Celeste": "Number nine is Celeste. Precise controls, smart level design and a heartfelt story create an exceptional platformer for handheld sessions.",
    "Transistor": "Kicking off at number ten, Transistor blends tactical combat with a stunning science-fiction world. Its thoughtful pace makes it a great portable adventure.",
}


def review(root: Path) -> None:
    rights = json.loads((root / "rights.json").read_text(encoding="utf-8"))
    previews = root / "previews"
    previews.mkdir(exist_ok=True)
    clips = {clip["game"]: clip for clip in rights["clips"]}
    if set(clips) != set(RANKS):
        raise RuntimeError("exactly_ten_selected_games_required")
    for game, clip in clips.items():
        duration = clip["duration_seconds"]
        target = previews / f"{clip['app_id']}.jpg"
        run(["ffmpeg", "-y", "-i", str(root / clip["local_path"]), "-vf", f"fps=5/{duration:.6f},scale=384:216,tile=5x1", "-frames:v", "1", "-q:v", "2", str(target)])
    print(json.dumps({"contact_sheets": len(clips), "directory": str(previews)}))


def plan(root: Path) -> None:
    rights = json.loads((root / "rights.json").read_text(encoding="utf-8"))
    clips = {clip["game"]: clip for clip in rights["clips"]}
    if set(clips) != set(RANKS):
        raise RuntimeError("exactly_ten_selected_games_required")
    scenes = []
    for index, game in enumerate(RANKS):
        rank = 10 - index
        clip = clips[game]
        scenes.append({
            "rank": rank,
            "game": game,
            "kicker": KICKERS[game],
            "narration": NARRATION[game],
            "clip_url": clip["clip_url"],
            "policy_url": clip["policy_url"],
            "source_path": clip["local_path"],
            "start_seconds": clip.get("edit_start_seconds", EDIT_STARTS[game]),
            "source_duration_seconds": clip["duration_seconds"],
            "rights_holder": clip["rights_holder"],
            "rights_evidence": clip["rights_evidence"],
            "music_allowed": clip["music_allowed"],
            "attribution": clip["attribution"],
        })
    payload = {
        "title": "10 games worth your time on Legion Go 2",
        "hook": "Ten genuinely great games for your Legion Go two, ranked for handheld play. Number one is a modern classic.",
        "post_text": "Our editorial top 10 handheld games for Legion Go 2: controller-first design, readable gameplay and great short-session experiences. Not an FPS benchmark. Which game would be your number one? Follow for more handheld picks. All gameplay belongs to the respective publishers; this independent editorial video is not sponsored or endorsed. Sources and official game links are in the rights manifest.",
        "voice_dir": "voice",
        "scenes": scenes,
    }
    validated = RankingPlan.model_validate(payload)
    (root / "plan.json").write_text(validated.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"plan": str(root / "plan.json"), "games": len(scenes)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["review", "plan"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "review":
        review(args.root)
    else:
        plan(args.root)
