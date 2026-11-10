from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import replace
from pathlib import Path


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build = load("build_posts", "/data/tools/build_test_posts.py")
finish = load("finish_posts", "/data/tools/finish_test_posts.py")


def rebuild_scene(post: str, mode: str, index: int, title: str) -> Path:
    build.POSTS[post]["scenes"][index] = replace(build.POSTS[post]["scenes"][index], title=title)
    post_dir = build.OUTPUT / post
    work = post_dir / f"work-{mode}"
    build.render_segment(post, mode, index, work)
    segments = [work / f"scene-{item:02d}.mp4" for item in range(len(build.POSTS[post]["scenes"]))]
    visual = work / "visual.mp4"
    build.concat_visual(segments, visual, work)
    master = post_dir / f"master-{mode}.mp4"
    build.mux_master(visual, build.POSTS[post]["avatar_landscape"], post_dir / "original-music.wav", master)
    return master


def finalise(post: str, platform: str, source: Path) -> None:
    content = finish.WORK / f"{post}-{platform}-content-fixed.mp4"
    target = finish.FINAL / f"pixel-and-parameters-{post}-{platform}.mp4"
    finish.brand_content(post, source, content, "vertical")
    finish.concat(
        finish.WORK / "ident-vertical-intro.mp4",
        content,
        finish.WORK / "ident-vertical-outro.mp4",
        target,
    )


def main() -> None:
    # Gaming: only the closing headline is too long in 9:16.
    gaming_zoom = rebuild_scene("gaming", "zoom", 6, "YOUR HANDHELD PICK?")
    gaming_safe = rebuild_scene("gaming", "safe", 6, "YOUR HANDHELD PICK?")
    gaming_timings = build.TIMINGS["gaming"]["paragraphs"]
    gaming_tiktok = build.OUTPUT / "gaming" / "tiktok-9x16.mp4"
    build.cut_scenes(gaming_zoom, gaming_timings, build.POSTS["gaming"]["tiktok_scenes"], gaming_tiktok)
    gaming_reels = build.OUTPUT / "gaming" / "instagram-reels-9x16.mp4"
    shutil.copyfile(gaming_safe, gaming_reels)
    finalise("gaming", "tiktok-9x16", gaming_tiktok)
    finalise("gaming", "instagram-reels-9x16", gaming_reels)

    # AI: the three-spec headline gets a concise vertical title.
    ai_safe = rebuild_scene("ai", "safe", 2, "THE THREE SPECS")
    ai_timings = build.TIMINGS["ai"]["paragraphs"]
    ai_tiktok = build.OUTPUT / "ai" / "tiktok-safe-9x16.mp4"
    build.cut_scenes(ai_safe, ai_timings, build.POSTS["ai"]["tiktok_scenes"], ai_tiktok)
    ai_reels = build.OUTPUT / "ai" / "instagram-reels-9x16.mp4"
    build.cut_scenes(ai_safe, ai_timings, build.POSTS["ai"]["reels_scenes"], ai_reels)
    finalise("ai", "tiktok-9x16", ai_tiktok)
    finalise("ai", "instagram-reels-9x16", ai_reels)


if __name__ == "__main__":
    main()
