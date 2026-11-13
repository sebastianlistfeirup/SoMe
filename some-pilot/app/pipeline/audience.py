"""Series, derivatives from one research packet, viewer comments, manual tests and source comments.

- Series: recurring formats from content/SERIES.json; production validates the
  series id and learning reports performance per series.
- Derivatives: one researched packet with several variants becomes several
  media plans (one per variant) without repeating the research.
- Comments: public top-level comments on our own YouTube videos become FAQ and
  idea signals. Author names and channel IDs are never stored.
- Manual tests: YouTube Studio "Test & Compare" has no API; the owner records
  its outcome against a pre-registered experiment.
- Sources comment: a ready-to-paste comment listing the video's sources. The
  API cannot pin comments, and posting one is a publishing action, so it is
  prepared for the owner, not posted.
"""

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuditEvent, Experiment, IdeaSuggestion, Publication, VideoComment, VideoVersion

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"
STOPWORDS = set("the a an and or but if of to in on for with is are was were be it this that these those you your i we they he she what why how when where which who can could would should do does did not no yes my our their there here just so very more most about from as at by into than then too also really game games video".split())


# --- series ---------------------------------------------------------------------

def load_series() -> list[dict]:
    return json.loads((CONTENT_ROOT / "SERIES.json").read_text(encoding="utf-8"))["series"]


def series_by_recipe() -> dict[str, str]:
    return {item["recipe_id"]: item["id"] for item in load_series()}


def validate_series(series_id: str | None, recipe_id: str | None) -> None:
    if not series_id:
        return
    entry = next((item for item in load_series() if item["id"] == series_id), None)
    if entry is None:
        raise ValueError(f"series_unknown:{series_id}")
    if recipe_id and entry["recipe_id"] != recipe_id:
        raise ValueError(f"series_recipe_mismatch:{series_id}")


def series_report(db: Session, metric: str = "net_subscribers_per_1k_views") -> list[dict]:
    from app.pipeline.learning import _publication_metrics, _signals

    values: dict[str, list[float]] = defaultdict(list)
    for publication_id, metrics in _publication_metrics(db, False, 7).items():
        publication = db.get(Publication, publication_id)
        video = db.get(VideoVersion, publication.video_version_id) if publication else None
        signal = _signals(metrics).get(metric)
        if video is None or signal is None:
            continue
        values[(video.features_json or {}).get("series_id") or "no_series"].append(signal)
    return [{"series": key, "n": len(items), "median": statistics.median(items)} for key, items in sorted(values.items())]


# --- derivatives -------------------------------------------------------------------

