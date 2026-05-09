"""Aggregation: pure-Python aggregation across per-answer analyses.

Caps top_topics at 20 (with up to 3 example phrases each), top_entities at 20.
``type='person'`` entities are filtered out of aggregation.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.services.analytics.schemas import (
    AnswerAnalysis,
    QuestionNlpResult,
    Sentiment,
    TopEntity,
    TopTopic,
)

_SENTIMENTS: tuple[str, ...] = ("positive", "neutral", "negative", "mixed")
_TOP_TOPICS_CAP = 20
_TOP_ENTITIES_CAP = 20
_PARTIAL_THRESHOLD = 0.5


def _dominant(breakdown: dict[str, int]) -> Sentiment:
    if not breakdown:
        return "neutral"
    return max(breakdown.items(), key=lambda kv: (kv[1], kv[0]))[0]  # type: ignore[return-value]


def aggregate_question(
    *,
    question_id: int,
    question_text: str,
    per_answer: list[AnswerAnalysis],
    subtopic_map: dict[tuple[str, str], str],
    entity_map: dict[tuple[str, str], str],
    failure_ratio: float,
) -> QuestionNlpResult:
    valid = [a for a in per_answer if a.is_valid]
    valid_count = len(valid)
    sarcastic_count = sum(1 for a in valid if a.is_sarcastic)

    sentiment_dist: dict[str, int] = {s: 0 for s in _SENTIMENTS}
    for a in valid:
        if a.sentiment in sentiment_dist:
            sentiment_dist[a.sentiment] += 1

    # Topics — count by (category, canonical_subtopic) and track sentiment + examples
    topic_counts: Counter[tuple[str, str]] = Counter()
    topic_breakdown: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {s: 0 for s in _SENTIMENTS}
    )
    topic_examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen_examples: dict[tuple[str, str], set[str]] = defaultdict(set)

    for a in valid:
        for t in a.topics:
            if not t.subtopic:
                continue
            canon = subtopic_map.get((t.category, t.subtopic), t.subtopic)
            key = (t.category, canon)
            topic_counts[key] += 1
            ts = t.topic_sentiment if t.topic_sentiment in topic_breakdown[key] else "neutral"
            topic_breakdown[key][ts] += 1
            if t.subtopic not in seen_examples[key] and len(topic_examples[key]) < 3:
                topic_examples[key].append(t.subtopic)
                seen_examples[key].add(t.subtopic)

    top_topics: list[TopTopic] = [
        TopTopic(
            category=cat,
            subtopic=subtopic,
            count=cnt,
            dominant_sentiment=_dominant(topic_breakdown[(cat, subtopic)]),
            sentiment_breakdown=dict(topic_breakdown[(cat, subtopic)]),
            examples=list(topic_examples[(cat, subtopic)]),
        )
        for (cat, subtopic), cnt in topic_counts.most_common(_TOP_TOPICS_CAP)
    ]

    # Entities — count by (type, canonical_name); EXCLUDE persons.
    entity_counts: Counter[tuple[str, str]] = Counter()
    for a in valid:
        for e in a.entities:
            if e.type == "person" or not e.name:
                continue
            canon = entity_map.get((e.type, e.name), e.name)
            entity_counts[(e.type, canon)] += 1

    top_entities: list[TopEntity] = [
        TopEntity(name=name, type=etype, count=cnt)  # type: ignore[arg-type]
        for (etype, name), cnt in entity_counts.most_common(_TOP_ENTITIES_CAP)
    ]

    return QuestionNlpResult(
        question_id=question_id,
        question_text=question_text,
        valid_count=valid_count,
        sarcastic_count=sarcastic_count,
        sentiment_distribution=sentiment_dist,
        top_topics=top_topics,
        top_entities=top_entities,
        partial=failure_ratio > _PARTIAL_THRESHOLD,
    )
