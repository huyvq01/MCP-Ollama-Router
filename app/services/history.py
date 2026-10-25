from collections import OrderedDict
from threading import Lock
from time import monotonic

from app.core.settings import settings
from app.models.message import Message


class HistoryManager:
    def __init__(self) -> None:
        self._history: OrderedDict[str, tuple[float, list[Message]]] = OrderedDict()
        self._lock = Lock()
        self._max_history = settings.max_history

    def _prune(self) -> None:
        now = monotonic()
        for key in list(self._history):
            if now - self._history[key][0] > settings.session_ttl:
                self._history.pop(key, None)
        while len(self._history) > settings.max_sessions:
            self._history.popitem(last=False)

    def get(self, session_id: str) -> list[Message]:
        with self._lock:
            self._prune()
            item = self._history.get(session_id)
            if item is None:
                return []
            self._history.move_to_end(session_id)
            self._history[session_id] = (monotonic(), item[1])
            return [dict(m) for m in item[1]]

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._prune()
            messages = self._history.get(session_id, (0, []))[1]
            messages.append({"role": role, "content": content})
            messages = messages[-self._max_history :]
            # Bound stored text too; never retain unbounded pasted files.
            while (
                len(messages) > 1
                and sum(len(m["content"].encode("utf-8")) for m in messages)
                > settings.num_ctx * 4
            ):
                messages.pop(0)
            if (
                len(messages) == 1
                and len(messages[0]["content"].encode("utf-8")) > settings.num_ctx * 4
            ):
                messages = []
            self._history[session_id] = (monotonic(), messages)
            self._history.move_to_end(session_id)
            self._prune()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._history.pop(session_id, None)

    def sessions(self) -> list[str]:
        with self._lock:
            self._prune()
            return list(self._history)
