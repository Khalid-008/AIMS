"""Cheap token estimator and synthesis-input trimmer.

The trim helper iteratively reduces top_topics per question (10 -> 8 -> 6 -> 4)
until the JSON-encoded payload fits within the configured budget.
"""
from __future__ import annotations

import json

from app.services.analytics.schemas import SynthesisInput


def estimate_tokens(text: str) -> int:
    """Char-based heuristic: Arabic is ~3 chars/token, English ~4. Use 3.5 conservatively."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.5))


def estimate_payload_tokens(payload: SynthesisInput) -> int:
    return estimate_tokens(payload.model_dump_json())


def trim_synthesis_input(payload: SynthesisInput, budget: int) -> SynthesisInput:
    """Iteratively shrink top_topics-per-question until under budget.

    Never goes below 4 topics per question.
    """
    levels = [10, 8, 6, 4]
    current = payload.model_copy(deep=True)

    for cap in levels:
        for nlp in current.nlp:
            if len(nlp.top_topics) > cap:
                nlp.top_topics = nlp.top_topics[:cap]
        if estimate_payload_tokens(current) <= budget:
            return current

    # Last resort: also drop sentiment_breakdown to slim the payload further.
    for nlp in current.nlp:
        for t in nlp.top_topics:
            t.sentiment_breakdown = {}
    return current
