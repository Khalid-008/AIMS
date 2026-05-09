"""Aggregation: caps, person exclusion, sentiment math, partial flag."""
from app.services.analytics.aggregation import aggregate_question
from app.services.analytics.schemas import AnswerAnalysis, Entity, Topic


def _ans(aid: int, sentiment="positive", topics=None, entities=None, sarcastic=False, valid=True):
    return AnswerAnalysis(
        answer_id=aid,
        language="en",
        is_valid=valid,
        sentiment=sentiment,
        is_sarcastic=True if sarcastic else None,
        entities=entities or [],
        topics=topics or [],
    )


def test_top_topics_capped_at_20_and_sorted_by_count():
    answers: list[AnswerAnalysis] = []
    # 50 distinct subtopics; subtopic_i has count = i
    for i in range(1, 51):
        for _ in range(i):
            answers.append(
                _ans(
                    aid=len(answers) + 1,
                    topics=[Topic(category="service", subtopic=f"sub_{i}", topic_sentiment="positive")],
                )
            )
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    assert len(nlp.top_topics) == 20
    # sorted descending by count
    assert nlp.top_topics[0].count >= nlp.top_topics[-1].count
    assert nlp.top_topics[0].count == 50
    assert nlp.top_topics[-1].count == 50 - 19  # i.e. 31


def test_person_entities_excluded_from_aggregation():
    answers = [
        _ans(
            aid=1,
            entities=[
                Entity(name="Ahmed", type="person"),
                Entity(name="Acme Corp", type="organization"),
            ],
        ),
        _ans(
            aid=2,
            entities=[Entity(name="Acme Corp", type="organization")],
        ),
    ]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    names = {e.name for e in nlp.top_entities}
    assert "Ahmed" not in names
    assert "Acme Corp" in names


def test_top_entities_capped_at_20():
    answers = [
        _ans(
            aid=i,
            entities=[Entity(name=f"org_{i}", type="organization")],
        )
        for i in range(1, 30)
    ]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    assert len(nlp.top_entities) == 20


def test_sentiment_breakdown_sums_to_count():
    answers = [
        _ans(aid=1, sentiment="positive", topics=[Topic(category="x", subtopic="y", topic_sentiment="positive")]),
        _ans(aid=2, sentiment="negative", topics=[Topic(category="x", subtopic="y", topic_sentiment="negative")]),
        _ans(aid=3, sentiment="positive", topics=[Topic(category="x", subtopic="y", topic_sentiment="positive")]),
    ]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    [topic] = nlp.top_topics
    assert topic.count == 3
    assert sum(topic.sentiment_breakdown.values()) == 3
    assert topic.dominant_sentiment == "positive"


def test_partial_flag_threshold():
    answers = [_ans(aid=1)]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.51,
    )
    assert nlp.partial is True

    nlp2 = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.49,
    )
    assert nlp2.partial is False


def test_invalid_answers_excluded_from_counts():
    answers = [
        _ans(aid=1, valid=True, sentiment="positive"),
        _ans(aid=2, valid=False, sentiment="negative"),
        _ans(aid=3, valid=True, sentiment="negative"),
    ]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    assert nlp.valid_count == 2
    assert nlp.sentiment_distribution["positive"] == 1
    assert nlp.sentiment_distribution["negative"] == 1


def test_sarcastic_count():
    answers = [
        _ans(aid=1, sarcastic=True),
        _ans(aid=2, sarcastic=False),
        _ans(aid=3, sarcastic=True),
    ]
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map={},
        entity_map={},
        failure_ratio=0.0,
    )
    assert nlp.sarcastic_count == 2


def test_subtopic_canonicalization_via_map():
    answers = [
        _ans(aid=1, topics=[Topic(category="service", subtopic="fast", topic_sentiment="positive")]),
        _ans(aid=2, topics=[Topic(category="service", subtopic="quick", topic_sentiment="positive")]),
    ]
    sub_map = {("service", "fast"): "speedy", ("service", "quick"): "speedy"}
    nlp = aggregate_question(
        question_id=1,
        question_text="q",
        per_answer=answers,
        subtopic_map=sub_map,
        entity_map={},
        failure_ratio=0.0,
    )
    [topic] = nlp.top_topics
    assert topic.subtopic == "speedy"
    assert topic.count == 2
    assert {"fast", "quick"} == set(topic.examples)
