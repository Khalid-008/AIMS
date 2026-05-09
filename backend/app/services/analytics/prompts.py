"""All prompt templates for the analytics pipeline.

Output language is parameterized via ``target_lang_full`` ("Arabic" / "English").
"""
from __future__ import annotations


LANG_FULL = {"ar": "Arabic", "en": "English"}


ANALYSIS_SYSTEM = (
    "You are a survey response analysis engine. For each answer, output a strict JSON record. "
    "Do not add prose. Do not echo any answer text outside topic 'subtopic' fields. "
    "Never include phone numbers, emails, or ID numbers in any field."
)

ANALYSIS_USER_TEMPLATE = """\
Question (English): {question_en}
Question (Arabic): {question_ar}

Analyze the {n} answers below. For each one return a JSON object with these EXACT keys:
- "answer_id": (int) the id provided
- "language": one of "ar", "en", "unknown"
- "is_valid": true if the answer expresses a real opinion or fact relevant to the question; false for gibberish, single keystrokes, "n/a", "test", repeated punctuation, or off-topic noise.
- "sentiment": one of "positive", "neutral", "negative", "mixed"
- "is_sarcastic": INCLUDE this key ONLY if true. Omit otherwise.
- "entities": array of objects {{"name": "...", "type": "person|organization|product|location|service|other"}}. Empty array if none.
- "topics": array of objects {{"category": "...", "subtopic": "...", "topic_sentiment": "positive|neutral|negative|mixed"}}. Empty array if none.

Rules:
- "category" is a broad English bucket (e.g. "service", "pricing", "delivery", "staff", "product_quality", "ui", "communication", "other"). Reuse the same category across answers when the topic is the same.
- "subtopic" is a short noun phrase (2 to 6 words) in the SAME LANGUAGE as the answer. NEVER translate.
- Include named persons in "entities" with type "person", but do not describe them in "topics".
- Do not invent topics; if the answer is short or vague, return an empty "topics" array.
- Output a single JSON array of length exactly {n}, one object per answer, in input order. Each answer_id must appear exactly once.

Answers:
{answers_block}

Respond with ONLY the JSON array. No prose. No markdown fences."""


CLUSTERING_TEMPLATE = """\
You are normalizing survey {kind} phrases extracted from answers under {context_label}.

Phrases mix Arabic and English and contain heavy near-duplicate variation. AGGRESSIVELY merge phrases that express the SAME core concept, even when surface forms differ. Treat the following as identical and put them in ONE cluster:
- Diacritic / spelling variants ("شكراً" vs "شكرا" vs "شكرن").
- Definite-article forms ("الشكر" vs "شكر").
- Particle additions ("شكرا لك" vs "شكرا").
- Singular / plural / gender variants of the same noun.
- Different verb conjugations of the same root expressing the same idea.
- Synonyms or near-synonyms ("سعر مرتفع" / "غالي" / "تكلفة عالية" — all "high price").
- Cross-lingual equivalents ("thank you" / "شكرا" → same cluster).

Choose ONE "canonical_name" per cluster, written in {target_lang_full}, 2 to 5 words, neutral tone, the most natural and common surface form. Prefer fewer, broader clusters over many narrow ones — when in doubt, MERGE.

Output strictly:
{{"clusters": [{{"canonical_name": "...", "members": ["...", "..."]}}, ...]}}

Every input phrase must appear in exactly one cluster's "members".

Phrases:
{phrases_block}

Respond with ONLY the JSON object. No prose. No markdown fences."""


SUMMARIZATION_TEMPLATE = """\
Write a {target_lang_full} narrative paragraph (4 to 6 sentences) describing what respondents said about this question. Do NOT use bullet points or lists. Do NOT mention any individual person's name or any personally identifying information (phone numbers, emails, IDs). Do not invent statistics; only use the numbers provided.

Question: {question_text}
Valid answers: {valid_count}
Sarcastic answers: {sarcastic_count}
Sentiment distribution: {sentiment_distribution_json}
Top topics (canonical, with counts): {top_topics_json}
Top entities (excluding persons, with counts): {top_entities_json}
{partial_warning}

Output a single paragraph in {target_lang_full}. No preamble, no headings, no JSON, no markdown."""


SYNTHESIS_SYSTEM = (
    "You are a senior survey analyst writing an executive report. Output strict JSON only. "
    "Do not name individual respondents. Do not echo any PII (phone numbers, emails, ID numbers). "
    "Do not invent numbers; ground every claim in the provided data."
)

SYNTHESIS_USER_TEMPLATE = """\
Write a comprehensive analytics report for survey "{survey_subject}" in {target_lang_full}.

You receive two data sources:

1) SQL aggregates for choice/yes-no/dropdown/emoji questions:
{sql_json}

2) NLP findings for each free-text question (already pre-aggregated and pre-summarized):
{nlp_json}

Output JSON with EXACTLY these keys:
- "executive_summary": 3 to 5 sentence narrative paragraph in {target_lang_full}.
- "detailed_analysis": 6 to 12 sentence paragraph in {target_lang_full} weaving SQL and NLP findings together. May reference question subjects but never specific people.
- "key_metrics": array of objects {{"label": "...", "value": "...", "context": "..."}}, between 4 and 8 entries. label and context in {target_lang_full}; value may be a number or short phrase. Provide a BALANCED view: cover BOTH positive findings (strengths, satisfaction, top performers) AND negative findings (concerns, complaints, weak spots). Do not stack multiple metrics on the same positive angle while leaving the negative side underrepresented; aim for roughly equal coverage of strengths and weaknesses across the metrics.
- "recommendations": array of 3 to 5 short actionable recommendations in {target_lang_full}, each one sentence.

Constraints:
- All natural-language fields MUST be in {target_lang_full}.
- Do NOT name any individual person.
- Do NOT echo verbatim free-text answers.
- Do NOT include phone numbers, emails, or ID numbers anywhere in the output.
- For questions marked "partial": true, hedge ("preliminary", "indicative").

Respond with ONLY the JSON object. No prose. No markdown fences."""


def lang_full(code: str) -> str:
    return LANG_FULL.get(code, "English")
