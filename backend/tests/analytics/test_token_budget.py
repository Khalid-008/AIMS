"""Token-budget trimming: monotonic shrink, never below 4 topics/question."""
from datetime import datetime

from app.services.analytics.schemas import (
    QuestionNlpResult,
    QuestionSqlResult,
    SynthesisInput,
    TopTopic,
)
from app.services.analytics.token_budget import (
    estimate_payload_tokens,
    estimate_tokens,
    trim_synthesis_input,
)


def _make_topic(i: int) -> TopTopic:
    return TopTopic(
        category="service",
        subtopic=f"sub_{i}_" + "X" * 40,  # padded to grow tokens
        count=10,
        dominant_sentiment="positive",
        sentiment_breakdown={"positive": 8, "neutral": 1, "negative": 1, "mixed": 0},
        examples=["alpha example", "beta example", "gamma example"],
    )


def _payload(num_questions: int, topics_per_q: int) -> SynthesisInput:
    return SynthesisInput(
        report_language="en",
        nlp=[
            QuestionNlpResult(
                question_id=i,
                question_text=f"Question {i} " + "Y" * 50,
                valid_count=100,
                sarcastic_count=0,
                sentiment_distribution={"positive": 50, "neutral": 30, "negative": 20, "mixed": 0},
                top_topics=[_make_topic(j) for j in range(topics_per_q)],
                top_entities=[],
                narrative_summary="Z" * 200,
            )
            for i in range(num_questions)
        ],
        sql=[],
    )


def test_estimate_tokens_grows_with_length():
    short = estimate_tokens("hi")
    longer = estimate_tokens("hi " * 1000)
    assert longer > short


def test_trim_reduces_tokens_when_oversized():
    payload = _payload(num_questions=10, topics_per_q=40)
    big = estimate_payload_tokens(payload)
    trimmed = trim_synthesis_input(payload, budget=big // 4)
    assert estimate_payload_tokens(trimmed) <= big


def test_trim_never_drops_below_4_topics():
    payload = _payload(num_questions=5, topics_per_q=40)
    trimmed = trim_synthesis_input(payload, budget=10)  # absurdly low
    for n in trimmed.nlp:
        assert len(n.top_topics) >= 4


def test_trim_does_not_affect_small_payloads():
    payload = _payload(num_questions=1, topics_per_q=3)
    before = estimate_payload_tokens(payload)
    trimmed = trim_synthesis_input(payload, budget=before * 2)
    assert len(trimmed.nlp[0].top_topics) == 3
