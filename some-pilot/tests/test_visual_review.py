import json

import pytest
from PIL import Image

from app.config import get_settings
from app.db.models import Cost
from app.pipeline.visual_review import review_storyboard


def test_qwen_review_requires_configuration_before_network(db, tmp_path):
    image = tmp_path / "storyboard.jpg"
    Image.new("RGB", (32, 32)).save(image)
    with pytest.raises(RuntimeError, match="qwen_not_configured_or_disabled"):
        review_storyboard(db, image, {}, "qwen-missing")


def test_qwen_storyboard_review_contract_and_cost(db, tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "paid_jobs_enabled", True)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "qwen_workspace_id", "workspace")
    monkeypatch.setattr(settings, "qwen_input_dkk_per_million", 10)
    monkeypatch.setattr(settings, "qwen_output_dkk_per_million", 20)
    image = tmp_path / "storyboard.jpg"
    Image.new("RGB", (32, 32)).save(image)
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": json.dumps({"decision": "ALLOW", "issues": [], "rights_not_evaluated": True})}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.pipeline.visual_review.httpx.post", post)
    result = review_storyboard(db, image, {"real_media_ratio": 1}, "qwen-live-contract")
    assert result.decision == "ALLOW"
    assert result.rights_not_evaluated is True
    assert captured["url"].startswith("https://workspace.ap-southeast-1.maas.aliyuncs.com/")
    content = captured["json"]["messages"][0]["content"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "real_media_ratio" in content[1]["text"]
    cost = db.query(Cost).filter_by(job_id="qwen-live-contract").one()
    assert cost.status == "SETTLED"
    assert cost.actual_amount == pytest.approx(0.0014)
