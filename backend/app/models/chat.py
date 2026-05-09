from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class AiChatSession(Base):
    __tablename__ = "ai_chat_session"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    survey_number = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    messages = relationship("AiChatMessage", back_populates="session", lazy="noload")


class AiChatMessage(Base):
    __tablename__ = "ai_chat_message"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("ai_chat_session.id"), nullable=False)
    role = Column(Enum("user", "assistant", "tool"), nullable=False)
    content = Column(Text, nullable=False)
    tool_name = Column(String(64))
    tool_args = Column(JSON)
    language = Column(String(2))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("AiChatSession", back_populates="messages", lazy="noload")
