import base64
import json
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.pipeline.costs import reserve, settle


class VisualReviewResult(BaseModel):
    decision: Literal["ALLOW", "REVIEW", "BLOCK"]
    issues: list[str] = []
    rights_not_evaluated: bool = True


def review_storyboard(db, storyboard: Path, composition: dict, job_id: str) -> VisualReviewResult:
    settings = get_settings()
    if not settings.paid_jobs_enabled or not settings.dashscope_api_key or not settings.qwen_workspace_id:
        raise RuntimeError("qwen_not_configured_or_disabled")
    if settings.qwen_input_dkk_per_million <= 0 or settings.qwen_output_dkk_per_million <= 0:
        raise RuntimeError("verified_qwen_pricing_required")
    reservation = reserve(db, job_id, "qwen_visual_review", settings.max_job_ai_cost_dkk)
    image = base64.b64encode(storyboard.read_bytes()).decode("ascii")
    media_type = "image/jpeg" if storyboard.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    prompt = (
        "Review this storyboard for a short social video. Identify slide/PowerPoint-style content, "
        "lack of real photographic or video content, black frames, unreadable overlays, clipping and obvious context mismatches. "
        "Do not infer copyright permission and do not claim to verify facts. Return JSON only as "
        '{"decision":"ALLOW","issues":[],"rights_not_evaluated":true}. '
        "Use REVIEW for uncertainty and BLOCK only for clear visual defects. Issues must be a flat list of short strings.\n"
        f"Declared media composition: {json.dumps(composition, ensure_ascii=False)[:12_000]}"
    )
    payload = {
        "model": settings.qwen_model_vision,
        "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image}"}}, {"type": "text", "text": prompt}]}],
        "max_tokens": 700,
    }
    url = f"https://{settings.qwen_workspace_id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
        if response.status_code >= 400:
            raise RuntimeError(f"qwen_http_error:{response.status_code}")
        body = response.json()
        usage = body.get("usage", {})
        token_in = usage.get("prompt_tokens", 0)
        token_out = usage.get("completion_tokens", 0)
        actual = (token_in * settings.qwen_input_dkk_per_million + token_out * settings.qwen_output_dkk_per_million) / 1_000_000
        settle(db, reservation, actual, token_in, token_out)
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise RuntimeError("qwen_text_content_missing")
        return VisualReviewResult.model_validate(json.loads(content))
    except httpx.TimeoutException as exc:
        settle(db, reservation, settings.max_job_ai_cost_dkk, uncertain=True)
        raise RuntimeError("qwen_timeout_cost_uncertain") from exc
    except (ValidationError, json.JSONDecodeError, KeyError, IndexError) as exc:
        if reservation.status == "RESERVED":
            settle(db, reservation, settings.max_job_ai_cost_dkk, uncertain=True)
        raise RuntimeError("qwen_output_validation_failed") from exc
    except Exception:
        if reservation.status == "RESERVED":
            settle(db, reservation, settings.max_job_ai_cost_dkk, uncertain=True)
        raise
