from __future__ import annotations

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, nullable=False)
    role: str = Field(nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    # "metadata" is reserved on declarative classes, so the attribute is `meta`.
    meta: str | None = Field(default=None, sa_column=Column("metadata", Text, nullable=True))
    created_at: str = Field(nullable=False)
