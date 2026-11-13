"""ElevenLabs pronunciation dictionary for game names.

content/PRONUNCIATIONS.json holds alias rules. When the rules change, a new
dictionary version is created with POST /v1/pronunciation-dictionaries/add-from-rules
and its id/version are stored in data/elevenlabs-pronunciation.json. Every
ElevenLabs narration request then sends pronunciation_dictionary_locators, so the
same name is spoken the same way in every video.
"""

import hashlib
import json
from pathlib import Path

import httpx

from app.config import get_settings

RULES_FILE = Path(__file__).resolve().parents[2] / "content" / "PRONUNCIATIONS.json"


def load_rules(path: Path = RULES_FILE) -> list[dict]:
    rules = json.loads(path.read_text(encoding="utf-8"))["rules"]
    seen = set()
    for rule in rules:
        if not rule.get("string_to_replace") or not rule.get("alias"):
            raise ValueError("pronunciation_rule_incomplete")
        if rule["string_to_replace"] in seen:
            raise ValueError(f"pronunciation_rule_duplicate:{rule['string_to_replace']}")
        seen.add(rule["string_to_replace"])
    return rules


def rules_hash(rules: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rules, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def state_path() -> Path:
    return get_settings().data_dir / "elevenlabs-pronunciation.json"


def current_locator() -> dict | None:
    path = state_path()
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("rules_sha256") != rules_hash(load_rules()):
        return None  # rules changed since the last sync; never send a stale dictionary
    return {"pronunciation_dictionary_id": state["id"], "version_id": state["version_id"]}


def sync(force: bool = False) -> dict:
    settings = get_settings()
    rules = load_rules()
    digest = rules_hash(rules)
    path = state_path()
    if path.is_file() and not force and json.loads(path.read_text(encoding="utf-8")).get("rules_sha256") == digest:
        return {"status": "unchanged", "rules": len(rules)}
    if not settings.elevenlabs_api_key:
        return {"status": "not_configured", "rules": len(rules)}
    response = httpx.post(
        "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-rules",
        headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
        json={"name": f"pixel-and-parameters-{digest[:8]}", "description": "Game and product names for Pixel and Parameters narration.", "rules": [{"type": "alias", **rule} for rule in rules]},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    state = {"id": body["id"], "version_id": body["version_id"], "rules_sha256": digest, "rules": len(rules)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"status": "created", **state}


def names_in_text(text: str) -> list[str]:
    return [rule["string_to_replace"] for rule in load_rules() if rule["string_to_replace"] in text]
