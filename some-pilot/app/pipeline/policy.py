import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Asset, License


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class PolicyResult(BaseModel):
    decision: Decision
    reasons: list[str]


FORBIDDEN_PATTERNS = {
    "minors": r"\b(minor|child|under\s*18|ungdomsspiller|barn)\b",
    "sexual_content": r"\b(porn|nude|sexualized|pornografi|nøgenhed)\b",
    "graphic_violence": r"\b(graphic violence|gore|grafisk vold)\b",
    "hate_or_doxxing": r"\b(doxx|private address|hate speech|hadefuld)\b",
    "gambling": r"\b(casino|betting|gambling|spillehjemmeside)\b",
    "financial_hype": r"\b(guaranteed profit|risk-free income|garanteret indtjening)\b",
}


def content_policy(text: str, contains_people: bool = False, ages_verified: bool = False) -> PolicyResult:
    reasons = [name for name, pattern in FORBIDDEN_PATTERNS.items() if re.search(pattern, text, re.I)]
    if reasons:
        return PolicyResult(decision=Decision.BLOCK, reasons=reasons)
    if contains_people and not ages_verified:
        return PolicyResult(decision=Decision.REVIEW, reasons=["age_not_verified"])
    return PolicyResult(decision=Decision.ALLOW, reasons=[])


def rights_policy(db: Session, asset_ids: list[int], platform: str, now: datetime | None = None) -> PolicyResult:
    now = now or datetime.now(timezone.utc)
    if not asset_ids:
        return PolicyResult(decision=Decision.BLOCK, reasons=["no_assets"])
    reasons: list[str] = []
    decision = Decision.ALLOW
    for asset_id in asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is None:
            reasons.append(f"asset_{asset_id}:missing")
            continue
        license_ = db.scalar(select(License).where(License.asset_id == asset_id))
        if license_ is None or asset.rights_status != "CLEARED" or license_.status != "ALLOW":
            reasons.append(f"asset_{asset_id}:license_not_cleared")
            continue
        expires = license_.expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                reasons.append(f"asset_{asset_id}:license_expired")
        if not license_.commercial_allowed:
            reasons.append(f"asset_{asset_id}:commercial_use_not_allowed")
        if not license_.derivative_allowed:
            reasons.append(f"asset_{asset_id}:derivatives_not_allowed")
        if license_.platforms_json and platform not in license_.platforms_json:
            reasons.append(f"asset_{asset_id}:platform_not_allowed")
        if license_.age_clearance == "UNKNOWN":
            reasons.append(f"asset_{asset_id}:age_not_verified")
            decision = Decision.REVIEW
        elif license_.age_clearance not in {"NO_PEOPLE", "ALL_ADULTS_VERIFIED"}:
            reasons.append(f"asset_{asset_id}:minors_or_unclear_age")
    if reasons:
        if any("age_not_verified" in reason for reason in reasons) and len(reasons) == 1:
            return PolicyResult(decision=Decision.REVIEW, reasons=reasons)
        return PolicyResult(decision=Decision.BLOCK, reasons=reasons)
    return PolicyResult(decision=decision, reasons=[])
