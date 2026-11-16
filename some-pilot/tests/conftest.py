import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.models import Base, Script, Topic, VideoVersion


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def pragmas(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    session.info["tmp_path"] = tmp_path
    session.info["database_path"] = path
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def awaiting_video(db):
    root = db.info["tmp_path"] / "version"
    root.mkdir()
    (root / "video.mp4").write_bytes(b"video-one")
    (root / "thumbnail.jpg").write_bytes(b"thumbnail-one")
    checks = {name: {"decision": "ALLOW"} for name in ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice", "media_composition")}
    (root / "checks.json").write_text(json.dumps(checks))
    topic = Topic(niche="test", language="en", title="Safe test topic")
    db.add(topic)
    db.flush()
    script = Script(topic_id=topic.id, content="Original test narration", prompt_version="test", model="test")
    db.add(script)
    db.flush()
    video = VideoVersion(script_id=script.id, topic_id=topic.id, status="AWAITING_OWNER", output_dir=str(root), video_path=str(root / "video.mp4"), thumbnail_path=str(root / "thumbnail.jpg"), post_json={"text": "safe post", "links": []}, features_json={"is_demo": True})
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture(autouse=True)
def isolated_tiktok_token_store(tmp_path, monkeypatch):
    """Tests must never read, refresh or overwrite the real TikTok token store under /data,
    nor use TikTok values from the deploy environment (deploy.sh runs pytest with app.env)."""
    from app.config import get_settings
    from app.pipeline import tiktok_auth

    store = tmp_path / "tiktok-secrets" / tiktok_auth.TOKEN_FILE_NAME
    monkeypatch.setattr(tiktok_auth, "token_path", lambda: store)
    settings = get_settings()
    for name, value in {"tiktok_access_token": "", "tiktok_open_id": "", "tiktok_client_key": "", "tiktok_client_secret": "", "tiktok_direct_post_enabled": False, "tiktok_direct_post_reviewed": False, "tiktok_direct_post_consent_confirmed": False}.items():
        monkeypatch.setattr(settings, name, value)
    return store


@pytest.fixture(autouse=True)
def default_login_without_totp(monkeypatch):
    """deploy.sh runs pytest with the production app.env, where REQUIRE_TOTP=true; tests that
    exercise 2FA turn it on themselves, all others log in with password only."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "require_totp", False)
