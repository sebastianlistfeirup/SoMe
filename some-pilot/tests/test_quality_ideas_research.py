from datetime import datetime, timedelta, timezone

from app.db.models import IdeaSuggestion, MetricSnapshot, Observation, Publication, Review, Setting, VideoVersion
from app.pipeline.ideas import classify_idea_hook, rank_ideas, research_plan, research_query, suggestions_from_research
from app.pipeline.quality import _spearman, calibration_report, feedback_prompt_block, normalize_categories, rejection_category_counts, requires_new_production

NOW = datetime.now(timezone.utc)


def test_rejection_categories_decide_whether_text_revision_is_enough():
    assert normalize_categories(["voice", "bogus", "voice"]) == ["voice"]
    assert requires_new_production(["title_caption"]) is False
    assert requires_new_production(["title_caption", "clips"]) is True
    assert requires_new_production([]) is False


def test_owner_feedback_reaches_prompts_and_category_counts(db, awaiting_video):
    db.add(Review(video_version_id=awaiting_video.id, decision="REJECTED", reviewer="owner", note="The hook is too slow; open on the decision.", digest_json={"rejection_categories": ["hook"]}))
    db.commit()
    block = feedback_prompt_block(db)
    assert "open on the decision" in block and "never a source of facts" in block
    assert rejection_category_counts(db)["hook"] == 1


def test_spearman_and_calibration_report(db, awaiting_video):
    assert _spearman([(1, 1), (2, 2), (3, 3), (4, 4)]) == 1.0
    assert _spearman([(1, 4), (2, 3), (3, 2), (4, 1)]) == -1.0
    assert _spearman([(1, 1)]) is None
    for index, (predicted, independent, subs) in enumerate([(90, 86, 2), (95, 92, 4), (88, 90, 3), (99, 97, 6)]):
        video = VideoVersion(script_id=awaiting_video.script_id, topic_id=awaiting_video.topic_id, status="PUBLISHED", output_dir="x", features_json={"predicted_quality_score": predicted, "independent_quality_score": independent})
        db.add(video)
        db.flush()
        publication = Publication(video_version_id=video.id, platform="youtube", account="a", idempotency_key=f"cal{index}", status="PUBLISHED", published_at=NOW - timedelta(days=7))
        db.add(publication)
        db.flush()
        for name, value in {"views": 1000, "subscribersGained": subs, "subscribersLost": 0}.items():
            db.add(MetricSnapshot(publication_id=publication.id, collected_at=NOW, metric_definition_version="t", metric_name=name, metric_value=value, is_demo=False))
    db.commit()
    report = calibration_report(db)
    assert report["predicted_n"] == 4 and report["independent_n"] == 4
    assert report["independent_spearman"] == 1.0


def test_idea_hook_classification():
    assert classify_idea_hook("When did this tiny soldier become someone you cared about?") == "question"
    assert classify_idea_hook("Top 10 handhelds of 2026") == "ranking_reveal"
    assert classify_idea_hook("Steam Deck vs ROG Ally") == "comparison"
    assert classify_idea_hook("This door is more interesting before it opens.") == "bold_claim"


def test_rank_ideas_splits_exploit_and_explore_and_uses_active_hook_model(db):
    db.merge(Setting(key="learning_governance", value_json={"active": {"version": 1, "model": {"hook_multipliers": {"question": 1.2, "bold_claim": 0.8}}, "activated_at": NOW.isoformat()}, "candidate": None, "history": [], "events": []}))
    db.commit()
    ranked = rank_ideas(db, 10, lane="gaming")
    assert len(ranked) == 10
    assert [item["allocation"] for item in ranked].count("exploit") == 8
    assert all(item["lane"] == "gaming" for item in ranked)
    exploit = [item for item in ranked if item["allocation"] == "exploit"]
    assert all(item["hook_type"] == "question" for item in exploit[:3])
    assert all(item["rationale"] for item in ranked)


def test_produced_ideas_are_not_suggested_again(db, awaiting_video):
    awaiting_video.features_json = {**awaiting_video.features_json, "idea_id": "GI001"}
    db.commit()
    assert "GI001" not in {item["idea_id"] for item in rank_ideas(db, 120)}


def test_research_plan_and_suggestions_have_rationale(db):
    plan = research_plan(db, 3)
    assert len(plan) == 3 and all(item["query"] for item in plan)
    assert research_query({"title": "The Amiga Corner: The Soldier You Wanted to Bring Home"}) == "Soldier Wanted Bring Home"
    first = plan[0]
    for views in (1000, 3000):
        db.add(Observation(source_url="https://www.youtube.com/watch?v=x", platform="youtube", topic=f"{first['query']}:Some video", metric_name="views", metric_value=views, method="test", confidence="high", is_demo=False))
    db.commit()
    created = suggestions_from_research(db, plan)
    assert db.query(IdeaSuggestion).count() == 3
    with_data = next(item for item in created if item.idea_id == first["idea_id"])
    assert with_data.evidence_json["observations"] == 2 and "2,000" in with_data.rationale
    assert "Interest signal only" in with_data.evidence_json["limitations"]


def test_worker_research_uses_bible_plan_not_fixed_terms(db, tmp_path):
    from app.adapters.base import ResearchAdapter
    from app.pipeline.research import bible_research

    queries = []

    class Recording(ResearchAdapter):
        name = "recording"
        is_demo = True

        def discover(self, query, language, days=30):
            queries.append(query)
            return []

        def fetch_metadata(self, external_id):
            return {}

        def refresh_metrics(self, external_id):
            return {}

        def capabilities(self):
            return {}

    result = bible_research(db, tmp_path, [Recording()], limit=4)
    assert queries == [item["query"] for item in result["plan"]]
    assert "handheld gaming PC" not in queries and len(result["suggestions"]) == 4
