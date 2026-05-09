"""Clustering: cross-lingual clustering of subtopic phrases and entity names.

Behavior:
- Per (question, category): collect distinct subtopic phrases. If <= 8 distinct,
  identity map (no LLM call). Else one LLM call returns canonical groups.
- Per (question, entity_type): same flow, EXCLUDING ``person`` (filtered out).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Iterable

from app.services.analytics.llm_io import LlmJsonError, LlmTransportError, call_json
from app.services.analytics.prompts import CLUSTERING_TEMPLATE, lang_full
from app.services.analytics.schemas import AnswerAnalysis

logger = logging.getLogger(__name__)

_IDENTITY_THRESHOLD = 8  # don't cluster if <= this many distinct phrases


def _identity_map(phrases: Iterable[str]) -> dict[str, str]:
    return {p: p for p in phrases}


async def _cluster_one_group(
    phrases: list[str],
    *,
    kind: str,  # "subtopic" or "entity"
    context_label: str,
    target_language: str,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, str], int]:
    """Returns (phrase->canonical map, llm_calls_made)."""
    distinct = sorted(set(p for p in phrases if p))
    if len(distinct) <= _IDENTITY_THRESHOLD:
        return _identity_map(distinct), 0

    block = "\n".join(f"- {p}" for p in distinct)
    prompt = CLUSTERING_TEMPLATE.format(
        kind=kind,
        context_label=context_label,
        target_lang_full=lang_full(target_language),
        phrases_block=block,
    )

    try:
        raw = await call_json(prompt, semaphore=semaphore, json_root="object", max_tokens=1500)
    except (LlmJsonError, LlmTransportError) as exc:
        logger.warning("cluster failed for %s/%s, identity-fallback: %s", kind, context_label, exc)
        return _identity_map(distinct), 1

    clusters = raw.get("clusters") if isinstance(raw, dict) else None
    if not isinstance(clusters, list):
        return _identity_map(distinct), 1

    mapping: dict[str, str] = {}
    seen: set[str] = set()
    for c in clusters:
        if not isinstance(c, dict):
            continue
        canon = c.get("canonical_name")
        members = c.get("members") or []
        if not canon or not isinstance(members, list):
            continue
        for m in members:
            if isinstance(m, str) and m in distinct and m not in seen:
                mapping[m] = canon
                seen.add(m)

    # Fall back to identity for any phrase the LLM missed
    for p in distinct:
        mapping.setdefault(p, p)
    return mapping, 1


async def build_subtopic_map(
    per_answer: list[AnswerAnalysis],
    *,
    target_language: str,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[tuple[str, str], str], int]:
    """Returns mapping {(category, raw_subtopic): canonical_subtopic} and LLM-calls count."""
    by_cat: dict[str, list[str]] = defaultdict(list)
    for a in per_answer:
        if not a.is_valid:
            continue
        for t in a.topics:
            if t.subtopic:
                by_cat[t.category].append(t.subtopic)

    mapping: dict[tuple[str, str], str] = {}
    total_calls = 0

    async def _one(cat: str, phrases: list[str]) -> None:
        nonlocal total_calls
        sub_map, calls = await _cluster_one_group(
            phrases,
            kind="subtopic",
            context_label=f'category "{cat}"',
            target_language=target_language,
            semaphore=semaphore,
        )
        total_calls += calls
        for raw, canon in sub_map.items():
            mapping[(cat, raw)] = canon

    await asyncio.gather(*[_one(c, p) for c, p in by_cat.items()])
    return mapping, total_calls


async def build_entity_map(
    per_answer: list[AnswerAnalysis],
    *,
    target_language: str,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[tuple[str, str], str], int]:
    """Returns mapping {(entity_type, raw_name): canonical_name} and LLM-calls count.

    EXCLUDES type='person' from clustering (and thus from aggregation downstream).
    """
    by_type: dict[str, list[str]] = defaultdict(list)
    for a in per_answer:
        if not a.is_valid:
            continue
        for e in a.entities:
            if e.type == "person" or not e.name:
                continue
            by_type[e.type].append(e.name)

    mapping: dict[tuple[str, str], str] = {}
    total_calls = 0

    async def _one(etype: str, names: list[str]) -> None:
        nonlocal total_calls
        sub_map, calls = await _cluster_one_group(
            names,
            kind="entity",
            context_label=f'entity type "{etype}"',
            target_language=target_language,
            semaphore=semaphore,
        )
        total_calls += calls
        for raw, canon in sub_map.items():
            mapping[(etype, raw)] = canon

    await asyncio.gather(*[_one(t, n) for t, n in by_type.items()])
    return mapping, total_calls
