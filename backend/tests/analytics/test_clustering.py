"""Clustering: identity-shortcut, mapping correctness, person exclusion."""
import asyncio

import pytest

from app.services.analytics import clustering as cluster_mod
from app.services.analytics.clustering import build_entity_map, build_subtopic_map
from app.services.analytics.schemas import AnswerAnalysis, Entity, Topic


def _ans(aid, topics=None, entities=None):
    return AnswerAnalysis(
        answer_id=aid,
        language="en",
        is_valid=True,
        sentiment="positive",
        entities=entities or [],
        topics=topics or [],
    )


@pytest.mark.asyncio
async def test_identity_shortcut_when_few_phrases(monkeypatch):
    """<= 8 distinct phrases per category should NOT trigger an LLM call."""
    call_count = 0

    async def fake_call_json(*a, **kw):
        nonlocal call_count
        call_count += 1
        return {"clusters": []}

    monkeypatch.setattr(cluster_mod, "call_json", fake_call_json)

    answers = [
        _ans(1, topics=[Topic(category="service", subtopic="fast", topic_sentiment="positive")]),
        _ans(2, topics=[Topic(category="service", subtopic="slow", topic_sentiment="negative")]),
    ]
    sem = asyncio.Semaphore(4)
    mapping, calls = await build_subtopic_map(answers, target_language="en", semaphore=sem)
    assert calls == 0
    assert call_count == 0
    assert mapping[("service", "fast")] == "fast"
    assert mapping[("service", "slow")] == "slow"


@pytest.mark.asyncio
async def test_clustering_with_canonical_mapping(monkeypatch):
    """LLM returns canonical groups → map merges members."""

    async def fake_call_json(*a, **kw):
        return {
            "clusters": [
                {"canonical_name": "speedy service", "members": [f"phrase_{i}" for i in range(10)]}
            ]
        }

    monkeypatch.setattr(cluster_mod, "call_json", fake_call_json)

    answers = [
        _ans(i, topics=[Topic(category="service", subtopic=f"phrase_{i}", topic_sentiment="positive")])
        for i in range(10)
    ]
    sem = asyncio.Semaphore(4)
    mapping, calls = await build_subtopic_map(answers, target_language="en", semaphore=sem)
    assert calls == 1
    for i in range(10):
        assert mapping[("service", f"phrase_{i}")] == "speedy service"


@pytest.mark.asyncio
async def test_entity_map_excludes_persons(monkeypatch):
    async def fake_call_json(*a, **kw):
        raise AssertionError("should not call: identity shortcut applies")

    monkeypatch.setattr(cluster_mod, "call_json", fake_call_json)

    answers = [
        _ans(
            1,
            entities=[
                Entity(name="Ahmed", type="person"),
                Entity(name="Acme", type="organization"),
            ],
        ),
    ]
    sem = asyncio.Semaphore(4)
    mapping, calls = await build_entity_map(answers, target_language="en", semaphore=sem)
    assert ("organization", "Acme") in mapping
    assert ("person", "Ahmed") not in mapping