def plan_derivatives(plan_path: Path) -> list[Path]:
    """Write one media plan per packet variant next to the original plan (research reused)."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    packet = json.loads((plan_path.parent / plan.get("editorial_packet", "editorial-packet.json")).read_text(encoding="utf-8"))
    written = []
    for variant in packet.get("variants", []):
        target = plan_path.parent / f"plan-{variant['id']}.json"
        if target.exists():
            continue
        derived = {**plan, "packet_variant_id": variant["id"], "derivative_of": plan_path.name}
        target.write_text(json.dumps(derived, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(target)
    return written


def derivatives_report(db: Session) -> list[dict]:
    """How many posts each researched story produced."""
    stories: dict[str, set] = defaultdict(set)
    for video in db.query(VideoVersion).all():
        features = video.features_json or {}
        if features.get("story_id") and not features.get("is_demo"):
            stories[features["story_id"]].add(features.get("packet_variant_id") or "default")
    return [{"story_id": key, "variants_produced": len(value)} for key, value in sorted(stories.items())]


# --- comments ----------------------------------------------------------------------

def _is_question(text: str) -> bool:
    lowered = text.strip().casefold()
    return lowered.endswith("?") or lowered.startswith(("how ", "why ", "what ", "which ", "does ", "can ", "is ", "will "))


def fetch_youtube_comments(db: Session, publication: Publication, max_pages: int = 3) -> int:
    settings = get_settings()
    if not settings.youtube_api_key:
        raise RuntimeError("youtube_api_key_missing")
    if publication.platform != "youtube" or not publication.remote_id:
        raise ValueError("youtube_publication_with_remote_id_required")
    page_token = None
    stored = 0
    for _ in range(max_pages):
        params = {"part": "snippet", "videoId": publication.remote_id, "maxResults": 100, "order": "relevance", "textFormat": "plainText", "key": settings.youtube_api_key}
        if page_token:
            params["pageToken"] = page_token
        response = httpx.get("https://www.googleapis.com/youtube/v3/commentThreads", params=params, timeout=20)
        if response.status_code == 403:
            return stored  # comments disabled or quota; not an error for the pipeline
        response.raise_for_status()
        body = response.json()
        for item in body.get("items", []):
            top = item["snippet"]["topLevelComment"]
            remote_id = top["id"]
            if db.query(VideoComment).filter(VideoComment.remote_id == remote_id).first():
                continue
            snippet = top["snippet"]
            text = (snippet.get("textOriginal") or snippet.get("textDisplay") or "").strip()[:2000]
            published = snippet.get("publishedAt")
            db.add(VideoComment(publication_id=publication.id, remote_id=remote_id, text=text, like_count=int(snippet.get("likeCount", 0)), is_question=_is_question(text), published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None))
            stored += 1
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    db.commit()
    return stored


def collect_comments(db: Session, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    results = {"fetched": 0, "errors": []}
    for publication in db.query(Publication).filter(Publication.status == "PUBLISHED", Publication.platform == "youtube").all():
        published = publication.published_at.replace(tzinfo=timezone.utc) if publication.published_at and publication.published_at.tzinfo is None else publication.published_at
        if published and published < since:
            continue
        try:
            results["fetched"] += fetch_youtube_comments(db, publication)
        except Exception as exc:
            results["errors"].append({"publication_id": publication.id, "error": type(exc).__name__})
    results["insights"] = comment_insights(db)
    return results


def comment_insights(db: Session, limit: int = 10) -> dict:
    comments = db.query(VideoComment).all()
    questions = sorted((comment for comment in comments if comment.is_question), key=lambda comment: comment.like_count, reverse=True)
    words = Counter(word for comment in questions for word in re.findall(r"[a-zA-Z][a-zA-Z0-9+'-]{2,}", comment.text.casefold()) if word not in STOPWORDS)
    return {"comments": len(comments), "questions": len(questions), "top_questions": [{"text": comment.text[:300], "likes": comment.like_count, "publication_id": comment.publication_id} for comment in questions[:limit]], "question_terms": words.most_common(15), "note": "Viewer questions are idea signals, never facts. Authors are not stored."}


def suggestions_from_comments(db: Session, minimum_questions: int = 3) -> list[IdeaSuggestion]:
    insights = comment_insights(db, limit=20)
    created = []
    for term, count in insights["question_terms"]:
        if count < minimum_questions:
            continue
        examples = [item for item in insights["top_questions"] if term in item["text"].casefold()][:3]
        title = f"Viewer FAQ: {term}"
        if db.query(IdeaSuggestion).filter(IdeaSuggestion.title == title, IdeaSuggestion.status == "NEW").first():
            continue
        suggestion = IdeaSuggestion(idea_id=None, lane="crossover", title=title, query=term, rationale=f"{count} viewer questions mention '{term}'. A short answer video or pinned reply may help.", evidence_json={"examples": examples, "source": "youtube_comments"}, score=float(count))
        db.add(suggestion)
        created.append(suggestion)
    db.commit()
    return created


# --- manual test results (YouTube Test & Compare) ------------------------------------

def record_manual_result(db: Session, experiment_id: int, winner_variant_id: str | None, evidence: str, actor: str = "owner") -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.status != "ACTIVE":
        raise ValueError("experiment_not_active")
    variant_ids = {variant["id"] for variant in experiment.variants_json}
    if winner_variant_id is not None and winner_variant_id not in variant_ids:
        raise ValueError("unknown_variant")
    if len(evidence.strip()) < 10:
        raise ValueError("manual_result_evidence_required")
    decision = f"manual_winner:{winner_variant_id}" if winner_variant_id else "manual_no_difference"
    experiment.results_json = {**(experiment.results_json or {}), "manual": {"winner": winner_variant_id, "evidence": evidence.strip()[:2000], "source": "YouTube Studio Test & Compare (no API)", "recorded_by": actor, "recorded_at": datetime.now(timezone.utc).isoformat()}}
    experiment.status = "COMPLETED"
    experiment.decision = decision
    experiment.ended_at = datetime.now(timezone.utc)
    db.add(AuditEvent(actor=actor, action="EXPERIMENT_MANUAL_RESULT", entity_type="experiment", entity_id=str(experiment.id), details_json={"decision": decision}))
    db.commit()
    return experiment


# --- sources comment -----------------------------------------------------------------

def sources_comment(video: VideoVersion) -> str:
    claims_path = Path(video.output_dir) / "claims.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.is_file() else []
    urls = []
    for claim in claims:
        url = claim.get("source_url")
        if url and url.startswith("https://") and url not in urls:
            urls.append(url)
    if not urls:
        return ""
    lines = ["Sources for this video:", *[f"• {url}" for url in urls[:10]], "", "Spotted something out of date? Reply and we'll check it."]
    return "\n".join(lines)
