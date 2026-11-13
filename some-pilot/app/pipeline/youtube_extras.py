"""YouTube work after a successful upload: caption track, series playlist and chapters.

Both API calls need the OAuth scope youtube.force-ssl (captions.insert costs 400
quota units, playlistItems.insert 50). They run only when the owner approved
them as part of the destination (approval digest v2), never block or undo a
publication that already succeeded, and report a precise status such as
scope_missing_reauthorize when the token lacks the scope.
"""

import json
import re
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.db.models import Publication, Setting, VideoVersion

PLAYLISTS_KEY = "youtube_series_playlists"
SRT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
MIN_CHAPTERS = 3
MIN_CHAPTER_SECONDS = 10


def _shift(match: re.Match, offset: float) -> str:
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    total = max(0.0, hours * 3600 + minutes * 60 + seconds + millis / 1000 + offset)
    whole = int(total)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d},{round((total - whole) * 1000) % 1000:03d}"


def shifted_srt(srt_text: str, offset_seconds: float) -> str:
    """Captions are timed against the editorial content; the published file starts with the brand intro."""
    return SRT_TIME.sub(lambda match: _shift(match, offset_seconds), srt_text)


def _status_from(response: httpx.Response) -> str:
    if response.status_code == 403 and "insufficient" in response.text.casefold():
        return "scope_missing_reauthorize"
    if response.status_code in {401, 403}:
        return f"authorization_http_{response.status_code}"
    return f"http_{response.status_code}"


def upload_captions(video: VideoVersion, remote_id: str, token: str) -> dict:
    captions = Path(video.output_dir) / "captions.srt"
    if not captions.is_file():
        return {"status": "no_captions_file"}
    offset = float((video.features_json or {}).get("intro_seconds") or 0)
    body = shifted_srt(captions.read_text(encoding="utf-8"), offset).encode("utf-8")
    metadata = {"snippet": {"videoId": remote_id, "language": video.language or "en", "name": "English" if (video.language or "en").startswith("en") else video.language, "isDraft": False}}
    response = httpx.post(
        "https://www.googleapis.com/upload/youtube/v3/captions",
        params={"part": "snippet", "uploadType": "multipart"},
        headers={"Authorization": f"Bearer {token}"},
        files={"metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"), "media": ("captions.srt", body, "application/octet-stream")},
        timeout=60,
    )
    if response.status_code >= 400:
        return {"status": _status_from(response)}
    return {"status": "uploaded", "caption_id": response.json().get("id"), "offset_seconds": offset}


def ensure_series_playlist(db: Session, series: dict, token: str) -> tuple[str | None, str]:
    mapping = dict((db.get(Setting, PLAYLISTS_KEY).value_json if db.get(Setting, PLAYLISTS_KEY) else {}) or {})
    if series["id"] in mapping:
        return mapping[series["id"]], "existing"
    response = httpx.post(
        "https://www.googleapis.com/youtube/v3/playlists",
        params={"part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}"},
        json={"snippet": {"title": series["name"][:150], "description": series.get("promise", "")[:5000]}, "status": {"privacyStatus": "public"}},
        timeout=30,
    )
    if response.status_code >= 400:
        return None, _status_from(response)
    mapping[series["id"]] = response.json()["id"]
    db.merge(Setting(key=PLAYLISTS_KEY, value_json=mapping))
    db.commit()
    return mapping[series["id"]], "created"


def add_to_series_playlist(db: Session, series_id: str, remote_id: str, token: str) -> dict:
    from app.pipeline.audience import load_series

    series = next((item for item in load_series() if item["id"] == series_id), None)
    if series is None:
        return {"status": "series_unknown"}
    playlist_id, state = ensure_series_playlist(db, series, token)
    if playlist_id is None:
        return {"status": state}
    response = httpx.post(
        "https://www.googleapis.com/youtube/v3/playlistItems",
        params={"part": "snippet"},
        headers={"Authorization": f"Bearer {token}"},
        json={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": remote_id}}},
        timeout=30,
    )
    if response.status_code >= 400:
        return {"status": _status_from(response), "playlist_id": playlist_id}
    return {"status": "added", "playlist_id": playlist_id, "playlist": state}


def run_post_publish(db: Session, video: VideoVersion, publication: Publication, token: str, plan: dict) -> dict:
    """Never raises: the video is already public; problems are recorded and alerted."""
    results = {}
    if plan.get("captions"):
        try:
            results["captions"] = upload_captions(video, publication.remote_id, token)
        except Exception as exc:
            results["captions"] = {"status": "error", "error": type(exc).__name__}
    if plan.get("series_playlist"):
        try:
            results["series_playlist"] = add_to_series_playlist(db, plan["series_playlist"], publication.remote_id, token)
        except Exception as exc:
            results["series_playlist"] = {"status": "error", "error": type(exc).__name__}
    publication.response_json = {**(publication.response_json or {}), "post_publish": results}
    db.commit()
    problems = [f"{name}:{item['status']}" for name, item in results.items() if item.get("status") not in {"uploaded", "added", "no_captions_file"}]
    if problems:
        try:
            from app.pipeline.alerts import immediate

            immediate(db, "warning", f"youtube_post_publish:{publication.id}", f"YouTube {publication.remote_id}: " + ", ".join(problems))
        except Exception:
            pass
    return results


# --- chapters ----------------------------------------------------------------

def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}" if whole >= 3600 else f"{whole // 60}:{whole % 60:02d}"


def build_chapters(packet: dict, narration: str, caption_segments: list[dict], chapter_titles: list[dict], intro_seconds: float, total_seconds: float) -> dict:
    """Chapter timestamps for the description, following YouTube's rules
    (first at 0:00, at least three, each at least ten seconds) or a reason why not."""
    if not chapter_titles:
        return {"status": "not_requested", "text": ""}
    segments = {segment["id"]: segment for segment in packet["segments"]}
    offsets, cursor = [], 0
    for segment in caption_segments:
        offsets.append((cursor, float(segment["start"])))
        cursor += len(segment["text"].strip()) + 1
    chapters = []
    for item in chapter_titles:
        segment = segments.get(item["segment_id"])
        if segment is None:
            return {"status": f"unknown_segment:{item['segment_id']}", "text": ""}
        position = narration.find(segment["voiceover"].strip()[:40])
        if position < 0:
            return {"status": f"segment_not_in_narration:{item['segment_id']}", "text": ""}
        start = next((time for char, time in reversed(offsets) if char <= position), 0.0)
        chapters.append({"title": item["title"].strip()[:80], "seconds": intro_seconds + start})
    chapters.sort(key=lambda row: row["seconds"])
    if chapters:
        # The 3.5 s brand intro is too short to be its own chapter; the first chapter starts at 0:00 and covers it.
        chapters[0]["seconds"] = 0.0
    if len(chapters) < MIN_CHAPTERS:
        return {"status": "too_few_chapters", "text": ""}
    bounds = [row["seconds"] for row in chapters] + [total_seconds]
    if any(end - start < MIN_CHAPTER_SECONDS for start, end in zip(bounds, bounds[1:])):
        return {"status": "chapter_shorter_than_10_seconds", "text": ""}
    text = "\n".join(f"{_clock(row['seconds'])} {row['title']}" for row in chapters)
    return {"status": "ok", "text": text, "chapters": chapters}
