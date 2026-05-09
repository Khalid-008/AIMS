from datetime import datetime

from sqlalchemy import BigInteger, Column, Date, DateTime, Enum, Integer, String, Text

from app.db import Base


class SurveyAnalyticsReport(Base):
    __tablename__ = "survey_analytics_report"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    survey_number = Column(String(64), nullable=False)
    report_language = Column(String(2), nullable=False)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    submissions_limit = Column(Integer, nullable=True)
    input_hash = Column(String(64), nullable=False)
    max_answer_id = Column(BigInteger, nullable=False)
    answer_count = Column(Integer, nullable=False)
    status = Column(
        Enum("pending", "running", "done", "failed", "empty"),
        nullable=False,
    )
    payload_json = Column(Text)
    error_message = Column(Text)
    llm_calls = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
