from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ReportLanguage = Literal["ar", "en"]
ReportStatus = Literal["pending", "running", "done", "failed", "empty"]
QuestionType = Literal["MULTIPLE_CHOICE", "YES_NO", "DROPDOWN", "TEXT_INPUT", "EMOJIS"]
Sentiment = Literal["positive", "neutral", "negative", "mixed"]
EntityType = Literal["person", "organization", "product", "location", "service", "other"]


class Entity(BaseModel):
    name: str
    type: EntityType


class Topic(BaseModel):
    category: str
    subtopic: str
    topic_sentiment: Sentiment


class AnswerAnalysis(BaseModel):
    answer_id: int
    language: Literal["ar", "en", "unknown"] = "unknown"
    is_valid: bool = True
    sentiment: Sentiment = "neutral"
    is_sarcastic: Optional[bool] = None  # only when true
    entities: list[Entity] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)


class TopTopic(BaseModel):
    category: str
    subtopic: str  # canonical
    count: int
    dominant_sentiment: Sentiment
    sentiment_breakdown: dict[str, int]
    examples: list[str] = Field(default_factory=list, max_length=3)


class TopEntity(BaseModel):
    name: str  # canonical
    type: EntityType
    count: int


class QuestionNlpResult(BaseModel):
    question_id: int
    question_text: str
    valid_count: int
    sarcastic_count: int
    sentiment_distribution: dict[str, int]
    top_topics: list[TopTopic] = Field(default_factory=list)
    top_entities: list[TopEntity] = Field(default_factory=list)
    narrative_summary: str = ""
    partial: bool = False


class QuestionSqlResult(BaseModel):
    question_id: int
    question_text: str
    type: QuestionType
    results: dict[str, Any]


class SynthesisInput(BaseModel):
    report_language: ReportLanguage
    survey_subject: Optional[str] = None
    sql: list[QuestionSqlResult] = Field(default_factory=list)
    nlp: list[QuestionNlpResult] = Field(default_factory=list)


class KeyMetric(BaseModel):
    label: str
    value: str
    context: str = ""


class SynthesisOutput(BaseModel):
    executive_summary: str
    detailed_analysis: str
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ReportPayload(BaseModel):
    report_language: ReportLanguage
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    submissions_limit: Optional[int] = None
    synthesis: SynthesisOutput
    nlp: list[QuestionNlpResult] = Field(default_factory=list)
    sql: list[QuestionSqlResult] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime
