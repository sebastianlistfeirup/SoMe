import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.adapters.youtube import YouTubeAdapter
from app.config import get_settings
from app.db.models import AuthSession, AuthUser, Cost, Job, MetricSnapshot, Publication, Review, Script, Setting, Topic, VideoVersion
from app.db.session import get_db, init_database
from app.pipeline.approvals import ApprovalError, approve, paused, set_pause, transition
from app.pipeline.platforms import FacebookPublisher, InstagramPublisher, TikTokPublisher, YouTubePublisher, manual_export
from app.pipeline.signed_media import SignedMediaError, create_link, resolve_link

from contextlib import asynccontextmanager

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    yield


app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, lifespan=lifespan)
root = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=root / "static"), name="static")
templates = Jinja2Templates(directory=root / "templates")
login_attempts: dict[str, list[float]] = {}
hasher = PasswordHasher()


def current_session(request: Request, db: Session) -> AuthSession | None:
    session_id = request.cookies.get("some_session")
    if not session_id:
        return None
    session = db.get(AuthSession, session_id)
    if not session:
        return None
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    if expires <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return session


def require_user(request: Request, db: Session = Depends(get_db)) -> tuple[AuthUser, AuthSession]:
    session = current_session(request, db)
    if not session:
        raise HTTPException(status_code=401, headers={"X-Login-Required": "true"})
    user = db.get(AuthUser, session.user_id)
    if not user:
        raise HTTPException(status_code=401)
    return user, session


def csrf_check(request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)) -> tuple[AuthUser, AuthSession]:
    user, session = require_user(request, db)
    if not secrets.compare_digest(csrf_token, session.csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    return user, session


def render(request: Request, template: str, db: Session, auth: tuple[AuthUser, AuthSession], **context) -> HTMLResponse:
    user, session = auth
    return templates.TemplateResponse(request, template, {"request": request, "user": user, "csrf_token": session.csrf_token, "paused": paused(db), "app_name": settings.app_name, **context})


@app.exception_handler(401)
async def login_redirect(request: Request, _exc: HTTPException):
    if request.url.path.startswith("/healthz"):
        return HTMLResponse("Unauthorized", status_code=401)
    return RedirectResponse("/login", status_code=303)


@app.get("/healthz")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "publish_enabled": settings.publish_enabled, "paid_jobs_enabled": settings.paid_jobs_enabled}


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "terms.html", {"request": request})


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {"request": request})


@app.get("/tiktokDNEepLrDLh4SgEN8VZPDcTcL09iuTuaj.txt", response_class=PlainTextResponse)
def tiktok_domain_verification():
    path = root / "static" / "tiktokDNEepLrDLh4SgEN8VZPDcTcL09iuTuaj.txt"
    if not path.is_file():
        raise HTTPException(404)
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"request": request, "app_name": settings.app_name, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{username}"
    now = time.monotonic()
    login_attempts[key] = [stamp for stamp in login_attempts.get(key, []) if now - stamp < 300]
    if len(login_attempts[key]) >= 5:
        return templates.TemplateResponse(request, "login.html", {"request": request, "app_name": settings.app_name, "error": "For mange forsøg. Prøv igen om fem minutter."}, status_code=429)
    user = db.query(AuthUser).filter(AuthUser.username == username).first()
    try:
        if not user:
            hasher.verify("$argon2id$v=19$m=65536,t=3,p=4$QY2i6upG8NkqT0YmfG8m0w$0op42hVt1zByHvlUk6Jyyk2zQX8E3fY1p7hCSj0c4j8", password)
            raise VerifyMismatchError
        hasher.verify(user.password_hash, password)
    except (VerificationError, VerifyMismatchError):
        login_attempts[key].append(now)
        return templates.TemplateResponse(request, "login.html", {"request": request, "app_name": settings.app_name, "error": "Forkert brugernavn eller password."}, status_code=401)
    session = AuthSession(id=secrets.token_urlsafe(32), user_id=user.id, csrf_token=secrets.token_urlsafe(32), expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes))
    db.add(session)
    db.commit()
    response = RedirectResponse("/opportunities", status_code=303)
    response.set_cookie("some_session", session.id, httponly=True, secure=settings.secure_cookies, samesite="strict", max_age=settings.session_ttl_minutes * 60, path="/")
    return response


