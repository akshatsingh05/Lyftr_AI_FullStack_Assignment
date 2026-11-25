"""SQLite persistence for conversation history."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models.message import Message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_exists(engine: Engine, session_id: str) -> bool:
    with Session(engine) as s:
        return s.exec(select(func.count()).select_from(Message).where(Message.session_id == session_id)).one() > 0


def load_context(engine: Engine, session_id: str, limit: int) -> list[dict]:
    """Most recent `limit` messages, chronological, as LLM chat messages."""
    with Session(engine) as s:
        rows = s.exec(
            select(Message).where(Message.session_id == session_id).order_by(Message.id.desc()).limit(limit)
        ).all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def save_exchange(engine: Engine, session_id: str, user_text: str, reply: str, metadata: dict) -> None:
    """Persist user + assistant messages atomically (called only after a successful LLM response)."""
    with Session(engine) as s:
        s.add(Message(session_id=session_id, role="user", content=user_text, created_at=_now()))
        s.add(Message(session_id=session_id, role="assistant", content=reply,
                      meta=json.dumps(metadata), created_at=_now()))
        s.commit()


def list_messages(engine: Engine, session_id: str) -> list[dict]:
    with Session(engine) as s:
        rows = s.exec(select(Message).where(Message.session_id == session_id).order_by(Message.id.asc())).all()
    out = []
    for r in rows:
        item: dict = {"role": r.role, "content": r.content}
        if r.role == "assistant" and r.meta:
            item["metadata"] = json.loads(r.meta)
        out.append(item)
    return out
