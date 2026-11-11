from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.db.models import AuthUser
from app.db.session import get_db
from app.main import app


def test_login_csrf_and_protected_routes(db, awaiting_video):
    db.add(AuthUser(username="owner", password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    for route in ("/terms", "/privacy"):
        response = client.get(route)
        assert response.status_code == 200
        assert b"Pixel and Parameters" in response.content
    response = client.get("/opportunities", follow_redirects=False)
    assert response.status_code == 303
    response = client.post("/login", data={"username": "owner", "password": "wrong"}, follow_redirects=False)
    assert response.status_code == 401
    response = client.post("/login", data={"username": "owner", "password": "a-secure-test-password"}, follow_redirects=False)
    assert response.status_code == 303
    response = client.get("/review/1")
    assert response.status_code == 200
    assert b'value="facebook"' in response.content
    for route in ("/dashboard", "/drafts", "/learnings", "/settings"):
        response = client.get(route)
        assert response.status_code == 200
    response = client.post("/pause", data={"csrf_token": "wrong"}, follow_redirects=False)
    assert response.status_code == 403
    response = client.get(f"/media/{awaiting_video.id}/video.mp4")
    assert response.status_code == 200
    app.dependency_overrides.clear()
