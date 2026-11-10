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
    checks = {name: {"decision": "ALLOW"} for name in ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice")}
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
