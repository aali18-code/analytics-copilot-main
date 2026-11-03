"""Temporary Ask AI sessions for the small, single-process POC backend."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from uuid import uuid4

from backend_modules.ask_ai import engine

MAX_SESSIONS = 3
SESSION_IDLE_SECONDS = 90 * 60
MAX_ANSWERS = 12


@dataclass
class Session:
    id: str
    prepared: engine.PreparedData
    settings: engine.Settings
    router: engine.LLMRouter
    load_errors: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    answers: OrderedDict[str, engine.AnswerResult] = field(default_factory=OrderedDict)
    touched_at: float = field(default_factory=time.monotonic)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def remember(self, question: str, answer: engine.AnswerResult, answer_id: str) -> None:
        self.answers[answer_id] = answer
        self.messages.extend([{"role": "user", "text": question}, {"role": "assistant", "answer_id": answer_id, "text": answer.text, "ok": answer.ok}])
        if answer.ok:
            self.history.extend(answer.history)
        while len(self.answers) > MAX_ANSWERS:
            old_id, _ = self.answers.popitem(last=False)
            self.messages = self.messages[2:]  # discard the matching oldest question and answer


_sessions: OrderedDict[str, Session] = OrderedDict()
_sessions_lock = threading.Lock()


def _cleanup(now: float) -> None:
    """Called with _sessions_lock held."""
    for session_id, session in list(_sessions.items()):
        if now - session.touched_at > SESSION_IDLE_SECONDS:
            _sessions.pop(session_id, None)


def create(prepared: engine.PreparedData, settings: engine.Settings, errors: list[str]) -> Session:
    router = engine.LLMRouter(settings)
    session = Session(id=uuid4().hex, prepared=prepared, settings=settings, router=router, load_errors=errors)
    router.session_id = session.id[:12]
    with _sessions_lock:
        _cleanup(time.monotonic())
        while len(_sessions) >= MAX_SESSIONS:
            _sessions.popitem(last=False)
        _sessions[session.id] = session
    return session


def get(session_id: str) -> Session | None:
    with _sessions_lock:
        now = time.monotonic()
        _cleanup(now)
        session = _sessions.get(session_id)
        if session is not None:
            session.touched_at = now
            _sessions.move_to_end(session_id)
        return session


def delete(session_id: str) -> bool:
    with _sessions_lock:
        return _sessions.pop(session_id, None) is not None
