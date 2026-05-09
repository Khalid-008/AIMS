"""Smoke test every prompt template formats and contains expected markers."""
import json

from app.services.analytics.prompts import (
    ANALYSIS_USER_TEMPLATE,
    CLUSTERING_TEMPLATE,
    SUMMARIZATION_TEMPLATE,
    SYNTHESIS_USER_TEMPLATE,
    lang_full,
)


def test_analysis_template_renders():
    out = ANALYSIS_USER_TEMPLATE.format(
        question_en="What did you like?",
        question_ar="ما الذي أعجبك؟",
        n=3,
        answers_block="[1] good\n[2] bad\n[3] meh",
    )
    assert "answer_id" in out
    assert "[1] good" in out
    assert "JSON array" in out


def test_clustering_template_renders():
    out = CLUSTERING_TEMPLATE.format(
        kind="subtopic",
        context_label='category "service"',
        target_lang_full=lang_full("ar"),
        phrases_block="- fast\n- quick",
    )
    assert "canonical_name" in out
    assert "members" in out
    assert "Arabic" in out
    # Aggressive merge instruction must remain — guards against accidental softening.
    assert "AGGRESSIVELY" in out
    assert "MERGE" in out


def test_summarization_template_renders():
    out = SUMMARIZATION_TEMPLATE.format(
        target_lang_full=lang_full("en"),
        question_text="Q",
        valid_count=10,
        sarcastic_count=1,
        sentiment_distribution_json=json.dumps({"positive": 5, "neutral": 3, "negative": 2, "mixed": 0}),
        top_topics_json="[]",
        top_entities_json="[]",
        partial_warning="",
    )
    assert "single paragraph in English" in out


def test_synthesis_template_renders():
    out = SYNTHESIS_USER_TEMPLATE.format(
        survey_subject="Customer Survey 2025",
        target_lang_full=lang_full("ar"),
        sql_json="[]",
        nlp_json="[]",
    )
    assert "executive_summary" in out
    assert "detailed_analysis" in out
    assert "key_metrics" in out
    assert "recommendations" in out
    assert "Arabic" in out
    # Balanced metrics guard — strengths AND weaknesses must both be requested.
    assert "BALANCED" in out


def test_lang_full_defaults_to_english_for_unknown():
    assert lang_full("xx") == "English"
    assert lang_full("ar") == "Arabic"
    assert lang_full("en") == "English"
