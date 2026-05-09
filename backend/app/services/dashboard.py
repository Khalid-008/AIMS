"""
Builds the per-question chart payload for the dashboard endpoint.
Calls the same tool functions used by the agent to guarantee consistency.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.mcp.tools import (
    aggregate_choice_question,
    aggregate_emoji,
    aggregate_yes_no,
    list_questions,
    submission_timeline,
    summarize_text_answers,
)

_SKIP_TYPES = {"FILE_UPLOAD", "TEXT_INPUT"}

_PERSONAL_EN = re.compile(
    r"\b(name|full[\s_]name|first[\s_]name|last[\s_]name|your[\s_]name|"
    r"phone|mobile|tel|telephone|cell[\s_]?phone|"
    r"national[\s_]?id|iqama|id[\s_]?number|identity|id\b|"
    r"email|e[\s-]mail|"
    r"partner|company[\s_]name|organization|organisation)\b",
    re.IGNORECASE,
)

_PERSONAL_AR = re.compile(
    r"(الاسم|اسمك|اسم|اسم الشريك|اسم الزوج|اسم الزوجة|"
    r"رقم الجوال|جوال|رقم الهاتف|هاتف|موبايل|"
    r"رقم الهوية|الهوية الوطنية|رقم بطاقة|هوية|"
    r"البريد الإلكتروني|بريد إلكتروني|إيميل|"
    r"اسم الشركة|اسم المنظمة|اسم الجهة)"
)


def _is_personal_info(q: dict) -> bool:
    text = " ".join(filter(None, [q.get("questionEn") or "", q.get("questionAr") or ""]))
    return bool(_PERSONAL_EN.search(text) or _PERSONAL_AR.search(text))


async def build_dashboard(
    survey_number: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return a dict with questions array and timeline, ready for the frontend."""
    questions = await list_questions(survey_number)
    timeline = await submission_timeline(survey_number, bucket="day", date_from=date_from, date_to=date_to)

    async def _question_card(q: dict) -> dict[str, Any]:
        qid: int = q["questionId"]
        qtype: str = q["type"]
        card: dict[str, Any] = {
            "questionId": qid,
            "type": qtype,
            "questionEn": q["questionEn"],
            "questionAr": q["questionAr"],
            "isRequired": q["isRequired"],
            "orderBy": q["orderBy"],
            "data": None,
        }

        try:
            if qtype in ("MULTIPLE_CHOICE", "DROPDOWN"):
                card["data"] = await aggregate_choice_question(
                    survey_number, qid, date_from=date_from, date_to=date_to
                )
            elif qtype == "YES_NO":
                card["data"] = await aggregate_yes_no(
                    survey_number, qid, date_from=date_from, date_to=date_to
                )
            elif qtype == "EMOJIS":
                card["data"] = await aggregate_emoji(
                    survey_number, qid, date_from=date_from, date_to=date_to
                )
            elif qtype == "TEXT_INPUT":
                card["data"] = await summarize_text_answers(
                    survey_number, qid, date_from=date_from, date_to=date_to
                )
        except Exception as exc:
            card["error"] = str(exc)

        return card

    visible_questions = [
        q for q in questions
        if q["type"] not in _SKIP_TYPES and not _is_personal_info(q)
    ]
    cards = await asyncio.gather(*[_question_card(q) for q in visible_questions])

    return {
        "surveyNumber": survey_number,
        "questions": list(cards),
        "timeline": timeline,
    }
