import json
from datetime import datetime, timezone

import pytest

from app.pipeline.reception import ReceptionError, metacritic_reception, steam_reception


def test_steam_reception_preserves_english_scope_and_recent_window(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"success": 1, "query_summary": {"review_score_desc": "Very Positive", "total_positive": 90, "total_negative": 10, "total_reviews": 100}}

    def get(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.pipeline.reception.httpx.get", get)
    result = steam_reception(590380, recent_days=30, now=datetime.now(timezone.utc))
    params = json.loads(captured["params"]["input_json"])
    assert params["language"] == "english"
    assert params["day_range"] == 30
    assert result.review_window == "last_30_days"
    assert result.steam_positive_share == 90
    assert result.steam_review_count == 100
    assert "Very Positive" in result.spoken_line


def test_metacritic_requires_actual_score(monkeypatch):
    class Response:
        status_code = 200
        text = '{"criticScore":90}'

    monkeypatch.setattr("app.pipeline.reception.httpx.get", lambda *_args, **_kwargs: Response())
    result = metacritic_reception("into-the-breach", now=datetime.now(timezone.utc))
    assert result.critic_provider == "metacritic"
    assert result.critic_score == 90
    assert result.spoken_line == "On PC, Metacritic lists it at 90."


def test_blocked_reception_never_becomes_zero_reviews(monkeypatch):
    class Response:
        status_code = 403

    monkeypatch.setattr("app.pipeline.reception.httpx.get", lambda *_args, **_kwargs: Response())
    with pytest.raises(ReceptionError, match="unavailable:403"):
        steam_reception(1)
