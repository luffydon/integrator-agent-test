from __future__ import annotations
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from app.db import Base

class AgentDB(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)  # e.g., "agent_1bcb483f"
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    emoji = Column(String(16), nullable=True)

    visibility = Column(String(16), nullable=False, default="private")  # public|unlisted|private
    teachable = Column(Boolean, nullable=False, default=True)
    tools_allowed = Column(JSON, nullable=False, default=list)

    status = Column(String(16), nullable=False, default="active")  # active|disabled|archived

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AgentMemoryDB(Base):
    __tablename__ = "agent_memories"

    memory_id  = Column(String, primary_key=True)  # short sha1 we generate
    agent_id   = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    scope      = Column(String(16), nullable=False)  # shared|per_user
    user_id    = Column(String, nullable=True)
    tags       = Column(JSON, nullable=False, default=list)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship(
        "AgentDB",
        backref=backref("memories", cascade="all, delete-orphan", passive_deletes=True)
    )
