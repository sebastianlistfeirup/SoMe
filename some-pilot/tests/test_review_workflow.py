import hashlib
import json
import re
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import AuthUser, Review, Setting, VideoVersion
from app.db.session import get_db
from app.main import app
from app.pipeline.ai import PostRevision
from app.pipeline.approvals import ApprovalError, verify_approval
from app.pipeline.jobs import claim, complete
from app.pipeline.posts import build_post, normalize_hashtags, post_view
from app.worker import execute


def authenticated_client(db, username="review-owner"):
    db.add(AuthUser(username=username, password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/login", data={"username": username, "password": "a-secure-test-password"}, follow_redirects=False)
    assert response.status_code == 303
    page = client.get("/review")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    return client, token


def complete_source_files(video):
    root = Path(video.output_dir)
    files = {
        "captions.srt": "1\n00:00:00,000 --> 00:00:01,000\nTest\n",
        "claims.json": "[]",
        "rights.json": '{"assets": []}',
        "clip_plan.json": "{}",
        "storyboard.jpg": "storyboard",
        "voice_assets.json": '{"decision": "ALLOW"}',
        "media_composition.json": '{"decision": "ALLOW", "real_media_ratio": 1.0}',
        "post.json": json.dumps(video.post_json),
    }
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    video.manifest_json = {"asset_ids": []}


def test_post_normalization_and_composition():
    assert normalize_hashtags(["#Gaming", "gaming", "handheld-gaming", "AI"]) == ["Gaming", "handheldgaming", "AI"]
    post = build_post("A title", "A caption", ["gaming", "ai"], ["https://example.com"])
    assert post["text"] == "A caption\n\n#gaming #ai"
    assert post_view(post)["title"] == "A title"
    assert post_view({"text": "Caption\n\n#gaming #tech"}, "Fallback")["caption"] == "Caption"


def test_complete_reject_revise_and_approve_flow(db, awaiting_video, monkeypatch):
    complete_source_files(awaiting_video)
    awaiting_video.post_json = build_post("Original title", "Original caption", ["gaming"], [])
    awaiting_video.features_json = {"is_demo": True, "platform": "youtube"}
    db.add(Setting(key="youtube_connection", value_json={"channel_id": "channel-1", "channel_title": "Pixel and Parameters"}))
    db.commit()
    monkeypatch.setattr(get_settings(), "data_dir", db.info["tmp_path"])
    monkeypatch.setattr(get_settings(), "dry_run", False)
    monkeypatch.setattr(get_settings(), "publish_enabled", True)
    client, csrf = authenticated_client(db)
    try:
        response = client.get("/review")
        assert response.status_code == 200
        assert "Original title" in response.text
        assert "Original caption" in response.text
        assert "#gaming" in response.text
        assert 'class="review-card-media"' in response.text

        response = client.get(f"/review/{awaiting_video.id}")
        assert response.status_code == 200
        assert "Pixel and Parameters" in response.text
        assert 'value="channel-1"' in response.text
        assert "Godkend opslag" in response.text
        assert "Afvis med kommentar" in response.text
        assert 'value="youtube"' in response.text
        assert 'value="tiktok"' in response.text

        response = client.post(f"/review/{awaiting_video.id}/reject", data={"csrf_token": csrf, "note": ""}, follow_redirects=False)
        assert response.status_code == 422
        response = client.post(f"/review/{awaiting_video.id}/reject", data={"csrf_token": csrf, "note": "Make it shorter and more direct"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].endswith("?rejected=1")
        db.refresh(awaiting_video)
        assert awaiting_video.status == "REJECTED"
        rejection = db.query(Review).filter_by(video_version_id=awaiting_video.id, decision="REJECTED").one()
        assert rejection.note == "Make it shorter and more direct"

        response = client.post(f"/review/{awaiting_video.id}/revise", data={"csrf_token": csrf}, follow_redirects=False)
        assert response.status_code == 303
        monkeypatch.setattr("app.pipeline.revisions.claude_revise_post", lambda *args: PostRevision(title="Short direct title", caption="A sharper caption.", hashtags=["gaming", "handheldgaming", "tech"]))
        job = claim(db, "revision-test")
        assert job.kind == "revise_post"
        result_path = execute(db, job)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        complete(db, job, str(result_path))
        revised = db.get(VideoVersion, result["video_id"])
        assert revised.id != awaiting_video.id
        assert revised.status == "AWAITING_OWNER"
        assert revised.post_json["title"] == "Short direct title"
        assert revised.post_json["text"] == "A sharper caption.\n\n#gaming #handheldgaming #tech"
        assert revised.features_json["revision_of"] == awaiting_video.id
        assert revised.features_json["revision_scope"] == "title_caption_hashtags"
        assert Path(revised.video_path).read_bytes() == Path(awaiting_video.video_path).read_bytes()
        for name, digest in revised.manifest_json["files_sha256"].items():
            assert hashlib.sha256((Path(revised.output_dir) / name).read_bytes()).hexdigest() == digest
        with pytest.raises(ApprovalError, match="owner_approval_required"):
            verify_approval(db, revised, "youtube", "channel-1")
        from app.pipeline.revisions import create_post_revision
        assert create_post_revision(db, awaiting_video.id, rejection.id, "retry-after-success").id == revised.id
        assert db.query(VideoVersion).filter(VideoVersion.topic_id == revised.topic_id).count() == 2

        response = client.get(f"/review/{awaiting_video.id}")
        assert "En rettet version er klar" in response.text
        assert f"/review/{revised.id}" in response.text
        response = client.get(f"/review/{revised.id}")
        assert "Short direct title" in response.text
        assert "#handheldgaming" in response.text

        response = client.post(f"/review/{revised.id}/approve", data={"csrf_token": csrf, "platform": "youtube", "account": "", "watched": "true"}, follow_redirects=False)
        assert response.status_code == 303
        db.refresh(revised)
        assert revised.status == "APPROVED"
        approval = db.query(Review).filter_by(video_version_id=revised.id, decision="APPROVED").one()
        assert approval.digest_json["account"] == "channel-1"
        assert verify_approval(db, revised, "youtube", "channel-1").id == approval.id
    finally:
        app.dependency_overrides.clear()


def test_revision_is_idempotent_and_rejects_non_rejected_source(db, awaiting_video, monkeypatch):
    complete_source_files(awaiting_video)
    db.commit()
    monkeypatch.setattr(get_settings(), "data_dir", db.info["tmp_path"])
    from app.pipeline.revisions import create_post_revision
    with pytest.raises(ValueError, match="rejected_source_and_review_required"):
        create_post_revision(db, awaiting_video.id, 999, "job-without-rejection")