@app.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), auth=Depends(csrf_check)):
    db.delete(auth[1])
    db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("some_session")
    return response


@app.get("/")
def home():
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    status_counts = {status: count for status, count in db.query(VideoVersion.status, func.count(VideoVersion.id)).group_by(VideoVersion.status).all()}
    metric_totals = {name: value for name, value in db.query(MetricSnapshot.metric_name, func.sum(MetricSnapshot.metric_value)).filter(MetricSnapshot.is_demo.is_(False), MetricSnapshot.metric_name.in_(["views", "likes", "comments", "shares"])).group_by(MetricSnapshot.metric_name).all()}
    latest_jobs = db.query(Job).order_by(Job.updated_at.desc()).limit(8).all()
    latest_learning = db.get(Setting, "learning_model")
    return render(request, "dashboard.html", db, auth, status_counts=status_counts, metric_totals=metric_totals, latest_jobs=latest_jobs, latest_learning=latest_learning)


@app.get("/opportunities", response_class=HTMLResponse)
def opportunities(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    topics = db.query(Topic).order_by(Topic.created_at.desc()).all()
    return render(request, "opportunities.html", db, auth, topics=topics)


@app.get("/drafts", response_class=HTMLResponse)
def drafts(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    scripts = db.query(Script).order_by(Script.created_at.desc()).limit(200).all()
    topics = {topic.id: topic for topic in db.query(Topic).filter(Topic.id.in_([script.topic_id for script in scripts])).all()} if scripts else {}
    videos = db.query(VideoVersion).order_by(VideoVersion.created_at.desc()).all()
    latest_video_by_script = {}
    for video in videos:
        latest_video_by_script.setdefault(video.script_id, video)
    return render(request, "drafts.html", db, auth, scripts=scripts, topics=topics, latest_video_by_script=latest_video_by_script)


@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    videos = db.query(VideoVersion).order_by(VideoVersion.created_at.desc()).all()
    return render(request, "queue.html", db, auth, videos=videos)


@app.get("/review", response_class=HTMLResponse)
def review_list(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    videos = db.query(VideoVersion).filter(VideoVersion.status.in_(["AWAITING_OWNER", "APPROVED", "REJECTED"])).order_by(VideoVersion.updated_at.desc()).all()
    return render(request, "review.html", db, auth, videos=videos)


@app.get("/review/{video_id}", response_class=HTMLResponse)
def review_detail(video_id: int, request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    video = db.get(VideoVersion, video_id)
    if not video:
        raise HTTPException(404)
    topic = db.get(Topic, video.topic_id)
    evidence = {}
    for name in ("claims.json", "rights.json", "checks.json"):
        path = Path(video.output_dir) / name
        if path.exists():
            try:
                evidence[name] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                evidence[name] = {"error": "unreadable_or_invalid_evidence"}
    return render(request, "review_detail.html", db, auth, video=video, topic=topic, evidence=evidence)


@app.post("/review/{video_id}/approve")
def approve_video(video_id: int, request: Request, platform: str = Form(...), account: str = Form(...), watched: bool = Form(False), db: Session = Depends(get_db), auth=Depends(csrf_check)):
    video = db.get(VideoVersion, video_id)
    if not video:
        raise HTTPException(404)
    try:
        approve(db, video, auth[0].username, platform, account, watched)
    except ApprovalError as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(f"/review/{video_id}", status_code=303)


@app.post("/review/{video_id}/reject")
def reject_video(video_id: int, note: str = Form(""), db: Session = Depends(get_db), auth=Depends(csrf_check)):
    video = db.get(VideoVersion, video_id)
    if not video or video.status != "AWAITING_OWNER":
        raise HTTPException(409)
    transition(video, "REJECTED", auth[0].username)
    db.add(Review(video_version_id=video.id, decision="REJECTED", reviewer=auth[0].username, note=note[:2000]))
    db.commit()
    return RedirectResponse("/review", status_code=303)


@app.get("/media/{video_id}/{name}")
def protected_media(video_id: int, name: str, db: Session = Depends(get_db), auth=Depends(require_user)):
    if name not in {"video.mp4", "thumbnail.jpg", "storyboard.jpg", "captions.srt"}:
        raise HTTPException(404)
    video = db.get(VideoVersion, video_id)
    if not video:
        raise HTTPException(404)
    path = Path(video.output_dir) / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/media/{video_id}/sign")
def sign_media(video_id: int, platform: str = Form(...), account: str = Form(...), db: Session = Depends(get_db), auth=Depends(csrf_check)):
    video = db.get(VideoVersion, video_id)
    if not video:
        raise HTTPException(404)
    try:
        link = create_link(db, video, platform, account)
    except SignedMediaError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"url": link, "expires_in_seconds": settings.signed_media_ttl_seconds}


@app.get("/public-media/{token}")
def public_signed_media(token: str, db: Session = Depends(get_db)):
    try:
        path = resolve_link(db, token)
    except SignedMediaError as exc:
        raise HTTPException(410, str(exc)) from exc
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"})


@app.get("/export/{video_id}/{platform}")
def export(video_id: int, platform: str, db: Session = Depends(get_db), auth=Depends(require_user)):
    video = db.get(VideoVersion, video_id)
    if not video:
        raise HTTPException(404)
    path = manual_export(video, platform, settings.data_dir)
    return FileResponse(path, filename=path.name, headers={"Cache-Control": "private, no-store"})


@app.get("/calendar", response_class=HTMLResponse)
def calendar(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    publications = db.query(Publication).order_by(Publication.scheduled_at.desc().nullslast()).all()
    return render(request, "calendar.html", db, auth, publications=publications)


@app.get("/results", response_class=HTMLResponse)
def results(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    metrics = db.query(MetricSnapshot).order_by(MetricSnapshot.collected_at.desc()).limit(200).all()
    return render(request, "results.html", db, auth, metrics=metrics)


@app.get("/learnings", response_class=HTMLResponse)
def learnings(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    models = [item for item in (db.get(Setting, "learning_model"), db.get(Setting, "learning_model_demo")) if item]
    reports = []
    report_dir = settings.data_dir / "reports"
    if report_dir.is_dir():
        for path in sorted(report_dir.glob("learning-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
            try:
                reports.append({"name": path.name, "data": json.loads(path.read_text(encoding="utf-8"))})
            except (json.JSONDecodeError, OSError):
                reports.append({"name": path.name, "data": {"error": "unreadable_or_invalid_report"}})
    return render(request, "learnings.html", db, auth, models=models, reports=reports)


@app.get("/economy", response_class=HTMLResponse)
def economy(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    costs = db.query(Cost).order_by(Cost.created_at.desc()).all()
    return render(request, "economy.html", db, auth, costs=costs, monthly_budget=settings.monthly_ai_budget_dkk)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db), auth=Depends(require_user)):
    safe = {"DRY_RUN": settings.dry_run, "PUBLISH_ENABLED": settings.publish_enabled, "PAID_JOBS_ENABLED": settings.paid_jobs_enabled, "APP_TIMEZONE": settings.app_timezone, "MONTHLY_AI_BUDGET_DKK": settings.monthly_ai_budget_dkk, "MAX_JOB_AI_COST_DKK": settings.max_job_ai_cost_dkk}
    capabilities = {"youtube_publish": YouTubePublisher().capabilities(db), "instagram_publish": InstagramPublisher().capabilities(db), "facebook_publish": FacebookPublisher().capabilities(db), "tiktok_publish": TikTokPublisher().capabilities(db), "youtube_research": YouTubeAdapter().capabilities()}
    voice_profiles = {
        "active": {"provider": settings.voice_provider, "preset": settings.voice_preset, "speed": settings.voice_speed, "avatar_required": False},
        "elevenlabs": {"configured": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id), "voice_id_configured": bool(settings.elevenlabs_voice_id), "verified_price_configured": settings.elevenlabs_cost_per_1000_chars_dkk > 0 and bool(settings.elevenlabs_pricing_verified_at), "voice_rights_confirmed": settings.elevenlabs_voice_rights_confirmed, "paid_jobs_enabled": settings.paid_jobs_enabled},
    }
    return render(request, "settings.html", db, auth, safe_settings=safe, capabilities=capabilities, voice_profiles=voice_profiles)


@app.post("/pause")
def pause_all(db: Session = Depends(get_db), auth=Depends(csrf_check)):
    set_pause(db, True, auth[0].username)
    return RedirectResponse("/settings", status_code=303)


@app.post("/resume")
def resume_all(db: Session = Depends(get_db), auth=Depends(csrf_check)):
    set_pause(db, False, auth[0].username)
    return RedirectResponse("/settings", status_code=303)
