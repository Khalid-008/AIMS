"""
LangChain StructuredTool wrappers around the MCP tool functions.

Each tool is pre-bound to a specific survey_number so the LLM never needs
to pass it — reducing prompt token usage and eliminating cross-survey risk.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import StructuredTool

from app.mcp.tools import (
    aggregate_choice_question as _aggregate_choice_question,
    aggregate_emoji as _aggregate_emoji,
    aggregate_yes_no as _aggregate_yes_no,
    get_survey_meta as _get_survey_meta,
    list_file_answers as _list_file_answers,
    list_questions as _list_questions,
    list_text_answers as _list_text_answers,
    submission_timeline as _submission_timeline,
    summarize_text_answers as _summarize_text_answers,
)


def build_tools(survey_number: str) -> list[StructuredTool]:
    """Return LangChain tools pre-bound to *survey_number*."""
    sn = survey_number

    async def get_survey_meta() -> dict:
        """Get survey metadata: subject, description, status, total questions and submissions."""
        return await _get_survey_meta(sn)

    async def list_questions() -> list:
        """List all questions in the survey with their types and labels."""
        return await _list_questions(sn)

    async def aggregate_choice_question(
        question_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list:
        """Get option counts and percentages for a MULTIPLE_CHOICE or DROPDOWN question."""
        return await _aggregate_choice_question(sn, question_id, date_from, date_to)

    async def aggregate_yes_no(
        question_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """Get yes/no counts for a YES_NO question."""
        return await _aggregate_yes_no(sn, question_id, date_from, date_to)

    async def aggregate_emoji(
        question_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list:
        """Get emoji answer histogram for an EMOJIS question."""
        return await _aggregate_emoji(sn, question_id, date_from, date_to)

    async def list_text_answers(
        question_id: int,
        limit: int = 20,
        offset: int = 0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """Get paginated raw text answers for a TEXT_INPUT question."""
        return await _list_text_answers(sn, question_id, limit, offset, date_from, date_to)

    async def summarize_text_answers(
        question_id: int,
        language: str = "en",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """Get top keywords for a TEXT_INPUT question (powered by LLM)."""
        return await _summarize_text_answers(sn, question_id, language, date_from, date_to)

    async def list_file_answers(question_id: int) -> list:
        """Get file URLs uploaded for a FILE_UPLOAD question."""
        return await _list_file_answers(sn, question_id)

    async def submission_timeline(
        bucket: str = "day",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list:
        """Get submission count over time grouped by day or hour. bucket: 'day' or 'hour'."""
        return await _submission_timeline(sn, bucket, date_from, date_to)

    return [
        StructuredTool.from_function(coroutine=fn)
        for fn in [
            get_survey_meta,
            list_questions,
            aggregate_choice_question,
            aggregate_yes_no,
            aggregate_emoji,
            list_text_answers,
            summarize_text_answers,
            list_file_answers,
            submission_timeline,
        ]
    ]
