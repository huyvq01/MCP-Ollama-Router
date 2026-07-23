from collections import defaultdict
from threading import Lock

from app.core.settings import settings
from app.models.message import Message


class HistoryManager:
    def __init__(self) -> None:
        self._history: defaultdict[str, list[Message]] = defaultdict(list)
        self._lock = Lock()
        self._max_history = settings.max_history

    def get(self, session_id: str) -> list[Message]:
        with self._lock:
            return list(self._history[session_id])

    def append(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        with self._lock:
            self._history[session_id].append(
                {
                    "role": role,
                    "content": content,
                }
            )

            if len(self._history[session_id]) > self._max_history:
                self._history[session_id] = self._history[session_id][
                    -self._max_history :
                ]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._history.pop(session_id, None)

    def sessions(self) -> list[str]:
        with self._lock:
            return list(self._history.keys())
