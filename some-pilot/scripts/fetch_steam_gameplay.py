import argparse
import hashlib
import json
from pathlib import Path

import httpx

from app.pipeline.downloader import download, validate_public_url
from app.pipeline.media import probe

GAMES = {
    "Hades II": (1145350, "https://www.supergiantgames.com/blog/policy-on-lets-play-videos/", "Supergiant Games, LLC", True, "Hades II official game page"),
    "Hollow Knight: Silksong": (1030300, "https://www.teamcherry.com.au/faq", "Team Cherry", False, "Hollow Knight: Silksong official game page"),
    "Balatro": (2379780, "https://www.playstack.com/video-policy", "Playstack Ltd / LocalThunk", False, "Balatro official game page"),
    "Stardew Valley": (413150, "https://www.stardewvalley.net/stardew-monetization-policy-for-twitch-streamers-youtubers-etc/", "ConcernedApe", False, "Stardew Valley official game page"),
    "Slay the Spire 2": (2868840, "https://www.megacrit.com/content-policy/", "Mega Crit Games, LLC", True, "Slay the Spire 2 official Steam page"),
    "Hades": (1145360, "https://www.supergiantgames.com/blog/policy-on-lets-play-videos/", "Supergiant Games, LLC", True, "Hades official game page"),
    "Hollow Knight": (367520, "https://www.teamcherry.com.au/faq", "Team Cherry", False, "Hollow Knight official game page"),
    "Slay the Spire": (646570, "https://www.megacrit.com/content-policy/", "Mega Crit Games, LLC", True, "Slay the Spire official Steam page"),
    "Celeste": (504230, "https://www.celestegame.com/letsplay.html", "Maddy Makes Games Inc.", False, "Celeste official game page"),
    "Transistor": (237930, "https://www.supergiantgames.com/blog/policy-on-lets-play-videos/", "Supergiant Games, LLC", True, "Transistor official game page"),
}

EVIDENCE = {
    "Supergiant Games, LLC": "Official publisher policy permits monetized reviews and commentary using captured gameplay and music as part of game videos; functional official game link required.",
    "Team Cherry": "Official FAQ grants a free license to game owners and press to create and publish original reviews and gameplay videos and to monetize them.",
    "Playstack Ltd / LocalThunk": "Official video policy permits free, publicly available monetized videos with original creative input and commentary using released Gaming Content or official promotional trailers.",
    "ConcernedApe": "Official developer monetization policy permits playing Stardew Valley in videos and monetizing those videos.",
    "Mega Crit Games, LLC": "Official content policy permits monetized gameplay videos and music used transformatively; link to respective store page requested.",
    "Maddy Makes Games Inc.": "Official Celeste page permits monetized Let's Plays, speedruns and reviews; separate soundtrack uploads prohibited.",
}


def fetch(output: Path, game_names: list[str]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    clips_dir = output / "clips"
    clips_dir.mkdir(exist_ok=True)
    clips = []
    for game in game_names:
        app_id, policy_url, holder, music_allowed, attribution = GAMES[game]
        api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english&cc=us"
        validate_public_url(api_url)
        response = httpx.get(api_url, timeout=30, follow_redirects=False, headers={"User-Agent": "SoMePilot/0.1"})
        response.raise_for_status()
        payload = response.json()
        data = payload[str(app_id)]["data"]
        movies = data.get("movies", [])
        if not movies:
            raise RuntimeError(f"no_official_gameplay_movies:{game}")
        selected = next((movie for movie in movies if "gameplay" in movie["name"].lower() or "showcase" in movie["name"].lower()), movies[0])
        candidates = [selected.get("hls_h264") or selected.get("mp4", {}).get("max") or selected.get("mp4", {}).get("480")]
        if not candidates or not candidates[0]:
            raise RuntimeError(f"no_downloadable_video:{game}")
        target = clips_dir / f"{app_id}-{selected['id']}.mp4"
        if not target.exists():
            if "hls_h264" in selected:
                validate_public_url(candidates[0])
                if httpx.URL(candidates[0]).host != "video.akamai.steamstatic.com":
                    raise RuntimeError("unexpected_video_host")
                from app.pipeline.media import run
                run(["ffmpeg", "-y", "-protocol_whitelist", "https,tcp,tls,crypto", "-i", candidates[0], "-fs", "200000000", "-c", "copy", "-movflags", "+faststart", str(target)], timeout=180)
                if target.stat().st_size >= 200_000_000:
                    target.unlink(missing_ok=True)
                    raise RuntimeError(f"video_too_large:{game}")
                metadata = {"source_url": candidates[0], "transport": "official_steam_hls_h264", "bytes": target.stat().st_size}
            else:
                source, metadata = download(candidates[0], output / "quarantine")
                source.replace(target)
        else:
            metadata = {"source_url": candidates[0], "already_downloaded": True}
        probed = probe(target)
        duration = float(probed["format"]["duration"])
        clip = {
            "game": game,
            "app_id": app_id,
            "store_url": f"https://store.steampowered.com/app/{app_id}/",
            "clip_url": f"https://store.steampowered.com/app/{app_id}/?movie={selected['id']}",
            "clip_title": selected["name"],
            "download_page": candidates[0],
            "local_path": str(target.relative_to(output)),
            "duration_seconds": duration,
            "policy_url": policy_url,
            "rights_holder": holder,
            "commercial_allowed": True,
            "derivative_allowed": True,
            "platforms": ["youtube", "instagram", "tiktok", "facebook"],
            "music_allowed": music_allowed,
            "attribution": attribution,
            "rights_evidence": EVIDENCE[holder],
            "evidence_date": "2026-11-08",
            "download": metadata,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "media": {"width": next(stream["width"] for stream in probed["streams"] if stream["codec_type"] == "video"), "height": next(stream["height"] for stream in probed["streams"] if stream["codec_type"] == "video"), "codec": next(stream["codec_name"] for stream in probed["streams"] if stream["codec_type"] == "video")},
            "official_movies": [{"id": movie["id"], "name": movie["name"], "highlight": movie.get("highlight", False)} for movie in movies],
        }
        clips.append(clip)
        print(json.dumps({"game": game, "selected": selected["name"], "duration": duration, "bytes": target.stat().st_size}), flush=True)
    rights_path = output / "rights.json"
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    rights["clips"] = clips
    rights_path.write_text(json.dumps(rights, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games", nargs="*", default=list(GAMES))
    args = parser.parse_args()
    fetch(args.output, args.games)
