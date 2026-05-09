from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Survey(Base):
    __tablename__ = "survey"

    id = Column(BigInteger, primary_key=True)
    survey_number = Column(String(64), nullable=False, unique=True)
    subject = Column(String(255))
    subject_ar = Column(String(255))
    description = Column(Text)
    description_ar = Column(Text)
    status = Column(String(64), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_public = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(255), nullable=False)

    questions = relationship("SurveyQuestion", back_populates="survey", lazy="noload")


class SurveyQuestion(Base):
    __tablename__ = "survey_question"

    id = Column(BigInteger, primary_key=True)
    survey_id = Column(BigInteger, ForeignKey("survey.id"), nullable=False)
    question_type = Column(String(64), nullable=False)
    question_en = Column(Text)
    question_ar = Column(Text)
    question_header_en = Column(String(255))
    question_header_ar = Column(String(255))
    is_required = Column(Boolean, nullable=False, default=True)
    order_by = Column(BigInteger)

    survey = relationship("Survey", back_populates="questions", lazy="noload")
    options = relationship("QuestionOption", back_populates="question", lazy="noload")
    dropdowns = relationship("QuestionDropdown", back_populates="question", lazy="noload")
    answers = relationship("SurveyAnswer", back_populates="question", lazy="noload")


class QuestionOption(Base):
    __tablename__ = "question_option"

    id = Column(BigInteger, primary_key=True)
    question_id = Column(BigInteger, ForeignKey("survey_question.id"), nullable=False)
    option_text_en = Column(Text)
    option_text_ar = Column(Text)
    order_by = Column(BigInteger)

    question = relationship("SurveyQuestion", back_populates="options", lazy="noload")


class QuestionDropdown(Base):
    __tablename__ = "question_dropdown"

    id = Column(BigInteger, primary_key=True)
    question_id = Column(BigInteger, ForeignKey("survey_question.id"), nullable=False)
    dropdown_text_en = Column(Text, nullable=False)
    dropdown_text_ar = Column(Text, nullable=False)

    question = relationship("SurveyQuestion", back_populates="dropdowns", lazy="noload")


class SurveyAnswer(Base):
    __tablename__ = "survey_answer"

    id = Column(BigInteger, primary_key=True)
    survey_question_id = Column(BigInteger, ForeignKey("survey_question.id"), nullable=False)
    answer = Column(Text)
    file_url = Column(Text)
    user_email = Column(String(255))
    submission_id = Column(String(64))
    selected_options_id = Column(String(255))
    created_date = Column(DateTime)

    question = relationship("SurveyQuestion", back_populates="answers", lazy="noload")
    selected_options = relationship("SurveyAnswerOption", back_populates="survey_answer", lazy="noload")


class SurveyAnswerOption(Base):
    __tablename__ = "survey_answer_option"

    id = Column(BigInteger, primary_key=True)
    survey_answer_id = Column(BigInteger, ForeignKey("survey_answer.id"), nullable=False)
    option_id = Column(BigInteger, ForeignKey("question_option.id"), nullable=False)

    survey_answer = relationship("SurveyAnswer", back_populates="selected_options", lazy="noload")
    option = relationship("QuestionOption", lazy="noload")
