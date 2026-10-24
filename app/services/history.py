from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic

from app.core.settings import settings
from app.models.message import Message
from app.runtime import runtime
from app.services.token_budget import trim_messages_to_tokens, truncate_text_to_tokens


@dataclass
class _Session:
    revision: int
    touched: float
    messages: list[Message] = field(default_factory=list)


class HistoryManager:
    """Bounded, expiring, process-local history. Never creates sessions on read."""
    def __init__(self, *, max_sessions: int = runtime.max_sessions,
                 ttl: float = runtime.session_ttl_s) -> None:
        self._history: OrderedDict[str, _Session] = OrderedDict()
        self._lock = Lock()
        self._max_history = settings.max_history
        self._max_history_tokens = settings.max_history_tokens
        self._max_sessions = max_sessions
        self._ttl = ttl
        self._revision = 0

    def _prune(self) -> None:
        now = monotonic()
        expired = [key for key, value in self._history.items()
                   if now - value.touched >= self._ttl]
        for key in expired:
            del self._history[key]

    def _ensure(self, session_id: str) -> _Session:
        self._prune()
        if session_id not in self._history:
            while len(self._history) >= self._max_sessions:
                self._history.popitem(last=False)
            self._revision += 1
            self._history[session_id] = _Session(self._revision, monotonic())
        entry = self._history[session_id]
        entry.touched = monotonic()
        self._history.move_to_end(session_id)
        return entry

    def revision(self, session_id: str) -> int:
        with self._lock:
            return self._ensure(session_id).revision

    def get(self, session_id: str) -> list[Message]:
        with self._lock:
            self._prune()
            entry = self._history.get(session_id)
            if entry is None:
                return []
            entry.touched = monotonic()
            self._history.move_to_end(session_id)
            return [dict(message) for message in entry.messages]

    def _store(self, entry: _Session, messages: list[Message]) -> None:
        entry.messages.extend({
            'role': message['role'],
            'content': truncate_text_to_tokens(message['content'], self._max_history_tokens),
        } for message in messages)
        entry.messages = trim_messages_to_tokens(
            entry.messages[-self._max_history:], self._max_history_tokens,
        )
        # Never start history with an orphaned assistant response.
        while entry.messages and entry.messages[0]['role'] == 'assistant':
            entry.messages.pop(0)

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            entry = self._ensure(session_id)
            self._store(entry, [{'role': role, 'content': content}])

    def append_turn(self, session_id: str, prompt: str, answer: str,
                    *, expected_revision: int) -> bool:
        with self._lock:
            self._prune()
            entry = self._history.get(session_id)
            if entry is None or entry.revision != expected_revision:
                return False
            self._store(entry, [
                {'role': 'user', 'content': prompt},
                {'role': 'assistant', 'content': answer},
            ])
            entry.touched = monotonic()
            return True

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._history.pop(session_id, None)

    def sessions(self) -> list[str]:
        with self._lock:
            self._prune()
            return list(self._history)
