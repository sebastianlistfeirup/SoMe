import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.base import ResearchAdapter
from app.db.models import Observation, Topic

FIELDS = ["source_url", "platform", "collected_at_utc", "published_at", "country", "language", "topic", "metric_name", "metric_value", "unit", "method", "confidence", "limitations"]


def priority_score(demand: float, momentum: float, monetization: float, opportunity: float, production_feasibility: float) -> float:
    values = [demand, momentum, monetization, opportunity, production_feasibility]
    if any(value < 0 or value > 100 for value in values):
        raise ValueError("scores_must_be_0_to_100")
    return round(0.35 * demand + 0.25 * momentum + 0.20 * monetization + 0.10 * opportunity + 0.10 * production_feasibility, 2)


def save_observations(db: Session, rows: list[dict], is_demo: bool = False) -> int:
    count = 0
    for row in rows:
        values = {field: row.get(field) for field in FIELDS}
        for field in ("collected_at_utc", "published_at"):
            if isinstance(values[field], str):
                values[field] = datetime.fromisoformat(values[field].replace("Z", "+00:00"))
        db.add(Observation(**values, is_demo=is_demo))
        count += 1
    db.commit()
    return count


def import_report(db: Session, path: Path, is_demo: bool = False) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    save_observations(db, document["observations"], is_demo=is_demo)
    topics = []
    for score in document.get("scores", []):
        title = f"{score['niche'].replace('_', ' ').title()} ({score['language']})"
        topic = db.query(Topic).filter(Topic.title == title, Topic.niche == score["niche"]).first()
        if not topic:
            topic = Topic(niche=score["niche"], language=score["language"], title=title, score_json=score)
            db.add(topic)
        else:
            topic.score_json = score
        topics.append(topic)
    db.commit()
    return {"observations": len(document["observations"]), "topics": len(topics), "recommendation": document.get("recommendation")}


def export_observations(rows: list[dict], output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    normalized = []
    for row in rows:
        normalized.append({field: _iso(row.get(field)) for field in FIELDS})
    json_path = output / "research.json"
    csv_path = output / "research.csv"
    json_path.write_text(json.dumps({"generated_at_utc": datetime.now(timezone.utc).isoformat(), "data_mode": "demo" if rows and rows[0].get("is_demo") else "real", "observations": normalized}, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(normalized)
    return {"research_json": str(json_path), "research_csv": str(csv_path), "count": len(normalized)}


def run_adapters(db: Session, adapters: list[ResearchAdapter], queries: list[str], languages: list[str], days: int, output: Path) -> dict:
    rows = []
    errors = []
    for adapter in adapters:
        for language in languages:
            for query in queries:
                try:
                    found = adapter.discover(query, language, days)
                    for row in found:
                        row["is_demo"] = adapter.is_demo
                    rows.extend(found)
                except Exception as exc:
                    errors.append({"adapter": adapter.name, "query": query, "language": language, "error": type(exc).__name__})
    save_observations(db, rows, is_demo=any(adapter.is_demo for adapter in adapters))
    result = export_observations(rows, output)
    result["errors"] = errors
    result["capabilities"] = {adapter.name: adapter.capabilities() for adapter in adapters}
    (output / "run.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value
