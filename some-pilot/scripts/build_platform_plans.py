import argparse
import json
from pathlib import Path

TIKTOK_HOOK = "Handheld gamers, this is the list. Ten incredible Legion Go two games. Wait for number one."
YOUTUBE_HOOK = "Handheld gamers, this is the list. Ten incredible games for your Legion Go two, chosen for controller-first play, readability and brilliant game design. Our number one absolutely earns the crown."
DETAILS = {
    "Transistor": "The ability to pause and plan each sequence gives fights a satisfying tactical rhythm instead of turning them into button-mashing chaos.",
    "Celeste": "Every failure teaches you something, and the instant retries make even the toughest rooms feel worth another attempt.",
    "Slay the Spire": "Every card choice changes the direction of your run, which makes it easy to experiment without a huge time commitment.",
    "Hollow Knight": "The interconnected map rewards curiosity, while the responsive movement makes every discovery feel earned.",
    "Hades": "Each escape attempt reveals more of the world and its characters, so even a failed run still feels like progress.",
    "Slay the Spire 2": "It keeps the clarity that made the original so compelling while giving returning players fresh decisions to master.",
    "Stardew Valley": "There is always a small goal within reach, whether that means harvesting crops, fishing or meeting the neighbors.",
    "Balatro": "Watching a clever combination turn a modest hand into an outrageous score is the kind of payoff that never gets old.",
    "Hollow Knight: Silksong": "Hornet's faster movement gives combat its own identity, with aggressive exchanges that look spectacular on a handheld screen.",
    "Hades II": "The variety of weapons, builds and challenges gives it enormous replay value, whether you have ten minutes or an entire evening.",
}


def short_narration(scene: dict) -> str:
    sentences = scene["narration"].split(". ")
    return sentences[0].rstrip(".") + "."


def main(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    tiktok = dict(plan)
    tiktok["hook"] = TIKTOK_HOOK
    tiktok["post_text"] = "Ten incredible handheld games. Which one is your number one? Follow for more handheld gaming picks. Editorial ranking, not an FPS benchmark. Independent and unsponsored; game footage belongs to the respective publishers."
    tiktok["scenes"] = [{**scene, "narration": short_narration(scene)} for scene in plan["scenes"]]
    tiktok["voice_dir"] = "voice-tiktok"
    (plan_path.parent / "plan-tiktok.json").write_text(json.dumps(tiktok, indent=2, ensure_ascii=False), encoding="utf-8")

    youtube = dict(plan)
    youtube["hook"] = YOUTUBE_HOOK
    youtube["post_text"] = "Our editorial top 10 games for Legion Go 2, chosen for controller-first design, readability and great handheld sessions. This is not an FPS benchmark. Tell us your number one in the comments and subscribe for more handheld gaming. Independent and unsponsored; gameplay belongs to the respective publishers. Official sources and policies are linked below."
    youtube["scenes"] = [{**scene, "narration": scene["narration"] + " " + DETAILS[scene["game"]]} for scene in plan["scenes"]]
    youtube["voice_dir"] = "voice-youtube"
    (plan_path.parent / "plan-youtube.json").write_text(json.dumps(youtube, indent=2, ensure_ascii=False), encoding="utf-8")
    plan["post_text"] = "Save this handheld gaming top 10 and share it with someone who needs a new game. Which title is your number one? Editorial ranking, not an FPS benchmark. Independent and unsponsored; game footage belongs to the respective publishers."
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"reels": str(plan_path), "tiktok": str(plan_path.parent / "plan-tiktok.json"), "youtube": str(plan_path.parent / "plan-youtube.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    main(args.plan)
